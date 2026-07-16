from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from .system_prompt import SYSTEM_PROMPT

chat_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("""Context:
{context}

Question:
{question}

{format_instruction}

Answer the question based ONLY on the provided context. Ensure you strictly adhere to the formatting rules.""")
])