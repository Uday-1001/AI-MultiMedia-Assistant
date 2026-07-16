import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from ..config.settings import settings
from typing import List, Optional
import uuid


class ChromaService:
    _instance = None
    _client = None
    _vectorstore = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, embedding_function: Embeddings):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=Settings(allow_reset=True)
            )
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                client=self._client,
                collection_name=settings.CHROMA_COLLECTION_NAME,
                embedding_function=embedding_function
            )
        return self._vectorstore

    @property
    def vectorstore(self) -> Chroma:
        return self._vectorstore

    def get_collection(self):
        return self._client.get_or_create_collection(settings.CHROMA_COLLECTION_NAME)

    def reset(self):
        if self._client:
            self._client.reset()
            self._vectorstore = None

    def add_documents(self, texts: List[str], metadatas: List[dict], ids: List[str]):
        if self._vectorstore is None:
            raise ValueError("Vectorstore not initialized. Call initialize() first.")
        self._vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def similarity_search(self, query: str, k: int = 4):
        if self._vectorstore is None:
            raise ValueError("Vectorstore not initialized. Call initialize() first.")
        return self._vectorstore.similarity_search(query=query, k=k)

    def similarity_search_with_score(self, query: str, k: int = 4):
        if self._vectorstore is None:
            raise ValueError("Vectorstore not initialized. Call initialize() first.")
        return self._vectorstore.similarity_search_with_score(query=query, k=k)

    def delete(self, ids: Optional[List[str]] = None, where: Optional[dict] = None):
        if self._client is None:
            from ..services.embeddings import embedding_service
            self.initialize(embedding_service.get_embeddings())
        collection = self.get_collection()
        if ids:
            collection.delete(ids=ids)
        elif where:
            collection.delete(where=where)


chroma_service = ChromaService()