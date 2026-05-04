"""
app.py — FYNZA Secure Steganography API
Supports: Images (PNG/BMP/JPG) + Audio (WAV) as carriers
"""

import base64
import hashlib
import io
import json
import os
import tempfile
import time
import zlib

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from crypto_utils import decrypt_message, encrypt_message
from image_utils import load_image
from plugin_manager import manager as plugin_manager
from steganalysis import SteganalysisEngine
from audio_steg import embed_in_wav, extract_from_wav, get_wav_capacity, get_wav_info
from file_steg import embed_in_file, extract_from_file, get_file_capacity, get_file_info

try:
    from ai_steganalysis import AI_Detector
    ai_detector = AI_Detector(os.path.join(os.path.dirname(__file__), 'steg_model.pth'))
    ai_detector_error = None
except Exception as e:
    print(f"Warning: Could not initialize AI Detector: {e}")
    ai_detector = None
    ai_detector_error = str(e)



# ── App ────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
app = Flask(__name__, static_folder=frontend_dir, static_url_path='/')
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

IMAGE_FORMATS = {"png", "bmp", "jpg", "jpeg", "tiff", "webp"}
AUDIO_FORMATS = {"wav"}
# ALL_FORMATS is no longer strictly used for filtering, as we allow any generic file.
# However, we keep them for logic branching (image vs audio vs generic).
# ── Runtime state ──────────────────────────────────────────────
_stats = {"hide_count": 0, "extract_count": 0, "total_bytes_hidden": 0, "operations": []}
_replay_store = {}


def allowed_image(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in IMAGE_FORMATS

def allowed_any(fn):
    # Now we allow literally any file to be a carrier.
    return "." in fn

def get_ext(fn):
    return fn.rsplit(".", 1)[1].lower() if "." in fn else ""

def bad(msg, code=400):
    return jsonify({"success": False, "error": msg}), code

def save_temp(file_storage, suffix=None):
    ext = suffix or (os.path.splitext(file_storage.filename)[1] or ".bin")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    file_storage.save(tmp.name)
    tmp.close()
    return tmp.name

def log_op(op_type, details):
    entry = {"type": op_type, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), **details}
    _stats["operations"].append(entry)
    if len(_stats["operations"]) > 100:
        _stats["operations"].pop(0)

# ── Hint packing ───────────────────────────────────────────────
HINT_MAGIC = b"\xFE\xFE\xFE"

def pack_hint(payload, hint, question, answer_hash):
    if not hint and not question:
        return payload
    block = HINT_MAGIC + json.dumps({"hint": hint, "question": question, "answer_hash": answer_hash}).encode()
    return payload + block

def unpack_hint(data):
    idx = data.rfind(HINT_MAGIC)
    if idx == -1:
        return data, {}
    try:
        return data[:idx], json.loads(data[idx + len(HINT_MAGIC):].decode())
    except Exception:
        return data, {}

# ── Explain steps ──────────────────────────────────────────────
EXPLAIN_HIDE = [
    {"step": 1, "title": "File Type Detection",      "detail": "System validates the carrier (image or WAV audio) and detects its format."},
    {"step": 2, "title": "Payload Preparation",      "detail": "Your secret is prefixed with a type header (TEXT: / FILE:) and serialized as binary."},
    {"step": 3, "title": "Hint Embedding",            "detail": "If a password hint was provided, it is appended after the payload with a magic separator."},
    {"step": 4, "title": "ZLIB Compression",         "detail": "The payload is compressed with DEFLATE, reducing size before encryption."},
    {"step": 5, "title": "Key Derivation (KDF)",     "detail": "Your password is stretched into a 256-bit key using PBKDF2 or Scrypt."},
    {"step": 6, "title": "Encryption",               "detail": "Data is encrypted with the chosen cipher (AES-256-GCM, ChaCha20, or AES-256-CBC)."},
    {"step": 7, "title": "LSB Embedding",            "detail": "Each bit of the encrypted payload replaces the Least Significant Bit of each sample/pixel."},
    {"step": 8, "title": "Quality Analysis",         "detail": "PSNR is computed and a security score (0–100) is generated for the output."},
]
EXPLAIN_EXTRACT = [
    {"step": 1, "title": "LSB Extraction",           "detail": "Hidden bits are read from pixels/audio samples using the same algorithm as hiding."},
    {"step": 2, "title": "Decryption",               "detail": "Cipher type is auto-detected from the 3-byte header, then data is decrypted."},
    {"step": 3, "title": "Decompression",            "detail": "Decrypted bytes are decompressed with ZLIB INFLATE."},
    {"step": 4, "title": "Hint Recovery",            "detail": "If a password hint block exists, it is separated from the payload."},
    {"step": 5, "title": "Payload Parsing",          "detail": "The type header (TEXT: / FILE:) determines how the secret is returned."},
]

