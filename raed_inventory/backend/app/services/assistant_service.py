"""
AI Assistant service — wraps OpenAI client + knowledge base loading.

Used by app/routers/assistant.py.

Design notes:
- Knowledge base is loaded once at module import time (cached).
- Reload only requires server restart (acceptable for MVP).
- Role context is injected per-request into the system prompt.
- Language is auto-detected so the assistant replies in same language.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

KNOWLEDGE_FILE = Path(__file__).resolve().parent / "assistant_knowledge.md"


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
    """Compose the system prompt: knowledge + role context + language directive."""
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

    return (
        "You are the Raed Inventory System assistant — a helpful guide for employees "
        "learning to use the system. You answer questions, explain workflows, and "
        "discuss improvement ideas. You do NOT execute actions; you only inform.\n\n"
        f"{role_context}\n\n"
        f"{directive}\n\n"
        "─── KNOWLEDGE BASE ───\n"
        f"{knowledge}"
    )


def is_available() -> bool:
    """Check if the assistant can run (feature flag + API key set)."""
    return bool(settings.ASSISTANT_ENABLED and settings.OPENAI_API_KEY)


def ask(
    question: str,
    user_role: str,
    branch_name: Optional[str] = None,
) -> dict:
    """
    Send a single-turn question to OpenAI and return the answer.

    Returns: {"answer": str, "language": str, "model": str}
    Raises: RuntimeError if assistant is not available or API call fails.
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

    answer = (completion.choices[0].message.content or "").strip()
    return {
        "answer": answer,
        "language": lang,
        "model": settings.OPENAI_MODEL,
    }
