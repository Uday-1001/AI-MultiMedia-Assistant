# Hybrid search pipeline: Vector + Keyword search, reranked for better accuracy

from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker

from ..vectorstore.chroma import chroma_service

logger = logging.getLogger(__name__)

# Limit BM25 index size to avoid memory issues
_BM25_MAX_CORPUS = 5_000

# Global reranker model (do not mutate per request)

try:
    _cross_encoder_model = HuggingFaceCrossEncoder(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    _RERANKER_AVAILABLE = True
    logger.info("Cross-Encoder reranker loaded: ms-marco-MiniLM-L-6-v2")
except Exception as _reranker_err:
    _cross_encoder_model = None
    _RERANKER_AVAILABLE = False
    logger.warning(
        "CrossEncoder reranker unavailable (%s). "
        "Retrieval will use EnsembleRetriever without reranking.",
        _reranker_err,
    )


class RetrievalService:
    # Handles vector + keyword hybrid search with fallback logic



    def get_retriever(
        self,
        search_k: int = 4,
        filter_by_file_id: Optional[int] = None,
    ):
        where_clause = (
            {"document_id": str(filter_by_file_id)}
            if filter_by_file_id
            else None
        )

        # Fetch more candidates for reranker input (2×)
        candidate_k = search_k * 2 if _RERANKER_AVAILABLE else search_k

        # Setup vector search
        vector_retriever = chroma_service.vectorstore.as_retriever( # type: ignore
            search_type="similarity",
            search_kwargs={
                "k":      candidate_k,
                **({"filter": where_clause} if where_clause else {}),
            },
        )

        # Setup keyword search
        bm25_retriever = self._build_bm25_retriever(
            filter_by_file_id=filter_by_file_id,
            k=candidate_k,
        )

        # Combine results favoring semantic matches
        if bm25_retriever is not None:
            base_retriever = EnsembleRetriever(
                retrievers=[bm25_retriever, vector_retriever],
                weights=[0.4, 0.6],         # slight preference for semantic
            )
        else:
            logger.debug("BM25 retriever unavailable — using vector-only retrieval.")
            base_retriever = vector_retriever

        # Rerank combined results
        if _RERANKER_AVAILABLE and _cross_encoder_model is not None:
            # Use a fresh reranker instance for thread safety
            reranker = CrossEncoderReranker(
                model=_cross_encoder_model,
                top_n=search_k,
            )
            return ContextualCompressionRetriever(
                base_compressor=reranker,
                base_retriever=base_retriever,
            )

        return base_retriever

    def retrieve_documents(
        self,
        query: str,
        number_of_results: int = 4,
        filter_by_file_id: Optional[int] = None,
    ) -> List[Document]:
        # Get the top matching documents for a query
        retriever = self.get_retriever(
            search_k=number_of_results,
            filter_by_file_id=filter_by_file_id,
        )
        return retriever.invoke(query)



    def _build_bm25_retriever(
        self,
        filter_by_file_id: Optional[int] = None,
        k: int = 4,
    ) -> Optional[BM25Retriever]:
        # Build a temporary BM25 index for keyword search, failing gracefully
        try:
            where_clause = (
                {"document_id": str(filter_by_file_id)}
                if filter_by_file_id
                else None
            )

            fetch_kwargs: dict = {"limit": _BM25_MAX_CORPUS}
            if where_clause:
                fetch_kwargs["where"] = where_clause

            raw = chroma_service.vectorstore.get(**fetch_kwargs) # type: ignore

            texts     = raw.get("documents") or []
            metadatas = raw.get("metadatas") or []

            if not texts:
                logger.debug("BM25: ChromaDB returned no documents — skipping BM25.")
                return None

            corpus = [
                Document(
                    page_content=text,
                    metadata=metadatas[i] if i < len(metadatas) else {},
                )
                for i, text in enumerate(texts)
                if text and text.strip()
            ]

            if not corpus:
                return None

            bm25 = BM25Retriever.from_documents(corpus)
            bm25.k = k
            logger.debug("BM25: index built from %d documents.", len(corpus))
            return bm25

        except Exception as exc:
            logger.error("Failed to build BM25 retriever: %s", exc)
            return None


retrieval_service = RetrievalService()