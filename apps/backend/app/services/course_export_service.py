import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models.course_export import CourseExport
from app.models.generated_audio import GeneratedAudio
from app.models.generated_content import GeneratedContent
from app.models.generated_video import GeneratedVideo
from app.models.project import Project
from app.models.user import User
from app.schemas.course_export import CourseExportCreate
from app.services.audio_service import get_audio_storage_dir
from app.services.export_service import as_list, safe_text
from app.services.project_service import get_project_by_id, slugify
from app.services.video_pipeline_service import get_lesson_narration_text, get_lesson_script_dict
from app.services.video_service import get_video_storage_dir, is_valid_mp4_file

COMPLETED_VIDEO_STATUSES = {"completed", "completed_mock"}


def get_export_storage_dir(settings: Settings | None = None) -> Path:
    active_settings = settings or get_settings()
    path = Path(active_settings.storage_path) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def folder_slug(value: Any, fallback: str) -> str:
    text = safe_text(value, "").strip()
    if not text:
        return fallback
    slug = slugify(text)
    return slug or fallback


def get_content_field_number(content: GeneratedContent, field: str) -> int:
    content_json = content.content_json or {}
    for key in ("lesson_script", "module_quiz", "metadata"):
        source = content_json.get(key)
        if isinstance(source, dict) and source.get(field) not in (None, ""):
            try:
                return int(source.get(field))
            except (TypeError, ValueError):
                continue
    return 0


def list_lesson_scripts(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent).where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type == "lesson_script",
            )
        )
        .scalars()
        .all()
    )
    contents.sort(
        key=lambda content: (
            get_content_field_number(content, "module_number") or 9999,
            get_content_field_number(content, "lesson_number") or 9999,
            content.created_at,
        )
    )
    return contents


def list_module_quizzes(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent).where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type.in_(["module_quiz", "module_quizzes"]),
            )
        )
        .scalars()
        .all()
    )
    contents.sort(key=lambda content: (get_content_field_number(content, "module_number") or 9999, content.created_at))
    return contents


def list_complementary_materials(db: Session, project: Project) -> list[GeneratedContent]:
    contents = list(
        db.execute(
            select(GeneratedContent).where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type.in_(["complementary_material", "complementary_materials"]),
            )
        )
        .scalars()
        .all()
    )
    contents.sort(key=lambda content: content.created_at)
    return contents


