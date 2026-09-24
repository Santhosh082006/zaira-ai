"""
services/report_generator.py
Generates a PDF Evidence & Consistency Report.
"""
from fpdf import FPDF
from datetime import datetime
from typing import Any, Optional

class ReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, "TruthLens AI - Evidence & Consistency Report", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C", new_x="LMARGIN", new_y="NEXT")

def _safe_str(val: Any) -> str:
    """Safe conversion to string, transliterating common Unicode characters for FPDF."""
    if val is None:
        return ""
    s = str(val)
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2014": " - ", "\u2013": "-",
        "\u2026": "...", "\u2192": "->",
        "\u2022": "*", "\u00a0": " ",
        "\u2713": "[v]", "\u2705": "[v]",
        "\u274c": "[x]", "\u26a0": "[!]",
    }
    for orig, rep in replacements.items():
        s = s.replace(orig, rep)
    # FPDF built-in fonts support latin-1; replace any remaining unmappable characters
    return s.encode("latin-1", "replace").decode("latin-1")

def generate_evidence_report(
    comparison_result: dict,
    story_a: Optional[dict] = None,
    story_b: Optional[dict] = None,
    speech_a: Optional[dict] = None,
    speech_b: Optional[dict] = None,
    visual_a: Optional[dict] = None,
    visual_b: Optional[dict] = None
) -> bytes:
    """
    Generate a deterministic, highly structured PDF report from application state.
    Returns the PDF file contents as bytes.
    """
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def title(text):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 51, 102) # Dark blue
        pdf.cell(0, 10, _safe_str(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
    def section(text):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, _safe_str(text), new_x="LMARGIN", new_y="NEXT")
        
    def body(text, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, _safe_str(text), new_x="LMARGIN", new_y="NEXT")

    def bullet(text):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, _safe_str(f"  * {text}"), new_x="LMARGIN", new_y="NEXT")
        
    # 1. Analysis Overview
    title("1. Analysis Overview")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    body(f"Report Generated: {date_str}")
    
    person_a_label = story_a.get("person", "Person A") if story_a else "Person A"
    person_b_label = story_b.get("person", "Person B") if story_b else "Person B"
    
    if not comparison_result or not isinstance(comparison_result, dict):
        comparison_result = {}

    overall = comparison_result.get("overall_status", "UNKNOWN").upper()
    body(f"Overall Status: {overall}", bold=True)
    pdf.ln(5)

    # 2. Overall Statistics
    title("2. Overall Statistics")
    events_count = len(comparison_result.get("timeline_comparison", []))
    claims_count = len(comparison_result.get("claim_comparison", []))
    
    all_comps = comparison_result.get("timeline_comparison", []) + comparison_result.get("claim_comparison", [])
    matches = sum(1 for c in all_comps if c.get("status") == "MATCH")
    partial = sum(1 for c in all_comps if c.get("status") == "PARTIAL_MATCH")
    conflicts = sum(1 for c in all_comps if c.get("status") == "CONFLICT")
    miss_a = sum(1 for c in all_comps if c.get("status") == "MISSING_A")
    miss_b = sum(1 for c in all_comps if c.get("status") == "MISSING_B")
    unknown = sum(1 for c in all_comps if c.get("status") == "UNKNOWN")
    
    body(f"Events Analyzed: {events_count}")
    body(f"Claims Analyzed: {claims_count}")
    body(f"Matches: {matches} | Partial: {partial} | Conflicts: {conflicts}")
    body(f"Missing {person_a_label}: {miss_a} | Missing {person_b_label}: {miss_b} | Unknown: {unknown}")
    pdf.ln(5)

    # 3. Timeline Comparison
    title("3. Timeline Comparison")
    timeline = comparison_result.get("timeline_comparison", [])
    if not timeline:
        body("No timeline events to compare.")
    else:
        for i, ev in enumerate(timeline):
            section(f"Event {i+1} [{ev.get('status', 'UNKNOWN')}]")
            body(f"Reason: {ev.get('reason', 'N/A')}")
            for ep in ev.get("evidence_points", []):
                bullet(ep)
            
            ea = ev.get("event_a")
            eb = ev.get("event_b")
            
            pdf.ln(2)
            if ea and ea.get("source_text"):
                body(f"{person_a_label} Source:")
                body(f'"{ea.get("source_text")}"')
            if eb and eb.get("source_text"):
                body(f"{person_b_label} Source:")
                body(f'"{eb.get("source_text")}"')
            pdf.ln(4)

    # 4. Claim-Level Comparison
    title("4. Claim-Level Comparison")
    claims = comparison_result.get("claim_comparison", [])
    if not claims:
        body("No claims to compare.")
    else:
        for i, c in enumerate(claims):
            section(f"Claim {i+1} [{c.get('status', 'UNKNOWN')}]")
            body(f"Subject: {c.get('subject', 'N/A')} | Attribute: {c.get('attribute', 'N/A')}")
            body(f"Reason: {c.get('reason', 'N/A')}")
            for ep in c.get("evidence_points", []):
                bullet(ep)
            
            pa = c.get("person_a")
            pb = c.get("person_b")
            
            pdf.ln(2)
            if pa and pa.get("source_text"):
                body(f"{person_a_label} Source:")
                body(f'"{pa.get("source_text")}"')
            if pb and pb.get("source_text"):
                body(f"{person_b_label} Source:")
                body(f'"{pb.get("source_text")}"')
            pdf.ln(4)

    # 5. Agreements
    title("5. Agreements")
    matches_list = comparison_result.get("matches", [])
    if not matches_list:
        body("No explicit agreements found.")
    for m in matches_list:
        bullet(f"[{m.get('category', '').upper()}] {m.get('description', '')}")
    pdf.ln(5)

    # 6. Conflicts
    title("6. Conflicts")
    discrepancies = comparison_result.get("discrepancies", [])
    if not discrepancies:
        body("No explicit conflicts found.")
    for d in discrepancies:
        bullet(f"[{d.get('category', '').upper()}] {d.get('description', '')}")
        bullet(f"{person_a_label}: {d.get('person_a_value', 'N/A')} | {person_b_label}: {d.get('person_b_value', 'N/A')}")
    pdf.ln(5)

    # 7. Missing Information
    title("7. Missing Information")
    missing = comparison_result.get("missing_information", [])
    if not missing:
        body("No missing information explicitly flagged.")
    for m in missing:
        bullet(f"[{m.get('category', '').upper()}] {m.get('description', '')}")
    pdf.ln(5)

    # 8. Unclear Information
    title("8. Unclear / Unknown Information")
    unclear = comparison_result.get("unclear_information", [])
    if not unclear:
        body("No unclear information explicitly flagged.")
    for u in unclear:
        bullet(f"[{u.get('category', '').upper()}] {u.get('description', '')}")
    pdf.ln(5)
    
    # 9. Speech Signals
    title("9. Speech Signals")
    if not speech_a and not speech_b:
        body("No data available.")
    else:
        if speech_a:
            section(f"{person_a_label} Speech")
            body(f"Duration: {speech_a.get('duration_seconds', 'N/A')}s | WPM: {speech_a.get('speaking_rate_wpm', 'N/A')}")
            body(f"Reliability: {speech_a.get('reliability_flag', 'N/A')}")
            pdf.ln(2)
        if speech_b:
            section(f"{person_b_label} Speech")
            body(f"Duration: {speech_b.get('duration_seconds', 'N/A')}s | WPM: {speech_b.get('speaking_rate_wpm', 'N/A')}")
            body(f"Reliability: {speech_b.get('reliability_flag', 'N/A')}")
            pdf.ln(2)
    pdf.ln(3)
    
    # 10. Visual Signals
    title("10. Visual Signals")
    if not visual_a and not visual_b:
        body("No data available.")
    else:
        if visual_a:
            section(f"{person_a_label} Visuals")
            body(f"Face Present: {visual_a.get('face_detected', 'N/A')} | Blinks: {visual_a.get('blink_count', 'N/A')}")
            pdf.ln(2)
        if visual_b:
            section(f"{person_b_label} Visuals")
            body(f"Face Present: {visual_b.get('face_detected', 'N/A')} | Blinks: {visual_b.get('blink_count', 'N/A')}")
            pdf.ln(2)
    pdf.ln(3)

    # 11. Important Limitations
    title("11. Important Limitations")
    body("This tool compares information between accounts for consistency. It does not determine truthfulness or deception. Speech and visual signals are supporting observations only and should not be used as proof of lying.")
    
    return bytes(pdf.output())


