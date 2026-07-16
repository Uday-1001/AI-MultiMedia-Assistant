import streamlit as st
import requests

st.set_page_config(
    page_title="AI Multimedia Assistant",
    page_icon="🤓",
    layout="wide"
)

import ui_enhancer
backend_online = ui_enhancer.apply_custom_theme()

API_BASE_URL = "http://localhost:8000"

def fetch_statistics():
    """
    Fetches the total number of uploaded documents from the backend API.
    Used to display current session statistics in the sidebar.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/history/documents", timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def main():
    """
    Renders the main Home page of the AI Multimedia Knowledge Assistant.
    Displays the hero section, feature cards, and 'How it works' instructions.
    """
    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size: 0.75rem; color: var(--text-muted); "
            "letter-spacing: 1px; margin-bottom: 0.5rem; font-weight: 600;'>"
            "CURRENT SESSION</div>",
            unsafe_allow_html=True,
        )

        docs = fetch_statistics()
        doc_count = len(docs)
        session_id = st.session_state.get("session_id", None)
        display_id = "Not started" if not session_id else f"sess_{session_id}"

        st.markdown(
            f"""
            <div class="sidebar-stats-box">
                <div class="stats-row">
                    <span class="stats-label">Session ID</span>
                    <span class="stats-value">{display_id[:12]}...</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Documents</span>
                    <span class="stats-value">{doc_count}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Messages</span>
                    <span class="stats-value">{len(st.session_state.get('messages', []))}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Started</span>
                    <span class="stats-value">Just now</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Small spacer to separate stats from profile
        st.markdown(
            "<div style='min-height:40px;'></div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="background-color:var(--surface-color); border:1px solid var(--border-color);
                        border-radius:8px; padding:0.75rem; display:flex; align-items:center;
                        margin-top:1rem;">
                <div style="width:32px; height:32px; background-color:#3B82F6; border-radius:50%;
                            display:flex; align-items:center; justify-content:center;
                            color:white; font-weight:bold; margin-right:0.75rem; flex-shrink:0;">U</div>
                <div style="display:flex; flex-direction:column;">
                    <span style="color:var(--text-main); font-weight:600; font-size:0.9rem;">Guest User</span>
                    <span style="color:var(--text-muted); font-size:0.75rem;">Guest</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Main Content ─────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)

    # Hero section
    st.markdown(
        """
        <style>
        .hero-title-new {
            font-size: 3.8rem;
            font-weight: 800;
            text-align: center;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #4ADE80, #3B82F6, #C084FC);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.2;
        }
        .hero-subtitle-new {
            font-size: 1.25rem;
            color: var(--text-muted);
            text-align: center;
            max-width: 750px;
            margin: 0 auto 2.5rem auto;
            line-height: 1.6;
        }
        .hero-icon-container {
            display: flex;
            justify-content: center;
            margin-bottom: 2rem;
            animation: float 6s ease-in-out infinite;
        }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-15px); }
            100% { transform: translateY(0px); }
        }
        .hero-icon {
            background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.01));
            padding: 2rem;
            border-radius: 30px;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1);
        }
        .stButton>button {
            border-radius: 12px;
            font-weight: 600;
            padding: 0.5rem 2rem;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px rgba(59, 130, 246, 0.4);
        }
        </style>
        
        <div class="hero-icon-container">
            <div class="hero-icon">
                <span style="font-size:4.5rem; filter: drop-shadow(0 0 20px rgba(96, 165, 250, 0.6));">✨</span>
            </div>
        </div>
        <div class="hero-title-new">Talk to Your Multimedia</div>
        <div class="hero-subtitle-new">
            Stop searching and start conversing. Upload your PDFs, scanned documents, videos, and audio files, 
            and our AI will instantly turn them into an interactive knowledge base. 
            Get precise, citable answers in seconds.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Start Exploring", use_container_width=True, type="primary"):
            st.switch_page("pages/Upload.py")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Feature cards ─────────────────────────────────────────────────────────
    feature_col_1, feature_col_2, feature_col_3, feature_col_4 = st.columns(4)
    feature_cards = [
        (feature_col_1, "#60A5FA", "📄", "Any Format, Anywhere",
         "PDFs, Scanned Docs, DOCX, PPTX, TXT, MP4, MP3 & more. We extract the knowledge automatically."),
        (feature_col_2, "#4ADE80", "🧠", "Smart OCR Included",
         "Image-heavy or scanned PDFs? No problem. Our built-in OCR pipeline reads them flawlessly."),
        (feature_col_3, "#C084FC", "🕒", "Pinpoint Accuracy",
         "Every answer includes exact timestamps or page numbers so you can verify the source instantly."),
        (feature_col_4, "#FBBF24", "🛡️", "Total Privacy",
         "Your files and conversations stay completely private and secure within your own infrastructure."),
    ]
    for column, hex_color, emoji_icon, card_title, card_description in feature_cards:
        with column:
            st.markdown(
                f"""
                <div class="feature-card">
                    <div class="feature-icon" style="color:{hex_color};">{emoji_icon}</div>
                    <div class="feature-title">{card_title}</div>
                    <div class="feature-desc">{card_description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ── How it works ──────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center; color:var(--text-main); font-size:1.4rem;
                    font-weight:700; margin-bottom:1.5rem;">
            How It Works
        </div>
        """,
        unsafe_allow_html=True,
    )

    s1, s2, s3 = st.columns(3)
    instruction_steps = [
        (s1, "01", "#60A5FA", "Upload",
         "Go to the <b>Upload</b> page and drop in any file — PDF, video, audio, or document."),
        (s2, "02", "#C084FC", "Process",
         "The system automatically transcribes, extracts, and indexes your content into the knowledge base."),
        (s3, "03", "#4ADE80", "Ask",
         "Head to the <b>Chat</b> page and ask anything. Receive rich answers with source citations."),
    ]
    for column, step_number, hex_color, step_label, step_description in instruction_steps:
        with column:
            st.markdown(
                f"""
                <div class="feature-card" style="align-items:flex-start; text-align:left;">
                    <div style="font-size:2rem; font-weight:900; color:{hex_color};
                                margin-bottom:0.75rem; opacity:0.7;">{step_number}</div>
                    <div class="feature-title" style="margin-bottom:0.5rem;">{step_label}</div>
                    <div class="feature-desc">{step_description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ── Engaging Footer Strip ──────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="display:flex; justify-content:center; gap:2rem; flex-wrap:wrap;
                    color:var(--text-main); font-size:1rem; font-weight:600; 
                    background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0));
                    padding: 1.5rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.05);
                    margin-top: 1rem;">
            <span style="display:flex; align-items:center; gap:0.5rem;">⚡ <span style="opacity:0.9;">Lightning Fast</span></span>
            <span style="opacity:0.3;">|</span>
            <span style="display:flex; align-items:center; gap:0.5rem;">🎯 <span style="opacity:0.9;">Pinpoint Accuracy</span></span>
            <span style="opacity:0.3;">|</span>
            <span style="display:flex; align-items:center; gap:0.5rem;">🔒 <span style="opacity:0.9;">100% Private</span></span>
            <span style="opacity:0.3;">|</span>
            <span style="display:flex; align-items:center; gap:0.5rem;">💡 <span style="opacity:0.9;">Endless Possibilities</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()