# ── Demo ───────────────────────────────────────────────────────
DEMO_MESSAGES = {
    "short": "Hello from FYNZA! 🔒",
    "medium": "This is a confidential test message hidden with AES-256-GCM + Camouflage LSB steganography.",
    "long": "FYNZA Suite — military-grade steganography. Payload encrypted with AES-256-GCM, compressed with ZLIB-9, and scattered across the image using Camouflage LSB mode. Security score: 94/100.",
}


# ── HEALTH ─────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"success": True, "status": "ok", "plugins": list(plugin_manager.plugins.keys())})

@app.route("/")
def index():
    return app.send_static_file("index.html")


# ── SUPPORTED FORMATS ──────────────────────────────────────────
@app.route("/supported-formats")
def supported_formats():
    return jsonify({
        "success": True,
        "carrier_types": {
            "images": sorted(IMAGE_FORMATS),
            "audio":  sorted(AUDIO_FORMATS),
        },
        "payload_types": ["text", "any binary file (PDF, ZIP, image, audio, doc…)"],
        "steganography_modes": plugin_manager.list_plugins(),
        "encryption_ciphers": {
            "aes_gcm":  "AES-256-GCM — Authenticated Encryption (recommended)",
            "chacha20": "ChaCha20 — Fast stream cipher",
            "aes_cbc":  "AES-256-CBC — Legacy block cipher",
        },
        "kdf_algorithms": {
            "scrypt":  "Scrypt — Memory-hard, GPU-resistant",
            "pbkdf2":  "PBKDF2-SHA256 — Standard, fast",
        },
    })


# ── CAPACITY CHECK ─────────────────────────────────────────────
@app.route("/check-capacity", methods=["POST"])
def check_capacity():
    if "carrier" not in request.files:
        return bad("No 'carrier' file.")
    tmp = None
    try:
        f = request.files["carrier"]
        ext = get_ext(f.filename)
        tmp = save_temp(f)
        algo = request.form.get("algorithm", "camouflage_lsb")
        payload_size = int(request.form.get("payload_size", 0))

        if ext in AUDIO_FORMATS:
            cap = get_wav_capacity(tmp)
            media_info = get_wav_info(tmp)
            media_type = "audio"
        elif ext in IMAGE_FORMATS:
            img = load_image(tmp)
            plugin = plugin_manager.get_plugin(algo)
            cap = plugin.get_capacity(img)
            media_info = {"width": img.shape[1], "height": img.shape[0], "channels": img.shape[2] if len(img.shape) == 3 else 1}
            media_type = "image"
        else:
            cap = get_file_capacity(tmp)
            media_info = get_file_info(tmp)
            media_type = "generic_file"

        used_pct = round(payload_size / cap * 100, 1) if cap > 0 else 0
        rec = "✅ OK — safe to embed." if used_pct < 60 else \
              "⚠️ High density — detectability risk increases." if used_pct < 100 else \
              "❌ Payload too large — use a bigger carrier or compress more."

        return jsonify({"success": True, "media_type": media_type, "media_info": media_info,
                        "capacity_bytes": cap, "payload_bytes": payload_size,
                        "used_percent": used_pct, "recommendation": rec})
    except Exception as e:
        return bad(str(e), 500)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)


