from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from ..config.settings import settings
from typing import Optional


class EmbeddingService:
    """
    Manages the creation of text embeddings (numerical representations of text) 
    using either local models (Ollama) or HuggingFace.
    """
    _instance = None
    _embeddings: Optional[Embeddings] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_embeddings(self) -> Embeddings:
        if self._embeddings is None:
            if settings.EMBEDDING_PROVIDER == "ollama":
                self._embeddings = OllamaEmbeddings(
                    base_url=settings.OLLAMA_BASE_URL,
                    model=settings.OLLAMA_EMBEDDING_MODEL
                )
            elif settings.EMBEDDING_PROVIDER == "huggingface":
                self._embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
            else:
                raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER}")
        
        return self._embeddings

    def get_embeddings_for_provider(self, provider: str, model_name: Optional[str] = None) -> Embeddings:
        if provider == "ollama":
            return OllamaEmbeddings(
                base_url=settings.OLLAMA_BASE_URL,
                model=model_name or settings.OLLAMA_EMBEDDING_MODEL
            )
        elif provider == "huggingface":
            return HuggingFaceEmbeddings(
                model_name=model_name or "sentence-transformers/all-MiniLM-L6-v2"
            )
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")


embedding_service = EmbeddingService()