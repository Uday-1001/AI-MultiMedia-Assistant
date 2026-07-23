from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="sqlite:///./multimedia_assistant.db")
    CHROMA_PERSIST_DIRECTORY: str = Field(default="./chroma_db")
    CHROMA_COLLECTION_NAME: str = Field(default="multimedia_knowledge")
    
    LLM_PROVIDER: str = Field(default="google")
    GROQ_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    LLM_MODEL: str = Field(default="gemini-3.6-flash")
    OLLAMA_FALLBACK_MODEL: str = Field(default="phi3")
    
    EMBEDDING_PROVIDER: str = Field(default="huggingface")
    OLLAMA_EMBEDDING_MODEL: str = Field(default="nomic-embed-text")
    
    WHISPER_MODEL_SIZE: str = Field(default="medium")
    WHISPER_DEVICE: str = Field(default="cpu")
    
    UPLOAD_DIR: str = Field(default="./storage/uploads")
    TRANSCRIPT_DIR: str = Field(default="./storage/transcripts")
    TEMP_DIR: str = Field(default="./storage/temp")
    
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_RELOAD: bool = Field(default=True)
    
    FRONTEND_PORT: int = Field(default=8501)

    OCR_DPI: int = Field(default=400)
    OCR_LANGUAGE: str = Field(default="en")
    OCR_SCANNED_CHAR_THRESHOLD: int = Field(default=10)
    OCR_MAX_WORKERS: int = Field(default=0)

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.env")
        case_sensitive = False
        extra = "ignore"


settings = Settings()