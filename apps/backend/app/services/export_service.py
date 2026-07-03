from io import BytesIO
from datetime import UTC, datetime
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
            or value.get("pergunta")
            or value.get("answer")
            or value.get("resposta")
        )
        description = (
            value.get("explanation")
            or value.get("feedback")
            or value.get("comment")
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


def get_content_number(content: GeneratedContent, field: str) -> int:
    content_json = content.content_json or {}
    script = content_json.get("lesson_script", {}) if isinstance(content_json.get("lesson_script"), dict) else {}
    quiz = content_json.get("module_quiz", {}) if isinstance(content_json.get("module_quiz"), dict) else {}
    metadata = content_json.get("metadata", {}) if isinstance(content_json.get("metadata"), dict) else {}
    for source in (script, quiz, metadata):
        try:
            return int(source.get(field) or 0)
        except (TypeError, ValueError):
            continue
    return 0


def get_lesson_scripts(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent)
            .where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type.in_(["lesson_script", "lesson_scripts"]),
            )
            .order_by(GeneratedContent.created_at.asc())
        ).scalars().all()
    )

    contents.sort(
        key=lambda content: (
            get_content_number(content, "module_number") or 9999,
            get_content_number(content, "lesson_number") or 9999,
            content.created_at,
        )
    )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum roteiro de aula foi encontrado para este projeto.",
        )

    return contents


def get_module_quizzes(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent)
            .where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type.in_(["module_quiz", "module_quizzes"]),
            )
            .order_by(GeneratedContent.created_at.asc())
        ).scalars().all()
    )

    contents.sort(key=lambda content: (get_content_number(content, "module_number") or 9999, content.created_at))

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum quiz foi encontrado para este projeto.",
        )

    return contents


def get_complementary_materials(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent)
            .where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type.in_(["complementary_material", "complementary_materials"]),
            )
            .order_by(GeneratedContent.created_at.asc())
        ).scalars().all()
    )

    contents.sort(
        key=lambda content: (
            safe_text(
                (content.content_json or {}).get("complementary_material", {}).get("material_title")
                if isinstance((content.content_json or {}).get("complementary_material"), dict)
                else content.title,
                "",
            ).lower(),
            content.created_at,
        )
    )

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum material complementar foi encontrado para este projeto.",
        )

    return contents


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


def build_lesson_scripts_pdf(project: Project, lesson_scripts: list[GeneratedContent]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"Roteiros de Aula - {project.title}",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "VveLessonTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=16,
    )
    subtitle_style = ParagraphStyle(
        "VveLessonSubtitle",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=10,
    )
    lesson_title_style = ParagraphStyle(
        "VveLessonHeading",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "VveLessonSection",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=9,
        spaceAfter=5,
    )
    label_style = ParagraphStyle(
        "VveLessonLabel",
        parent=base_styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=6,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "VveLessonBody",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )

    generated_at = datetime.now(UTC).strftime("%d/%m/%Y")
    story: list[Any] = [
        Spacer(1, 2.4 * cm),
        paragraph(project.title, subtitle_style),
        paragraph("Roteiros de Aula", title_style),
        paragraph(f"Gerado em {generated_at}", subtitle_style),
        paragraph("Documento exportado pelo Virtus et Veritas Engine", subtitle_style),
        PageBreak(),
    ]

    section_keys = [
        ("Objetivo da aula", ["learning_objective", "lesson_objective", "objective"]),
        ("Abertura", ["opening", "hook"]),
        ("Introducao", ["introduction", "intro"]),
        ("Desenvolvimento", ["development", "lesson_development"]),
        ("Exemplo pratico", ["practical_example", "examples", "example"]),
        ("Atividade pratica", ["practical_activity", "activity", "exercise"]),
        ("Pergunta de reflexao", ["reflection_question"]),
        ("Conclusao", ["conclusion", "closing"]),
        ("Call to action", ["call_to_action", "cta"]),
        ("Notas do instrutor", ["instructor_notes", "teaching_notes"]),
        ("Texto de narracao", ["narration", "voiceover"]),
        ("Sugestao visual", ["visual_suggestion"]),
    ]

    for index, content in enumerate(lesson_scripts):
        content_json = content.content_json or {}
        script = content_json.get("lesson_script", {}) if isinstance(content_json.get("lesson_script"), dict) else {}
        module_number = safe_text(script.get("module_number") or get_content_number(content, "module_number"), "")
        lesson_number = safe_text(script.get("lesson_number") or get_content_number(content, "lesson_number"), "")
        lesson_title = script.get("lesson_title") or content.title or f"Aula {lesson_number or index + 1}"

        story.append(paragraph(f"Modulo {module_number or '-'} | Aula {lesson_number or index + 1}", section_style))
        story.append(paragraph(lesson_title, lesson_title_style))
        story.extend(labeled_paragraph("Titulo do curso", script.get("course_title") or project.title, label_style, body_style))
        story.extend(labeled_paragraph("Modulo", script.get("module_title"), label_style, body_style))

        for label, keys in section_keys:
            value = next((script.get(key) for key in keys if script.get(key) not in (None, "", [])), None)
            if value not in (None, "", []):
                story.extend(labeled_paragraph(label, value, label_style, body_style))

        blocks = (
            as_list(script.get("main_script"))
            or as_list(script.get("sections"))
            or as_list(script.get("blocks"))
            or as_list(script.get("content_blocks"))
        )
        if blocks:
            story.append(Paragraph("Blocos da aula", section_style))
            for block_index, block in enumerate(blocks, start=1):
                block_data = block if isinstance(block, dict) else {"content": block}
                block_title = (
                    block_data.get("section_title")
                    or block_data.get("title")
                    or block_data.get("name")
                    or f"Bloco {block_index}"
                )
                story.append(Paragraph(escape(safe_text(block_title)), label_style))
                block_fields = [
                    block_data.get("narration"),
                    block_data.get("content"),
                    block_data.get("text"),
                    block_data.get("description"),
                ]
                block_text = next((value for value in block_fields if value not in (None, "", [])), "")
                story.append(paragraph(block_text, body_style))
                if block_data.get("teaching_notes"):
                    story.extend(labeled_paragraph("Notas de ensino", block_data.get("teaching_notes"), label_style, body_style))
                if block_data.get("visual_suggestion"):
                    story.extend(labeled_paragraph("Sugestao visual", block_data.get("visual_suggestion"), label_style, body_style))
                story.append(Spacer(1, 0.12 * cm))

        if index < len(lesson_scripts) - 1:
            story.append(PageBreak())

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def first_quiz_value(source: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, "", []):
            return value
    return None


