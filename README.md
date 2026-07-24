# CogniSphere - AI MultiModal Knowledge Assistant

A production-ready Retrieval-Augmented Generation (RAG) assistant capable of understanding multimedia content using **Streamlit + FastAPI + LangChain + SQLite + ChromaDB + Faster-Whisper + EasyOCR**.

## Features

- **Multimedia Processing:** Upload and process videos (mp4, mov, mkv, avi, webm), audio (mp3, wav, m4a, flac), and documents (pdf, docx, pptx, txt).
- **Intelligent PDF Handling:** Uses **Docling** as the primary parser for deep document understanding, with fallback to PyMuPDF and an advanced parallel **EasyOCR** pipeline for scanned/image-based documents.
- **Audio/Video Transcription:** Automatic, high-quality transcription using Faster-Whisper.
- **Robust LLM Fallback Chain:** Never goes down! Primary inference through **Gemini**, with automatic fallback to **Groq (Llama)**, and finally local **Ollama** if APIs fail.
- **Advanced Hybrid Retrieval:** Combines sparse (BM25) and dense (ChromaDB) vector search, augmented with **Multi-Query Expansion** and **CrossEncoder Reranking** for high-precision semantic retrieval.
- **Modern UI:** A sleek, fully-featured dark-mode Streamlit frontend with interactive feature cards and real-time processing statistics.
- **Rich Citations:** Natural language Q&A with exact source citations and timestamp references for multimedia.

## Prerequisites

- Python 3.10+
- FFmpeg (required for video/audio processing)
- Ollama (optional, for local LLM fallback and embeddings)

## Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd AI_Multimedia_Assistant
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```
*(Note: Installing PyTorch and EasyOCR may take some time depending on your internet connection)*

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys (Google Gemini, Groq)
```

4. **Create necessary directories:**
```bash
mkdir -p storage/uploads storage/transcripts storage/temp chroma_db
```

## Running the Application

### Backend (FastAPI)
The backend handles all heavy lifting: chunking, OCR, embeddings, and LLM querying.
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Streamlit)
The frontend provides the conversational UI and dashboard.
```bash
cd frontend
streamlit run Home.py
```

## Configuration (.env)

Here is a sample of the key configuration variables:

```env
# Database
DATABASE_URL=sqlite:///./multimedia_assistant.db

# LLM Fallback Chain (Primary -> Secondary -> Local)
LLM_PROVIDER=google
GOOGLE_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
LLM_MODEL=gemini-2.5-flash
OLLAMA_FALLBACK_MODEL=phi3

# Embeddings
EMBEDDING_PROVIDER=huggingface

# OCR Pipeline
OCR_LANGUAGE=en
OCR_DPI=200
OCR_MAX_WORKERS=4

# Whisper settings
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
```

## Architecture Flow

```
Streamlit Frontend
       ↓
REST API (FastAPI)
       ↓
Processing Pipeline
        ├─ Audio/Video → Faster-Whisper Transcription
        ├─ Document Parsing → Docling (Primary) / PyMuPDF (Fallback)
        └─ Scanned PDF → Parallel EasyOCR Pipeline
       ↓
RecursiveCharacterTextSplitter (Optimized Chunking) → Metadata Enrichment
       ↓
Embedding Generation (HuggingFace) → ChromaDB Vector Store
       ↓
Multi-Query Expansion → Hybrid Retriever (BM25 + Chroma) → CrossEncoder Reranker
       ↓
RAG Chain (Gemini → Groq → Ollama) → LLM Response
       ↓
Answer with Document Sources & Timestamps
```

## Usage

1. Start both backend and frontend servers.
2. Navigate to the **Upload** page in the sidebar and add multimedia files.
3. Wait for the automatic processing, transcription, and OCR to complete.
4. Go to the **Chat** page to ask questions about your documents and media.
5. View system statistics on the **Home** dashboard or previous conversations on the **History** page.