def generate_performance_report(
    person_label: str = "Performer",
    story: Optional[dict] = None,
    speech: Optional[dict] = None,
    visual: Optional[dict] = None,
    eval_data: Optional[dict] = None,
    coverage_score: int = 0,
    coverage_breakdown: Optional[list] = None
) -> bytes:
    """
    Generate a detailed PDF report for an individual live performance session.
    """
    pdf = ReportPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def title(text):
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, _safe_str(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        
    def section(text):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, _safe_str(text), new_x="LMARGIN", new_y="NEXT")
        
    def body(text, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, _safe_str(text), new_x="LMARGIN", new_y="NEXT")

    def bullet(text):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, _safe_str(f"  * {text}"), new_x="LMARGIN", new_y="NEXT")

    # 1. Overview
    title("1. Performance Session Overview")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    body(f"Report Generated: {date_str}")
    body(f"Session Performer: {person_label}")
    body(f"Analysis Coverage Score: {coverage_score}/100", bold=True)
    if coverage_breakdown:
        for b in coverage_breakdown:
            bullet(b.replace("&nbsp;", " ").replace("<br>", " "))
    pdf.ln(4)

    # 2. Speech Observations
    title("2. Observable Speech Signals")
    if speech:
        body(f"Duration: {speech.get('duration_seconds', 'N/A')}s | Words: {speech.get('word_count', 'N/A')} | Rate: {speech.get('speaking_rate_wpm', 'N/A')} WPM")
        body(f"Pauses: {speech.get('pause_count', 'N/A')} | Pause Time: {speech.get('total_pause_duration_sec', 'N/A')}s | Filler Words: {speech.get('filler_word_count', 'N/A')}")
        body(f"Pitch (F0): {speech.get('pitch_mean_hz', 'N/A')} Hz (var: {speech.get('pitch_variation_hz', 'N/A')} Hz) | Energy: {speech.get('energy_mean_db', 'N/A')} dB")
    else:
        body("Speech signals not available or audio extraction pending.")
    pdf.ln(4)

    # 3. Visual Observations
    title("3. Observable Visual Signals")
    if visual:
        body(f"Face Detected: {'Yes' if visual.get('face_detected') else 'No'} | Presence Ratio: {visual.get('face_presence_ratio', 'N/A')}")
        body(f"Head Movements: {visual.get('head_movement_count', 'N/A')} | Blinks: {visual.get('blink_count', 'N/A')} | Tracking Reliability: {visual.get('tracking_reliability', 'N/A')}")
    else:
        body("Visual signals not available or tracking failed.")
    pdf.ln(4)

    # 4. Performance Assessment Dimensions
    if eval_data:
        title("4. Performance & Communication Assessment")
        dims = [
            ("confidence_indicators", "Confidence Indicators"),
            ("body_language", "Body Language & Posture"),
            ("speaking_style", "Speaking Style & Fluency"),
            ("engagement", "Engagement & Delivery"),
            ("story_quality", "Story Quality & Structure")
        ]
        for k, name in dims:
            item = eval_data.get(k)
            if isinstance(item, dict):
                score = item.get("score", "N/A")
                section(f"{name} (Score: {score})")
                if item.get("assessment"):
                    body(f"Assessment: {item.get('assessment')}")
                if item.get("evidence_observation"):
                    body(f"Evidence/Observation: {item.get('evidence_observation')}")
                if item.get("what_went_well"):
                    bullet(f"Strength: {item.get('what_went_well')}")
                if item.get("what_needs_improvement"):
                    bullet(f"Improvement Area: {item.get('what_needs_improvement')}")
                if item.get("practical_recommendation"):
                    bullet(f"Recommendation: {item.get('practical_recommendation')}")
                pdf.ln(2)

    # 5. Story Content & Transcript
    if story:
        title("5. Story Content & Facts")
        if story.get("summary"):
            body(f"Summary: {story.get('summary')}")
        events = story.get("events", [])
        if events:
            section("Timeline Events:")
            for e in events:
                bullet(f"{e.get('time', 'Unknown')} - {e.get('location', 'Unknown')}: {e.get('description', '')}")
    pdf.ln(4)

    # 6. Limitations
    title("6. Limitations & Disclaimer")
    body("This analysis is based on automated speech, visual, and language feature extraction. It reflects observable communication dynamics and should not be construed as a psychological evaluation or determination of truthfulness.")

    return bytes(pdf.output())