def get_optional_latest_content(db: Session, project: Project, content_type: str) -> GeneratedContent | None:
    return db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == project.organization_id,
            GeneratedContent.content_type == content_type,
        )
        .order_by(GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().first()


def list_audios_for_lesson(db: Session, project_id: UUID, lesson_id: UUID) -> list[GeneratedAudio]:
    audios = list(
        db.execute(
            select(GeneratedAudio)
            .where(
                GeneratedAudio.project_id == project_id,
                GeneratedAudio.generated_content_id == lesson_id,
            )
            .order_by(GeneratedAudio.created_at.desc())
        )
        .scalars()
        .all()
    )
    latest_by_block: dict[int, GeneratedAudio] = {}
    for audio in audios:
        if audio.block_index not in latest_by_block:
            latest_by_block[audio.block_index] = audio
    return [latest_by_block[key] for key in sorted(latest_by_block)]


def list_videos_for_lesson(
    db: Session, project_id: UUID, lesson_id: UUID, only_completed: bool
) -> list[GeneratedVideo]:
    videos = list(
        db.execute(
            select(GeneratedVideo)
            .where(GeneratedVideo.project_id == project_id, GeneratedVideo.lesson_id == lesson_id)
            .order_by(GeneratedVideo.created_at.asc())
        )
        .scalars()
        .all()
    )
    if only_completed:
        return [video for video in videos if video.status in COMPLETED_VIDEO_STATUSES]
    return videos


# --- Text formatting toolkit (Markdown or plain TXT) -----------------------------------


def fmt_heading(text: str, level: int, format_text: str) -> str:
    if format_text == "txt":
        line = safe_text(text, "")
        return f"{line}\n{'-' * max(len(line), 3)}"
    return f"{'#' * max(level, 1)} {safe_text(text, '')}"


def fmt_label(label: str, value: Any, format_text: str) -> str:
    text = safe_text(value, "")
    if not text:
        return ""
    if format_text == "txt":
        return f"{label}: {text}"
    return f"**{label}:** {text}"


def fmt_bullets(label: str, values: Any, format_text: str) -> str:
    items = [safe_text(item, "") for item in as_list(values)]
    items = [item for item in items if item]
    if not items:
        return ""
    bullet = "*" if format_text == "txt" else "-"
    lines = [f"{bullet} {item}" for item in items]
    if format_text == "txt":
        return f"{label}:\n" + "\n".join(lines)
    return f"**{label}:**\n" + "\n".join(lines)


def dict_to_text(data: Any, format_text: str, level: int = 3) -> str:
    if data is None:
        return ""
    if isinstance(data, dict):
        parts: list[str] = []
        for key, value in data.items():
            if key in {"generation_language"} or value in (None, "", []):
                continue
            label = str(key).replace("_", " ").strip().capitalize()
            if isinstance(value, dict):
                parts.append(fmt_heading(label, level, format_text))
                parts.append(dict_to_text(value, format_text, level + 1))
            elif isinstance(value, list):
                rendered = fmt_bullets(label, value, format_text) if not any(
                    isinstance(item, dict) for item in value
                ) else ""
                if rendered:
                    parts.append(rendered)
                else:
                    parts.append(fmt_heading(label, level, format_text))
                    for index, item in enumerate(value, start=1):
                        parts.append(fmt_heading(f"{label} {index}", level + 1, format_text))
                        parts.append(dict_to_text(item, format_text, level + 2))
            else:
                rendered = fmt_label(label, value, format_text)
                if rendered:
                    parts.append(rendered)
        return "\n\n".join(part for part in parts if part)
    return safe_text(data, "")


def join_sections(*sections: str) -> str:
    return "\n\n".join(section for section in sections if section and section.strip()) + "\n"


# --- Section builders --------------------------------------------------------------


def build_document_analysis_text(content: GeneratedContent | None, format_text: str) -> str:
    if content is None or not content.content_json:
        return join_sections(
            fmt_heading("Analise do documento base", 1, format_text),
            "Nenhuma analise de documento base foi gerada para este projeto.",
        )
    data = content.content_json.get("document_analysis")
    if not isinstance(data, dict):
        data = content.content_json
    return join_sections(fmt_heading("Analise do documento base", 1, format_text), dict_to_text(data, format_text, 2))


def build_course_summary_text(content: GeneratedContent | None, format_text: str) -> str:
    if content is None or not content.content_json:
        return join_sections(
            fmt_heading("Resumo do curso", 1, format_text),
            "Nenhum resumo do curso foi gerado para este projeto.",
        )
    summary = content.content_json.get("course_summary")
    if not isinstance(summary, dict):
        summary = content.content_json
    return join_sections(fmt_heading("Resumo do curso", 1, format_text), dict_to_text(summary, format_text, 2))


def build_course_structure_text(content: GeneratedContent | None, project: Project, format_text: str) -> str:
    if content is None or not content.content_json:
        return join_sections(
            fmt_heading("Estrutura do curso", 1, format_text),
            "Nenhuma estrutura de curso foi gerada para este projeto.",
        )
    structure = content.content_json
    course = structure.get("course") if isinstance(structure.get("course"), dict) else structure
    parts = [fmt_heading("Estrutura do curso", 1, format_text)]
    if isinstance(course, dict):
        parts.append(fmt_label("Titulo", course.get("title") or project.title, format_text))
        if course.get("description"):
            parts.append(fmt_label("Descricao", course.get("description"), format_text))
        modules = as_list(course.get("modules"))
    else:
        modules = []
    for module_index, module in enumerate(modules, start=1):
        module_data = module if isinstance(module, dict) else {"title": module}
        module_number = module_data.get("module_number") or module_index
        module_title = safe_text(module_data.get("title"), "")
        parts.append(fmt_heading(f"Modulo {module_number}: {module_title}", 2, format_text))
        if module_data.get("description"):
            parts.append(fmt_label("Descricao", module_data.get("description"), format_text))
        lessons = as_list(module_data.get("lessons"))
        for lesson_index, lesson in enumerate(lessons, start=1):
            lesson_data = lesson if isinstance(lesson, dict) else {"title": lesson}
            lesson_number = lesson_data.get("lesson_number") or lesson_index
            lesson_title = safe_text(lesson_data.get("title"), "")
            parts.append(fmt_label(f"Aula {lesson_number}", lesson_title, format_text))
    return join_sections(*parts)


def build_presentation_text(content: GeneratedContent | None, format_text: str) -> str:
    if content is None or not content.content_json:
        return join_sections(
            fmt_heading("Apresentacao do curso", 1, format_text),
            "Nenhuma apresentacao foi gerada para este projeto.",
        )
    deck = content.content_json
    parts = [
        fmt_heading("Apresentacao do curso", 1, format_text),
        fmt_label("Titulo", deck.get("presentation_title") or content.title, format_text),
        fmt_label("Publico-alvo", deck.get("target_audience"), format_text),
        fmt_label("Duracao estimada", deck.get("estimated_duration"), format_text),
        fmt_label("Estilo visual", deck.get("visual_style"), format_text),
        fmt_label("Objetivo", deck.get("presentation_objective"), format_text),
    ]
    for slide_index, slide in enumerate(as_list(deck.get("slides")), start=1):
        slide_data = slide if isinstance(slide, dict) else {"title": slide}
        slide_number = slide_data.get("slide_number") or slide_index
        parts.append(fmt_heading(f"Slide {slide_number}: {safe_text(slide_data.get('title'), '')}", 2, format_text))
        parts.append(fmt_bullets("Bullets", slide_data.get("bullets"), format_text))
        parts.append(fmt_label("Notas do apresentador", slide_data.get("speaker_notes"), format_text))
        parts.append(fmt_label("Sugestao visual", slide_data.get("visual_suggestion"), format_text))
        parts.append(fmt_label("Pergunta de interacao", slide_data.get("interaction_question"), format_text))
    parts.append(fmt_label("Mensagem de encerramento", deck.get("closing_message"), format_text))
    return join_sections(*parts)


LESSON_SCRIPT_SECTION_KEYS = [
    ("Objetivo da aula", "learning_objective"),
    ("Abertura", "opening"),
    ("Exemplo pratico", "practical_example"),
    ("Pergunta de reflexao", "reflection_question"),
    ("Encerramento", "closing"),
    ("Chamada para acao", "call_to_action"),
]


def build_lesson_script_text(content: GeneratedContent, format_text: str) -> str:
    script = get_lesson_script_dict(content)
    parts = [
        fmt_heading(safe_text(script.get("lesson_title") or content.title, "Roteiro de aula"), 1, format_text),
        fmt_label("Modulo", script.get("module_title"), format_text),
        fmt_label("Duracao estimada (min)", script.get("estimated_duration_minutes"), format_text),
    ]
    for label, key in LESSON_SCRIPT_SECTION_KEYS:
        value = script.get(key)
        if value:
            parts.append(fmt_heading(label, 2, format_text))
            parts.append(safe_text(value, ""))
    main_script = as_list(script.get("main_script"))
    if main_script:
        parts.append(fmt_heading("Desenvolvimento", 2, format_text))
        for block_index, block in enumerate(main_script, start=1):
            block_data = block if isinstance(block, dict) else {"narration": block}
            section_title = safe_text(block_data.get("section_title"), f"Bloco {block_index}")
            parts.append(fmt_heading(section_title, 3, format_text))
            parts.append(safe_text(block_data.get("narration"), ""))
    return join_sections(*parts)


def build_teleprompter_text(content: GeneratedContent) -> str:
    script = get_lesson_script_dict(content)
    text = get_lesson_narration_text(script)
    return text or "Nenhum texto de narracao disponivel para esta aula."


def build_quiz_text(content: GeneratedContent, format_text: str) -> str:
    quiz = content.content_json.get("module_quiz") if content.content_json else None
    quiz = quiz if isinstance(quiz, dict) else {}
    parts = [
        fmt_heading(safe_text(quiz.get("module_title") or content.title, "Quiz"), 1, format_text),
        fmt_label("Instrucoes", quiz.get("instructions"), format_text),
    ]
    for question_index, question in enumerate(as_list(quiz.get("questions")), start=1):
        question_data = question if isinstance(question, dict) else {"question": question}
        parts.append(fmt_heading(f"Pergunta {question_index}", 2, format_text))
        parts.append(safe_text(question_data.get("question"), ""))
        parts.append(fmt_bullets("Alternativas", question_data.get("options"), format_text))
        parts.append(fmt_label("Resposta correta", question_data.get("correct_answer"), format_text))
        parts.append(fmt_label("Explicacao", question_data.get("explanation"), format_text))
    return join_sections(*parts)


def build_materials_text(materials: list[GeneratedContent], format_text: str) -> str:
    if not materials:
        return join_sections(
            fmt_heading("Materiais complementares", 1, format_text),
            "Nenhum material complementar foi gerado para este projeto.",
        )
    parts = [fmt_heading("Materiais complementares", 1, format_text)]
    for material_index, content in enumerate(materials, start=1):
        material = content.content_json.get("complementary_material") if content.content_json else None
        material = material if isinstance(material, dict) else {}
        parts.append(
            fmt_heading(safe_text(material.get("material_title") or content.title, f"Material {material_index}"), 2, format_text)
        )
        parts.append(fmt_label("Tipo", material.get("material_type"), format_text))
        parts.append(fmt_label("Visao geral", material.get("overview"), format_text))
        parts.append(fmt_bullets("Conceitos-chave", material.get("key_concepts"), format_text))
        parts.append(fmt_bullets("Aplicacoes praticas", material.get("practical_applications"), format_text))
        parts.append(fmt_bullets("Exercicios reflexivos", material.get("reflection_exercises"), format_text))
        parts.append(fmt_bullets("Proximos passos", material.get("recommended_next_steps"), format_text))
    return join_sections(*parts)


# --- Manifest & checklist -----------------------------------------------------------


def get_planned_lessons(course_structure: GeneratedContent | None) -> list[tuple[int, int, str]]:
    if course_structure is None or not course_structure.content_json:
        return []
    structure = course_structure.content_json
    course = structure.get("course") if isinstance(structure.get("course"), dict) else structure
    if not isinstance(course, dict):
        return []
    planned: list[tuple[int, int, str]] = []
    for module_index, module in enumerate(as_list(course.get("modules")), start=1):
        module_data = module if isinstance(module, dict) else {}
        module_number = int(module_data.get("module_number") or module_index)
        for lesson_index, lesson in enumerate(as_list(module_data.get("lessons")), start=1):
            lesson_data = lesson if isinstance(lesson, dict) else {}
            lesson_number = int(lesson_data.get("lesson_number") or lesson_index)
            planned.append((module_number, lesson_number, safe_text(lesson_data.get("title"), "")))
    return planned


def build_manifest_text(
    project: Project,
    stats: dict[str, Any],
    generated_at: datetime,
) -> str:
    lines = [
        "# Manifesto do curso",
        "",
        f"- Nome do projeto: {project.title}",
        f"- Data de exportacao: {generated_at.strftime('%d/%m/%Y %H:%M UTC')}",
        f"- Total de modulos: {stats['total_modules']}",
        f"- Total de aulas: {stats['total_lessons']}",
        f"- Total de roteiros: {stats['total_scripts']}",
        f"- Total de quizzes: {stats['total_quizzes']}",
        f"- Total de audios exportados: {stats['total_audios']}",
        f"- Total de videos exportados: {stats['total_videos']}",
        f"- Providers de video usados: {', '.join(stats['video_providers']) if stats['video_providers'] else 'nenhum'}",
        "",
        "## Observacoes",
    ]
    if stats["missing_notes"]:
        lines.extend(f"- {note}" for note in stats["missing_notes"])
    else:
        lines.append("- Nenhuma pendencia identificada.")
    lines.append("")
    return "\n".join(lines)


def build_checklist_text(checklist: dict[str, list[str]]) -> str:
    labels = {
        "lessons_without_script": "Aulas sem roteiro",
        "lessons_without_audio": "Aulas sem audio",
        "lessons_without_video": "Aulas sem video",
        "videos_not_completed": "Videos nao concluidos",
        "modules_without_quiz": "Modulos sem quiz",
        "missing_materials": "Materiais ausentes",
    }
    lines = ["# Checklist de exportacao", ""]
    for key, label in labels.items():
        items = checklist.get(key) or []
        lines.append(f"## {label}")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- Nenhuma pendencia.")
        lines.append("")
    return "\n".join(lines)


# --- ZIP assembly ---------------------------------------------------------------


def safe_resolve_within(storage_dir: Path, file_path: str | None) -> Path | None:
    if not file_path:
        return None
    resolved = Path(file_path).resolve()
    if storage_dir.resolve() not in resolved.parents:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


def build_course_export_zip(
    db: Session,
    project: Project,
    payload: CourseExportCreate,
    destination: Path,
) -> dict[str, Any]:
    format_text = payload.format_text
    text_ext = "md" if format_text == "md" else "txt"

    lesson_scripts = list_lesson_scripts(db, project)
    module_quizzes = list_module_quizzes(db, project)
    materials = list_complementary_materials(db, project)
    course_structure = get_optional_latest_content(db, project, "course_structure")
    course_summary = get_optional_latest_content(db, project, "course_summary")
    document_analysis = get_optional_latest_content(db, project, "document_analysis")
    presentation = get_optional_latest_content(db, project, "presentation_deck")

    audio_storage_dir = get_audio_storage_dir()
    video_storage_dir = get_video_storage_dir()

    checklist: dict[str, list[str]] = {
        "lessons_without_script": [],
        "lessons_without_audio": [],
        "lessons_without_video": [],
        "videos_not_completed": [],
        "modules_without_quiz": [],
        "missing_materials": [],
    }
    video_providers: set[str] = set()
    total_audios_exported = 0
    total_videos_exported = 0

    planned_lessons = get_planned_lessons(course_structure)
    found_lesson_keys = {
        (get_content_field_number(content, "module_number"), get_content_field_number(content, "lesson_number"))
        for content in lesson_scripts
    }
    for module_number, lesson_number, lesson_title in planned_lessons:
        if (module_number, lesson_number) not in found_lesson_keys:
            checklist["lessons_without_script"].append(
                f"Modulo {module_number}, Aula {lesson_number}: {lesson_title or 'sem titulo'}"
            )

    quiz_module_numbers = {get_content_field_number(content, "module_number") for content in module_quizzes}
    planned_module_numbers = sorted({module_number for module_number, _, _ in planned_lessons})
    for module_number in planned_module_numbers:
        if module_number not in quiz_module_numbers:
            checklist["modules_without_quiz"].append(f"Modulo {module_number}")

    if not materials:
        checklist["missing_materials"].append("Nenhum material complementar foi gerado para o curso.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        if payload.include_document_base:
            archive.writestr(
                f"00_documento_base/analise_documento_base.{text_ext}",
                build_document_analysis_text(document_analysis, format_text),
            )

        if payload.include_course_summary:
            archive.writestr(
                f"01_resumo_do_curso/resumo_do_curso.{text_ext}",
                build_course_summary_text(course_summary, format_text),
            )

        if payload.include_course_structure:
            archive.writestr(
                f"02_estrutura_do_curso/estrutura_do_curso.{text_ext}",
                build_course_structure_text(course_structure, project, format_text),
            )
            if course_structure and course_structure.content_json:
                archive.writestr(
                    "02_estrutura_do_curso/estrutura_do_curso.json",
                    json.dumps(course_structure.content_json, ensure_ascii=False, indent=2),
                )

        if payload.include_presentation:
            archive.writestr(
                f"03_apresentacao/apresentacao.{text_ext}",
                build_presentation_text(presentation, format_text),
            )
            if presentation and presentation.content_json:
                archive.writestr(
                    "03_apresentacao/slides.json",
                    json.dumps(presentation.content_json, ensure_ascii=False, indent=2),
                )

        if payload.include_materials:
            archive.writestr(
                f"materiais_complementares/materiais_complementares.{text_ext}",
                build_materials_text(materials, format_text),
            )

        module_folders: dict[int, str] = {}
        for content in lesson_scripts:
            script = get_lesson_script_dict(content)
            module_number = get_content_field_number(content, "module_number") or 9999
            lesson_number = get_content_field_number(content, "lesson_number") or 9999

            if module_number not in module_folders:
                module_title = folder_slug(script.get("module_title"), "sem-titulo")
                module_folders[module_number] = f"modulos/modulo_{module_number:02d}_{module_title}"
            module_folder = module_folders[module_number]

            if payload.include_quizzes:
                quiz_key = f"{module_folder}/quiz.{text_ext}"
                quiz_content = next(
                    (q for q in module_quizzes if get_content_field_number(q, "module_number") == module_number), None
                )
                if quiz_content is not None and quiz_key not in archive.namelist():
                    archive.writestr(quiz_key, build_quiz_text(quiz_content, format_text))

            lesson_title_slug = folder_slug(script.get("lesson_title") or content.title, "sem-titulo")
            lesson_folder = f"{module_folder}/aula_{lesson_number:02d}_{lesson_title_slug}"

            if payload.include_lesson_scripts:
                archive.writestr(f"{lesson_folder}/roteiro.{text_ext}", build_lesson_script_text(content, format_text))

            if payload.include_teleprompter:
                archive.writestr(f"{lesson_folder}/teleprompter.txt", build_teleprompter_text(content))

            has_audio = False
            if payload.include_audio:
                audios = list_audios_for_lesson(db, project.id, content.id)
                for audio_index, audio in enumerate(audios, start=1):
                    resolved_path = safe_resolve_within(audio_storage_dir, audio.file_path)
                    if resolved_path is None:
                        continue
                    audio_ext = (audio.format or "mp3").lower()
                    archive.write(resolved_path, f"{lesson_folder}/audio/audio_{audio_index:02d}.{audio_ext}")
                    has_audio = True
                    total_audios_exported += 1
            if not has_audio:
                checklist["lessons_without_audio"].append(
                    f"Modulo {module_number}, Aula {lesson_number}: {safe_text(script.get('lesson_title'), '')}"
                )

            has_video = False
            if payload.include_video:
                videos = list_videos_for_lesson(db, project.id, content.id, only_completed=False)
                video_index = 0
                for video in videos:
                    is_completed = video.status in COMPLETED_VIDEO_STATUSES
                    if not is_completed:
                        checklist["videos_not_completed"].append(
                            f"Modulo {module_number}, Aula {lesson_number} ({video.provider}): status {video.status}"
                        )
                        if payload.only_completed_video:
                            continue
                    resolved_path = safe_resolve_within(video_storage_dir, video.file_path)
                    if resolved_path is None or not is_valid_mp4_file(resolved_path):
                        continue
                    video_index += 1
                    archive.write(
                        resolved_path, f"{lesson_folder}/video/video_{video_index:02d}.{video.format or 'mp4'}"
                    )
                    has_video = True
                    total_videos_exported += 1
                    video_providers.add(video.provider)
            if not has_video:
                checklist["lessons_without_video"].append(
                    f"Modulo {module_number}, Aula {lesson_number}: {safe_text(script.get('lesson_title'), '')}"
                )

        generated_at = datetime.now(UTC)
        missing_notes = []
        if checklist["lessons_without_script"]:
            missing_notes.append(f"{len(checklist['lessons_without_script'])} aula(s) planejada(s) sem roteiro gerado.")
        if checklist["lessons_without_audio"]:
            missing_notes.append(f"{len(checklist['lessons_without_audio'])} aula(s) sem audio exportado.")
        if checklist["lessons_without_video"]:
            missing_notes.append(f"{len(checklist['lessons_without_video'])} aula(s) sem video exportado.")
        if checklist["videos_not_completed"]:
            missing_notes.append(f"{len(checklist['videos_not_completed'])} video(s) ainda nao concluido(s).")
        if checklist["modules_without_quiz"]:
            missing_notes.append(f"{len(checklist['modules_without_quiz'])} modulo(s) sem quiz gerado.")
        if checklist["missing_materials"]:
            missing_notes.append("Nenhum material complementar foi gerado para o curso.")

        stats = {
            "total_modules": len({m for m, _, _ in planned_lessons} | set(module_folders.keys())),
            "total_lessons": len(lesson_scripts),
            "total_scripts": len(lesson_scripts),
            "total_quizzes": len(module_quizzes),
            "total_audios": total_audios_exported,
            "total_videos": total_videos_exported,
            "video_providers": sorted(video_providers),
            "missing_notes": missing_notes,
        }

        archive.writestr("04_relatorios/manifesto_do_curso.md", build_manifest_text(project, stats, generated_at))
        archive.writestr("04_relatorios/checklist_de_exportacao.md", build_checklist_text(checklist))

    return stats


# --- Job orchestration -----------------------------------------------------------


def create_course_export(
    db: Session, current_user: User, project_id: UUID, payload: CourseExportCreate
) -> CourseExport:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    export = CourseExport(
        project_id=project.id,
        status="pending",
        export_type="full_course",
        options_json=payload.model_dump(mode="json"),
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export


def run_course_export_job(export_id: UUID, user_id: UUID, project_id: UUID) -> None:
    with SessionLocal() as db:
        export = db.get(CourseExport, export_id)
        user = db.get(User, user_id)
        if export is None or user is None:
            return
        try:
            execute_course_export(db, user, export)
        except Exception as exc:  # noqa: BLE001 - top-level safety net for the background task
            db.rollback()
            export = db.get(CourseExport, export_id)
            if export is not None:
                export.status = "failed"
                export.error_message = str(exc)[:2000]
                export.completed_at = datetime.now(UTC)
                db.add(export)
                db.commit()


def execute_course_export(db: Session, current_user: User, export: CourseExport) -> None:
    if export.status != "pending":
        return

    project = get_project_by_id(db, current_user.organization_id, export.project_id)
    payload = CourseExportCreate(**(export.options_json or {}))

    export.status = "running"
    export.started_at = datetime.now(UTC)
    db.add(export)
    db.commit()

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"{project.slug}-full-course-{timestamp}.zip"
    destination = get_export_storage_dir() / filename

    try:
        build_course_export_zip(db, project, payload, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    export.status = "completed"
    export.file_path = str(destination)
    export.file_size_bytes = destination.stat().st_size
    export.completed_at = datetime.now(UTC)
    db.add(export)
    db.commit()
    db.refresh(export)


def get_course_export_for_project(db: Session, project_id: UUID, export_id: UUID) -> CourseExport:
    export = db.execute(
        select(CourseExport).where(CourseExport.id == export_id, CourseExport.project_id == project_id)
    ).scalar_one_or_none()

    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exportacao nao encontrada.")

    return export


def list_course_exports(db: Session, current_user: User, project_id: UUID) -> list[CourseExport]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    return list(
        db.execute(
            select(CourseExport)
            .where(CourseExport.project_id == project.id)
            .order_by(CourseExport.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_course_export(db: Session, current_user: User, project_id: UUID, export_id: UUID) -> CourseExport:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    return get_course_export_for_project(db, project.id, export_id)


def get_course_export_download_path(
    db: Session, current_user: User, project_id: UUID, export_id: UUID
) -> tuple[CourseExport, Path]:
    export = get_course_export(db, current_user, project_id, export_id)
    if export.status != "completed" or not export.file_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta exportacao ainda nao esta concluida.")

    export_dir = get_export_storage_dir().resolve()
    file_path = Path(export.file_path).resolve()
    if export_dir not in file_path.parents:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caminho de exportacao invalido.")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de exportacao nao encontrado.")

    return export, file_path


def delete_course_export(db: Session, current_user: User, project_id: UUID, export_id: UUID) -> None:
    export = get_course_export(db, current_user, project_id, export_id)
    if export.file_path:
        export_dir = get_export_storage_dir().resolve()
        file_path = Path(export.file_path).resolve()
        if export_dir in file_path.parents and file_path.exists() and file_path.is_file():
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass

    db.delete(export)
    db.commit()
