from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Brand,
    EvaluationTargetMode,
    EvaluationTemplate,
    EvaluationTemplateQuestion,
    EvaluationTemplateSection,
    EvaluationTemplateVersion,
    EvaluationTemplateVersionStatus,
    EvaluationType,
)


_SEED_TEMPLATES = [
    ("Ronaldos Pizza", "Ronaldos Branch Evaluation", EvaluationType.BRANCH, EvaluationTargetMode.BRANCH),
    ("Ronaldos Pizza", "Ronaldos Employee Evaluation", EvaluationType.EMPLOYEE, EvaluationTargetMode.EMPLOYEE),
    ("Shawarma", "Shawarma Branch Evaluation", EvaluationType.BRANCH, EvaluationTargetMode.BRANCH),
    ("Shawarma", "Shawarma Employee Evaluation", EvaluationType.EMPLOYEE, EvaluationTargetMode.EMPLOYEE),
    ("Griddle", "Griddle Branch Evaluation", EvaluationType.BRANCH, EvaluationTargetMode.BRANCH),
    ("Griddle", "Griddle Employee Evaluation", EvaluationType.EMPLOYEE, EvaluationTargetMode.EMPLOYEE),
    ("Onda", "Onda Branch Placeholder", EvaluationType.BRANCH, EvaluationTargetMode.BRANCH),
    ("Onda", "Onda Store Visit Placeholder", EvaluationType.STORE_VISIT, EvaluationTargetMode.BRANCH),
    ("Onda", "Onda Barista Placeholder", EvaluationType.ROLE_SPECIFIC, EvaluationTargetMode.EMPLOYEE),
]


def _brand(db: Session, name: str) -> Brand:
    row = db.query(Brand).filter(Brand.name == name).first()
    if row:
        return row
    row = Brand(name=name, active=True)
    db.add(row)
    db.flush()
    return row


def _sections_for(template_name: str, is_employee: bool) -> list[dict]:
    if "Placeholder" in template_name:
        return [
            {
                "name": "Starter Checklist",
                "weight_percent": None,
                "questions": [
                    "Starter quality criterion is met",
                    "Required notes are captured when performance is low",
                ],
            }
        ]
    if is_employee:
        return [
            {"name": "Role Performance", "weight_percent": 40, "questions": ["Follows role standards", "Completes assigned duties on time"]},
            {"name": "Customer Service", "weight_percent": 30, "questions": ["Communicates politely with guests", "Handles feedback professionally"]},
            {"name": "Hygiene and Safety", "weight_percent": 30, "questions": ["Maintains personal hygiene", "Follows food safety procedures"]},
        ]
    return [
        {"name": "Operations", "weight_percent": 35, "questions": ["Branch opening standards are followed", "Service workflow is organized"]},
        {"name": "Product Quality", "weight_percent": 35, "questions": ["Products match brand quality standards", "Presentation standards are followed"]},
        {"name": "Cleanliness and Safety", "weight_percent": 30, "questions": ["Branch cleanliness is maintained", "Food safety requirements are followed"]},
    ]


def seed_evaluation_templates(db: Session, created_by: int | None = None) -> int:
    created = 0
    for brand_name, template_name, evaluation_type, target_mode in _SEED_TEMPLATES:
        brand = _brand(db, brand_name)
        exists = db.query(EvaluationTemplate).filter(EvaluationTemplate.name == template_name, EvaluationTemplate.brand_id == brand.id).first()
        if exists:
            continue
        template = EvaluationTemplate(
            name=template_name,
            brand_id=brand.id,
            evaluation_type=evaluation_type,
            target_mode=target_mode,
            target_role="barista" if "Barista" in template_name else None,
            active=True,
            created_by=created_by,
        )
        db.add(template)
        db.flush()
        version = EvaluationTemplateVersion(
            template_id=template.id,
            version_no=1,
            status=EvaluationTemplateVersionStatus.PUBLISHED,
            published_at=datetime.utcnow(),
            created_by=created_by,
            notes="Seeded editable starter template",
        )
        db.add(version)
        db.flush()
        for section_order, section_data in enumerate(_sections_for(template_name, target_mode == EvaluationTargetMode.EMPLOYEE), start=1):
            section = EvaluationTemplateSection(
                template_version_id=version.id,
                name=section_data["name"],
                weight_percent=section_data["weight_percent"],
                display_order=section_order,
                active=True,
            )
            db.add(section)
            db.flush()
            for question_order, text in enumerate(section_data["questions"], start=1):
                db.add(EvaluationTemplateQuestion(
                    section_id=section.id,
                    question_text_ar=text,
                    question_text_en=text,
                    max_score=5,
                    allow_na=True,
                    requires_note_if_low_score=True,
                    low_score_threshold=2,
                    requires_photo=False,
                    display_order=question_order,
                    active=True,
                ))
        created += 1
    if created:
        db.commit()
    return created
