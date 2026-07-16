import streamlit as st
import os
import requests

def apply_custom_theme():
    if 'theme' not in st.session_state:
        st.session_state.theme = 'dark'
        
    if st.session_state.theme == 'dark':
        css_vars = """
        :root {
            --bg-color: #0F172A;
            --surface-color: #1E293B;
            --accent-color: #3B82F6; 
            --accent-hover: #60A5FA;
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }
        """
    else:
        css_vars = """
        :root {
            --bg-color: #F8FAFC;
            --surface-color: #FFFFFF;
            --accent-color: #2563EB; 
            --accent-hover: #1D4ED8;
            --border-color: #E2E8F0;
            --text-main: #0F172A;
            --text-muted: #64748B;
        }
        """

    custom_css = f"""
    <style>
    {css_vars}

    /* Base Streamlit App Background */
    .stApp {{
        background-color: var(--bg-color) !important;
    }}

    /* Sidebar UI */
    [data-testid="stSidebar"] {{
        background-color: var(--bg-color) !important;
        border-right: 1px solid var(--border-color) !important;
    }}

    /* Always-visible scrollbar in the sidebar */
    [data-testid="stSidebar"] > div:first-child {{
        overflow-y: scroll !important;
        scrollbar-width: thin !important;          /* Firefox */
        scrollbar-color: #334155 transparent !important; /* Firefox thumb + track */
    }}

    /* Webkit (Chrome / Edge) */
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar {{
        width: 6px !important;
    }}
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-track {{
        background: transparent !important;
    }}
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb {{
        background-color: #334155 !important;
        border-radius: 3px !important;
    }}
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb:hover {{
        background-color: #475569 !important;
    }}
    
    [data-testid="stSidebarNav"] span {{
        color: var(--text-main) !important;
    }}

    [data-testid="stSidebarNav"] a {{
        border-radius: 6px !important;
        transition: background-color 0.2s ease, transform 0.1s ease !important;
    }}

    [data-testid="stSidebarNav"] a:hover {{
        background-color: var(--surface-color) !important;
    }}

    /* Top Header */
    header[data-testid="stHeader"] {{
        background-color: var(--bg-color) !important;
        border-bottom: 1px solid var(--border-color) !important;
    }}

    /* Gradients & Typography */
    .gradient-text {{
        background: linear-gradient(90deg, #60A5FA, #C084FC, #F472B6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
        font-weight: 800;
        font-size: 2.5rem;
    }}
    
    .hero-title {{
        text-align: center;
        color: var(--text-main);
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }}
    
    .hero-subtitle {{
        text-align: center;
        color: var(--text-muted);
        font-size: 1.1rem;
        max-width: 600px;
        margin: 0 auto 3rem auto;
        line-height: 1.5;
    }}

    /* Feature Cards */
    .feature-card {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .feature-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        border-color: rgba(255,255,255,0.15);
    }}
    
    .feature-icon {{
        font-size: 2rem;
        margin-bottom: 1rem;
    }}
    
    .feature-title {{
        color: var(--text-main);
        font-weight: 600;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }}
    
    .feature-desc {{
        color: var(--text-muted);
        font-size: 0.9rem;
        line-height: 1.4;
    }}

    /* Mock Chat Input Wrapper */
    .mock-chat-wrapper {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 24px;
        padding: 0.5rem 1rem;
        display: flex;
        align-items: center;
        margin-top: 4rem;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }}
    
    .mock-chat-input {{
        flex-grow: 1;
        background: transparent;
        border: none;
        color: var(--text-main);
        font-size: 1rem;
        padding: 0.5rem;
        outline: none;
    }}

    /* Sidebar Stats Box */
    .sidebar-stats-box {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
    }}
    
    .stats-row {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
    }}
    
    .stats-label {{
        color: var(--text-muted);
    }}
    
    .stats-value {{
        color: var(--text-main);
        font-weight: 500;
    }}

    /* Sidebar User Profile - pinned to bottom via flex */
    .sidebar-user-profile {{
        background-color: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.75rem;
        display: flex;
        align-items: center;
        margin-top: auto;
        width: 100%;
    }}
    
    .user-avatar {{
        width: 32px;
        height: 32px;
        background-color: #3B82F6;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        margin-right: 0.75rem;
    }}
    
    .user-info {{
        display: flex;
        flex-direction: column;
    }}
    
    .user-name {{
        color: var(--text-main);
        font-weight: 600;
        font-size: 0.9rem;
    }}
    
    .user-role {{
        color: var(--text-muted);
        font-size: 0.75rem;
    }}

    /* Hide default metric styling we don't want */
    [data-testid="stMetricValue"] {{
        color: var(--text-main) !important;
    }}
    
    /* End Session Button global styling fallback */
    [data-testid="stSidebar"] button[kind="primary"] {{
        background-color: #DC2626 !important;
        color: white !important;
        border: none !important;
    }}

    /* Backend Status Bar */
    .backend-status-bar {{
        display: flex;
        align-items: center;
        gap: 0.55rem;
        background: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.55rem 0.9rem;
        margin-top: -1.5rem;
        margin-bottom: 1rem;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--text-main);
    }}

    .status-dot {{
        width: 9px;
        height: 9px;
        border-radius: 50%;
        flex-shrink: 0;
    }}

    .status-dot-online {{
        background-color: #4ADE80;
        box-shadow: 0 0 6px #4ADE80;
        animation: blink-green 1.6s ease-in-out infinite;
    }}

    .status-dot-offline {{
        background-color: #F87171;
        box-shadow: 0 0 6px #F87171;
        animation: blink-red 1.6s ease-in-out infinite;
    }}

    @keyframes blink-green {{
        0%, 100% {{ opacity: 1; box-shadow: 0 0 6px #4ADE80; }}
        50%        {{ opacity: 0.35; box-shadow: 0 0 2px #4ADE80; }}
    }}

    @keyframes blink-red {{
        0%, 100% {{ opacity: 1; box-shadow: 0 0 6px #F87171; }}
        50%        {{ opacity: 0.35; box-shadow: 0 0 2px #F87171; }}
    }}
    </style>
    """

    backend_online = False
    try:
        r = requests.get("http://localhost:8000/health", timeout=2)
        backend_online = r.status_code < 500
    except Exception:
        try:
            r = requests.get("http://localhost:8000/", timeout=2)
            backend_online = r.status_code < 500
        except Exception:
            backend_online = False

    dot_class = "status-dot-online" if backend_online else "status-dot-offline"
    status_label = "All Ready 👍" if backend_online else "Backend Offline"
    status_bar_html = f"""
    <div class="backend-status-bar">
        <span class="status-dot {dot_class}"></span>
        <span>{status_label}</span>
    </div>
    """

    with st.sidebar:
        st.markdown(custom_css, unsafe_allow_html=True)
        st.markdown(status_bar_html, unsafe_allow_html=True)
        
        config_dir = os.path.join(os.path.dirname(__file__), ".streamlit")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.toml")
        
        if st.session_state.theme == 'dark':
            toml_content = '''[theme]
primaryColor = "#3B82F6"
backgroundColor = "#0F172A"
secondaryBackgroundColor = "#1E293B"
textColor = "#F8FAFC"
font = "sans serif"

[server]
headless = true
port = 8501
'''
        else:
            toml_content = '''[theme]
primaryColor = "#2563EB"
backgroundColor = "#F8FAFC"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#0F172A"
font = "sans serif"

[server]
headless = true
port = 8501
'''
        current_toml = ""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                current_toml = f.read()
                
        if current_toml != toml_content:
            with open(config_path, "w") as f:
                f.write(toml_content)
            st.rerun()