# ── HIDE ───────────────────────────────────────────────────────
@app.route("/hide", methods=["POST"])
def hide():
    if "image" not in request.files:
        return bad("No 'image' field (carrier) in request.")

    carrier_file  = request.files["image"]
    ext           = get_ext(carrier_file.filename)
    message       = request.form.get("message", "")
    secret_file   = request.files.get("secret_file")
    password      = request.form.get("password", "").strip()
    algorithm     = request.form.get("algorithm", "camouflage_lsb").strip()
    encryption    = request.form.get("encryption", "aes_gcm").strip()
    kdf           = request.form.get("kdf", "pbkdf2").strip()
    iterations    = int(request.form.get("iterations", 100000))
    comp_level    = int(request.form.get("compression_level", 9))
    hint          = request.form.get("hint", "").strip()
    question      = request.form.get("recovery_question", "").strip()
    answer        = request.form.get("recovery_answer", "").strip()
    explain_mode  = request.form.get("explain_mode", "false").lower() == "true"

    if not message and not secret_file:
        return bad("Provide a text message or a secret file.")
    if not password:
        return bad("'password' is required.")

    # Removed strict extension checking to allow generic files.
    if not allowed_any(carrier_file.filename):
        return bad("Invalid file name (no extension).")

    tmp = None
    t0  = time.time()
    try:
        # Build payload
        if secret_file and secret_file.filename:
            fb = secret_file.read()
            fn = secret_file.filename.encode()
            payload = b"FILE:" + bytes([len(fn)]) + fn + fb
        else:
            payload = b"TEXT:" + message.encode("utf-8")

        original_size = len(payload)

        # Hint
        answer_hash = hashlib.sha256(answer.encode()).hexdigest() if answer else ""
        payload = pack_hint(payload, hint, question, answer_hash)

        # Compress + Encrypt
        compressed   = zlib.compress(payload, level=comp_level)
        enc          = encrypt_message(compressed, password, encryption, kdf, iterations)
        compressed_size = len(compressed)
        encrypted_size  = len(enc)

        tmp = save_temp(carrier_file)

        # ── Audio carrier ──────────────────────────────────────
        if ext in AUDIO_FORMATS:
            cap = get_wav_capacity(tmp)
            if encrypted_size > cap:
                return bad(f"Payload too large for this audio ({encrypted_size:,} B > {cap:,} B capacity).")

            stego_wav_bytes = embed_in_wav(tmp, enc)
            audio_b64       = base64.b64encode(stego_wav_bytes).decode()
            processing_time = time.time() - t0
            wav_info        = get_wav_info(tmp)

            report = _build_report(carrier_file.filename, "audio", original_size, compressed_size,
                                   encrypted_size, algorithm, encryption, kdf, iterations,
                                   processing_time, cap, psnr=None, score=None,
                                   extra={"duration": f"{wav_info['duration_seconds']}s",
                                          "sample_rate": f"{wav_info['sample_rate_hz']} Hz",
                                          "channels": wav_info["channels"]})

            _stats["hide_count"] += 1
            _stats["total_bytes_hidden"] += original_size
            log_op("HIDE", {"algorithm": algorithm, "media_type": "audio", "payload_bytes": original_size})
            _replay_store["last"] = {"operation": "hide", "algorithm": algorithm,
                                     "encryption": encryption, "kdf": kdf,
                                     "iterations": iterations, "compression_level": comp_level}

            explanations = EXPLAIN_HIDE.copy()
            if algorithm == "dct":
                explanations[6] = {"step": 7, "title": "DCT Embedding", "detail": "The image is divided into 8x8 blocks, and bits are embedded into frequency coefficients using Discrete Cosine Transform."}
            elif algorithm == "dwt":
                explanations[6] = {"step": 7, "title": "DWT Embedding", "detail": "The image is decomposed into frequency sub-bands, and bits are embedded into the High-High (HH) wavelet coefficients."}
            elif algorithm == "svd":
                explanations[6] = {"step": 7, "title": "SVD Embedding", "detail": "The image is processed in 8x8 blocks, and bits are embedded by modifying the largest Singular Value (S matrix) of each block."}
            elif algorithm == "lbb":
                explanations[6] = {"step": 7, "title": "LBB Embedding", "detail": "The image is divided into 3x3 blocks, and 8 bits are hidden per block by adjusting neighbor pixels relative to the center pixel."}
            elif algorithm.startswith("overlay_"):
                explanations[6] = {"step": 7, "title": "Overlay Watermarking", "detail": "The payload is transformed into a robust pattern and blended with the carrier using additive, alpha, or multiplicative formulas."}

            return jsonify({
                "success": True,
                "media_type": "audio",
                "audio_data": audio_b64,
                "audio_filename": carrier_file.filename.rsplit(".", 1)[0] + "_stego.wav",
                "capacity": cap,
                "stats": _make_stats(original_size, compressed_size, encrypted_size, cap, processing_time),
                "report": report,
                "explanations": explanations if explain_mode else [],
            })

        # ── Image carrier ──────────────────────────────────────
        elif ext in IMAGE_FORMATS:
            carrier = load_image(tmp)
            plugin  = plugin_manager.get_plugin(algorithm)
            cap     = plugin.get_capacity(carrier)

            if encrypted_size > cap:
                return bad(f"Payload too large ({encrypted_size:,} B). Carrier capacity: {cap:,} B.")

            stego      = plugin.embed(carrier, enc)
            score_data = SteganalysisEngine.calculate_security_score(carrier, stego)
            heatmap_data = SteganalysisEngine.generate_heatmap_layers(carrier, stego)

            ok, buf = cv2.imencode(".png", stego)
            if not ok: return bad("Failed to encode stego image.", 500)
            stego_b64 = base64.b64encode(buf).decode()

            processing_time = time.time() - t0
            report = _build_report(carrier_file.filename, "image", original_size, compressed_size,
                                   encrypted_size, algorithm, encryption, kdf, iterations,
                                   processing_time, cap, score_data.get("psnr", 0),
                                   score_data.get("score", 0))

            _stats["hide_count"] += 1
            _stats["total_bytes_hidden"] += original_size
            log_op("HIDE", {"algorithm": algorithm, "media_type": "image", "payload_bytes": original_size})
            _replay_store["last"] = {"operation": "hide", "algorithm": algorithm,
                                     "encryption": encryption, "kdf": kdf,
                                     "iterations": iterations, "compression_level": comp_level}

            explanations = EXPLAIN_HIDE.copy()
            if algorithm == "dct":
                explanations[6] = {"step": 7, "title": "DCT Embedding", "detail": "The image is divided into 8x8 blocks, and bits are embedded into frequency coefficients using Discrete Cosine Transform."}
            elif algorithm == "dwt":
                explanations[6] = {"step": 7, "title": "DWT Embedding", "detail": "The image is decomposed into frequency sub-bands, and bits are embedded into the High-High (HH) wavelet coefficients."}

            return jsonify({
                "success": True,
                "media_type": "image",
                "stego_image": stego_b64,
                "heatmap_image":  heatmap_data["layers"].get("composite", ""),
                "heatmap_layers": heatmap_data["layers"],
                "heatmap_stats":  heatmap_data["stats"],
                "security": score_data,
                "capacity": cap,
                "stats": _make_stats(original_size, compressed_size, encrypted_size, cap, processing_time),
                "report": report,
                "explanations": explanations if explain_mode else [],
            })

        # ── Generic File carrier ───────────────────────────────
        else:
            cap = get_file_capacity(tmp)
            stego_file_bytes = embed_in_file(tmp, enc)
            file_b64         = base64.b64encode(stego_file_bytes).decode()
            processing_time  = time.time() - t0
            file_info        = get_file_info(tmp)

            report = _build_report(carrier_file.filename, "generic_file", original_size, compressed_size,
                                   encrypted_size, algorithm, encryption, kdf, iterations,
                                   processing_time, cap, psnr=None, score=None,
                                   extra={"mime_type": file_info["mime_type"], "size": file_info["size_bytes"]})

            _stats["hide_count"] += 1
            _stats["total_bytes_hidden"] += original_size
            log_op("HIDE", {"algorithm": "append", "media_type": "generic_file", "payload_bytes": original_size})
            _replay_store["last"] = {"operation": "hide", "algorithm": algorithm,
                                     "encryption": encryption, "kdf": kdf,
                                     "iterations": iterations, "compression_level": comp_level}

            # Return same format as audio, but identify as generic
            stego_filename = carrier_file.filename.rsplit(".", 1)[0] + "_stego." + ext
            
            return jsonify({
                "success": True,
                "media_type": "generic_file",
                "generic_data": file_b64,
                "generic_filename": stego_filename,
                "capacity": cap,
                "stats": _make_stats(original_size, compressed_size, encrypted_size, cap, processing_time),
                "report": report,
                "explanations": EXPLAIN_HIDE if explain_mode else [],
            })

    except ValueError as e:
        return bad(str(e))
    except Exception as e:
        app.logger.exception("Error in /hide")
        return bad(f"Server error: {e}", 500)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)


