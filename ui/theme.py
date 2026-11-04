"""
TruthLens V3 Theme - Cinematic OLED Emerald Edition
"""

def get_core_css() -> str:
    return """
    <style>
    /* OLED Black Background & Font Base */
    html, body, [class*="css"] {
        background-color: #000000 !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #e0e0e0;
    }

    /* Streamlit overrides */
    .stApp {
        background: radial-gradient(circle at 50% -20%, rgba(16, 185, 129, 0.08) 0%, #000000 60%) !important;
        background-color: #000000 !important;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    footer { display: none !important; }
    
    .block-container {
        max-width: 1200px !important;
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
    }

    /* Cinematic Sidebar */
    [data-testid="stSidebar"] {
        background-color: #020805 !important;
        border-right: 1px solid rgba(16, 185, 129, 0.1) !important;
        box-shadow: inset -10px 0 30px rgba(0,0,0,0.8);
    }

    /* RADIO BUTTONS (acting as navigation/selection) */
    .stRadio div[role="radiogroup"] > label {
        display: none !important;
    }
    
    .stRadio div[role="radiogroup"] div[role="radio"] {
        border-radius: 8px;
        padding: 8px 14px;
        margin-bottom: 4px;
        color: #71717a;
        transition: all 0.2s ease;
    }
    
    .stRadio div[role="radiogroup"] div[role="radio"]:hover {
        background: rgba(16, 185, 129, 0.05);
        color: #ffffff;
    }

    .stRadio div[role="radiogroup"] div[role="radio"][aria-checked="true"] {
        background: rgba(16, 185, 129, 0.1) !important;
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
        color: #ffffff !important;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.05);
    }

    .stRadio div[role="radiogroup"] div[role="radio"][aria-checked="true"] > div:first-child {
        background-color: #10b981 !important; /* Emerald active dot */
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(180deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.1) 100%) !important;
        border: 1px solid rgba(16, 185, 129, 0.4) !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        letter-spacing: 0.01em !important;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.08) !important;
    }

    .stButton > button:hover {
        background: linear-gradient(180deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.2) 100%) !important;
        border-color: rgba(16, 185, 129, 0.6) !important;
        box-shadow: 0 0 25px rgba(16, 185, 129, 0.15) !important;
        transform: translateY(-1px) !important;
    }

    .stButton > button:active {
        transform: translateY(1px) !important;
    }

    /* File Uploader Hiders */
    [data-testid="stFileUploader"] > label {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] > div:first-child {
        display: none !important;
    }
    [data-testid="stFileUploaderDropzone"] button > span:first-child {
        display: none !important;
    }

    /* Dropzone Styling */
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(16, 185, 129, 0.02) !important;
        border: 1px dashed rgba(16, 185, 129, 0.2) !important;
        border-radius: 12px !important;
        padding: 3rem !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stFileUploaderDropzone"]:hover {
        background: rgba(16, 185, 129, 0.04) !important;
        border-color: rgba(16, 185, 129, 0.4) !important;
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.05) !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
    }
    
    [data-testid="stExpanderDetails"] {
        background: rgba(0,0,0,0.5) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        border-top: none !important;
        border-bottom-left-radius: 8px !important;
        border-bottom-right-radius: 8px !important;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        color: #ffffff !important;
        font-weight: 400 !important;
        font-size: 2.2rem !important;
        text-shadow: 0 0 20px rgba(255,255,255,0.1) !important;
    }
    [data-testid="stMetricLabel"] {
        color: #888888 !important;
        font-weight: 500 !important;
        letter-spacing: 0.03em !important;
    }

    /* Scrollbars */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
    </style>
    """

def apply_theme():
    import streamlit as st
    st.markdown(get_core_css(), unsafe_allow_html=True)

def top_navigation_bar_html(active_feature: str, context_name: str) -> str:
    return f"""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; background: linear-gradient(90deg, rgba(255,255,255,0.03) 0%, transparent 100%); border-left: 2px solid #10b981; border-radius: 4px; margin-bottom: 2rem;">
        <div style="font-weight: 600; color: #ffffff; letter-spacing: -0.01em;">TruthLens <span style="color: #10b981; margin-left:4px; font-weight:400;">{active_feature}</span></div>
        <div style="font-size: 0.75rem; color: #71717a; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
            <div style="width:4px;height:4px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;"></div>
            {context_name}
        </div>
    </div>
    """

def editorial_page_header_html(pretitle: str, title: str, subtitle: str) -> str:
    return f"""
    <div style="margin-bottom: 2.5rem; margin-top: 1rem;">
        <div style="font-size: 0.7rem; font-weight: 600; color: #10b981; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; text-shadow: 0 0 10px rgba(16,185,129,0.3);">{pretitle}</div>
        <h1 style="font-size: 3.5rem; font-weight: 300; color: #ffffff; margin: 0 0 0.5rem 0; letter-spacing: -0.03em; line-height: 1.1;">{title}</h1>
        <div style="font-size: 1.1rem; color: #888888; font-weight: 300; max-width: 600px;">{subtitle}</div>
    </div>
    """

