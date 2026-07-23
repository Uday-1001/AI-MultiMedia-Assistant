import streamlit as st
import requests
import os
import sys
from typing import Optional

st.set_page_config(
    page_title="AI Multimedia Assistant",
    page_icon="🤓",
    layout="wide"
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_enhancer
ui_enhancer.apply_custom_theme()

API_BASE_URL = "http://localhost:8000"

SUPPORTED_FORMATS = {
    "video":    ["mp4", "mov", "mkv", "avi", "webm"],
    "audio":    ["mp3", "wav", "m4a", "flac"],
    "document": ["pdf", "docx", "pptx", "txt"],
}

TYPE_META = {
    "video":    {"icon": "🎦", "label": "Video",    "color": "#C084FC"},
    "audio":    {"icon": "🎧️", "label": "Audio",    "color": "#4ADE80"},
    "document": {"icon": "📄", "label": "Document", "color": "#60A5FA"},
}


def get_file_type(filename: str) -> Optional[str]:
    # Map file extensions to their broad category (video, audio, document)
    file_extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    for format_category, valid_extensions in SUPPORTED_FORMATS.items():
        if file_extension in valid_extensions:
            return format_category
    return None


ERROR_HINTS = {
    "no text could be extracted": (
        "This file doesn't contain any readable text. It might be a scanned "
        "or image-based PDF. Try exporting it as a text-based PDF, or run OCR "
        "on it before uploading."
    ),
    "unsupported file type": "This file format isn't supported. Please upload a PDF, DOCX, PPTX, TXT, or multimedia file.",
    "file not found": "The file couldn't be found on the server. Please try uploading again.",
    "timeout": "The request timed out. The file may be too large — try a smaller file or check your connection.",
    "connection": "Could not reach the server. Make sure the backend is running.",
}


def friendly_error(response=None, exception: Optional[Exception] = None) -> str:
    # Parse raw error details into friendly UI messages
    raw = ""
    if exception is not None:
        raw = str(exception).lower()
        for keyword, hint in ERROR_HINTS.items():
            if keyword in raw:
                return hint
        return f"An unexpected error occurred: {exception}"
    if response is not None:
        try:
            detail = response.json().get("detail", "")
        except Exception:
            detail = response.text
        raw = detail.lower()
        for keyword, hint in ERROR_HINTS.items():
            if keyword in raw:
                return hint
        return detail if detail else f"Server returned status {response.status_code}."
    return "An unknown error occurred."


def main():

    st.markdown(
        """
        <style>
        .format-pill {
            display: inline-block;
            padding: 0.25rem 0.65rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            margin: 0.2rem;
        }
        .pill-video    { background: rgba(192,132,252,0.15); color: #C084FC; border: 1px solid rgba(192,132,252,0.3); }
        .pill-audio    { background: rgba(74,222,128,0.15);  color: #4ADE80; border: 1px solid rgba(74,222,128,0.3); }
        .pill-document { background: rgba(96,165,250,0.15);  color: #60A5FA; border: 1px solid rgba(96,165,250,0.3); }

        /* Upload zone styling */
        [data-testid="stFileUploadDropzone"] {
            background: var(--surface-color) !important;
            border: 2px dashed var(--border-color) !important;
            border-radius: 16px !important;
            transition: border-color 0.25s ease !important;
        }
        [data-testid="stFileUploadDropzone"]:hover {
            border-color: var(--accent-color) !important;
        }

        .info-card {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
        }
        .step-num {
            width: 28px; height: 28px;
            border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.85rem;
            margin-right: 0.6rem;
            flex-shrink: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


    st.markdown(
        """
        <div style="margin-bottom:0.25rem;">
            <span style="font-size:2rem; font-weight:800; color:var(--text-main);">
                📤 Add to Your Knowledge Base
            </span>
        </div>
        <div style="color:var(--text-muted); font-size:1rem; margin-bottom:1.5rem; max-width:620px;">
            Drop in a lecture video, a podcast episode, a research paper — 
            anything you want to be able to <b>ask questions about</b>. We handle 
            transcription and indexing automatically.
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.markdown(
        """
        <div style="margin-bottom:1.75rem;">
            <span class="format-pill pill-video">🎬 MP4</span>
            <span class="format-pill pill-video">🎬 MOV</span>
            <span class="format-pill pill-video">🎬 MKV</span>
            <span class="format-pill pill-video">🎬 AVI</span>
            <span class="format-pill pill-video">🎬 WEBM</span>
            <span class="format-pill pill-audio">🎙️ MP3</span>
            <span class="format-pill pill-audio">🎙️ WAV</span>
            <span class="format-pill pill-audio">🎙️ M4A</span>
            <span class="format-pill pill-audio">🎙️ FLAC</span>
            <span class="format-pill pill-document">📄 PDF</span>
            <span class="format-pill pill-document">📄 DOCX</span>
            <span class="format-pill pill-document">📄 PPTX</span>
            <span class="format-pill pill-document">📄 TXT</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


    uploaded_file = st.file_uploader(
        "Drag & drop your file here, or click to browse",
        type=["mp4","mov","mkv","avi","webm","mp3","wav","m4a","flac","pdf","docx","pptx","txt"],
        help="Up to 200 MB per file. Videos and audio are auto-transcribed with Whisper.",
        label_visibility="visible",
    )

    if uploaded_file:
        file_type = get_file_type(uploaded_file.name)
        meta = TYPE_META.get(file_type or "", {"icon": "📁", "label": "Unknown", "color": "#94A3B8"})
        size_mb = uploaded_file.size / (1024 * 1024)

        st.markdown("<br>", unsafe_allow_html=True)


        warning_html = "<div style='color:#FBBF24;font-size:0.8rem;'>⚠️ Audio/video will be transcribed — large files may take a few minutes.</div>" if file_type in ['video', 'audio'] else ""
        card_html = (
            '<div class="info-card" style="margin-bottom:1rem;">'
            '<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;">'
            f'<div style="font-size:2.5rem;">{meta["icon"]}</div>'
            '<div style="flex:1;min-width:180px;">'
            f'<div style="font-weight:700;color:var(--text-main);font-size:1rem;word-break:break-all;">{uploaded_file.name}</div>'
            '<div style="color:var(--text-muted);font-size:0.85rem;margin-top:0.2rem;">'
            f'<span style="color:{meta["color"]};font-weight:600;">{meta["label"]}</span>'
            f'&nbsp;·&nbsp;{size_mb:.2f} MB'
            '</div></div>'
            + warning_html
            + '</div></div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)


        existing_file_id = st.session_state.get(f"uploaded_{uploaded_file.name}", {}).get("file_id")
        if not existing_file_id:
            try:
                docs_response = requests.get(f"{API_BASE_URL}/history/documents", timeout=5)
                if docs_response.status_code == 200:
                    for doc in docs_response.json():
                        if doc.get("filename") == uploaded_file.name:
                            existing_file_id = doc["id"]
                            st.session_state[f"uploaded_{uploaded_file.name}"] = {"file_id": existing_file_id}
                            break
            except Exception:
                pass

        if existing_file_id:
            view_url = f"http://localhost:8000/upload/{existing_file_id}/view"
            st.markdown(
                f'<a href="{view_url}" target="_blank" style="'
                'display:inline-flex;align-items:center;gap:0.45rem;'
                'padding:0.45rem 1rem;border-radius:8px;font-size:0.88rem;font-weight:600;'
                'background:rgba(96,165,250,0.12);color:#60A5FA;'
                'border:1px solid rgba(96,165,250,0.35);text-decoration:none;">'
                '\U0001f441\ufe0f View File</a>',
                unsafe_allow_html=True,
            )
        st.markdown("<div style='margin-bottom:0.75rem'></div>", unsafe_allow_html=True)


        button_column, space_column = st.columns([2, 5])
        with button_column:
            if st.button(f"🚀 Upload & Process {uploaded_file.name[:30]}{'…' if len(uploaded_file.name)>30 else ''}",
                         type="primary", use_container_width=True):

                with st.status("📤 Uploading your file…", expanded=True) as status:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/upload/",
                            files=files,
                            timeout=60,
                        )
                        if response.status_code != 200:
                            err = friendly_error(response=response)
                            status.update(label="❌ Upload failed", state="error")
                            st.error(f"**Upload failed**\n\n{err}")
                            st.stop()

                        result = response.json()
                        file_id = result.get("file_id")
                        st.write(f"✅ File received! ID: `{file_id}`")


                        status.update(label="⚙️ Starting processing...", expanded=True)
                        process_response = requests.post(
                            f"{API_BASE_URL}/upload/{file_id}/process",
                            timeout=60,
                        )
                        
                        if process_response.status_code == 200:
                            import time
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            while True:
                                try:
                                    status_response = requests.get(f"{API_BASE_URL}/upload/{file_id}/status", timeout=10)
                                    if status_response.status_code == 200:
                                        status_data = status_response.json()
                                        current_step = status_data.get("current", 0)
                                        total_steps = status_data.get("total", 0)
                                        status_message = status_data.get("message", "Processing...")
                                        job_status = status_data.get("status")
                                        
                                        if total_steps > 0:
                                            progress_percentage = min(1.0, max(0.0, current_step / total_steps))
                                            progress_bar.progress(progress_percentage)
                                        
                                        status_text.markdown(f"**{status_message}**")
                                        
                                        if job_status == "processed":
                                            progress_bar.progress(1.0)
                                            st.write("✅ Indexing complete — ready to chat!")
                                            status.update(
                                                label="🎉 All done! Your file is now part of your knowledge base.",
                                                state="complete",
                                                expanded=False,
                                            )
                                            st.session_state[f"file_{file_id}"] = result

                                            st.session_state[f"uploaded_{uploaded_file.name}"] = {"file_id": file_id}
                                            break
                                        elif job_status == "error":
                                            status.update(label="❌ Processing failed", state="error")
                                            st.error(f"**Could not process this file**\n\n{status_message}")
                                            break
                                        
                                        time.sleep(1.5)
                                    else:
                                        time.sleep(2)
                                except Exception:
                                    time.sleep(2)
                                    
                        else:
                            error_message = friendly_error(response=process_response)
                            status.update(label="❌ Processing failed", state="error")
                            st.error(f"**Could not process this file**\n\n{error_message}")

                    except requests.exceptions.ConnectionError:
                        status.update(label="❌ Connection failed", state="error")
                        st.error("**Cannot reach the server.**\n\nMake sure the backend is running at `http://localhost:8000`.")
                    except requests.exceptions.Timeout:
                        status.update(label="❌ Timed out", state="error")
                        st.error("**The request timed out.**\n\nThe file may be very large. Try a smaller file or check your connection.")
                    except Exception as unexpected_error:
                        status.update(label="❌ Unexpected error", state="error")
                        st.error(f"**Something went wrong**\n\n{friendly_error(exception=unexpected_error)}")

    st.markdown("<br><br>", unsafe_allow_html=True)


    st.markdown(
        "<div style='color:var(--text-main); font-weight:700; font-size:1rem;"
        " margin-bottom:1rem;'>How it works</div>",
        unsafe_allow_html=True,
    )

    s1, s2, s3 = st.columns(3)
    steps = [
        (s1, "#60A5FA", "01", "Upload",
         "Drop any video, audio, or document file using the uploader above."),
        (s2, "#C084FC", "02", "Auto-Process",
         "We transcribe audio/video with Whisper and extract text from documents — all automatically."),
        (s3, "#4ADE80", "03", "Chat",
         "Head to the Chat page and ask anything. Your file is now part of your knowledge base."),
    ]
    for col, color, num, label, body in steps:
        with col:
            st.markdown(
                f"""
                <div class="info-card">
                    <div style="display:flex; align-items:center; margin-bottom:0.6rem;">
                        <div class="step-num" style="background:rgba(255,255,255,0.06);
                                    color:{color};">{num}</div>
                        <span style="font-weight:700; color:var(--text-main);">{label}</span>
                    </div>
                    <div style="color:var(--text-muted); font-size:0.88rem; line-height:1.5;">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()