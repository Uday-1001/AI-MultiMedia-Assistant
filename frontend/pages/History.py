import streamlit as st
import requests
import sys
import os
from datetime import datetime

st.set_page_config(
    page_title="AI Multimedia Assistant",
    page_icon="🤓",
    layout="wide"
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_enhancer
ui_enhancer.apply_custom_theme()

API_BASE_URL = "http://localhost:8000"

# ── Page-level CSS ────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Session card */
    .session-card {
        background: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        transition: border-color 0.2s ease;
    }
    .session-card:hover { border-color: rgba(96,165,250,0.4); }

    .session-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .session-title {
        font-weight: 700;
        color: var(--text-main);
        font-size: 0.95rem;
    }
    .session-meta {
        color: var(--text-muted);
        font-size: 0.78rem;
    }
    .msg-bubble {
        border-radius: 10px;
        padding: 0.65rem 1rem;
        margin: 0.4rem 0;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .msg-user {
        background: rgba(96,165,250,0.12);
        border-left: 3px solid #60A5FA;
        color: var(--text-main);
    }
    .msg-assistant {
        background: rgba(192,132,252,0.1);
        border-left: 3px solid #C084FC;
        color: var(--text-main);
    }
    .msg-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        margin-bottom: 0.2rem;
    }
    /* Doc card */
    .doc-card {
        background: var(--surface-color);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
        transition: border-color 0.2s ease;
    }
    .doc-card:hover { border-color: rgba(96,165,250,0.4); }
    .status-pill {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .pill-processed { background: rgba(74,222,128,0.15); color: #4ADE80; border: 1px solid rgba(74,222,128,0.3); }
    .pill-pending   { background: rgba(251,191,36,0.15);  color: #FBBF24; border: 1px solid rgba(251,191,36,0.3); }
    .pill-failed    { background: rgba(248,113,113,0.15); color: #F87171; border: 1px solid rgba(248,113,113,0.3); }
    </style>
    """,
    unsafe_allow_html=True,
)

TYPE_ICON = {"video": "🎬", "audio": "🎙️", "document": "📄"}


def status_pill(status: str) -> str:
    cls = {"processed": "pill-processed", "pending": "pill-pending", "failed": "pill-failed"}.get(status, "pill-pending")
    label = {"processed": "✅ Processed", "pending": "⏳ Pending", "failed": "❌ Failed"}.get(status, status.capitalize())
    return f'<span class="status-pill {cls}">{label}</span>'


def main():
    # ── Hero ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="margin-bottom:1.5rem;">
            <div style="font-size:2rem; font-weight:800; color:var(--text-main);">
                📜 Your History
            </div>
            <div style="color:var(--text-muted); font-size:0.95rem; margin-top:0.25rem;">
                Browse past conversations and every file you've added to your knowledge base.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["💬 Chat Sessions", "📁 Uploaded Documents"])

    # ── TAB 1 — Chat Sessions ─────────────────────────────────────────────────
    with tab1:
        st.markdown(
            "<div style='color:var(--text-muted); font-size:0.88rem; margin-bottom:1rem;'>"
            "Every conversation you've had is preserved here. Expand a session to relive the exchange."
            "</div>",
            unsafe_allow_html=True,
        )
        try:
            response = requests.get(f"{API_BASE_URL}/history/sessions", timeout=5)
            if response.status_code == 200:
                chat_sessions = response.json()
                if not chat_sessions:
                    st.markdown(
                        """
                        <div style="text-align:center; padding:3rem 1rem;">
                            <div style="font-size:2.5rem; margin-bottom:0.75rem;">💬</div>
                            <div style="color:var(--text-main); font-weight:600; margin-bottom:0.4rem;">No conversations yet</div>
                            <div style="color:var(--text-muted); font-size:0.88rem;">
                                Head over to the Chat page and ask your first question!
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    for session in chat_sessions:
                        session_id   = session.get("session_id", "—")
                        session_title = session.get("title", "Untitled Session")
                        messages  = session.get("messages", [])
                        message_count = len(messages)

                        with st.expander(f"🗨️ {session_title}  ·  {message_count} message{'s' if message_count != 1 else ''}"):
                            st.markdown(
                                f"<div style='color:var(--text-muted); font-size:0.75rem; margin-bottom:0.75rem;'>"
                                f"Session ID: <code>{session_id}</code></div>",
                                unsafe_allow_html=True,
                            )
                            if not messages:
                                st.markdown(
                                    "<div style='color:var(--text-muted); font-size:0.88rem;'>"
                                    "No messages in this session.</div>",
                                    unsafe_allow_html=True,
                                )
                            for message in messages:
                                role    = message.get("role", "unknown")
                                content = message.get("content", "")
                                is_user_message = role == "user"
                                bubble_class = "msg-user" if is_user_message else "msg-assistant"
                                label_html = (
                                    f'<div class="msg-label" style="color:{"#60A5FA" if is_user_message else "#C084FC"};">'
                                    f'{"🧑 You" if is_user_message else "🧠 Assistant"}</div>'
                                )
                                st.markdown(
                                    f'<div class="msg-bubble {bubble_class}">'
                                    f'{label_html}'
                                    f'{content}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                                if message.get("sources"):
                                    st.caption(f"📎 Sources: {message['sources']}")
            else:
                st.error(f"Could not load sessions: {response.text}")
        except Exception as error:
            st.error(f"Could not reach the server: {error}")

    # ── TAB 2 — Uploaded Documents ────────────────────────────────────────────
    with tab2:
        col_search, col_space = st.columns([3, 4])
        with col_search:
            search_query = st.text_input(
                "Search your knowledge base",
                placeholder="🔍 Filter by filename…",
                label_visibility="collapsed",
            )

        st.markdown(
            "<div style='color:var(--text-muted); font-size:0.88rem; margin-bottom:1rem; margin-top:0.25rem;'>"
            "All files you've uploaded. Processed files are ready to chat with. "
            "Deleting a file removes it from the library but won't erase past answers."
            "</div>",
            unsafe_allow_html=True,
        )

        try:
            response = requests.get(f"{API_BASE_URL}/history/documents", timeout=5)
            if response.status_code == 200:
                documents = response.json()

                if search_query:
                    documents = [d for d in documents if search_query.lower() in d.get("filename", "").lower()]

                if not documents:
                    st.markdown(
                        """
                        <div style="text-align:center; padding:3rem 1rem;">
                            <div style="font-size:2.5rem; margin-bottom:0.75rem;">📁</div>
                            <div style="color:var(--text-main); font-weight:600; margin-bottom:0.4rem;">
                                Nothing here yet
                            </div>
                            <div style="color:var(--text-muted); font-size:0.88rem;">
                                Upload your first file on the Upload page to get started!
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    for document in documents:
                        file_type  = document.get("file_type", "document")
                        icon   = TYPE_ICON.get(file_type, "📁")
                        file_name  = document.get("filename", "Unknown")
                        status = document.get("status", "pending")
                        file_size_mb  = document.get("file_size_mb")
                        formatted_size = f"{file_size_mb:.2f} MB" if file_size_mb else ""

                        info_column, button_column = st.columns([6, 1])
                        with info_column:
                            st.markdown(
                                f"""
                                <div class="doc-card">
                                    <div style="font-size:1.8rem; flex-shrink:0;">{icon}</div>
                                    <div style="flex:1; min-width:120px;">
                                        <div style="font-weight:700; color:var(--text-main);
                                                    font-size:0.95rem; word-break:break-all;">{file_name}</div>
                                        <div style="color:var(--text-muted); font-size:0.78rem; margin-top:0.2rem;">
                                            {file_type.capitalize()}{f'  ·  {formatted_size}' if formatted_size else ''}
                                        </div>
                                    </div>
                                    <div>{status_pill(status)}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        with button_column:
                            st.markdown("<div style='padding-top:0.6rem;'>", unsafe_allow_html=True)
                            if st.button("🗑️ Delete", key=f"del_{document.get('id')}", use_container_width=True):
                                delete_response = requests.delete(
                                    f"{API_BASE_URL}/history/document/{document.get('id')}",
                                    timeout=30,
                                )
                                if delete_response.status_code == 200:
                                    st.success(f"'{file_name}' removed from your library.")
                                    st.rerun()
                                else:
                                    st.error("Could not delete the file. Please try again.")
                            st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.error(f"Could not load documents: {response.text}")
        except Exception as error:
            st.error(f"Could not reach the server: {error}")


if __name__ == "__main__":
    main()