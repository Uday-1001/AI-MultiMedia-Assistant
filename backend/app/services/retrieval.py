from typing import List, Optional
from langchain_core.documents import Document
from ..vectorstore.chroma import chroma_service
from .embeddings import embedding_service


class RetrievalService:
    """
    Handles searching through the vector database to find the most relevant 
    pieces of information for a given user query.
    """
    def get_retriever(self, search_k: int = 4):
        embeddings = embedding_service.get_embeddings()
        return chroma_service.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": search_k}
        )

    def retrieve_documents(
        self,
        query: str,
        number_of_results: int = 4,
        filter_by_file_id: Optional[int] = None
    ) -> List[Document]:
        """
        Retrieves the top matching documents for a query, optionally filtering by a specific file.
        """
        embeddings = embedding_service.get_embeddings()
        
        where_clause = None
        if filter_by_file_id:
            where_clause = {"document_id": str(filter_by_file_id)}
        
        retriever = chroma_service.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": number_of_results, "filter": where_clause} if where_clause else {"k": number_of_results}
        )
        
        return retriever.invoke(query)


retrieval_service = RetrievalService()