def build_quizzes_pdf(project: Project, quizzes: list[GeneratedContent]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"Quizzes do Curso - {project.title}",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "VveQuizTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=16,
    )
    subtitle_style = ParagraphStyle(
        "VveQuizSubtitle",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=10,
    )
    quiz_title_style = ParagraphStyle(
        "VveQuizHeading",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "VveQuizSection",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=9,
        spaceAfter=5,
    )
    label_style = ParagraphStyle(
        "VveQuizLabel",
        parent=base_styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=6,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "VveQuizBody",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )
    option_style = ParagraphStyle(
        "VveQuizOption",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=0,
        spaceAfter=3,
    )

    generated_at = datetime.now(UTC).strftime("%d/%m/%Y")
    story: list[Any] = [
        Spacer(1, 2.4 * cm),
        paragraph(project.title, subtitle_style),
        paragraph("Quizzes do Curso", title_style),
        paragraph(f"Gerado em {generated_at}", subtitle_style),
        paragraph("Documento exportado pelo Virtus et Veritas Engine", subtitle_style),
        PageBreak(),
    ]

    for quiz_index, content in enumerate(quizzes):
        content_json = content.content_json or {}
        quiz = content_json.get("module_quiz", {}) if isinstance(content_json.get("module_quiz"), dict) else {}
        module_number = safe_text(quiz.get("module_number") or get_content_number(content, "module_number"), "")
        module_title = quiz.get("module_title") or content.title or "Quiz"
        quiz_title = quiz.get("quiz_title") or quiz.get("title") or f"Quiz - Modulo {module_number or quiz_index + 1}"

        story.append(paragraph(quiz_title, quiz_title_style))
        story.extend(labeled_paragraph("Modulo", module_number or "Nao informado", label_style, body_style))
        story.extend(labeled_paragraph("Titulo do modulo", module_title, label_style, body_style))
        if quiz.get("instructions"):
            story.extend(labeled_paragraph("Instrucoes", quiz.get("instructions"), label_style, body_style))

        questions = (
            as_list(quiz.get("questions"))
            or as_list(quiz.get("perguntas"))
            or as_list(quiz.get("items"))
        )
        if questions:
            story.append(Paragraph("Perguntas", section_style))

        for question_index, question in enumerate(questions, start=1):
            question_data = question if isinstance(question, dict) else {"question": question}
            question_text = first_quiz_value(question_data, ["question", "pergunta", "title", "text", "content"])
            story.append(Paragraph(escape(f"Pergunta {question_index}"), label_style))
            story.append(paragraph(question_text, body_style))

            options = (
                as_list(question_data.get("options"))
                or as_list(question_data.get("alternatives"))
                or as_list(question_data.get("alternativas"))
                or as_list(question_data.get("answers"))
            )
            if options:
                story.append(Paragraph("Alternativas", label_style))
                story.append(
                    ListFlowable(
                        [
                            ListItem(
                                paragraph(
                                    f"{safe_text(option.get('letter') or chr(65 + option_index), '')}. "
                                    f"{safe_text(option.get('text') or option.get('content') or option.get('value'), '')}"
                                    if isinstance(option, dict)
                                    else f"{chr(65 + option_index)}. {safe_text(option, '')}",
                                    option_style,
                                ),
                                leftIndent=10,
                            )
                            for option_index, option in enumerate(options)
                        ],
                        bulletType="bullet",
                        start="circle",
                        leftIndent=16,
                    )
                )
                story.append(Spacer(1, 0.12 * cm))

            correct_answer = first_quiz_value(
                question_data,
                ["correct_answer", "answer", "resposta_correta", "correct_option", "resposta"],
            )
            explanation = first_quiz_value(
                question_data,
                ["explanation", "feedback", "comment", "comentario", "explicacao"],
            )
            if correct_answer not in (None, "", []):
                story.extend(labeled_paragraph("Resposta correta", correct_answer, label_style, body_style))
            if explanation not in (None, "", []):
                story.extend(labeled_paragraph("Explicacao", explanation, label_style, body_style))
            story.append(Spacer(1, 0.2 * cm))

        if quiz_index < len(quizzes) - 1:
            story.append(PageBreak())

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def build_complementary_materials_pdf(project: Project, materials: list[GeneratedContent]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"Materiais Complementares - {project.title}",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "VveMaterialTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=16,
    )
    subtitle_style = ParagraphStyle(
        "VveMaterialSubtitle",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=17,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=10,
    )
    material_title_style = ParagraphStyle(
        "VveMaterialHeading",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "VveMaterialSection",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=9,
        spaceAfter=5,
    )
    label_style = ParagraphStyle(
        "VveMaterialLabel",
        parent=base_styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#8A6A16"),
        spaceBefore=6,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "VveMaterialBody",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )

    generated_at = datetime.now(UTC).strftime("%d/%m/%Y")
    story: list[Any] = [
        Spacer(1, 2.4 * cm),
        paragraph(project.title, subtitle_style),
        paragraph("Materiais Complementares", title_style),
        paragraph(f"Gerado em {generated_at}", subtitle_style),
        paragraph("Documento exportado pelo Virtus et Veritas Engine", subtitle_style),
        PageBreak(),
    ]

    list_sections = [
        ("Aplicacoes praticas", ["practical_applications", "applications", "aplicacoes"]),
        ("Exercicios reflexivos", ["reflection_exercises", "exercises", "perguntas_reflexivas"]),
        ("Proximos passos", ["recommended_next_steps", "next_steps", "proximos_passos"]),
    ]
    extra_fields = [
        ("Resumo", ["summary"]),
        ("Detalhes", ["details"]),
        ("Conteudo", ["content", "text", "description"]),
    ]

    for index, content in enumerate(materials):
        content_json = content.content_json or {}
        material = (
            content_json.get("complementary_material", {})
            if isinstance(content_json.get("complementary_material"), dict)
            else {}
        )
        material_title = material.get("material_title") or material.get("title") or content.title or f"Material {index + 1}"
        material_type = material.get("material_type") or material.get("type") or "Material complementar"

        story.append(paragraph(material_title, material_title_style))
        story.extend(labeled_paragraph("Tipo do material", material_type, label_style, body_style))
        if material.get("overview"):
            story.extend(labeled_paragraph("Visao geral", material.get("overview"), label_style, body_style))

        concepts = as_list(material.get("key_concepts") or material.get("concepts") or material.get("conceitos_chave"))
        if concepts:
            story.append(Paragraph("Conceitos-chave", section_style))
            for concept_index, concept in enumerate(concepts, start=1):
                concept_data = concept if isinstance(concept, dict) else {"concept": concept}
                concept_title = (
                    concept_data.get("concept")
                    or concept_data.get("title")
                    or concept_data.get("name")
                    or f"Conceito {concept_index}"
                )
                concept_explanation = (
                    concept_data.get("explanation")
                    or concept_data.get("description")
                    or concept_data.get("text")
                    or concept_data.get("content")
                )
                story.append(Paragraph(escape(safe_text(concept_title)), label_style))
                if concept_explanation not in (None, "", []):
                    story.append(paragraph(concept_explanation, body_style))
                story.append(Spacer(1, 0.12 * cm))

        for label, keys in list_sections:
            value = next((material.get(key) for key in keys if material.get(key) not in (None, "", [])), None)
            items = as_list(value)
            if items:
                story.append(Paragraph(label, section_style))
                for item in items:
                    story.append(paragraph(item, body_style))
                story.append(Spacer(1, 0.12 * cm))

        for label, keys in extra_fields:
            value = next((material.get(key) for key in keys if material.get(key) not in (None, "", [])), None)
            if value not in (None, "", []):
                story.extend(labeled_paragraph(label, value, label_style, body_style))

        if index < len(materials) - 1:
            story.append(PageBreak())

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def export_presentation_pdf(db: Session, current_user: User, project_id: UUID) -> tuple[Project, bytes]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    presentation = get_latest_presentation_deck(db, project)
    return project, build_presentation_pdf(project, presentation)


def export_lesson_scripts_pdf(db: Session, current_user: User, project_id: UUID) -> tuple[Project, bytes]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    lesson_scripts = get_lesson_scripts(db, project)
    return project, build_lesson_scripts_pdf(project, lesson_scripts)


def export_quizzes_pdf(db: Session, current_user: User, project_id: UUID) -> tuple[Project, bytes]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    quizzes = get_module_quizzes(db, project)
    return project, build_quizzes_pdf(project, quizzes)


def export_complementary_materials_pdf(db: Session, current_user: User, project_id: UUID) -> tuple[Project, bytes]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    materials = get_complementary_materials(db, project)
    return project, build_complementary_materials_pdf(project, materials)