def cinematic_hud_stage_overlay(channel_name: str) -> str:
    return f"""
    <div style="position: absolute; top: 16px; left: 16px; background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(12px); padding: 4px 12px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; color: #ffffff; z-index: 10; border: 1px solid rgba(255, 255, 255, 0.05); letter-spacing: 0.05em; text-transform: uppercase;">
        {channel_name}
    </div>
    """

def studio_guidelines_strip_html() -> str:
    return """
    <div style="display: flex; flex-direction: column; gap: 0.75rem; color: #a1a1aa; font-size: 0.875rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 1.25rem;">
        <div style="color: #ffffff; font-weight: 500; margin-bottom: 4px;">Studio Guidelines</div>
        <div style="display:flex;gap:8px;"><span style="color:#10b981;">01</span> Ensure proper lighting</div>
        <div style="display:flex;gap:8px;"><span style="color:#10b981;">02</span> Frame yourself waist-up</div>
        <div style="display:flex;gap:8px;"><span style="color:#10b981;">03</span> Maintain eye contact</div>
    </div>
    """

def hero_score_radial_gauge_html(score: int, assessment_text: str) -> str:
    # Safely replace SVG bug by just returning empty string if this is accidentally called,
    # as the UX engineer replaced it with st.metric. But we keep the signature valid.
    return ""

def category_card_luxury_html(glyph: str, title: str, score: int, assessment: str, www: str, wni: str, rec: str, evidence: str) -> str:
    # Not heavily used in the new UI structure since UX engineer changed to st.metric and lists, 
    # but we will style it as a luxury glass card just in case it's still used somewhere.
    return f"""
    <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; transition: all 0.3s ease;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1rem;">
            <div style="font-size: 1rem; font-weight: 500; color: #ffffff;">{glyph} {title}</div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 300; color: #10b981;">{score}</div>
        </div>
        <div style="font-size: 0.85rem; color: #a1a1aa; line-height: 1.5;">{assessment}</div>
    </div>
    """

def comparison_verdict_hero_html(outcome: str, explanation: str) -> str:
    return f"""
    <div style="background: radial-gradient(circle at 50% 0%, rgba(16, 185, 129, 0.05) 0%, transparent 70%); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 12px; padding: 2.5rem; text-align: center; margin: 2rem 0; box-shadow: 0 10px 40px rgba(0,0,0,0.5);">
        <div style="font-size: 0.75rem; font-weight: 600; color: #10b981; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1rem;">Comparison Verdict</div>
        <div style="font-size: 1.75rem; font-weight: 300; color: #ffffff; margin-bottom: 1rem; letter-spacing: -0.01em;">{outcome}</div>
        <div style="font-size: 0.95rem; color: #a1a1aa; line-height: 1.6; max-width: 600px; margin: 0 auto;">{explanation}</div>
    </div>
    """

def comparison_vs_nexus_html() -> str:
    return """
    <div style="display: flex; align-items: center; justify-content: center; margin: 2rem 0; width: 100%;">
        <div style="height: 1px; flex-grow: 1; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1));"></div>
        <div style="margin: 0 1rem; font-size: 0.7rem; font-weight: 600; color: #555555; text-transform: uppercase; letter-spacing: 0.1em;">VS</div>
        <div style="height: 1px; flex-grow: 1; background: linear-gradient(90deg, rgba(255,255,255,0.1), transparent);"></div>
    </div>
    """

def recording_live_pulse_html() -> str:
    return """
    <div style="display: flex; align-items: center; gap: 8px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 4px; padding: 4px 10px; display: inline-flex;">
        <div style="width: 6px; height: 6px; background: #ef4444; border-radius: 50%; box-shadow: 0 0 8px #ef4444; animation: pulse 1.5s infinite;"></div>
        <div style="font-size: 0.7rem; font-weight: 600; color: #ef4444; letter-spacing: 0.05em; text-transform: uppercase;">REC</div>
    </div>
    <style>@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }</style>
    """

def section_divider_glow_html() -> str:
    return """
    <div style="width: 100%; height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%); margin: 3rem 0;"></div>
    """

def section_label_chip_html(label: str) -> str:
    return f"""
    <div style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: #a1a1aa; margin-bottom: 1rem; border-left: 2px solid #10b981; padding-left: 8px;">
        {label}
    </div>
    """

# Backward compatibility bindings
hero_score_html = hero_score_radial_gauge_html
category_score_html = category_card_luxury_html
coverage_bar_html = lambda *args, **kwargs: ""
page_header_html = lambda title, subtitle="": editorial_page_header_html("", title, subtitle)
recording_indicator_html = recording_live_pulse_html
winner_badge_html = lambda *args, **kwargs: ""
recommendation_html = lambda *args, **kwargs: ""
evidence_badge_html = lambda *args, **kwargs: ""
section_label_html = section_label_chip_html
separator_html = section_divider_glow_html
FONT_IMPORT = ""
PREMIUM_CSS = get_core_css()