# ── EXTRACT ────────────────────────────────────────────────────
@app.route("/extract", methods=["POST"])
def extract():
    if "image" not in request.files:
        return bad("No 'image' field in request.")

    stego_file   = request.files["image"]
    ext          = get_ext(stego_file.filename)
    password     = request.form.get("password", "").strip()
    algorithm    = request.form.get("algorithm", "camouflage_lsb").strip()
    kdf          = request.form.get("kdf", "pbkdf2").strip()
    iterations   = int(request.form.get("iterations", 100000))
    explain_mode = request.form.get("explain_mode", "false").lower() == "true"

    if not password: return bad("'password' is required.")
    if not allowed_any(stego_file.filename):
        return bad("Invalid file name (no extension).")

    tmp = None
    t0  = time.time()
    try:
        tmp = save_temp(stego_file)

        if ext in AUDIO_FORMATS:
            enc_data = extract_from_wav(tmp)
        elif ext in IMAGE_FORMATS:
            stego    = load_image(tmp)
            plugin   = plugin_manager.get_plugin(algorithm)
            enc_data = plugin.extract(stego)
        else:
            enc_data = extract_from_file(tmp)

        secret = decrypt_message(enc_data, password, kdf, iterations)

        try:
            decompressed = zlib.decompress(secret)
        except zlib.error:
            decompressed = b"TEXT:" + secret

        decompressed, hint_block = unpack_hint(decompressed)
        processing_time = time.time() - t0

        if decompressed.startswith(b"TEXT:"):
            result = {"type": "text", "message": decompressed[5:].decode("utf-8")}
        elif decompressed.startswith(b"FILE:"):
            fn_len   = decompressed[5]
            filename = decompressed[6: 6 + fn_len].decode("utf-8")
            file_data= decompressed[6 + fn_len:]
            result   = {"type": "file", "filename": filename,
                        "file_data": base64.b64encode(file_data).decode(),
                        "file_size_bytes": len(file_data)}
        else:
            result = {"type": "text", "message": decompressed.decode("utf-8", errors="replace")}

        media_type = "audio" if ext in AUDIO_FORMATS else "image" if ext in IMAGE_FORMATS else "generic_file"
        _stats["extract_count"] += 1
        log_op("EXTRACT", {"algorithm": algorithm, "media_type": media_type})

        explanations = EXPLAIN_EXTRACT.copy()
        if algorithm == "dct":
            explanations[0] = {"step": 1, "title": "DCT Extraction", "detail": "The image is processed in 8x8 blocks, and hidden bits are recovered from the frequency domain coefficients."}
        elif algorithm == "dwt":
            explanations[0] = {"step": 1, "title": "DWT Extraction", "detail": "The image is decomposed using Haar Wavelet, and hidden bits are recovered from the HH sub-band coefficients."}
        elif algorithm == "svd":
            explanations[0] = {"step": 1, "title": "SVD Extraction", "detail": "The image is processed in 8x8 blocks, and hidden bits are recovered by analyzing the Singular Values (S matrix) of each block."}
        elif algorithm == "lbb":
            explanations[0] = {"step": 1, "title": "LBB Extraction", "detail": "The image is processed in 3x3 blocks, and 8 bits are recovered from each block by comparing neighbor values to the center pixel."}
        elif algorithm.startswith("overlay_"):
            explanations[0] = {"step": 1, "title": "Overlay Extraction", "detail": "The hidden pattern is recovered using a differential high-pass filter and block-mean analysis."}

        return jsonify({
            "success": True,
            **result,
            "hints": hint_block,
            "stats": {
                "processing_time_seconds": round(processing_time, 3),
                "bits_extracted": len(enc_data) * 8,
                "media_type": media_type,
            },
            "explanations": explanations if explain_mode else [],
        })

    except ValueError as e:
        return bad(str(e))
    except Exception as e:
        app.logger.exception("Error in /extract")
        return bad(f"Server error: {e}", 500)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)


