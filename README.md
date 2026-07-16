# AI Multimedia Knowledge Assistant

A production-ready Retrieval-Augmented Generation (RAG) assistant capable of understanding multimedia content using **Streamlit + FastAPI + LangChain + PostgreSQL + ChromaDB + Faster-Whisper**.

## Features

- Upload and process videos (mp4, mov, mkv, avi, webm)
- Upload and process audio files (mp3, wav, m4a, flac)
- Upload and process documents (pdf, docx, pptx, txt)
- Automatic transcription for audio/video using Faster-Whisper
- Text extraction for documents using LangChain loaders
- Embedding generation with configurable providers (Ollama/HuggingFace)
- Natural language Q&A with source citations
- Timestamp references for multimedia content
- Conversation history tracking

## Prerequisites

- Python 3.10+
- PostgreSQL
- FFmpeg (for video/audio processing)
- Ollama (optional, for local LLM/embeddings)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd AI_Multimedia_Assistant
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Set up PostgreSQL database:
```bash
# Create database
createdb multimedia_assistant
# Or use your preferred PostgreSQL tool
```

5. Create necessary directories:
```bash
mkdir -p storage/uploads storage/transcripts storage/temp chroma_db
```

## Running the Application

### Backend (FastAPI)
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Streamlit)
```bash
cd frontend
streamlit run Home.py
```

## Configuration (.env)

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/multimedia_assistant

# LLM Provider (groq or ollama)
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here

# Embedding Provider (ollama or huggingface)
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Whisper settings
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /upload/ | POST | Upload a file |
| /upload/{id}/process | POST | Process uploaded file |
| /chat/ | POST | Ask a question |
| /history/sessions | GET | Get chat sessions |
| /history/documents | GET | Get uploaded documents |
| /history/document/{id} | DELETE | Delete a document |
| /health | GET | Health check |

## Architecture

```
Streamlit Frontend
       ↓
REST API (FastAPI)
       ↓
Upload Service
       ↓
Processing Pipeline
       ↓
LangChain Document Loaders → RecursiveCharacterTextSplitter → Metadata Enrichment
       ↓
Embedding Generation → ChromaDB Vector Store
       ↓
Retriever → RAG Chain → LLM
       ↓
Answer with Sources
```

## Project Structure

```
AI_Multimedia_Assistant/
├── frontend/
│   ├── Home.py
│   └── pages/
│       ├── Upload.py
│       ├── Chat.py
│       └── History.py
├── backend/
│   └── app/
│       ├── api/
│       ├── services/
│       ├── prompts/
│       ├── vectorstore/
│       ├── database/
│       └── main.py
├── storage/
│   ├── uploads/
│   ├── transcripts/
│   └── temp/
├── database/
├── chroma_db/
├── requirements.txt
└── .env.example
```

## Usage

1. Start both backend and frontend
2. Navigate to the Upload page and add multimedia files
3. Wait for automatic processing
4. Go to the Chat page to ask questions
5. View history on the History page