import streamlit as st
import requests
import time

st.set_page_config(
    page_title="AI Multimedia Assistant",
    page_icon="🤓",
    layout="wide"
)

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_enhancer
ui_enhancer.apply_custom_theme()

API_BASE_URL = "http://localhost:8000"

# Initialize session state for tracking chat history and selected files
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "file_id" not in st.session_state:
    st.session_state.file_id = None
if "show_end_dialog" not in st.session_state:
    st.session_state.show_end_dialog = False


def do_end_session():
    # Clear chat history and reset session
    if st.session_state.session_id:
        try:
            response = requests.post(
                f"{API_BASE_URL}/chat/end-session",
                json={"session_id": st.session_state.session_id},
                timeout=5,
            )
            if response.status_code == 200:
                st.session_state.session_id = response.json().get("new_session_id")
        except Exception:
            pass
    st.session_state.messages = []
    st.session_state.file_id = None
    st.session_state.show_end_dialog = False


def main():
    # Custom styling for the Chat page components
    st.markdown(
        """
        <style>
        /* Red End-Session button — scoped so it doesn't affect other buttons */
        [data-testid="stSidebar"] .end-session-btn > button {
            background: linear-gradient(135deg, #DC2626, #B91C1C) !important;
            color: #fff !important;
            border: none !important;
            transition: background 0.25s ease, transform 0.15s ease !important;
        }
        [data-testid="stSidebar"] .end-session-btn > button:hover {
            background: linear-gradient(135deg, #B91C1C, #991B1B) !important;
            transform: translateY(-1px) !important;
        }
        /* Thinking indicator pulse */
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
        .thinking-dot { animation: pulse 1.2s ease-in-out infinite; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar for selecting data sources and managing the session
    with st.sidebar:
        st.markdown(
            "<div style='font-size:1.1rem; font-weight:700; color:var(--text-main);"
            " margin-bottom:0.25rem;'>🧠 Knowledge Focus</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:0.82rem; color:var(--text-muted); margin-bottom:0.75rem;'>"
            "Select a document to narrow answers to that source, or keep "
            "<b>All Sources</b> to search your entire knowledge base.</div>",
            unsafe_allow_html=True,
        )

        # Dropdown to filter context to a specific document
        try:
            response = requests.get(f"{API_BASE_URL}/history/documents", timeout=5)
            if response.status_code == 200:
                documents = response.json()
                document_options = {
                    f"{document['filename']}": document["id"]
                    for document in documents
                    if document.get("status") == "processed"
                }
                selected_document = st.selectbox(
                    "Filter source",
                    options=[None] + list(document_options.keys()),
                    format_func=lambda source: "✨ All Sources" if source is None else f"📄 {source}",
                )
                st.session_state.file_id = document_options.get(selected_document) if selected_document else None
            else:
                st.session_state.file_id = None
        except Exception:
            st.warning("⚠️ Could not reach the backend. Is the server running?")
            st.session_state.file_id = None

        st.markdown("<hr style='border-color:var(--border-color); margin:1rem 0;'>", unsafe_allow_html=True)

        # Display current session metrics
        message_count = len(st.session_state.messages)
        st.markdown(
            f"""
            <div style='font-size:0.75rem; color:var(--text-muted); letter-spacing:1px;
                        font-weight:600; margin-bottom:0.5rem;'>CURRENT SESSION</div>
            <div class="sidebar-stats-box">
                <div class="stats-row">
                    <span class="stats-label">Messages</span>
                    <span class="stats-value">{message_count}</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">Source filter</span>
                    <span class="stats-value">{'Active' if st.session_state.file_id else 'All'}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Bottom spacer before session controls
        st.markdown("<div style='min-height:40px;'></div>", unsafe_allow_html=True)

        st.markdown("<div class='end-session-btn'>", unsafe_allow_html=True)
        if st.button("⏹️ End Session", use_container_width=True, key="end_session_btn"):
            st.session_state.show_end_dialog = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # Render a mock user profile card
        st.markdown(
            """
            <div style="background-color:var(--surface-color); border:1px solid var(--border-color);
                        border-radius:8px; padding:0.75rem; display:flex; align-items:center;
                        margin-top:0.75rem;">
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

    # Render the confirmation dialog for ending a session
    if st.session_state.show_end_dialog:
        st.markdown(
            """
            <div style="background:var(--surface-color); border:1px solid #DC2626;
                        border-radius:12px; padding:1.5rem; margin-bottom:1rem;">
                <div style="font-size:1.2rem; font-weight:700; color:#F87171; margin-bottom:0.5rem;">
                    ⚠️ End Current Session?
                </div>
                <div style="color:var(--text-muted); font-size:0.95rem;">
                    This will clear your entire conversation, remove the active
                    document focus, and start a fresh session.<br>
                    <b>Your uploaded documents will not be deleted.</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("← Keep Chatting", use_container_width=True, key="cancel_end"):
                st.session_state.show_end_dialog = False
                st.rerun()
        with col2:
            if st.button("⏹️ Yes, End Session", use_container_width=True, key="confirm_end"):
                do_end_session()
                st.success("✅ Session ended! Ready for a fresh start.")
                time.sleep(1.2)
                st.rerun()
        st.stop()

    # Render a welcome screen with quick-start prompts if chat is empty
    if not st.session_state.messages:
        st.markdown(
            """
            <div style="text-align:center; padding:4rem 1rem 2rem;">
                <div style="font-size:3rem; margin-bottom:1rem;">💬</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--text-main);
                            margin-bottom:0.5rem;">Ask Anything About Your Content</div>
                <div style="color:var(--text-muted); font-size:1rem; max-width:520px;
                            margin:0 auto; line-height:1.6;">
                    Your knowledge base is ready. Ask a question, request a summary,
                    create flashcards, or quiz yourself — all sourced directly from
                    your uploaded files.
                </div>
            </div>

            <div style="display:flex; justify-content:center; gap:1rem; flex-wrap:wrap;
                        margin-bottom:3rem;">
                <div style="background:var(--surface-color); border:1px solid var(--border-color);
                            border-radius:10px; padding:0.6rem 1.1rem; font-size:0.85rem;
                            color:var(--text-muted);">💡 Summarize this lecture</div>
                <div style="background:var(--surface-color); border:1px solid var(--border-color);
                            border-radius:10px; padding:0.6rem 1.1rem; font-size:0.85rem;
                            color:var(--text-muted);">🃏 Create flashcards for deadlocks</div>
                <div style="background:var(--surface-color); border:1px solid var(--border-color);
                            border-radius:10px; padding:0.6rem 1.1rem; font-size:0.85rem;
                            color:var(--text-muted);">📝 Revision notes for Chapter 5</div>
                <div style="background:var(--surface-color); border:1px solid var(--border-color);
                            border-radius:10px; padding:0.6rem 1.1rem; font-size:0.85rem;
                            color:var(--text-muted);">🧪 Quiz me on routing algorithms</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Display previous messages in the conversation
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                st.caption(f"📎 Sources: {', '.join(message['sources'])}")

    # Input field and submit logic for new questions
    if prompt := st.chat_input("Ask a question, request a summary, or create flashcards…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown(
                "<span class='thinking-dot'>🧠 Searching your knowledge base…</span>",
                unsafe_allow_html=True,
            )
            try:
                response = requests.post(
                    f"{API_BASE_URL}/chat/",
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id,
                        "file_id": st.session_state.file_id,
                    },
                    timeout=300,
                )
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "No answer received.")
                    sources = result.get("sources", [])

                    placeholder.markdown(answer)
                    if sources:
                        st.caption(f"📎 Sources: {', '.join(sources)}")

                    st.session_state.session_id = result.get("session_id")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                        "timestamps": result.get("timestamps", []),
                    })
                else:
                    placeholder.error(f"Something went wrong: {response.text}")
            except Exception as e:
                placeholder.error(f"Could not reach the server: {e}")


if __name__ == "__main__":
    main()