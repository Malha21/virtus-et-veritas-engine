from io import BytesIO
from typing import Any
from uuid import UUID
from xml.sax.saxutils import escape

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.generated_content import GeneratedContent
from app.models.project import Project
from app.models.user import User
from app.services.project_service import get_project_by_id

FOOTER_TEXT = "Virtus et Veritas Engine"


def safe_text(value: Any, fallback: str = "Nao informado") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    if isinstance(value, bool | int | float):
        return str(value)
    if isinstance(value, list):
        text = "\n".join(safe_text(item, "") for item in value).strip()
        return text or fallback
    if isinstance(value, dict):
        title = (
            value.get("title")
            or value.get("subtitle")
            or value.get("concept")
            or value.get("question")
            or value.get("answer")
        )
        description = (
            value.get("explanation")
            or value.get("description")
            or value.get("content")
            or value.get("text")
            or value.get("summary")
            or value.get("details")
            or value.get("speaker_notes")
            or value.get("visual_suggestion")
            or value.get("interaction_question")
        )
        if title and description:
            return f"{safe_text(title, '')}: {safe_text(description, '')}".strip(": ")
        if description:
            return safe_text(description, fallback)
        if title:
            return safe_text(title, fallback)

        parts = [safe_text(item, "") for item in value.values()]
        text = "\n".join(part for part in parts if part).strip()
        return text or fallback

    return str(value)


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def get_latest_presentation_deck(db: Session, project: Project) -> GeneratedContent:
    content = db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == project.organization_id,
            GeneratedContent.content_type == "presentation_deck",
        )
        .order_by(GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().first()

    if content is None or not content.content_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A apresentacao ainda nao foi gerada para este projeto.",
        )

    return content


def paragraph(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(safe_text(text)), style)


def labeled_paragraph(label: str, value: Any, label_style: ParagraphStyle, body_style: ParagraphStyle) -> list[Any]:
    return [
        Paragraph(escape(label), label_style),
        paragraph(value, body_style),
        Spacer(1, 0.18 * cm),
    ]


def footer(canvas: Any, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(doc.leftMargin, 1.05 * cm, FOOTER_TEXT)
    canvas.drawRightString(A4[0] - doc.rightMargin, 1.05 * cm, str(doc.page))
    canvas.restoreState()


def build_presentation_pdf(project: Project, presentation: GeneratedContent) -> bytes:
    deck = presentation.content_json or {}
    slides = as_list(deck.get("slides"))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=safe_text(deck.get("presentation_title"), project.title),
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "VveTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=16,
    )
    subtitle_style = ParagraphStyle(
        "VveSubtitle",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "VveSection",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=20,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=10,
        spaceAfter=8,
    )
    slide_title_style = ParagraphStyle(
        "VveSlideTitle",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "VveLabel",
        parent=base_styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=7,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "VveBody",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        "VveBullet",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=0,
        spaceAfter=3,
    )

    story: list[Any] = [
        Spacer(1, 2.4 * cm),
        paragraph(project.title, subtitle_style),
        paragraph(deck.get("presentation_title") or project.title, title_style),
        paragraph("Apresentacao gerada pelo Virtus et Veritas Engine", subtitle_style),
        Spacer(1, 0.5 * cm),
    ]
    story.extend(labeled_paragraph("Publico-alvo", deck.get("target_audience"), label_style, body_style))
    story.extend(labeled_paragraph("Duracao estimada", deck.get("estimated_duration"), label_style, body_style))
    story.extend(labeled_paragraph("Estilo visual sugerido", deck.get("visual_style"), label_style, body_style))
    story.extend(labeled_paragraph("Objetivo da apresentacao", deck.get("presentation_objective"), label_style, body_style))

    if slides:
        story.append(PageBreak())

    for index, slide in enumerate(slides):
        slide_data = slide if isinstance(slide, dict) else {"title": slide}
        slide_number = safe_text(slide_data.get("slide_number") or index + 1)
        story.append(paragraph(f"Slide {slide_number}", section_style))
        story.append(paragraph(slide_data.get("title"), slide_title_style))
        if slide_data.get("subtitle"):
            story.append(paragraph(slide_data.get("subtitle"), body_style))

        bullets = as_list(slide_data.get("bullets"))
        if bullets:
            story.append(Paragraph("Pontos principais", label_style))
            story.append(
                ListFlowable(
                    [ListItem(paragraph(item, bullet_style), leftIndent=10) for item in bullets[:5]],
                    bulletType="bullet",
                    start="circle",
                    leftIndent=16,
                )
            )
            story.append(Spacer(1, 0.15 * cm))

        story.extend(labeled_paragraph("Notas do apresentador", slide_data.get("speaker_notes"), label_style, body_style))
        story.extend(labeled_paragraph("Sugestao visual", slide_data.get("visual_suggestion"), label_style, body_style))
        if slide_data.get("interaction_question"):
            story.extend(
                labeled_paragraph(
                    "Pergunta de interacao",
                    slide_data.get("interaction_question"),
                    label_style,
                    body_style,
                )
            )

        if index < len(slides) - 1:
            story.append(PageBreak())

    if deck.get("closing_message"):
        story.append(PageBreak())
        story.append(paragraph("Encerramento", section_style))
        story.append(paragraph(deck.get("closing_message"), body_style))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def export_presentation_pdf(db: Session, current_user: User, project_id: UUID) -> tuple[Project, bytes]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    presentation = get_latest_presentation_deck(db, project)
    return project, build_presentation_pdf(project, presentation)
