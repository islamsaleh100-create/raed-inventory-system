"""
AI Assistant service — wraps OpenAI client + knowledge base loading + suggestion detection.

Used by app/routers/assistant.py.

Design notes:
- Knowledge base is loaded once at module import time (cached).
- Reload only requires server restart (acceptable for MVP).
- Role context is injected per-request into the system prompt.
- Language is auto-detected so the assistant replies in same language.
- The model is instructed to append [SUGGESTION:category:priority] when the
  user message is an improvement suggestion. This service strips the tag from
  the visible answer and persists a UserSuggestion row.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    SuggestionCategory,
    SuggestionPriority,
    UserSuggestion,
)

logger = logging.getLogger(__name__)

KNOWLEDGE_FILE = Path(__file__).resolve().parent / "assistant_knowledge.md"

# Captures something like [SUGGESTION:feature:medium] anywhere in the response
SUGGESTION_TAG_RE = re.compile(
    r"\[SUGGESTION:(?P<category>ui|workflow|bug|feature|other):(?P<priority>low|medium|high)\]",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_knowledge_base() -> str:
    """Read the knowledge base markdown file. Cached for the lifetime of the process."""
    try:
        return KNOWLEDGE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("assistant_knowledge.md not found at %s", KNOWLEDGE_FILE)
        return ""


def _detect_language(text: str) -> str:
    """Return 'ar' or 'en'. Falls back to 'ar' on failure (most users are Arabic-first)."""
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0  # deterministic
        lang = detect(text)
        return "ar" if lang == "ar" else "en"
    except Exception:
        return "ar"


def _build_system_prompt(user_role: str, user_lang: str, branch_name: Optional[str]) -> str:
    """Compose the system prompt: knowledge + role context + language directive + suggestion tag instructions."""
    knowledge = _load_knowledge_base()
    role_context = f"The user's role is: {user_role}."
    if branch_name:
        role_context += f" They work at branch: {branch_name}."

    if user_lang == "ar":
        directive = (
            "أجب بالعربية الفصحى مع لمسة سعودية بسيطة. كن مختصراً و عملياً. "
            "لو السؤال خارج نطاق نظام Raed Inventory، قل ذلك بلطف. "
            "لا تخترع شاشات أو مزايا غير موجودة في الـ Knowledge Base."
        )
    else:
        directive = (
            "Reply in clear, concise English. Be practical. "
            "If the question is outside the Raed Inventory system, say so politely. "
            "Do not invent features or screens not described in the Knowledge Base."
        )

    suggestion_directive = (
        "\n\n─── SUGGESTION DETECTION ───\n"
        "If the user's message is an IMPROVEMENT SUGGESTION, BUG REPORT, FEATURE REQUEST, "
        "or WORKFLOW PAIN POINT (not a how-to question), do BOTH of the following:\n"
        "1. Acknowledge it warmly in 1-2 sentences (e.g., 'شكراً، اقتراحك مهم وتم تسجيله للمراجعة' or 'Thanks, your suggestion has been logged for review').\n"
        "2. At the very END of your reply, on a NEW LINE, append exactly one tag in this format:\n"
        "   [SUGGESTION:<category>:<priority>]\n"
        "   - category: one of ui | workflow | bug | feature | other\n"
        "   - priority: one of low | medium | high (use 'high' only if user describes a blocker)\n"
        "If the message is just a question (not a suggestion), DO NOT add the tag.\n"
        "Examples:\n"
        "- 'كيف أنشئ طلب؟' → just answer, NO tag.\n"
        "- 'الشاشة بطيئة جداً' → acknowledge + [SUGGESTION:bug:medium]\n"
        "- 'أتمنى تضيفوا زرار طباعة' → acknowledge + [SUGGESTION:feature:low]"
    )

    return (
        "You are the Raed Inventory System assistant — a helpful guide for employees "
        "learning to use the system. You answer questions, explain workflows, and "
        "discuss improvement ideas. You do NOT execute actions; you only inform.\n\n"
        f"{role_context}\n\n"
        f"{directive}"
        f"{suggestion_directive}"
        "\n\n─── KNOWLEDGE BASE ───\n"
        f"{knowledge}"
    )


def is_available() -> bool:
    """Check if the assistant can run (feature flag + API key set)."""
    return bool(settings.ASSISTANT_ENABLED and settings.OPENAI_API_KEY)


def _extract_suggestion(answer: str) -> tuple[str, Optional[dict]]:
    """
    If the answer contains a [SUGGESTION:...] tag, strip it and return the parsed
    category + priority. Otherwise return the answer unchanged and None.
    """
    match = SUGGESTION_TAG_RE.search(answer)
    if not match:
        return answer.strip(), None

    cleaned = SUGGESTION_TAG_RE.sub("", answer).strip()
    return cleaned, {
        "category": match.group("category").lower(),
        "priority": match.group("priority").lower(),
    }


def _persist_suggestion(
    db: Session,
    *,
    user_id: int,
    role_at_creation: str,
    branch_id: Optional[int],
    suggestion_text: str,
    category: str,
    priority: str,
) -> int:
    """Insert a UserSuggestion row and return its id."""
    try:
        cat_enum = SuggestionCategory(category)
    except ValueError:
        cat_enum = SuggestionCategory.other
    try:
        pri_enum = SuggestionPriority(priority)
    except ValueError:
        pri_enum = SuggestionPriority.medium

    row = UserSuggestion(
        user_id=user_id,
        role_at_creation=role_at_creation,
        branch_id=branch_id,
        suggestion_text=suggestion_text,
        category=cat_enum,
        priority=pri_enum,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def ask(
    question: str,
    user_role: str,
    *,
    db: Session,
    user_id: int,
    branch_id: Optional[int] = None,
    branch_name: Optional[str] = None,
) -> dict:
    """
    Send a single-turn question to OpenAI and return the answer.

    If the response contains a [SUGGESTION:...] tag, the tag is stripped from
    the visible answer and a UserSuggestion row is persisted.

    Returns:
        {
          "answer": str,
          "language": str,
          "model": str,
          "suggestion_saved": bool,
          "suggestion_id": Optional[int],
          "suggestion_category": Optional[str],
          "suggestion_priority": Optional[str],
        }
    """
    if not is_available():
        raise RuntimeError(
            "AI Assistant is currently unavailable. "
            "Please contact the administrator."
        )

    from openai import OpenAI

    lang = _detect_language(question)
    system_prompt = _build_system_prompt(user_role, lang, branch_name)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=settings.ASSISTANT_TEMPERATURE,
            max_tokens=settings.ASSISTANT_MAX_TOKENS,
        )
    except Exception as exc:
        logger.exception("OpenAI call failed")
        raise RuntimeError(f"AI Assistant error: {exc}") from exc

    raw_answer = (completion.choices[0].message.content or "").strip()
    cleaned_answer, suggestion = _extract_suggestion(raw_answer)

    suggestion_saved = False
    suggestion_id: Optional[int] = None
    suggestion_category: Optional[str] = None
    suggestion_priority: Optional[str] = None

    if suggestion is not None:
        try:
            suggestion_id = _persist_suggestion(
                db,
                user_id=user_id,
                role_at_creation=user_role,
                branch_id=branch_id,
                suggestion_text=question,
                category=suggestion["category"],
                priority=suggestion["priority"],
            )
            suggestion_saved = True
            suggestion_category = suggestion["category"]
            suggestion_priority = suggestion["priority"]
        except Exception:
            logger.exception("Failed to persist user suggestion (non-fatal)")
            db.rollback()

    return {
        "answer": cleaned_answer,
        "language": lang,
        "model": settings.OPENAI_MODEL,
        "suggestion_saved": suggestion_saved,
        "suggestion_id": suggestion_id,
        "suggestion_category": suggestion_category,
        "suggestion_priority": suggestion_priority,
    }
