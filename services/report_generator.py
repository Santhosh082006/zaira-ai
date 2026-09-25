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

def _format_metric(val: Any, unit: str = "", fmt: str = "") -> str:
    """
    Format a metric value safely. If None, empty string, or 'N/A', returns 'N/A'.
    Guarantees no null propagation into unit strings (prevents 'Nones', 'None WPM', 'None Hz').
    """
    if val is None or val == "" or val == "N/A":
        return "N/A"
    try:
        if fmt and isinstance(val, (int, float)):
            formatted = f"{val:{fmt}}"
        else:
            formatted = str(val)
        return f"{formatted}{unit}" if unit else formatted
    except Exception:
        return f"{val}{unit}" if unit else str(val)

def generate_evidence_report(
    comparison_result: dict,
    story_a: Optional[dict] = None,
    story_b: Optional[dict] = None,
    speech_a: Optional[dict] = None,
    speech_b: Optional[dict] = None,
    visual_a: Optional[dict] = None,
    visual_b: Optional[dict] = None,
    multimodal_comparison: Optional[dict] = None
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
    body(f"Overall Information Status: {overall}", bold=True)
    pdf.ln(3)

    # Multimodal Comparative Performance (if available)
    if multimodal_comparison:
        title("Comparative Performance Assessment")
        if multimodal_comparison.get("outcome_badge"):
            body(multimodal_comparison["outcome_badge"], bold=True)
        if multimodal_comparison.get("explanation"):
            body(multimodal_comparison["explanation"])
        pdf.ln(3)
        if multimodal_comparison.get("metric_deltas"):
            section("Measured Communication Deltas")
            for delta in multimodal_comparison["metric_deltas"]:
                bullet(f"{delta.get('metric')}: {person_a_label}={delta.get('val_a')} | {person_b_label}={delta.get('val_b')} (Delta: {delta.get('delta')})")
            pdf.ln(3)
        if multimodal_comparison.get("category_comparisons"):
            section("Performance Category Breakdown")
            for c in multimodal_comparison["category_comparisons"]:
                bullet(f"{c.get('category')}: {person_a_label}={c.get('score_a')} | {person_b_label}={c.get('score_b')} (Delta: {c.get('delta')}) - {c.get('status')}")
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
            dur_a = _format_metric(speech_a.get('duration_seconds'), 's', '.1f')
            wpm_a = _format_metric(speech_a.get('speaking_rate_wpm'), ' WPM', '.0f')
            body(f"Duration: {dur_a} | WPM: {wpm_a}")
            body(f"Reliability: {_format_metric(speech_a.get('reliability_flag'))}")
            pdf.ln(2)
        if speech_b:
            section(f"{person_b_label} Speech")
            dur_b = _format_metric(speech_b.get('duration_seconds'), 's', '.1f')
            wpm_b = _format_metric(speech_b.get('speaking_rate_wpm'), ' WPM', '.0f')
            body(f"Duration: {dur_b} | WPM: {wpm_b}")
            body(f"Reliability: {_format_metric(speech_b.get('reliability_flag'))}")
            pdf.ln(2)
    pdf.ln(3)
    
    # 10. Visual Signals
    title("10. Visual Signals")
    if not visual_a and not visual_b:
        body("No data available.")
    else:
        if visual_a:
            section(f"{person_a_label} Visuals")
            face_a = "Yes" if visual_a.get('face_detected') is True else ("No" if visual_a.get('face_detected') is False else "N/A")
            body(f"Face Present: {face_a} | Blinks: {_format_metric(visual_a.get('blink_count'))}")
            pdf.ln(2)
        if visual_b:
            section(f"{person_b_label} Visuals")
            face_b = "Yes" if visual_b.get('face_detected') is True else ("No" if visual_b.get('face_detected') is False else "N/A")
            body(f"Face Present: {face_b} | Blinks: {_format_metric(visual_b.get('blink_count'))}")
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
    has_speech_data = speech and any(speech.get(k) is not None for k in ("duration_seconds", "speaking_rate_wpm", "pitch_mean_hz", "energy_mean_db"))
    if speech and has_speech_data:
        dur = _format_metric(speech.get('duration_seconds'), 's', '.1f')
        words = _format_metric(speech.get('word_count'))
        rate = _format_metric(speech.get('speaking_rate_wpm'), ' WPM', '.0f')
        body(f"Duration: {dur} | Words: {words} | Rate: {rate}")
        
        pauses = _format_metric(speech.get('pause_count'))
        pause_time = _format_metric(speech.get('total_pause_duration_sec'), 's', '.1f')
        fillers = _format_metric(speech.get('filler_word_count'))
        body(f"Pauses: {pauses} | Pause Time: {pause_time} | Filler Words: {fillers}")
        
        pitch_m = _format_metric(speech.get('pitch_mean_hz'), ' Hz', '.1f')
        pitch_v = _format_metric(speech.get('pitch_variation_hz'), ' Hz', '.1f')
        energy = _format_metric(speech.get('energy_mean_db'), ' dB', '.1f')
        pitch_text = f"{pitch_m} (var: {pitch_v})" if pitch_m != "N/A" else "N/A"
        body(f"Pitch (F0): {pitch_text} | Energy: {energy}")
    else:
        body("Speech signals not available or acoustic extraction unmeasured.")
    pdf.ln(4)

    # 3. Visual Observations
    title("3. Observable Visual Signals")
    has_visual_data = visual and (visual.get("face_detected") or visual.get("head_movement_count") is not None)
    if visual and has_visual_data:
        face_det = "Yes" if visual.get('face_detected') is True else ("No" if visual.get('face_detected') is False else "N/A")
        presence = _format_metric(visual.get('face_presence_ratio'), fmt='.0%') if visual.get('face_presence_ratio') is not None else "N/A"
        body(f"Face Detected: {face_det} | Presence Ratio: {presence}")
        
        hm_count = visual.get('head_movement_count')
        hm_rate = visual.get('head_movement_rate_per_min')
        if hm_rate is None and hm_count is not None:
            dur = visual.get('duration_seconds') or (speech.get('duration_seconds') if speech else None)
            if dur and dur >= 3.0:
                hm_rate = round((hm_count / dur) * 60.0, 1)
        
        if hm_count is not None and hm_rate is not None:
            hm_text = f"{hm_count} ({hm_rate:.1f}/min, typical range: 15-35/min)"
        elif hm_count is not None:
            hm_text = f"{hm_count} (duration unmeasured)"
        else:
            hm_text = "N/A"
            
        blinks = _format_metric(visual.get('blink_count'))
        reliability = _format_metric(visual.get('tracking_reliability'))
        body(f"Head Movements: {hm_text} | Blinks: {blinks} | Tracking Reliability: {reliability}")
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
                score = item.get("score", "Insufficient Data")
                score_str = f"{score}/100" if isinstance(score, int) else str(score)
                section(f"{name} (Score: {score_str})")
                if item.get("assessment"):
                    body(f"Assessment: {item.get('assessment')}")
                if item.get("evidence_observation"):
                    body(f"Evidence/Observation: {item.get('evidence_observation')}")
                www = item.get("what_went_well")
                if www and str(www).strip().upper() != "N/A":
                    bullet(f"Strength: {www}")
                wni = item.get("what_needs_improvement")
                if wni and str(wni).strip().upper() != "N/A":
                    bullet(f"Improvement Area: {wni}")
                rec = item.get("practical_recommendation")
                if rec and str(rec).strip().upper() != "N/A":
                    bullet(f"Recommendation: {rec}")
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
                time_val = e.get('time') or e.get('time_or_relative_time') or e.get('time_normalized') or 'Time unstated'
                loc_val = e.get('location') or 'Location unstated'
                desc_val = e.get('description') or ''
                bullet(f"{time_val} - {loc_val}: {desc_val}")
    pdf.ln(4)

    # 6. Limitations
    title("6. Limitations & Disclaimer")
    body("This analysis is based on automated speech, visual, and language feature extraction. It reflects observable communication dynamics and should not be construed as a psychological evaluation or determination of truthfulness.")

    return bytes(pdf.output())