# ── DETECT ─────────────────────────────────────────────────────
@app.route("/detect", methods=["POST"])
def detect():
    if "image" not in request.files:
        return bad("No 'image' field.")
    tmp = None
    try:
        tmp = save_temp(request.files["image"])
        image = load_image(tmp)
        flat  = image.flatten().astype(np.int32)
        lsb   = flat & 1
        ones  = int(np.sum(lsb))
        zeros = int(len(lsb) - ones)
        ratio = ones / max(zeros, 1)
        chi   = abs(ratio - 1.0)
        score = min(100, int(chi * 500))
        
        print(f"DEBUG: ai_detector is {ai_detector}")
        ai_result = None
        debug_info = {}
        if ai_detector is not None:
            debug_info['is_loaded'] = ai_detector.is_loaded
            if ai_detector.is_loaded:
                result = ai_detector.predict(image)
                if result is not None:
                    ai_result = result
                    ai_probability = result["prob_stego"]
                    ai_score = int(ai_probability * 100)
                    score = int(score * 0.3 + ai_score * 0.7)
        else:
            debug_info['detector'] = 'None'
            debug_info['error'] = ai_detector_error

        risk  = "Low" if score < 30 else "Medium" if score < 60 else "High"

        return jsonify({"success": True, "detection": {
            "lsb_ones_ratio": round(ratio, 4),
            "chi_square_deviation": round(chi, 4),
            "suspicion_score": score,
            "risk_level": risk,
            "ai_result": ai_result,
            "verdict": f"{risk} probability of hidden data",
            "total_pixels": len(flat),
            "ones_count": ones, "zeros_count": zeros,
            "debug": debug_info
        }})
    except Exception as e:
        return bad(str(e), 500)
    finally:
        if tmp and os.path.exists(tmp): os.unlink(tmp)


