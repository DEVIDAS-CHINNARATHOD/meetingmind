"""
ai/summarization/groq_llm.py
Groq-powered LLM calls for summary, MoM, and action item extraction.
Uses LangChain Groq integration with structured output parsing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import structlog
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import settings

log = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════
# LLM client factory
# ═══════════════════════════════════════════════════════════════

def _get_llm(temperature: float = 0.2) -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=temperature,
        max_tokens=4096,
        timeout=60,
    )


# ═══════════════════════════════════════════════════════════════
# Data classes for structured outputs
# ═══════════════════════════════════════════════════════════════

@dataclass
class ActionItem:
    task: str
    assigned_to: str | None
    deadline: str | None
    priority: str  # low | medium | high


@dataclass
class SummaryResult:
    summary: str
    key_decisions: list[str]
    topics: list[str]
    action_items: list[ActionItem]


@dataclass
class MomResult:
    title: str
    markdown: str   # Full MoM in Markdown, ready for PDF/DOCX conversion


# ═══════════════════════════════════════════════════════════════
# Retry decorator
# ═══════════════════════════════════════════════════════════════

_retry = retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)


# ═══════════════════════════════════════════════════════════════
# Prompt helpers
# ═══════════════════════════════════════════════════════════════

def _truncate_transcript(transcript: str, max_chars: int = 12000) -> str:
    """Truncate long transcripts, preserving start and end context."""
    if len(transcript) <= max_chars:
        return transcript
    half = max_chars // 2
    return (
        transcript[:half]
        + "\n\n[... middle truncated for length ...]\n\n"
        + transcript[-half:]
    )


def _parse_json_block(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code fences."""
    text = text.strip()
    # Strip ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


# ═══════════════════════════════════════════════════════════════
# Summary generation
# ═══════════════════════════════════════════════════════════════

@_retry
def generate_summary(transcript: str, title: str = "") -> SummaryResult:
    """
    Generate a structured summary from a meeting transcript.
    Returns a SummaryResult with summary text, decisions, topics, and action items.
    """
    llm = _get_llm(temperature=0.1)
    truncated = _truncate_transcript(transcript)

    system = SystemMessage(content=(
        "You are MeetingMind AI, an expert meeting analyst. "
        "Analyze meeting transcripts and extract structured information. "
        "Always respond with valid JSON only — no preamble, no markdown fences."
    ))

    prompt = f"""Analyze this meeting transcript and return a JSON object with exactly these fields:

{{
  "summary": "2-3 paragraph executive summary of the meeting",
  "key_decisions": ["decision 1", "decision 2", ...],
  "topics": ["topic 1", "topic 2", ...],
  "action_items": [
    {{
      "task": "clear description of what needs to be done",
      "assigned_to": "person name or null",
      "deadline": "date string or null",
      "priority": "low|medium|high"
    }}
  ]
}}

Meeting title: {title or "Untitled Meeting"}

Transcript:
{truncated}

Return ONLY the JSON object."""

    log.info("llm_summary_start", title=title, chars=len(truncated))
    response = llm.invoke([system, HumanMessage(content=prompt)])
    raw = response.content

    try:
        data = _parse_json_block(raw)
    except json.JSONDecodeError as e:
        log.error("llm_json_parse_failed", error=str(e), raw_preview=raw[:200])
        raise ValueError(f"LLM returned invalid JSON: {e}")

    items = [
        ActionItem(
            task=a.get("task", ""),
            assigned_to=a.get("assigned_to"),
            deadline=a.get("deadline"),
            priority=a.get("priority", "medium"),
        )
        for a in data.get("action_items", [])
        if a.get("task")
    ]

    log.info(
        "llm_summary_done",
        decisions=len(data.get("key_decisions", [])),
        actions=len(items),
        topics=len(data.get("topics", [])),
    )

    return SummaryResult(
        summary=data.get("summary", ""),
        key_decisions=data.get("key_decisions", []),
        topics=data.get("topics", []),
        action_items=items,
    )


# ═══════════════════════════════════════════════════════════════
# Minutes of Meeting generation
# ═══════════════════════════════════════════════════════════════

@_retry
def generate_mom(
    transcript: str,
    title: str,
    participants: list[str],
    date_str: str = "",
    duration_str: str = "",
) -> MomResult:
    """
    Generate a professional Minutes of Meeting document in Markdown.
    The Markdown output can be rendered to PDF or DOCX downstream.
    """
    llm = _get_llm(temperature=0.15)
    truncated = _truncate_transcript(transcript, max_chars=14000)
    participants_str = ", ".join(participants) if participants else "Not specified"

    system = SystemMessage(content=(
        "You are a professional corporate secretary generating formal Minutes of Meeting. "
        "Write in clear, professional, third-person tone. "
        "Use Markdown formatting with proper headings and lists."
    ))

    prompt = f"""Generate a complete, professional Minutes of Meeting document in Markdown format.

Meeting Details:
- Title: {title}
- Date: {date_str or "As per recording"}
- Duration: {duration_str or "As per recording"}
- Participants: {participants_str}

Transcript:
{truncated}

The MoM must include ALL of these sections in order:
1. # Minutes of Meeting — {title}
2. ## Meeting Details (date, time, duration, participants table)
3. ## Agenda Items Discussed
4. ## Key Discussion Points (by topic)
5. ## Decisions Made (numbered list)
6. ## Action Items (table with: Task | Assigned To | Deadline | Priority)
7. ## Next Steps
8. ## Conclusion

Use professional, concise language. Be specific — include actual numbers, names, and decisions from the transcript."""

    log.info("llm_mom_start", title=title, participants=len(participants))
    response = llm.invoke([system, HumanMessage(content=prompt)])
    markdown = response.content.strip()

    log.info("llm_mom_done", chars=len(markdown))
    return MomResult(title=title, markdown=markdown)
