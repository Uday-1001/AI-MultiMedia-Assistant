import os
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from .retrieval import retrieval_service
from .embeddings import embedding_service
from ..vectorstore.chroma import chroma_service
from ..prompts.chat_prompt import chat_prompt
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Friendly names shown in logs and user-facing messages
PROVIDER_DISPLAY_NAMES = {
    "google": "Gemini (Google AI)",
    "gemini": "Gemini (Google AI)",
    "groq":   "Groq (Llama)",
    "ollama": "Ollama (local model)",
}


class RAGChainService:
    """
    Handles the full Retrieval-Augmented Generation (RAG) pipeline.
    Supports automatic fallback across multiple LLM providers so that
    a single API hiccup never leaves the user without an answer.

    Fallback order (skipping providers with no credentials configured):
      1. Primary provider set in LLM_PROVIDER (.env)
      2. Groq  — if GROQ_API_KEY is present
      3. Ollama — always available as a last resort (local)
    """

    _instance = None
    _chain = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── LLM helpers ──────────────────────────────────────────────────────────

    def _build_gemini(self) -> Any:
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = (
            settings.GOOGLE_API_KEY
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        if not api_key:
            raise ValueError("No Google/Gemini API key found. Set GOOGLE_API_KEY in your .env file.")
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            api_key=api_key,
            temperature=0.1,
        )

    def _build_groq(self) -> Any:
        if not settings.GROQ_API_KEY:
            raise ValueError("No Groq API key found. Set GROQ_API_KEY in your .env file.")
        return ChatGroq(
            groq_api_key=settings.GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",  # Updated — llama3-70b-8192 was decommissioned
            temperature=0.1,
        )

    def _build_ollama(self) -> Any:
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_FALLBACK_MODEL,
            temperature=0.1,
        )

    def _get_llm(self):
        """Returns the primary LLM object configured in .env."""
        provider = settings.LLM_PROVIDER
        if provider in ["google", "gemini"]:
            return self._build_gemini()
        elif provider == "groq":
            return self._build_groq()
        elif provider == "ollama":
            return self._build_ollama()
        else:
            raise ValueError(
                f"'{provider}' is not a recognised LLM provider. "
                "Please set LLM_PROVIDER to 'google', 'groq', or 'ollama' in your .env file."
            )

    def _get_fallback_providers(self) -> List[str]:
        """
        Returns an ordered list of fallback providers to try when the primary one fails.
        A provider is included only if its credentials are actually configured.
        """
        primary = settings.LLM_PROVIDER
        candidates = []

        # Groq — only if a key is set
        if primary != "groq" and settings.GROQ_API_KEY:
            candidates.append("groq")

        # Ollama — always available locally, but try last
        if primary != "ollama":
            candidates.append("ollama")

        return candidates

    def _build_llm_for_provider(self, provider: str) -> Any:
        if provider in ["google", "gemini"]:
            return self._build_gemini()
        elif provider == "groq":
            return self._build_groq()
        elif provider == "ollama":
            return self._build_ollama()
        raise ValueError(f"Unknown provider: {provider}")

    def _invoke_with_fallback(self, formatted_prompt: str) -> Tuple[str, str]:
        """
        Tries the primary LLM first, then works through the fallback list.
        Returns (answer_text, provider_name_used).

        Raises RuntimeError only when every configured provider has failed.
        """
        primary = settings.LLM_PROVIDER
        providers_to_try = [primary] + self._get_fallback_providers()

        last_error = None
        for provider in providers_to_try:
            display_name = PROVIDER_DISPLAY_NAMES.get(provider, provider)
            try:
                logger.info("Sending request to %s...", display_name)
                llm = self._build_llm_for_provider(provider)
                response = llm.invoke(formatted_prompt)
                if provider != primary:
                    logger.info(
                        "Primary provider (%s) failed. Answer generated by fallback: %s.",
                        PROVIDER_DISPLAY_NAMES.get(primary, primary),
                        display_name,
                    )
                return response.content, provider
            except Exception as provider_error:
                last_error = provider_error
                logger.warning(
                    "%s could not answer this time (%s). Trying next option...",
                    display_name,
                    provider_error,
                )

        # All providers exhausted — give the user a clear, friendly message
        raise RuntimeError(
            "Our AI assistant is taking a short break right now and couldn't generate a response. "
            "This usually happens when there's a connectivity issue or an API limit has been reached. "
            "Please wait a moment and try again — we'll be back up shortly!"
        )

    # ── Format helpers ────────────────────────────────────────────────────────

    def _get_format_instruction(self, query: str) -> str:
        query_lower = query.lower()
        if "summary" in query_lower or "summarize" in query_lower:
            return "Use the SUMMARY Response Format."
        elif "revision notes" in query_lower or "notes" in query_lower:
            return "Use the REVISION NOTES Response Format."
        elif "flashcard" in query_lower:
            return "Use the FLASHCARDS Response Format."
        elif "quiz" in query_lower or "mcq" in query_lower:
            return "Use the QUIZ Response Format."
        elif "compare" in query_lower or "difference" in query_lower:
            return "Use the COMPARISON Response Format."
        elif "define" in query_lower or "definition" in query_lower:
            return "Use the DEFINITIONS Response Format."
        elif "algorithm" in query_lower or "procedure" in query_lower or "steps" in query_lower:
            return "Use the ALGORITHMS / PROCEDURES Response Format."
        elif "code" in query_lower or "program" in query_lower:
            return "Use the PROGRAMMING QUESTIONS Response Format."
        else:
            return "Use the GENERAL RESPONSE FORMAT."

    def _format_docs(self, documents: List) -> str:
        formatted = []
        for document in documents:
            source = document.metadata.get("filename", "Unknown")
            source_type = document.metadata.get("source_type", "document")

            metadata_str = f"Document:\n{source}\n"

            if source_type in ["video", "audio"]:
                timestamp_start = document.metadata.get("timestamp_start")
                timestamp_end = document.metadata.get("timestamp_end")
                if timestamp_start and timestamp_end:
                    metadata_str += f"\nTimestamp:\n{timestamp_start}s - {timestamp_end}s\n"

            formatted.append(f"{metadata_str}\nContent:\n{document.page_content}")

        return "\n\n-------------------------------------\n\n".join(formatted)

    # ── Chain setup ───────────────────────────────────────────────────────────

    def _build_chain(self):
        """Builds the LangChain retrieval pipeline using the primary LLM."""
        language_model = self._get_llm()

        def retrieve_and_format(query: str) -> dict:
            if isinstance(query, dict):
                query_text = query.get("question", query.get("query", ""))
            else:
                query_text = query

            retrieved_documents = retrieval_service.retrieve_documents(query_text)
            context = self._format_docs(retrieved_documents)

            sources = list(set(
                document.metadata.get("filename", "Unknown")
                for document in retrieved_documents
            ))
            timestamps = [
                {
                    "filename": document.metadata.get("filename"),
                    "start": document.metadata.get("timestamp_start"),
                    "end": document.metadata.get("timestamp_end"),
                }
                for document in retrieved_documents
                if document.metadata.get("timestamp_start") and document.metadata.get("timestamp_end")
            ]

            return {
                "context": context,
                "question": query_text,
                "format_instruction": self._get_format_instruction(query_text),
                "sources": sources,
                "timestamps": timestamps,
            }

        self._chain = (
            RunnableLambda(retrieve_and_format)
            | chat_prompt
            | language_model
            | StrOutputParser()
        )

    def initialize(self):
        if not chroma_service.vectorstore:
            embedding_service.get_embeddings()
            chroma_service.initialize(embedding_service.get_embeddings())
        self._build_chain()

    # ── Public entry point ────────────────────────────────────────────────────

    def invoke(self, query: str, file_id: Optional[int] = None) -> Dict[str, Any]:
        """
        The main entry point for the AI.

        1. Retrieves the most relevant document chunks for the query.
        2. Builds a prompt with the context and question.
        3. Sends it to the primary LLM. If that fails, automatically retries
           with each configured fallback provider (Groq → Ollama) until one succeeds.
        4. Returns the answer along with source citations and timestamps.
        """
        if self._chain is None:
            self.initialize()

        retrieved_documents = retrieval_service.retrieve_documents(query, filter_by_file_id=file_id)
        context = self._format_docs(retrieved_documents)

        sources = list(set(
            document.metadata.get("filename", "Unknown")
            for document in retrieved_documents
        ))
        timestamps = [
            {
                "filename": document.metadata.get("filename"),
                "start": document.metadata.get("timestamp_start"),
                "end": document.metadata.get("timestamp_end"),
            }
            for document in retrieved_documents
            if document.metadata.get("timestamp_start") and document.metadata.get("timestamp_end")
        ]

        format_instruction = self._get_format_instruction(query)
        formatted_prompt = chat_prompt.format(
            context=context,
            question=query,
            format_instruction=format_instruction,
        )

        # Try the primary provider first, then fall back automatically
        answer, provider_used = self._invoke_with_fallback(formatted_prompt)

        # If a fallback stepped in, let the user know in a friendly, non-technical way
        provider_note = ""
        if provider_used != settings.LLM_PROVIDER:
            provider_note = (
                "\n\n---\n"
                "_🔄 Just so you know — our primary AI assistant had a small hiccup, "
                "so a backup assistant stepped in and answered this for you. "
                "The answer is just as accurate — you might not even notice the difference!_"
            )

        return {
            "answer": answer + provider_note,
            "sources": sources,
            "timestamps": timestamps,
            "context_used": context[:500],
            "provider_used": provider_used,
        }


rag_chain_service = RAGChainService()