# ── DEMO ───────────────────────────────────────────────────────
@app.route("/demo", methods=["POST"])
def demo():
    style   = request.form.get("style", "gradient")
    msg_key = request.form.get("message", "medium")
    pw      = "FynzaDemo2024!"
    try:
        h, w = 400, 600
        img  = np.zeros((h, w, 3), dtype=np.uint8)
        for i in range(w):
            img[:, i, 0] = int(60 * i / w)
            img[:, i, 2] = int(237 * i / w)
        cv2.putText(img, "FYNZA", (160, 230), cv2.FONT_HERSHEY_SIMPLEX, 3, (200, 100, 255), 4)

        message = DEMO_MESSAGES.get(msg_key, DEMO_MESSAGES["medium"])
        plugin  = plugin_manager.get_plugin("lsb_basic")
        payload = b"TEXT:" + message.encode()
        enc     = encrypt_message(zlib.compress(payload), pw, "aes_gcm", "pbkdf2", 100000)
        stego   = plugin.embed(img, enc)

        ok_c, buf_c = cv2.imencode(".png", img)
        ok_s, buf_s = cv2.imencode(".png", stego)

        return jsonify({
            "success": True,
            "carrier_image": base64.b64encode(buf_c).decode() if ok_c else "",
            "stego_image":   base64.b64encode(buf_s).decode() if ok_s else "",
            "demo_message": message, "demo_password": pw,
            "demo_algorithm": "lsb_basic", "demo_kdf": "pbkdf2", "demo_iterations": "100000",
            "note": "This is a demo — always use a unique strong password in production!",
        })
    except Exception as e:
        return bad(f"Demo failed: {e}", 500)


# ── STATISTICS ─────────────────────────────────────────────────
@app.route("/statistics")
def statistics():
    return jsonify({"success": True, "statistics": {
        "hide_operations": _stats["hide_count"],
        "extract_operations": _stats["extract_count"],
        "total_bytes_hidden": _stats["total_bytes_hidden"],
        "recent_operations": _stats["operations"][-20:],
    }})


# ── REPLAY ─────────────────────────────────────────────────────
@app.route("/replay")
def replay():
    if not _replay_store.get("last"):
        return bad("No previous operation to replay.")
    return jsonify({"success": True, "replay": _replay_store["last"]})


