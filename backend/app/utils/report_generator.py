"""
Serene Care — Clinical Depression Screening Report Generator

Generates a medical-grade PDF report using reportlab with:
- Session metadata & patient summary
- Voice analysis confidence timeline
- Facial emotion distribution
- Combined weighted assessment
- Clinical observations & recommendations
- Standard medical disclaimer
"""

import io
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Wedge, Line
from reportlab.graphics import renderPDF

logger = logging.getLogger("DepressionDetection")

# ── Colour palette ──────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#060e20")
BRAND_ACCENT = colors.HexColor("#87d0f0")
BRAND_MID    = colors.HexColor("#2d7d9a")
HEADER_BG    = colors.HexColor("#0b1326")
ROW_ALT      = colors.HexColor("#f0f7ff")
SEVERITY_COLORS = {
    "minimal":            colors.HexColor("#4CAF50"),
    "mild":               colors.HexColor("#8BC34A"),
    "moderate":           colors.HexColor("#FFC107"),
    "moderately_severe":  colors.HexColor("#FF9800"),
    "severe":             colors.HexColor("#F44336"),
}
EMOTION_COLORS = {
    "happy":    colors.HexColor("#4CAF50"),
    "neutral":  colors.HexColor("#9E9E9E"),
    "sad":      colors.HexColor("#2196F3"),
    "angry":    colors.HexColor("#F44336"),
    "fear":     colors.HexColor("#673AB7"),
    "disgust":  colors.HexColor("#795548"),
    "surprise": colors.HexColor("#FFC107"),
}


def _severity_label(score: float) -> str:
    """Map a 0-1 combined score to a PHQ-9-aligned severity label."""
    if score < 0.2:
        return "Minimal"
    elif score < 0.4:
        return "Mild"
    elif score < 0.6:
        return "Moderate"
    elif score < 0.8:
        return "Moderately Severe"
    return "Severe"


def _severity_color(score: float) -> colors.HexColor:
    if score < 0.2:
        return SEVERITY_COLORS["minimal"]
    elif score < 0.4:
        return SEVERITY_COLORS["mild"]
    elif score < 0.6:
        return SEVERITY_COLORS["moderate"]
    elif score < 0.8:
        return SEVERITY_COLORS["moderately_severe"]
    return SEVERITY_COLORS["severe"]


