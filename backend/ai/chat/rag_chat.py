"""
ai/chat/rag_chat.py
RAG pipeline: retrieve relevant transcript chunks → answer with Groq LLM.
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from ai.embeddings.chroma import RetrievedChunk, retrieve_chunks
from config.settings import settings

log = structlog.get_logger(__name__)

_MAX_CONTEXT_CHARS = 6000


@dataclass
class ChatAnswer:
    answer: str
    sources: list[dict]
    model_used: str


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Assemble retrieved chunks into a context block for the LLM prompt."""
    parts: list[str] = []
    total = 0
    for c in chunks:
        speaker_prefix = f"[{c.speaker}] " if c.speaker else ""
        time_prefix = f"[{c.start_time:.0f}s] " if c.start_time else ""
        line = f"**{c.meeting_title}** — {time_prefix}{speaker_prefix}{c.text}"
        if total + len(line) > _MAX_CONTEXT_CHARS:
            break
        parts.append(line)
        total += len(line)
    return "\n\n".join(parts)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=8))
def answer_question(
    question: str,
    workspace_id: str,
    meeting_ids: list[str] | None = None,
    top_k: int = 5,
) -> ChatAnswer:
    """
    Full RAG pipeline:
    1. Embed question
    2. Retrieve top-k transcript chunks from ChromaDB
    3. Send context + question to Groq LLM
    4. Return structured answer with source citations
    """
    # ── Retrieve ─────────────────────────────────────────────
    chunks = retrieve_chunks(
        query=question,
        workspace_id=workspace_id,
        meeting_ids=meeting_ids,
        top_k=top_k,
    )

    if not chunks:
        return ChatAnswer(
            answer="I couldn't find relevant information in the meeting transcripts for your question. Try uploading and processing more meetings, or rephrase your query.",
            sources=[],
            model_used=settings.groq_model,
        )

    context = _build_context(chunks)

    # ── Prompt ───────────────────────────────────────────────
    system = SystemMessage(content=(
        "You are MeetingMind AI, an intelligent meeting assistant. "
        "Answer questions based ONLY on the provided meeting transcript context. "
        "Be specific — quote names, numbers, and decisions from the context. "
        "If the answer isn't in the context, say so honestly. "
        "Format your response clearly with bullet points or numbered lists where appropriate."
    ))

    user_prompt = f"""Based on the following meeting transcript excerpts, answer the question.

CONTEXT FROM MEETINGS:
{context}

QUESTION: {question}

Provide a clear, specific answer based on the meeting context above."""

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=0.1,
        max_tokens=1500,
        timeout=30,
    )

    log.info("rag_chat_invoke", question=question[:80], chunks_used=len(chunks))
    response = llm.invoke([system, HumanMessage(content=user_prompt)])

    # ── Sources ──────────────────────────────────────────────
    sources = [
        {
            "meeting_id": c.meeting_id,
            "meeting_title": c.meeting_title,
            "speaker": c.speaker,
            "start_time": c.start_time,
            "relevance_score": round(1 - c.score, 3),  # convert distance to similarity
            "excerpt": c.text[:150] + "..." if len(c.text) > 150 else c.text,
        }
        for c in chunks[:3]   # top 3 sources only
    ]

    log.info("rag_chat_done", answer_chars=len(response.content))
    return ChatAnswer(
        answer=response.content.strip(),
        sources=sources,
        model_used=settings.groq_model,
    )
