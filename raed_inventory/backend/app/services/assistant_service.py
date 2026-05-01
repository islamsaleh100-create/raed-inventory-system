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
    """Compose the system prompt: knowledge + role context + language directive + suggestion classification."""
    knowledge = _load_knowledge_base()
    role_context = f"The user's role is: {user_role}."
    if branch_name:
        role_context += f" They work at branch: {branch_name}."

    # ─── LANGUAGE DIRECTIVE — Strict ───
    if user_lang == "ar":
        language_directive = (
            "─── قواعد اللغة (إلزامية) ───\n"
            "1. ردّك يجب أن يكون عربياً صرفاً. ممنوع منعاً باتاً وضع كلمات إنجليزية داخل الجملة العربية.\n"
            "2. حتى لو رأيت مصطلحاً إنجليزياً في قاعدة المعرفة (Knowledge Base) أو في سؤال المستخدم، "
            "ترجمه إلى العربية في ردك. لا تنسخ المصطلح الإنجليزي.\n"
            "3. حتى لو المستخدم كتب 'submit' أو 'item' أو 'area_manager' في سؤاله، "
            "ردّ باستخدام المرادف العربي.\n"
            "4. الاستثناء الوحيد: أسماء البراندات التجارية (Onda, Ronaldos, Shawarma, Griddle) — "
            "هذه أسماء علامات تجارية تُكتب كما هي.\n\n"
            "─── جدول الترجمة (الزم به) ───\n"
            "أسماء الشاشات و الأزرار:\n"
            "  Submit → إرسال\n"
            "  Save as Draft → حفظ كمسودة\n"
            "  New Request → طلب جديد\n"
            "  Add Item → إضافة صنف\n"
            "  Item / item → صنف (أو مادة)\n"
            "  Approvals → الموافقات\n"
            "  Production Orders → أوامر الإنتاج\n"
            "  Warehouse Lines → سطور المستودع\n"
            "  Delivery → التوصيل\n"
            "  Receiving → الاستلام\n"
            "  Dashboard → لوحة المعلومات\n"
            "  Login → تسجيل الدخول\n"
            "  Logout → تسجيل الخروج\n"
            "  Cart → السلة\n"
            "  Quantity → الكمية\n"
            "  Status → الحالة\n"
            "  Note → ملاحظة\n"
            "  Branch → فرع\n"
            "  Warehouse → مستودع\n"
            "  Kitchen → مطبخ\n\n"
            "أسماء الأدوار (لا تتركها بالإنجليزي أبداً):\n"
            "  super_admin → المدير العام\n"
            "  admin → المسؤول\n"
            "  operations_manager → مدير العمليات\n"
            "  area_manager → مدير المنطقة\n"
            "  branch_manager → مدير الفرع\n"
            "  branch_user → موظف الفرع\n"
            "  warehouse_manager → مدير المستودع\n"
            "  warehouse_user → موظف المستودع\n"
            "  kitchen_section_manager → مدير قسم المطبخ\n"
            "  delivery_user → موظف التوصيل\n"
            "  quality_manager → مدير الجودة\n"
            "  internal_auditor → المراجع الداخلي\n"
            "  sales_manager → مدير المبيعات\n"
            "  hr_manager → مدير الموارد البشرية\n\n"
            "أسماء الحالات:\n"
            "  DRAFT → مسودة\n"
            "  SUBMITTED → مُرسَل\n"
            "  AREA_APPROVED → موافَق عليه\n"
            "  AREA_REJECTED → مرفوض\n"
            "  WAITING_WAREHOUSE → بانتظار المستودع\n"
            "  WAITING_PRODUCTION → بانتظار الإنتاج\n"
            "  IN_PRODUCTION → قيد الإنتاج\n"
            "  READY_FOR_DELIVERY → جاهز للتوصيل\n"
            "  OUT_FOR_DELIVERY → في الطريق\n"
            "  DELIVERED → تم التسليم\n"
            "  RECEIVED → تم الاستلام\n\n"
            "─── إذا رأيت إنجليزياً في قاعدة المعرفة ───\n"
            "قاعدة المعرفة تحتوي على أقسام عربية و أقسام إنجليزية. عند الرد بالعربية، "
            "استخدم فقط محتوى الأقسام العربية. إذا اضطررت لذكر مصطلح إنجليزي ورد فقط في "
            "الأقسام الإنجليزية، ترجمه باستخدام الجدول أعلاه.\n\n"
            "─── أسلوب الرد ───\n"
            "استخدم العربية الفصحى السهلة مع لمسة سعودية بسيطة. كن مختصراً و عملياً. "
            "ردّك المثالي 2-5 جمل، أو قائمة خطوات مرقّمة لأسئلة 'كيف أعمل كذا'."
        )
    else:
        language_directive = (
            "─── LANGUAGE RULES ───\n"
            "Respond in pure English. Do not mix Arabic words into English sentences. "
            "Use the system's English UI labels: New Request, Submit, Approvals, etc. "
            "Be clear and concise. Ideal reply: 2-5 sentences, or a numbered list "
            "for 'how do I' questions."
        )

    # ─── CLASSIFIER — Balanced rules (escape patterns + semantic) ───
    suggestion_directive = (
        "\n\n─── HOW TO CLASSIFY THE USER'S MESSAGE ───\n"
        "Decide if the message is:\n"
        "  (A) a QUESTION — user wants info or help, OR\n"
        "  (B) a SUGGESTION — user is reporting a problem or proposing a change.\n\n"
        "═══ ALWAYS-SUGGESTION patterns (override everything) ═══\n"
        "If the message contains any of these intents, classify as SUGGESTION even "
        "if it's phrased as a question:\n\n"
        "  WISH/DESIRE: 'أتمنى', 'ياريت', 'يا حبذا', 'لو فيه', 'I wish', 'I hope', "
        "    'it would be nice if', 'لو ممكن تضيفوا', 'محتاجين خاصية', 'we need a feature'\n"
        "    → category: feature, priority: low (or medium if user emphasizes)\n\n"
        "  COMPLAINT/BROKEN: 'بطيء/ة', 'بتعلق', 'مش شغال', 'مكسور', 'بياخد وقت', "
        "    'broken', 'doesn't work', 'frozen', 'slow', 'crashing', 'lag'\n"
        "    → category: bug, priority: medium (or high if user says 'مستحيل أكمل شغلي')\n\n"
        "  PAIN POINT: 'الخطوة دي مرهقة', 'صعب', 'معقد', 'مزعج', 'painful', "
        "    'frustrating', 'too many clicks'\n"
        "    → category: workflow, priority: medium\n\n"
        "  EXPLICIT PROPOSAL: 'أقترح', 'I suggest', 'يفضل تكون', 'should be', "
        "    'بدل ما', 'instead of'\n"
        "    → category: depends on context (ui/workflow/feature), priority: medium\n\n"
        "═══ ALWAYS-QUESTION patterns ═══\n"
        "If the message is one of these, it's a QUESTION even if you sense complaint:\n\n"
        "  HOW/WHAT/WHY/WHERE: 'كيف', 'إزاي', 'ازاي', 'how do I', 'how does', "
        "    'ما هو', 'ايه', 'إيه', 'what is', 'why', 'ليه', 'where', 'فين'\n\n"
        "  CAPABILITY/META: 'تقدر', 'هل تقدر', 'ممكن تساعدني', 'هل يمكنك', "
        "    'can you', 'are you able to', 'do you know', 'هل تعرف', 'تفهم في'\n"
        "    NOTE: 'تقدر تساعدني اني اطور الصفحة' is META, NOT a suggestion. "
        "    Answer that you're informational and ask what specifically they need.\n\n"
        "  CONVERSATIONAL: 'شكراً', 'تمام', 'ok', 'هلا', 'مرحبا', greetings, thanks\n\n"
        "  CORRECTION: 'ده سؤال', 'this is a question', 'no I meant', 'لا قصدي'\n"
        "    → re-read user's previous turn, classify based on that\n\n"
        "═══ AMBIGUOUS — use semantic reasoning ═══\n"
        "If neither pattern set fires, ask yourself:\n"
        "  • Could the user walk away satisfied with just an explanation? → QUESTION\n"
        "  • Does it require a future code change to address? → SUGGESTION\n"
        "  • Is the user asserting something is wrong/missing? → SUGGESTION\n"
        "  • Is the user asking what something is or how to do it? → QUESTION\n\n"
        "═══ RESPONSE FORMAT ═══\n"
        "If QUESTION:\n"
        "  Answer using the knowledge base. NO tag.\n\n"
        "If SUGGESTION:\n"
        "  1. Acknowledge in 1 sentence (vary the wording each time, don't always "
        "     say 'شكراً اقتراحك مهم').\n"
        "  2. If a workaround exists today, mention it briefly.\n"
        "  3. End with the tag on a NEW LINE: [SUGGESTION:<category>:<priority>]\n"
        "     • category: ui | workflow | bug | feature | other\n"
        "     • priority: low | medium | high\n\n"
        "═══ EXAMPLES ═══\n\n"
        "User: 'الشاشة بطيئة جداً وبتعلق'\n"
        "  → ALWAYS-SUGGESTION pattern (COMPLAINT/BROKEN matched)\n"
        "  → 'تم تسجيل ملاحظتك بشأن البطء. حاول إعادة تحميل الصفحة أو مسح كاش "
        "    المتصفح كحل مؤقت. الفريق سيراجع أداء الشاشة.'\n"
        "    [SUGGESTION:bug:medium]\n\n"
        "User: 'أتمنى يكون فيه تقرير شهري للمصاريف'\n"
        "  → ALWAYS-SUGGESTION (WISH matched)\n"
        "  → 'فكرة ممتازة، تم تسجيلها. حالياً يمكنك تصدير قائمة الطلبات الشهرية "
        "    من شاشة التقارير و حساب الإجمالي يدوياً كحل مؤقت.'\n"
        "    [SUGGESTION:feature:low]\n\n"
        "User: 'تقدر تساعدني اني اطور الصفحة؟'\n"
        "  → ALWAYS-QUESTION (CAPABILITY/META matched)\n"
        "  → 'أنا مساعد إعلامي، أقدر أشرحلك خطوات الشاشة و أوضح صلاحيات دورك، "
        "    لكن تنفيذ التطوير بيتم بواسطة فريق البرمجة. عاوز تطور إيه بالظبط؟ "
        "    لو فكرة محددة، اقترحها و الفريق هيراجعها.'\n"
        "  → NO tag\n\n"
        "User: 'ليه الطلب لما اعمله submit بيروح للموافقة؟'\n"
        "  → ALWAYS-QUESTION (WHY matched)\n"
        "  → 'لأن النظام بيشترط مراجعة مدير المنطقة قبل البدء في الإنتاج "
        "    أو الصرف. لما تضغط إرسال، الطلب بيتحول لحالة \"مُرسَل\" و يظهر "
        "    لمدير منطقتك ليوافق أو يعدّل أو يرفض.'\n"
        "  → NO tag (Note: even though user wrote 'submit', I responded with 'إرسال')\n\n"
        "User: 'هل في طريقة اعدل الكمية بعد ما عملت Submit؟'\n"
        "  → ALWAYS-QUESTION (CAPABILITY/HOW matched)\n"
        "  → 'بعد الإرسال، لا تستطيع تعديل الكمية مباشرة. مدير المنطقة هو "
        "    اللي يقدر يعدّلها وقت الموافقة، أو يرفض الطلب و تنشئ واحد جديد. "
        "    لو محتاج تعديل عاجل، كلّم مدير منطقتك.'\n"
        "  → NO tag (Note: 'Submit' translated to 'الإرسال' in response)\n\n"
        "═══ FINAL CHECK BEFORE SENDING ═══\n"
        "1. Re-scan your reply for any English words. If found and the user's "
        "   language is Arabic, replace them with Arabic equivalents from the table above.\n"
        "2. Brand names (Onda, Ronaldos, Shawarma, Griddle) are the only allowed "
        "   Latin characters in Arabic replies.\n"
    )

    return (
        "You are the Raed Inventory System assistant — a helpful guide for employees "
        "learning to use the system. You answer questions, explain workflows, and "
        "discuss improvement ideas. You do NOT execute actions; you only inform.\n\n"
        f"{role_context}\n\n"
        f"{language_directive}"
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