class ReportGenerator:
    """Builds a clinical-quality PDF report from a Serene Care session."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._register_custom_styles()

    # ── Custom paragraph styles ──────────────────────────────────────────
    def _register_custom_styles(self):
        self.styles.add(ParagraphStyle(
            "ReportTitle", parent=self.styles["Title"],
            fontSize=22, textColor=BRAND_DARK, spaceAfter=6,
            fontName="Helvetica-Bold",
        ))
        self.styles.add(ParagraphStyle(
            "ReportSubtitle", parent=self.styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#666666"),
            alignment=TA_CENTER, spaceAfter=18,
        ))
        self.styles.add(ParagraphStyle(
            "SectionHead", parent=self.styles["Heading2"],
            fontSize=14, textColor=BRAND_MID, spaceBefore=18, spaceAfter=8,
            fontName="Helvetica-Bold", borderPadding=(0, 0, 4, 0),
        ))
        self.styles.add(ParagraphStyle(
            "BodyText2", parent=self.styles["Normal"],
            fontSize=10, leading=14, textColor=colors.HexColor("#333333"),
            alignment=TA_JUSTIFY,
        ))
        self.styles.add(ParagraphStyle(
            "SmallGrey", parent=self.styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#999999"),
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            "DisclaimerText", parent=self.styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#888888"),
            leading=11, alignment=TA_JUSTIFY,
        ))
        self.styles.add(ParagraphStyle(
            "MetricValue", parent=self.styles["Normal"],
            fontSize=28, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=BRAND_DARK, spaceAfter=2,
        ))
        self.styles.add(ParagraphStyle(
            "MetricLabel", parent=self.styles["Normal"],
            fontSize=9, alignment=TA_CENTER,
            textColor=colors.HexColor("#666666"),
        ))

    # ── Public API ───────────────────────────────────────────────────────
    def generate(self, session_data: Dict[str, Any]) -> bytes:
        """
        Generate the PDF and return raw bytes.

        session_data keys:
            session_id, session_duration_seconds,
            voice_messages: [{text, isAgent, confidence, severity, is_depressed, timestamp}],
            facial_emotions: [{emotion, score, timestamp}],
            voice_average_confidence, facial_average_score, combined_score
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=20*mm, bottomMargin=20*mm,
            leftMargin=18*mm, rightMargin=18*mm,
            title="Serene Care — Clinical Depression Screening Report",
            author="Serene Care AI",
        )

        story = []
        story += self._build_header(session_data)
        story += self._build_summary_cards(session_data)
        story += self._build_voice_analysis(session_data)
        story += self._build_facial_analysis(session_data)
        story += self._build_combined_assessment(session_data)
        story += self._build_clinical_observations(session_data)
        story += self._build_conversation_log(session_data)
        story += self._build_disclaimer()

        doc.build(story, onFirstPage=self._page_border, onLaterPages=self._page_border)
        return buf.getvalue()

    # ── Page decorator ───────────────────────────────────────────────────
    @staticmethod
    def _page_border(canvas, doc):
        canvas.saveState()
        w, h = A4
        # subtle top accent line
        canvas.setStrokeColor(BRAND_ACCENT)
        canvas.setLineWidth(3)
        canvas.line(18*mm, h - 14*mm, w - 18*mm, h - 14*mm)
        # footer
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#aaaaaa"))
        canvas.drawCentredString(w / 2, 12*mm,
            f"Serene Care — Confidential Clinical Report  |  Generated {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
        canvas.drawRightString(w - 18*mm, 12*mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    # ── 1. Header ────────────────────────────────────────────────────────
    def _build_header(self, data: Dict) -> list:
        elements = []
        elements.append(Paragraph("Serene Care", self.styles["ReportTitle"]))
        elements.append(Paragraph(
            "Clinical Depression Screening Report",
            self.styles["ReportSubtitle"]
        ))
        ts = datetime.now().strftime("%d %B %Y  •  %I:%M %p")
        session_id = data.get("session_id", "N/A")
        elements.append(Paragraph(
            f"Session: <b>{session_id}</b>  |  Date: <b>{ts}</b>",
            self.styles["SmallGrey"]
        ))
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#dddddd")))
        elements.append(Spacer(1, 10))
        return elements

    # ── 2. Summary Cards ─────────────────────────────────────────────────
    def _build_summary_cards(self, data: Dict) -> list:
        duration_s = data.get("session_duration_seconds", 0)
        duration_min = max(duration_s / 60, 0.1)
        voice_msgs = [m for m in data.get("voice_messages", []) if not m.get("isAgent")]
        combined = data.get("combined_score", 0)
        severity = _severity_label(combined)
        sev_color = _severity_color(combined)

        card_data = [
            [
                self._metric_cell(f"{duration_min:.1f} min", "Session Duration"),
                self._metric_cell(str(len(voice_msgs)), "Messages Analyzed"),
                self._metric_cell(f"{combined * 100:.0f}%", "Combined Score"),
                self._metric_cell(severity, "Severity Level"),
            ]
        ]

        t = Table(card_data, colWidths=[doc_width / 4] * 4 if False else [125, 125, 125, 125])
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#eeeeee")),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fbff")),
        ]))
        return [t, Spacer(1, 16)]

    def _metric_cell(self, value: str, label: str):
        """Return a list of Paragraphs for a metric card cell."""
        return [
            Paragraph(value, self.styles["MetricValue"]),
            Paragraph(label, self.styles["MetricLabel"]),
        ]

    # ── 3. Voice Analysis ────────────────────────────────────────────────
    def _build_voice_analysis(self, data: Dict) -> list:
        elements = []
        elements.append(Paragraph("Voice Analysis — Confidence Timeline", self.styles["SectionHead"]))

        voice_msgs = data.get("voice_messages", [])
        user_msgs = [m for m in voice_msgs if not m.get("isAgent")]

        if not user_msgs:
            elements.append(Paragraph(
                "No voice data was captured during this session.",
                self.styles["BodyText2"]
            ))
            elements.append(Spacer(1, 12))
            return elements

        avg_conf = data.get("voice_average_confidence", 0)
        elements.append(Paragraph(
            f"Average voice depression confidence: <b>{avg_conf * 100:.1f}%</b>  •  "
            f"Messages analyzed: <b>{len(user_msgs)}</b>",
            self.styles["BodyText2"]
        ))
        elements.append(Spacer(1, 8))

        # Table of messages with confidence
        header = ["#", "User Message (excerpt)", "Confidence", "Severity", "Flagged"]
        rows = [header]
        for i, msg in enumerate(user_msgs[:30], 1):  # cap at 30 rows
            text = msg.get("text", "")
            if len(text) > 80:
                text = text[:77] + "..."
            conf = msg.get("confidence", 0)
            sev = msg.get("severity", "mild")
            flagged = "Yes" if msg.get("is_depressed") else "No"
            rows.append([str(i), text, f"{conf * 100:.0f}%", sev.capitalize(), flagged])

        t = Table(rows, colWidths=[28, 250, 65, 75, 52])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_MID),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        # Alternate row coloring
        for i in range(1, len(rows)):
            if i % 2 == 0:
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
            # Highlight high-confidence rows
            conf_val = user_msgs[i - 1].get("confidence", 0) if i - 1 < len(user_msgs) else 0
            if conf_val >= 0.7:
                style_cmds.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#D32F2F")))
                style_cmds.append(("FONTNAME", (2, i), (2, i), "Helvetica-Bold"))

        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
        elements.append(Spacer(1, 16))
        return elements

    # ── 4. Facial Analysis ───────────────────────────────────────────────
    def _build_facial_analysis(self, data: Dict) -> list:
        elements = []
        elements.append(Paragraph("Facial Emotion Analysis", self.styles["SectionHead"]))

        emotions = data.get("facial_emotions", [])
        if not emotions:
            elements.append(Paragraph(
                "No facial analysis data was captured during this session. "
                "The camera module was either not activated or no face was detected.",
                self.styles["BodyText2"]
            ))
            elements.append(Spacer(1, 12))
            return elements

        # Count emotions
        emotion_counts = {}
        for e in emotions:
            em = e.get("emotion", "neutral")
            emotion_counts[em] = emotion_counts.get(em, 0) + 1
        total = sum(emotion_counts.values())

        avg_score = data.get("facial_average_score", 0)
        dominant = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"

        elements.append(Paragraph(
            f"Total frames analyzed: <b>{total}</b>  •  "
            f"Dominant emotion: <b>{dominant.capitalize()}</b>  •  "
            f"Average depression score: <b>{avg_score * 100:.1f}%</b>",
            self.styles["BodyText2"]
        ))
        elements.append(Spacer(1, 8))

        # Emotion distribution table
        header = ["Emotion", "Count", "Percentage", "Depression Weight"]
        rows = [header]
        weight_map = {
            "happy": 0.1, "neutral": 0.5, "sad": 0.8,
            "angry": 0.9, "fear": 0.85, "disgust": 0.8, "surprise": 0.4
        }
        for em in ["happy", "sad", "angry", "fear", "disgust", "surprise", "neutral"]:
            count = emotion_counts.get(em, 0)
            pct = (count / total * 100) if total > 0 else 0
            weight = weight_map.get(em, 0.5)
            rows.append([em.capitalize(), str(count), f"{pct:.1f}%", f"{weight:.1f}"])

        t = Table(rows, colWidths=[100, 65, 85, 100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_MID),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t)

        # Depression-indicative percentage
        dep_emotions = sum(emotion_counts.get(e, 0) for e in ["sad", "angry", "fear", "disgust"])
        dep_pct = (dep_emotions / total * 100) if total > 0 else 0
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(
            f"Depression-indicative emotions (sad, angry, fear, disgust): "
            f"<b>{dep_pct:.1f}%</b> of total frames",
            self.styles["BodyText2"]
        ))
        elements.append(Spacer(1, 16))
        return elements

    # ── 5. Combined Assessment ───────────────────────────────────────────
    def _build_combined_assessment(self, data: Dict) -> list:
        elements = []
        elements.append(Paragraph("Combined Assessment", self.styles["SectionHead"]))

        voice_avg = data.get("voice_average_confidence", 0)
        facial_avg = data.get("facial_average_score", 0)
        combined = data.get("combined_score", 0)
        severity = _severity_label(combined)
        sev_color = _severity_color(combined)

        has_voice = len([m for m in data.get("voice_messages", []) if not m.get("isAgent")]) > 0
        has_facial = len(data.get("facial_emotions", [])) > 0

        formula_parts = []
        if has_voice and has_facial:
            formula_parts.append(
                f"Voice Confidence: <b>{voice_avg * 100:.1f}%</b> (weight: 0.7)  ×  "
                f"Facial Score: <b>{facial_avg * 100:.1f}%</b> (weight: 0.3)"
            )
        elif has_voice:
            formula_parts.append(
                f"Voice Confidence (sole modality): <b>{voice_avg * 100:.1f}%</b>"
            )
        elif has_facial:
            formula_parts.append(
                f"Facial Score (sole modality): <b>{facial_avg * 100:.1f}%</b>"
            )

        formula_parts.append(
            f"<br/><br/><b>Combined Depression Score: {combined * 100:.1f}%</b>"
        )
        formula_parts.append(
            f"<br/>Severity Classification: <b>{severity}</b>"
        )

        elements.append(Paragraph("<br/>".join(formula_parts), self.styles["BodyText2"]))
        elements.append(Spacer(1, 10))

        # Visual gauge bar
        d = Drawing(470, 40)
        # Background bar
        d.add(Rect(0, 15, 470, 18, fillColor=colors.HexColor("#eeeeee"),
                    strokeColor=colors.HexColor("#dddddd"), strokeWidth=0.5, rx=9, ry=9))
        # Filled portion
        fill_w = max(combined * 470, 8)
        d.add(Rect(0, 15, fill_w, 18, fillColor=sev_color,
                    strokeColor=None, strokeWidth=0, rx=9, ry=9))
        # Score text
        d.add(String(fill_w + 6, 19, f"{combined * 100:.0f}%",
                      fontSize=10, fontName="Helvetica-Bold",
                      fillColor=BRAND_DARK))
        # Scale labels
        for pct, label in [(0, "0%"), (25, "25%"), (50, "50%"), (75, "75%"), (100, "100%")]:
            d.add(String(pct / 100 * 470 - 8, 4, label, fontSize=6,
                          fillColor=colors.HexColor("#999999")))

        elements.append(d)
        elements.append(Spacer(1, 16))
        return elements

    # ── 6. Clinical Observations ─────────────────────────────────────────
    def _build_clinical_observations(self, data: Dict) -> list:
        elements = []
        elements.append(Paragraph("Clinical Observations", self.styles["SectionHead"]))

        combined = data.get("combined_score", 0)
        severity = _severity_label(combined)
        voice_msgs = [m for m in data.get("voice_messages", []) if not m.get("isAgent")]
        emotions = data.get("facial_emotions", [])

        observations = []

        # Severity-based observations
        if combined >= 0.8:
            observations.append(
                "The combined assessment indicates a <b>severe</b> likelihood of depressive symptoms. "
                "Immediate professional intervention is strongly recommended."
            )
        elif combined >= 0.6:
            observations.append(
                "The combined assessment suggests <b>moderately severe</b> depressive indicators. "
                "A clinical evaluation by a qualified mental health professional is recommended."
            )
        elif combined >= 0.4:
            observations.append(
                "The assessment indicates <b>moderate</b> depressive tendencies. "
                "Monitoring and a follow-up evaluation are advised."
            )
        elif combined >= 0.2:
            observations.append(
                "The assessment shows <b>mild</b> depressive indicators. "
                "Continued self-care and periodic check-ins are suggested."
            )
        else:
            observations.append(
                "The assessment indicates <b>minimal</b> depressive symptoms at this time."
            )

        # Voice-specific observations
        if voice_msgs:
            high_conf = [m for m in voice_msgs if m.get("confidence", 0) >= 0.7]
            if high_conf:
                observations.append(
                    f"<b>{len(high_conf)}</b> out of <b>{len(voice_msgs)}</b> analyzed voice segments "
                    f"showed high depression confidence (≥70%). This suggests recurring distress signals "
                    f"in the subject's verbal communication."
                )

            severe_msgs = [m for m in voice_msgs if m.get("severity") == "severe"]
            if severe_msgs:
                observations.append(
                    f"<b>{len(severe_msgs)}</b> message(s) were classified as <b>severe</b> by the NLP engine. "
                    f"Content analysis detected indicators of significant emotional distress."
                )

            prof_help = [m for m in voice_msgs if m.get("needs_professional_help")]
            if prof_help:
                observations.append(
                    "The AI flagged professional help as recommended based on the content of one or "
                    "more voice segments."
                )

        # Facial observations
        if emotions:
            emotion_counts = {}
            for e in emotions:
                em = e.get("emotion", "neutral")
                emotion_counts[em] = emotion_counts.get(em, 0) + 1
            total = sum(emotion_counts.values())
            sad_pct = emotion_counts.get("sad", 0) / total * 100 if total > 0 else 0
            if sad_pct > 30:
                observations.append(
                    f"Facial analysis detected <b>sadness</b> in {sad_pct:.0f}% of frames, "
                    f"indicating persistent negative affect during the session."
                )
            happy_pct = emotion_counts.get("happy", 0) / total * 100 if total > 0 else 0
            if happy_pct > 50:
                observations.append(
                    f"Facial analysis detected <b>happiness</b> in {happy_pct:.0f}% of frames, "
                    f"which may indicate positive emotional states or masking behavior."
                )

        if not observations:
            observations.append("Insufficient data to generate clinical observations.")

        for obs in observations:
            elements.append(Paragraph(f"• {obs}", self.styles["BodyText2"]))
            elements.append(Spacer(1, 4))

        # Professional recommendation box
        elements.append(Spacer(1, 8))
        rec_text = (
            "<b>Recommendation:</b> "
            + ("This report should be reviewed by a qualified mental health professional. "
               "The subject is advised to schedule a clinical consultation at the earliest convenience."
               if combined >= 0.4 else
               "No immediate clinical action is required based on this screening. "
               "Periodic monitoring is recommended.")
        )
        rec_table = Table([[Paragraph(rec_text, self.styles["BodyText2"])]], colWidths=[460])
        rec_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f7ff")),
            ("BOX", (0, 0), (-1, -1), 1, BRAND_MID),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
        elements.append(rec_table)
        elements.append(Spacer(1, 16))
        return elements

    # ── 7. Conversation Log ──────────────────────────────────────────────
    def _build_conversation_log(self, data: Dict) -> list:
        elements = []
        voice_msgs = data.get("voice_messages", [])
        if not voice_msgs:
            return elements

        elements.append(PageBreak())
        elements.append(Paragraph("Full Conversation Log", self.styles["SectionHead"]))
        elements.append(Paragraph(
            "The following is a verbatim transcript of the voice session between the "
            "subject and the Serene AI assistant.",
            self.styles["BodyText2"]
        ))
        elements.append(Spacer(1, 8))

        for i, msg in enumerate(voice_msgs):
            speaker = "Serene AI" if msg.get("isAgent") else "Subject"
            text = msg.get("text", "")
            conf = msg.get("confidence")

            line = f"<b>{speaker}:</b> {text}"
            if conf is not None and not msg.get("isAgent"):
                line += f"  <i>[confidence: {conf * 100:.0f}%]</i>"

            elements.append(Paragraph(line, self.styles["BodyText2"]))
            elements.append(Spacer(1, 3))

        elements.append(Spacer(1, 16))
        return elements

    # ── 8. Disclaimer ────────────────────────────────────────────────────
    def _build_disclaimer(self, ) -> list:
        elements = []
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#dddddd")))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("DISCLAIMER", ParagraphStyle(
            "DisclaimerTitle", parent=self.styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#888888"), spaceAfter=4,
        )))
        disclaimer = (
            "This report is generated by the Serene Care AI Depression Screening System and is "
            "intended solely as a preliminary screening tool. It does NOT constitute a clinical diagnosis. "
            "The results are based on automated natural language processing (NLP) and facial emotion "
            "recognition algorithms, which may be subject to errors, biases, or limitations inherent "
            "in AI-based analysis. This report should be reviewed and interpreted by a licensed mental "
            "health professional or medical doctor. The developers of Serene Care assume no liability "
            "for clinical decisions made based on this report. If you or someone you know is in immediate "
            "danger, please contact emergency services or a crisis helpline immediately."
        )
        elements.append(Paragraph(disclaimer, self.styles["DisclaimerText"]))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            "© Serene Care AI  •  Confidential  •  Do Not Distribute Without Authorization",
            self.styles["SmallGrey"]
        ))
        return elements
