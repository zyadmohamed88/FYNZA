import os
import base64
from datetime import datetime
from fpdf import FPDF
import tempfile

class ForensicReporter:
    """Generates professional PDF forensic reports for steganalysis results."""

    def __init__(self, stats, security, layers, carrier_info=None):
        self.stats = stats
        self.security = security
        self.layers = layers
        self.carrier_info = carrier_info or {}
        self.pdf = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=15)

    def generate(self):
        self.pdf.add_page()
        self._add_header()
        self._add_security_summary()
        self._add_technical_stats()
        self._add_visual_evidence()
        self._add_disclaimer()
        
        # Return as bytes directly using output()
        return self.pdf.output()

    def _add_header(self):
        self.pdf.set_font("Helvetica", "B", 24)
        self.pdf.set_text_color(30, 41, 59)  # Slate 800
        self.pdf.cell(0, 20, "FYNZA Forensic Analysis Report", ln=True, align="C")
        
        self.pdf.set_font("Helvetica", "", 10)
        self.pdf.set_text_color(100, 116, 139) # Slate 500
        self.pdf.cell(0, 5, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
        self.pdf.cell(0, 5, f"Case ID: {datetime.now().strftime('%Y%m%d%H%M')}-FORENSIC", ln=True, align="C")
        self.pdf.ln(10)
        
        # Carrier Info
        self.pdf.set_fill_color(248, 250, 252)
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.set_text_color(51, 65, 85)
        self.pdf.cell(0, 10, " 1. Evidence Information", ln=True, fill=True)
        self.pdf.set_font("Helvetica", "", 10)
        self.pdf.ln(2)
        
        info = [
            ["Filename:", self.carrier_info.get("filename", "Unknown")],
            ["Dimensions:", f"{self.stats.get('dimensions', {}).get('width')} x {self.stats.get('dimensions', {}).get('height')} px"],
            ["Total Pixels:", f"{self.stats.get('total_pixels', 0):,}"],
            ["Format:", "Digital Image (Lossless/BMP/PNG)"]
        ]
        
        for label, val in info:
            self.pdf.set_font("Helvetica", "B", 10)
            self.pdf.cell(30, 7, label)
            self.pdf.set_font("Helvetica", "", 10)
            self.pdf.cell(0, 7, str(val), ln=True)
        self.pdf.ln(5)

    def _add_security_summary(self):
        self.pdf.set_fill_color(248, 250, 252)
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.cell(0, 10, " 2. Security & Risk Assessment", ln=True, fill=True)
        self.pdf.ln(3)
        
        # Risk Score Box
        score = self.security.get("score", 0)
        risk = self.security.get("risk_level", "Unknown")
        
        # Set color based on risk
        if risk == "Low": r, g, b = (34, 197, 94) # Green
        elif risk == "Medium": r, g, b = (234, 179, 8) # Yellow
        else: r, g, b = (239, 68, 68) # Red
        
        self.pdf.set_font("Helvetica", "B", 14)
        self.pdf.set_text_color(r, g, b)
        self.pdf.cell(0, 10, f"Integrity Score: {score}/100 - RISK LEVEL: {risk.upper()}", ln=True)
        
        self.pdf.set_text_color(51, 65, 85)
        self.pdf.set_font("Helvetica", "", 10)
        metrics = [
            ["PSNR (Visual Distortion):", f"{self.security.get('psnr', 0)} dB"],
            ["Statistical Stealth:", f"{self.security.get('statistical_stealth', 0)}/100"],
            ["Visual Integrity:", f"{self.security.get('visual_quality', 0)}/100"]
        ]
        for label, val in metrics:
            self.pdf.set_font("Helvetica", "B", 10)
            self.pdf.cell(50, 7, label)
            self.pdf.set_font("Helvetica", "", 10)
            self.pdf.cell(0, 7, str(val), ln=True)
        self.pdf.ln(5)

    def _add_technical_stats(self):
        self.pdf.set_fill_color(248, 250, 252)
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.cell(0, 10, " 3. Forensic Statistics", ln=True, fill=True)
        self.pdf.ln(3)
        
        stats = [
            ["Modified Pixels:", f"{self.stats.get('modified_pixels', 0):,}"],
            ["Affected Area:", f"{self.stats.get('affected_pct', 0)}%"],
            ["Embedding Pattern:", self.stats.get("pattern_type", "Unknown")],
            ["LSB Distribution:", f"{self.stats.get('bit_distribution', {}).get('ones', 0)} ones / {self.stats.get('bit_distribution', {}).get('zeros', 0)} zeros"]
        ]
        
        for label, val in stats:
            self.pdf.set_font("Helvetica", "B", 10)
            self.pdf.cell(50, 7, label)
            self.pdf.set_font("Helvetica", "", 10)
            self.pdf.cell(0, 7, str(val), ln=True)
            
        # Risk Zones
        self.pdf.ln(2)
        self.pdf.set_font("Helvetica", "B", 10)
        self.pdf.cell(0, 7, "Risk Zone Breakdown:", ln=True)
        rz = self.stats.get("risk_zones", {})
        self.pdf.set_font("Helvetica", "", 10)
        self.pdf.cell(0, 7, f"Safe: {rz.get('safe', 0)}% | Medium: {rz.get('medium', 0)}% | Risky: {rz.get('risky', 0)}%", ln=True)
        self.pdf.ln(5)

    def _add_visual_evidence(self):
        self.pdf.add_page()
        self.pdf.set_fill_color(248, 250, 252)
        self.pdf.set_font("Helvetica", "B", 12)
        self.pdf.cell(0, 10, " 4. Visual Evidence (Heatmaps)", ln=True, fill=True)
        self.pdf.ln(5)
        
        # We need to save b64 images to temp files to add them to PDF
        layer_names = ["composite", "intensity", "risk"]
        titles = ["Composite Analysis", "Change Intensity", "Risk Mapping"]
        
        for i, name in enumerate(layer_names):
            if name in self.layers:
                self.pdf.set_font("Helvetica", "B", 10)
                self.pdf.cell(0, 10, titles[i], ln=True)
                
                img_data = base64.b64decode(self.layers[name])
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(img_data)
                    tmp_path = tmp.name
                
                # Maintain aspect ratio
                self.pdf.image(tmp_path, x=15, w=180)
                os.unlink(tmp_path)
                self.pdf.ln(5)

    def _add_disclaimer(self):
        self.pdf.ln(10)
        self.pdf.set_font("Helvetica", "I", 8)
        self.pdf.set_text_color(150, 150, 150)
        disclaimer = "This report is generated by the FYNZA Steganalysis Engine using statistical and visual pixel analysis. The results are probabilistic and should be used as supporting evidence in digital forensic investigations. FYNZA Labs does not guarantee 100% detection accuracy for all steganographic methods."
        self.pdf.multi_cell(0, 5, disclaimer)
