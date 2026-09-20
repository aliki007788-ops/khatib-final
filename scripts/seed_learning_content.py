"""
Seeds initial LearningLevel + IraqiScenario content.
Run: python scripts/seed_learning_content.py
"""
from __future__ import annotations

from app.core.db import db_session
from app.core.models import IraqiScenario, LearningLevel, ScenarioCategory

LEVELS = [
    {"code": "beginner", "name_fa": "مبتدی", "order_index": 0, "description_fa": "آشنایی اولیه با گویش عراقی"},
    {"code": "A1", "name_fa": "A1 - پایه", "order_index": 1, "description_fa": "مکالمات ساده روزمره"},
    {"code": "A2", "name_fa": "A2 - مقدماتی", "order_index": 2, "description_fa": "موقعیت‌های رایج سفر و خرید"},
    {"code": "B1", "name_fa": "B1 - متوسط", "order_index": 3, "description_fa": "مکالمات کاری و اجتماعی"},
]

SCENARIOS_BY_LEVEL_CODE = {
    "beginner": [
        {
            "category": ScenarioCategory.daily_conversation, "order_index": 0,
            "title_fa": "سلام و احوال‌پرسی", "description_fa": "یادگیری سلام کردن و احوال‌پرسی ساده به گویش عراقی.",
            "key_vocabulary": [{"iq": "شلونك", "fa": "حالت چطوره؟"}, {"iq": "زين", "fa": "خوبم"}],
            "practice_prompt": "هلا! شلونك اليوم؟ (سلام! امروز حالت چطوره؟) — جواب بده تا تمرین کنیم.",
        },
        {
            "category": ScenarioCategory.daily_conversation, "order_index": 1,
            "title_fa": "معرفی خود", "description_fa": "یاد بگیرید خودتان را به گویش عراقی معرفی کنید.",
            "key_vocabulary": [{"iq": "اسمي", "fa": "اسم من"}, {"iq": "من وين انت", "fa": "اهل کجایی"}],
            "practice_prompt": "اسمك منو؟ ومن وين انت؟ (اسمت چیه و اهل کجایی؟)",
        },
    ],
    "A1": [
        {
            "category": ScenarioCategory.restaurant, "order_index": 0,
            "title_fa": "در رستوران", "description_fa": "سفارش غذا و نوشیدنی به گویش عراقی.",
            "key_vocabulary": [{"iq": "اريد اكل", "fa": "می‌خواهم غذا بخورم"}, {"iq": "الحساب", "fa": "صورت‌حساب"}],
            "practice_prompt": "هلا بيك بالمطعم! شتريد تاكل اليوم؟ (خوش اومدی به رستوران! امروز چی می‌خوای بخوری؟)",
        },
    ],
}


def run() -> None:
    with db_session() as db:
        level_id_by_code: dict[str, str] = {}

        for level_data in LEVELS:
            existing = db.query(LearningLevel).filter_by(code=level_data["code"]).first()
            if existing:
                level_id_by_code[level_data["code"]] = existing.id
                continue
            level = LearningLevel(**level_data)
            db.add(level)
            db.flush()
            level_id_by_code[level_data["code"]] = level.id

        for level_code, scenarios in SCENARIOS_BY_LEVEL_CODE.items():
            level_id = level_id_by_code[level_code]
            for sc_data in scenarios:
                existing = db.query(IraqiScenario).filter_by(
                    level_id=level_id, order_index=sc_data["order_index"]
                ).first()
                if existing:
                    continue
                db.add(IraqiScenario(level_id=level_id, **sc_data))

        print("Learning content seeded successfully.")


if __name__ == "__main__":
    run()
