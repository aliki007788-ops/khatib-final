"""
Prompt templates, isolated and versioned.
"""
from __future__ import annotations

from app.schemas.ai import ChatReplyResponse, SpeechAnalysisResponse, TranslationResponse

PROMPT_VERSIONS = {
    "speech_analysis": "speech_analysis_v1",
    "chat_iraqi_coach": "chat_iraqi_coach_v1",
    "translation_fa_iq": "translation_fa_iq_v1",
}


def _schema_hint(model_cls) -> str:
    fields = []
    for name, field in model_cls.model_fields.items():
        fields.append(f'"{name}": {field.annotation}')
    return "{\n  " + ",\n  ".join(fields) + "\n}"


def build_speech_analysis_prompt(topic: str, text: str) -> tuple[str, str]:
    system = (
        "شما یک مربی حرفه‌ای سخنرانی فارسی‌زبان هستید. متن سخنرانی کاربر را "
        "تحلیل می‌کنید و بازخورد سازنده، دقیق و قابل‌اجرا می‌دهید. "
        "همیشه فقط یک JSON معتبر و بدون هیچ متن اضافه برمی‌گردانید، دقیقاً "
        "با همین ساختار:\n"
        f"{_schema_hint(SpeechAnalysisResponse)}\n"
        "score باید عددی بین 0 تا 100 باشد. strengths، weaknesses و "
        "improvements باید آرایه‌ای از رشته‌های کوتاه فارسی باشند."
    )
    user = f"موضوع سخنرانی: {topic}\n\nمتن سخنرانی:\n{text}"
    return system, user


def build_chat_iraqi_coach_prompt(user_message: str, history_summary: str = "") -> tuple[str, str]:
    system = (
        "شما «خطیب»، یک مربی مکالمه به گویش عراقی هستید که به فارسی توضیح "
        "می‌دهید. اگر کاربر جمله‌ای به عربی/عراقی نوشت، اشتباهات گرامری یا "
        "تلفظی را با احترام اصلاح کنید. از عبارات رایج بغدادی استفاده کنید، "
        "نه عربی فصیح رسمی. فقط JSON معتبر با ساختار زیر برگردانید:\n"
        f"{_schema_hint(ChatReplyResponse)}"
    )
    context = f"خلاصه گفتگوی قبلی: {history_summary}\n\n" if history_summary else ""
    user = f"{context}پیام کاربر: {user_message}"
    return system, user


def build_translation_prompt(text: str, direction: str) -> tuple[str, str]:
    if direction == "fa_to_iq":
        instruction = "متن فارسی زیر را به گویش عراقی (بغدادی) ترجمه کن، نه عربی فصیح."
    else:
        instruction = "متن عربی/عراقی زیر را به فارسی روان ترجمه کن."

    system = (
        f"شما یک مترجم متخصص فارسی و گویش عراقی هستید. {instruction} "
        "ترجمه باید طبیعی و محاوره‌ای باشد، نه لغت‌به‌لغت. فقط JSON معتبر "
        f"با ساختار زیر برگردانید:\n{_schema_hint(TranslationResponse)}"
    )
    user = f"متن: {text}"
    return system, user