# ── EXPORT REPORT ──────────────────────────────────────────────
@app.route("/export-report", methods=["POST"])
def export_report():
    data = request.get_json(force=True, silent=True) or {}
    fmt  = request.args.get("format", "json")
    try:
        if fmt == "json":
            content, mime, fname = json.dumps(data, indent=2), "application/json", "fynza_report.json"
        elif fmt == "csv":
            rows = ["field,value"]
            for k, v in data.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items(): rows.append(f"{k}.{k2},{v2}")
                else: rows.append(f"{k},{v}")
            content, mime, fname = "\n".join(rows), "text/csv", "fynza_report.csv"
        elif fmt == "html":
            rows = "".join(f"<tr><td><b>{k}</b></td><td>{json.dumps(v) if isinstance(v,dict) else v}</td></tr>" for k,v in data.items())
            content = f"""<!DOCTYPE html><html><head><title>FYNZA Report</title>
<style>body{{font-family:Inter,sans-serif;background:#0d0d14;color:#f1f5f9;padding:32px;}}
h1{{color:#9f5fff;}} table{{border-collapse:collapse;width:100%;margin-top:20px;}}
td{{padding:12px;border-bottom:1px solid #222;}} td:first-child{{color:#94a3b8;width:40%;}}</style>
</head><body><h1>🔒 FYNZA Security Report</h1><table>{rows}</table></body></html>"""
            return send_file(io.BytesIO(content.encode()), mimetype="text/html", as_attachment=True, download_name="fynza_report.html")
        elif fmt == "pdf":
            from forensic_reporter import ForensicReporter
            reporter = ForensicReporter(
                stats=data.get("heatmap_stats", {}),
                security=data.get("security", {}),
                layers=data.get("heatmap_layers", {}),
                carrier_info=data.get("report", {}).get("carrier", {})
            )
            pdf_bytes = reporter.generate()
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype="application/pdf",
                as_attachment=True,
                download_name="fynza_forensic_report.pdf"
            )
        else:
            return bad("Unsupported format. Use json, csv, html, or pdf.")
    except Exception as e:
        return bad(f"Export failed: {e}", 500)


# ── EXPLANATIONS ───────────────────────────────────────────────
@app.route("/explanations/<operation>")
def get_explanations(operation):
    steps = EXPLAIN_HIDE if operation == "hide" else EXPLAIN_EXTRACT if operation == "extract" else []
    return jsonify({"success": True, "steps": steps})


# ── Helpers ────────────────────────────────────────────────────
def _make_stats(orig, comp, enc, cap, t):
    return {
        "original_size": orig,
        "compressed_size": comp,
        "encrypted_size": enc,
        "compression_ratio": round((1 - comp / orig) * 100, 1) if orig > 0 else 0,
        "processing_time_seconds": round(t, 3),
        "bits_embedded": enc * 8,
        "capacity_used_pct": round(enc / cap * 100, 1) if cap > 0 else 0,
    }

def _build_report(filename, media_type, orig, comp, enc, algo, cipher, kdf, iters, t, cap, psnr, score, extra=None):
    r = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "carrier":  {"filename": filename, "media_type": media_type},
        "payload":  {"original_bytes": orig, "compressed_bytes": comp, "encrypted_bytes": enc,
                     "compression_saved_pct": round((1 - comp/orig)*100, 1) if orig > 0 else 0},
        "security": {"algorithm": algo, "cipher": cipher, "kdf": kdf, "iterations": iters,
                     "capacity_used_pct": round(enc/cap*100, 1) if cap > 0 else 0},
        "performance": {"processing_time_seconds": round(t, 3)},
    }
    if psnr is not None: r["security"]["psnr_db"] = psnr
    if score is not None: r["security"]["score"] = score
    if extra: r["carrier"].update(extra)
    return r


@app.errorhandler(413)
def too_large(e):
    return bad("File too large. Maximum is 100 MB.", 413)


if __name__ == "__main__":
    print("[*] FYNZA API -> http://localhost:5000")
    print(f"[*] Plugins: {list(plugin_manager.plugins.keys())}")
    # Trigger auto-reload for AI model
    app.run(host="0.0.0.0", port=5000, debug=True)
