import base64
import math

import cv2
import numpy as np


class SteganalysisEngine:
    """Advanced steganalysis engine: multi-layer heatmaps + forensic statistics."""

    # ── Shared Utilities ──────────────────────────────────────────────────────

    @staticmethod
    def _to_bgr(img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 4:
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img.copy()

    @staticmethod
    def _to_b64(img: np.ndarray) -> str:
        ok, buf = cv2.imencode(".png", img)
        return base64.b64encode(buf).decode() if ok else ""

    @staticmethod
    def _blend(bg: np.ndarray, overlay: np.ndarray, alpha: np.ndarray) -> np.ndarray:
        return (bg.astype(np.float32) * (1.0 - alpha) +
                overlay.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)

    # ── Individual Layer Generators ───────────────────────────────────────────

    @staticmethod
    def _layer_change_map(orig3: np.ndarray, changed_bin: np.ndarray) -> np.ndarray:
        """Binary change map — cyan glow on dimmed original."""
        h, w = orig3.shape[:2]
        bg = (orig3.astype(np.float32) * 0.2).astype(np.uint8)
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(changed_bin, kernel, iterations=1).astype(np.float32)
        glow = np.zeros((h, w, 3), dtype=np.uint8)
        glow[:, :, 0] = (dilated * 255).astype(np.uint8)   # B
        glow[:, :, 1] = (dilated * 200).astype(np.uint8)   # G
        alpha = dilated[..., np.newaxis]
        return SteganalysisEngine._blend(bg, glow, alpha)

    @staticmethod
    def _layer_intensity_map(orig3: np.ndarray, pixel_diff: np.ndarray) -> np.ndarray:
        """Intensity map — how much each pixel changed (MAGMA colormap)."""
        intensity = pixel_diff.max(axis=2)
        boosted = np.clip(intensity * 50, 0, 255).astype(np.uint8)
        colorized = cv2.applyColorMap(boosted, cv2.COLORMAP_MAGMA)
        bg = (orig3.astype(np.float32) * 0.25).astype(np.uint8)
        alpha = (boosted.astype(np.float32) / 255.0)[..., np.newaxis]
        return SteganalysisEngine._blend(bg, colorized, alpha * 0.95)

    @staticmethod
    def _layer_density_map(orig3: np.ndarray, changed_bin: np.ndarray) -> np.ndarray:
        """Density map — Gaussian-blurred embedding distribution (TURBO colormap)."""
        d1 = cv2.GaussianBlur(changed_bin.astype(np.float32), (51, 51), sigmaX=18.0)
        d2 = cv2.GaussianBlur(changed_bin.astype(np.float32), (15, 15), sigmaX=5.0)
        density = d1 * 0.6 + d2 * 0.4
        if density.max() > 0:
            density /= density.max()
        density = np.power(density, 0.45)
        colorized = cv2.applyColorMap((density * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        bg = (orig3.astype(np.float32) * 0.25).astype(np.uint8)
        return SteganalysisEngine._blend(bg, colorized, density[..., np.newaxis] * 0.9)

    @staticmethod
    def _layer_risk_map(orig3: np.ndarray, changed_bin: np.ndarray) -> np.ndarray:
        """Risk map — Green (safe) → Yellow (medium) → Red (risky)."""
        local = cv2.GaussianBlur(changed_bin.astype(np.float32), (41, 41), sigmaX=14.0)
        if local.max() > 0:
            local /= local.max()
        r = np.clip(local * 2.0, 0, 1)
        g = np.clip(2.0 - local * 2.0, 0, 1)
        b = np.zeros_like(local)
        risk_bgr = np.stack([(b * 255).astype(np.uint8),
                              (g * 255).astype(np.uint8),
                              (r * 255).astype(np.uint8)], axis=2)
        bg = (orig3.astype(np.float32) * 0.25).astype(np.uint8)
        return SteganalysisEngine._blend(bg, risk_bgr, local[..., np.newaxis] * 0.85)

    @staticmethod
    def _layer_composite(orig3: np.ndarray, changed_mask: np.ndarray) -> np.ndarray:
        """Composite premium heatmap with grid overlay (TURBO colormap)."""
        h, w = orig3.shape[:2]
        bl = cv2.GaussianBlur(changed_mask.astype(np.float32), (31, 31), sigmaX=12.0)
        bs = cv2.GaussianBlur(changed_mask.astype(np.float32), (7, 7), sigmaX=2.5)
        heat = bl * 0.7 + bs * 0.3
        if heat.max() > 0:
            heat /= heat.max()
        heat = np.power(heat, 0.5)
        colorized = cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        bg = (orig3.astype(np.float32) * 0.35).astype(np.uint8)
        result = SteganalysisEngine._blend(bg, colorized, heat[..., np.newaxis] * 0.85)
        grid_step = max(32, min(h, w) // 8)
        for gx in range(0, w, grid_step):
            cv2.line(result, (gx, 0), (gx, h), (40, 40, 40), 1)
        for gy in range(0, h, grid_step):
            cv2.line(result, (0, gy), (w, gy), (40, 40, 40), 1)
        return result

    # ── Pattern Analysis ───────────────────────────────────────────────────────

    @staticmethod
    def _detect_pattern(changed_bin: np.ndarray, orig3: np.ndarray, h: int, w: int) -> str:
        coords = np.argwhere(changed_bin > 0)
        if len(coords) < 10:
            return "Minimal"
        row_var = np.var(coords[:, 0]) / (h ** 2)
        col_var = np.var(coords[:, 1]) / (w ** 2)
        median_row = coords[len(coords) // 2][0] / h
        # Edge-based check
        gray = cv2.cvtColor(orig3, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150).astype(np.float32) / 255.0
        edge_overlap = float((edges * changed_bin).sum()) / len(coords)
        if edge_overlap > 0.3:
            return "Edge-Based"
        if median_row < 0.35 and col_var > 0.08:
            return "Sequential"
        if row_var > 0.06 and col_var > 0.06:
            return "Random (Scattered)"
        return "Clustered"

    # ── Public APIs ────────────────────────────────────────────────────────────

    @staticmethod
    def generate_heatmap(original: np.ndarray, stego: np.ndarray) -> np.ndarray:
        """Backward-compatible: returns composite heatmap as numpy array."""
        orig3 = SteganalysisEngine._to_bgr(original)
        steg3 = SteganalysisEngine._to_bgr(stego)
        lsb_diff = np.abs((steg3 & 1).astype(np.float32) - (orig3 & 1).astype(np.float32))
        weights = np.array([0.114, 0.587, 0.299], dtype=np.float32)
        changed_mask = (lsb_diff * weights).sum(axis=2)
        return SteganalysisEngine._layer_composite(orig3, changed_mask)

    @staticmethod
    def generate_heatmap_layers(original: np.ndarray, stego: np.ndarray) -> dict:
        """
        Generate all analytical heatmap layers + comprehensive statistics.
        Returns {'layers': {name: b64_png}, 'stats': {...}}.
        """
        h, w = original.shape[:2]
        orig3 = SteganalysisEngine._to_bgr(original)
        steg3 = SteganalysisEngine._to_bgr(stego)
        if orig3.shape != steg3.shape:
            steg3 = cv2.resize(steg3, (w, h))

        pixel_diff   = cv2.absdiff(orig3, steg3).astype(np.float32)
        lsb_diff     = np.abs((steg3 & 1).astype(np.float32) - (orig3 & 1).astype(np.float32))
        weights      = np.array([0.114, 0.587, 0.299], dtype=np.float32)
        changed_mask = (lsb_diff * weights).sum(axis=2)
        changed_bin  = (changed_mask > 0).astype(np.uint8)

        # ── Hi-res upscale: render at 2× then encode ──────────────────────────
        # Ensures fine pixel-level detail is visible in the exported PNG.
        target_max = 2048
        scale_up = max(1, min(3, target_max // max(h, w))) if max(h, w) < target_max else 1
        def _upscale(img: np.ndarray) -> np.ndarray:
            if scale_up == 1:
                return img
            return cv2.resize(img, (img.shape[1] * scale_up, img.shape[0] * scale_up),
                              interpolation=cv2.INTER_LANCZOS4)

        def _to_b64_hires(img: np.ndarray) -> str:
            return SteganalysisEngine._to_b64(_upscale(img))

        layers = {
            "composite":  _to_b64_hires(SteganalysisEngine._layer_composite(orig3, changed_mask)),
            "change_map": _to_b64_hires(SteganalysisEngine._layer_change_map(orig3, changed_bin)),
            "intensity":  _to_b64_hires(SteganalysisEngine._layer_intensity_map(orig3, pixel_diff)),
            "density":    _to_b64_hires(SteganalysisEngine._layer_density_map(orig3, changed_bin)),
            "risk":       _to_b64_hires(SteganalysisEngine._layer_risk_map(orig3, changed_bin)),
        }

        total_pixels    = h * w
        modified_pixels = int(changed_bin.sum())
        affected_pct    = round(modified_pixels / total_pixels * 100, 3)

        ch_names = ["blue", "green", "red"]
        channel_stats = {}
        for i, ch in enumerate(ch_names):
            n = int((lsb_diff[:, :, i] > 0).sum())
            channel_stats[ch] = {"modified": n, "pct": round(n / total_pixels * 100, 2)}

        stego_lsb = (steg3 & 1).flatten()
        ones_count  = int(stego_lsb.sum())
        zeros_count = int(len(stego_lsb) - ones_count)

        local_d = cv2.GaussianBlur(changed_bin.astype(np.float32), (41, 41), sigmaX=14.0)
        if local_d.max() > 0:
            local_d /= local_d.max()
        safe_pct   = round(float((local_d < 0.33).sum()) / total_pixels * 100, 1)
        medium_pct = round(float(((local_d >= 0.33) & (local_d < 0.66)).sum()) / total_pixels * 100, 1)
        risky_pct  = round(float((local_d >= 0.66).sum()) / total_pixels * 100, 1)

        return {
            "layers": layers,
            "stats": {
                "total_pixels":     total_pixels,
                "modified_pixels":  modified_pixels,
                "affected_pct":     affected_pct,
                "pattern_type":     SteganalysisEngine._detect_pattern(changed_bin, orig3, h, w),
                "bit_distribution": {"ones": ones_count, "zeros": zeros_count},
                "channel_stats":    channel_stats,
                "risk_zones":       {"safe": safe_pct, "medium": medium_pct, "risky": risky_pct},
                "dimensions":       {"width": w, "height": h},
            },
        }

    @staticmethod
    def calculate_security_score(original: np.ndarray, stego: np.ndarray) -> dict:
        """Calculate 0-100 security score using PSNR + LSB chi-square analysis."""
        orig3 = SteganalysisEngine._to_bgr(original)
        steg3 = SteganalysisEngine._to_bgr(stego)

        mse  = np.mean((orig3.astype(np.float64) - steg3.astype(np.float64)) ** 2)
        psnr = 100.0 if mse == 0 else 10.0 * math.log10((255.0 ** 2) / mse)

        stego_lsb = steg3.flatten() & 1
        ones_ratio = np.mean(stego_lsb)
        divergence = abs(0.5 - ones_ratio)
        chi_score  = min(100, divergence * 1000)
        psnr_score = max(0, min(100, (psnr - 30) * 2.5))
        final      = (psnr_score * 0.4) + (chi_score * 0.6)

        return {
            "score":               round(final, 1),
            "psnr":                round(psnr, 2),
            "statistical_stealth": round(chi_score, 1),
            "visual_quality":      round(psnr_score, 1),
            "risk_level":          "High" if final < 40 else "Medium" if final < 70 else "Low",
        }
