import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.generated_content import GeneratedContent
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.user import User
from app.prompts import (
    COMPLEMENTARY_MATERIAL_PROMPT_VERSION,
    COURSE_SUMMARY_PROMPT_VERSION,
    LESSON_SCRIPT_PROMPT_VERSION,
    MODULE_QUIZ_PROMPT_VERSION,
    PRESENTATION_DECK_PROMPT_VERSION,
    build_complementary_material_prompt,
    build_course_summary_prompt,
    build_lesson_script_prompt,
    build_module_quiz_prompt,
    build_presentation_deck_prompt,
)
from app.providers.ai import AIProviderRequest, OpenAIProvider
from app.services.ai_orchestrator_service import (
    get_latest_extracted_text_file,
    get_openai_provider_record,
    load_extracted_text,
    parse_json_content,
    register_ai_request,
)
from app.services.processing_service import add_processing_log, update_processing_job
from app.services.project_service import get_project_by_id

EXCERPT_CHARS = 20000
MAX_LESSON_SCRIPTS_PER_RUN = 3
MAX_MODULE_QUIZZES_PER_RUN = 2
MAX_COMPLEMENTARY_MATERIALS_PER_RUN = 1
MAX_PRESENTATION_CONTEXT_ITEMS = 8
MAX_PRESENTATION_UPDATE_BYTES = 250_000
MAX_LESSON_SCRIPT_UPDATE_BYTES = 250_000


def get_content_metadata_number(content: GeneratedContent, field: str) -> int:
    def to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    content_json = content.content_json or {}
    metadata = content_json.get("metadata", {})
    if isinstance(metadata, dict) and metadata.get(field) is not None:
        return to_int(metadata.get(field))

    content_key = {
        "module_quiz": "module_quiz",
        "lesson_script": "lesson_script",
    }.get(content.content_type)
    nested = content_json.get(content_key, {}) if content_key else {}
    if isinstance(nested, dict) and nested.get(field) is not None:
        return to_int(nested.get(field))

    return 0


def get_latest_content(
    db: Session,
    project: Project,
    content_type: str,
) -> GeneratedContent | None:
    return db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == project.organization_id,
            GeneratedContent.content_type == content_type,
        )
        .order_by(GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().first()


def get_latest_contents(
    db: Session,
    project: Project,
    content_type: str,
    limit: int = MAX_PRESENTATION_CONTEXT_ITEMS,
) -> list[GeneratedContent]:
    return list(
        db.execute(
            select(GeneratedContent)
            .where(
                GeneratedContent.project_id == project.id,
                GeneratedContent.organization_id == project.organization_id,
                GeneratedContent.content_type == content_type,
            )
            .order_by(GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
            .limit(limit)
        ).scalars().all()
    )


def normalize_presentation_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    if isinstance(value, list):
        return "\n".join(normalize_presentation_text(item) for item in value if item is not None).strip()
    if isinstance(value, dict):
        for key in (
            "title",
            "subtitle",
            "concept",
            "explanation",
            "description",
            "question",
            "answer",
            "content",
            "text",
            "summary",
            "details",
            "speaker_notes",
            "visual_suggestion",
            "interaction_question",
        ):
            if key in value:
                text = normalize_presentation_text(value.get(key))
                if text:
                    return text
        return "\n".join(normalize_presentation_text(item) for item in value.values() if item is not None).strip()
    return str(value)


def normalize_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def normalize_lesson_section(section: Any) -> dict[str, Any]:
    if not isinstance(section, dict):
        return {
            "section_title": "",
            "narration": normalize_presentation_text(section),
            "teaching_notes": "",
            "visual_suggestion": "",
        }

    normalized = {
        key: normalize_presentation_text(value)
        for key, value in section.items()
        if key not in {"section_title", "narration", "teaching_notes", "visual_suggestion"}
    }
    normalized.update(
        {
            "section_title": normalize_presentation_text(section.get("section_title")),
            "narration": normalize_presentation_text(section.get("narration")),
            "teaching_notes": normalize_presentation_text(section.get("teaching_notes")),
            "visual_suggestion": normalize_presentation_text(section.get("visual_suggestion")),
        }
    )
    return normalized


def normalize_lesson_script_payload(payload: dict[str, Any], current_json: dict[str, Any]) -> dict[str, Any]:
    payload_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if payload_size > MAX_LESSON_SCRIPT_UPDATE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="O roteiro enviado e grande demais para salvar.",
        )

    incoming_script = payload.get("lesson_script") if isinstance(payload.get("lesson_script"), dict) else payload
    current_script = current_json.get("lesson_script", {}) if isinstance(current_json.get("lesson_script"), dict) else {}
    script = {**current_script, **incoming_script}
    main_script_payload = script.get("main_script") or []
    if not isinstance(main_script_payload, list):
        main_script_payload = [main_script_payload]

    normalized_script = {
        key: normalize_presentation_text(value)
        for key, value in script.items()
        if key
        not in {
            "module_number",
            "lesson_number",
            "estimated_duration_minutes",
            "main_script",
        }
    }
    normalized_script.update(
        {
            "course_title": normalize_presentation_text(script.get("course_title")),
            "module_number": normalize_int(script.get("module_number"), normalize_int(current_script.get("module_number"), 1)),
            "module_title": normalize_presentation_text(script.get("module_title")),
            "lesson_number": normalize_int(script.get("lesson_number"), normalize_int(current_script.get("lesson_number"), 1)),
            "lesson_title": normalize_presentation_text(script.get("lesson_title")),
            "estimated_duration_minutes": normalize_int(script.get("estimated_duration_minutes"), 10),
            "opening": normalize_presentation_text(script.get("opening")),
            "learning_objective": normalize_presentation_text(script.get("learning_objective")),
            "main_script": [normalize_lesson_section(section) for section in main_script_payload],
            "practical_example": normalize_presentation_text(script.get("practical_example")),
            "reflection_question": normalize_presentation_text(script.get("reflection_question")),
            "closing": normalize_presentation_text(script.get("closing")),
            "call_to_action": normalize_presentation_text(script.get("call_to_action")),
        }
    )

    metadata = {
        "module_number": normalized_script["module_number"],
        "lesson_number": normalized_script["lesson_number"],
        "module_title": normalized_script["module_title"],
        "lesson_title": normalized_script["lesson_title"],
    }

    return {
        **{key: value for key, value in current_json.items() if key not in {"lesson_script", "metadata"}},
        "lesson_script": normalized_script,
        "metadata": metadata,
    }


def update_lesson_script(
    db: Session,
    current_user: User,
    project_id: UUID,
    content_id: UUID,
    payload: dict[str, Any],
) -> GeneratedContent:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    content = db.execute(
        select(GeneratedContent).where(
            GeneratedContent.id == content_id,
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == current_user.organization_id,
            GeneratedContent.content_type == "lesson_script",
        )
    ).scalar_one_or_none()

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roteiro de aula nao encontrado.",
        )

    current_json = content.content_json or {}
    normalized = normalize_lesson_script_payload(payload, current_json)
    generation_language = current_json.get("generation_language") or content.language
    content.content_json = {
        **normalized,
        "generation_language": generation_language,
    }
    lesson_script = content.content_json.get("lesson_script", {})
    if isinstance(lesson_script, dict) and lesson_script.get("lesson_title"):
        content.title = str(lesson_script["lesson_title"])
    content.updated_at = datetime.now(UTC)
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def normalize_presentation_deck(payload: dict[str, Any]) -> dict[str, Any]:
    payload_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if payload_size > MAX_PRESENTATION_UPDATE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="A apresentacao enviada e grande demais para salvar.",
        )

    slides_payload = payload.get("slides")
    if not isinstance(slides_payload, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="slides deve ser uma lista.",
        )

    slides: list[dict[str, Any]] = []
    for index, slide in enumerate(slides_payload, start=1):
        slide_data = slide if isinstance(slide, dict) else {}
        title = normalize_presentation_text(slide_data.get("title")).strip()
        if not title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"O slide {index} deve ter titulo.",
            )

        bullets_payload = slide_data.get("bullets") or []
        if not isinstance(bullets_payload, list):
            bullets_payload = [bullets_payload]

        bullets = [normalize_presentation_text(item).strip() for item in bullets_payload]
        bullets = [item for item in bullets if item]

        slides.append(
            {
                "slide_number": index,
                "title": title,
                "subtitle": normalize_presentation_text(slide_data.get("subtitle")),
                "bullets": bullets,
                "speaker_notes": normalize_presentation_text(slide_data.get("speaker_notes")),
                "visual_suggestion": normalize_presentation_text(slide_data.get("visual_suggestion")),
                "interaction_question": normalize_presentation_text(slide_data.get("interaction_question")),
            }
        )

    return {
        "presentation_title": normalize_presentation_text(payload.get("presentation_title")),
        "target_audience": normalize_presentation_text(payload.get("target_audience")),
        "estimated_duration": normalize_presentation_text(payload.get("estimated_duration")),
        "visual_style": normalize_presentation_text(payload.get("visual_style")),
        "presentation_objective": normalize_presentation_text(payload.get("presentation_objective")),
        "slides": slides,
        "closing_message": normalize_presentation_text(payload.get("closing_message")),
    }


def update_presentation_deck(
    db: Session,
    current_user: User,
    project_id: UUID,
    payload: dict[str, Any],
) -> GeneratedContent:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    content = get_latest_content(db, project, "presentation_deck")

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A apresentacao ainda nao foi gerada para este projeto.",
        )

    normalized = normalize_presentation_deck(payload)
    current_json = content.content_json or {}
    generation_language = current_json.get("generation_language") or content.language
    content.content_json = {
        **normalized,
        "generation_language": generation_language,
    }
    content.title = normalized.get("presentation_title") or content.title or "Apresentacao do curso"
    content.updated_at = datetime.now(UTC)
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def get_next_content_version(db: Session, project: Project, content_type: str, title: str) -> int:
    latest_version = db.execute(
        select(func.max(GeneratedContent.version)).where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == project.organization_id,
            GeneratedContent.content_type == content_type,
            GeneratedContent.title == title,
        )
    ).scalar_one()
    return int(latest_version or 0) + 1


def save_versioned_content(
    db: Session,
    project: Project,
    provider_id: UUID,
    content_type: str,
    title: str,
    content_json: dict[str, Any],
    generation_language: str = "pt-BR",
) -> GeneratedContent:
    content_json = {
        **content_json,
        "generation_language": generation_language,
    }
    content = GeneratedContent(
        project_id=project.id,
        organization_id=project.organization_id,
        content_type=content_type,
        title=title,
        version=get_next_content_version(db, project, content_type, title),
        language=generation_language,
        content_json=content_json,
        status="generated",
        created_by_ai_provider_id=provider_id,
    )
    db.add(content)
    db.flush()
    return content


def call_ai_json(
    db: Session,
    ai_provider: OpenAIProvider,
    project: Project,
    job: ProcessingJob,
    provider_id: UUID,
    request_type: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt: str,
    generation_language: str,
) -> dict[str, Any]:
    settings = get_settings()
    response = ai_provider.generate_text(
        AIProviderRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=settings.openai_default_model,
        )
    )
    register_ai_request(
        db,
        project_id=project.id,
        job_id=job.id,
        provider_id=provider_id,
        request_type=request_type,
        prompt_version=f"{prompt_version}:{generation_language}",
        response=response,
        model_name=settings.openai_default_model,
    )
    if not response.success:
        raise RuntimeError(response.error or f"Falha na chamada de IA: {request_type}.")
    return parse_json_content(response.content)


def add_educational_log(
    db: Session,
    project: Project,
    current_user: User,
    job: ProcessingJob,
    message: str,
    level: str = "info",
    context_json: dict[str, Any] | None = None,
) -> None:
    add_processing_log(
        db,
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_id=job.id,
        level=level,
        message=message,
        context_json=context_json,
    )
    db.flush()


def generate_educational_content(
    db: Session,
    current_user: User,
    project_id: UUID,
    generation_language: str = "pt-BR",
    job: ProcessingJob | None = None,
) -> dict[str, Any]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    analysis_content = get_latest_content(db, project, "document_analysis")
    structure_content = get_latest_content(db, project, "course_structure")

    if structure_content is None or not structure_content.content_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gere a estrutura do curso antes de gerar conteudos educacionais.",
        )

    document_analysis = analysis_content.content_json if analysis_content and analysis_content.content_json else {}
    course_structure = structure_content.content_json
    modules = course_structure.get("course", {}).get("modules", [])

    provider_record = get_openai_provider_record(db)
    project_file = get_latest_extracted_text_file(db, project)
    extracted_excerpt = load_extracted_text(project_file)[:EXCERPT_CHARS]

    if job is None:
        job = ProcessingJob(
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_type="generate_educational_content",
            status="pending",
            attempts=0,
            max_attempts=1,
            progress=0,
            current_step="Aguardando geracao de conteudos",
            message="Job de conteudos educacionais criado",
            payload_json={"course_structure_id": str(structure_content.id)},
        )
        db.add(job)
        db.flush()
    else:
        job.payload_json = {
            **(job.payload_json or {}),
            "course_structure_id": str(structure_content.id),
        }

    ai_provider = OpenAIProvider(get_settings())
    counts = {
        "lesson_scripts": 0,
        "module_quizzes": 0,
        "complementary_materials": 0,
        "course_summaries": 0,
        "presentation_decks": 0,
    }

    try:
        job.status = "running"
        job.attempts = 1
        job.started_at = datetime.now(UTC)
        update_processing_job(db, job, 5, "Job iniciado", "Geracao educacional iniciada")
        project.processing_status = "ai_generating_educational_content"
        add_educational_log(
            db,
            project,
            current_user,
            job,
            message="Geração educacional iniciada",
            context_json={
                "generation_language": generation_language,
                "max_lesson_scripts": MAX_LESSON_SCRIPTS_PER_RUN,
                "max_module_quizzes": MAX_MODULE_QUIZZES_PER_RUN,
                "max_complementary_materials": MAX_COMPLEMENTARY_MATERIALS_PER_RUN,
                "presentation_deck": True,
            },
        )
        try:
            update_processing_job(db, job, 15, "Estrutura carregada", "Estrutura do curso carregada")
            system_prompt, user_prompt = build_course_summary_prompt(
                project,
                document_analysis,
                course_structure,
                generation_language,
            )
            summary_json = call_ai_json(
                db,
                ai_provider,
                project,
                job,
                provider_record.id,
                "generate_course_summary",
                COURSE_SUMMARY_PROMPT_VERSION,
                system_prompt,
                user_prompt,
                generation_language,
            )
            save_versioned_content(
                db,
                project,
                provider_record.id,
                "course_summary",
                summary_json.get("course_summary", {}).get("title") or "Resumo executivo do curso",
                summary_json,
                generation_language,
            )
            counts["course_summaries"] += 1
            add_educational_log(db, project, current_user, job, "Resumo do curso gerado")
        except Exception as exc:
            add_educational_log(
                db,
                project,
                current_user,
                job,
                "Falha ao gerar resumo do curso",
                level="error",
                context_json={"error": str(exc)},
            )
            raise RuntimeError("Falha ao gerar resumo do curso com IA. Tente novamente em instantes.") from exc

        for module in modules[:MAX_MODULE_QUIZZES_PER_RUN]:
            module_number_for_log = module.get("module_number") or "?"
            try:
                update_processing_job(db, job, 50, "Gerando quizzes", f"Gerando quiz do modulo {module_number_for_log}")
                system_prompt, user_prompt = build_module_quiz_prompt(
                    project,
                    document_analysis,
                    course_structure,
                    module,
                    generation_language,
                )
                quiz_json = call_ai_json(
                    db,
                    ai_provider,
                    project,
                    job,
                    provider_record.id,
                    "generate_module_quizzes",
                    MODULE_QUIZ_PROMPT_VERSION,
                    system_prompt,
                    user_prompt,
                    generation_language,
                )
                module_quiz = quiz_json.get("module_quiz", {})
                module_number = module_quiz.get("module_number") or module.get("module_number")
                module_title = module_quiz.get("module_title") or module.get("title")
                module_quiz["module_number"] = module_number
                module_quiz["module_title"] = module_title
                quiz_json["module_quiz"] = module_quiz
                quiz_json["metadata"] = {
                    "module_number": module_number,
                    "module_title": module_title,
                }
                save_versioned_content(
                    db,
                    project,
                    provider_record.id,
                    "module_quiz",
                    f"Quiz - Modulo {module_number}",
                    quiz_json,
                    generation_language,
                )
                counts["module_quizzes"] += 1
                add_educational_log(db, project, current_user, job, f"Quiz gerado: Módulo {module_number}")
            except Exception as exc:
                add_educational_log(
                    db,
                    project,
                    current_user,
                    job,
                    f"Falha ao gerar quiz: Módulo {module_number_for_log}",
                    level="error",
                    context_json={"error": str(exc)},
                )

        lesson_limit_reached = False
        for module in modules:
            if lesson_limit_reached:
                break
            for lesson in module.get("lessons", []):
                if counts["lesson_scripts"] >= MAX_LESSON_SCRIPTS_PER_RUN:
                    lesson_limit_reached = True
                    break
                module_number_for_log = module.get("module_number") or "?"
                lesson_number_for_log = lesson.get("lesson_number") or "?"
                try:
                    update_processing_job(
                        db,
                        job,
                        30,
                        "Gerando roteiros",
                        f"Gerando roteiro do modulo {module_number_for_log}, aula {lesson_number_for_log}",
                    )
                    system_prompt, user_prompt = build_lesson_script_prompt(
                        project,
                        document_analysis,
                        course_structure,
                        module,
                        lesson,
                        extracted_excerpt,
                        generation_language,
                    )
                    script_json = call_ai_json(
                        db,
                        ai_provider,
                        project,
                        job,
                        provider_record.id,
                        "generate_lesson_scripts",
                        LESSON_SCRIPT_PROMPT_VERSION,
                        system_prompt,
                        user_prompt,
                        generation_language,
                    )
                    script = script_json.get("lesson_script", {})
                    module_number = script.get("module_number") or module.get("module_number")
                    lesson_number = script.get("lesson_number") or lesson.get("lesson_number")
                    module_title = script.get("module_title") or module.get("title")
                    lesson_title = script.get("lesson_title") or lesson.get("title")
                    script["module_number"] = module_number
                    script["lesson_number"] = lesson_number
                    script["module_title"] = module_title
                    script["lesson_title"] = lesson_title
                    script_json["lesson_script"] = script
                    script_json["metadata"] = {
                        "module_number": module_number,
                        "lesson_number": lesson_number,
                        "module_title": module_title,
                        "lesson_title": lesson_title,
                    }
                    save_versioned_content(
                        db,
                        project,
                        provider_record.id,
                        "lesson_script",
                        lesson_title or "Roteiro de aula",
                        script_json,
                        generation_language,
                    )
                    counts["lesson_scripts"] += 1
                    add_educational_log(
                        db,
                        project,
                        current_user,
                        job,
                        f"Roteiro gerado: Módulo {module_number}, Aula {lesson_number}",
                    )
                except Exception as exc:
                    add_educational_log(
                        db,
                        project,
                        current_user,
                        job,
                        f"Falha ao gerar roteiro: Módulo {module_number_for_log}, Aula {lesson_number_for_log}",
                        level="error",
                        context_json={"error": str(exc)},
                    )
                    continue

        if MAX_COMPLEMENTARY_MATERIALS_PER_RUN > 0:
            try:
                update_processing_job(
                    db,
                    job,
                    65,
                    "Gerando materiais complementares",
                    "Gerando material complementar",
                )
                system_prompt, user_prompt = build_complementary_material_prompt(
                    project,
                    document_analysis,
                    course_structure,
                    generation_language,
                )
                material_json = call_ai_json(
                    db,
                    ai_provider,
                    project,
                    job,
                    provider_record.id,
                    "generate_complementary_materials",
                    COMPLEMENTARY_MATERIAL_PROMPT_VERSION,
                    system_prompt,
                    user_prompt,
                    generation_language,
                )
                material = material_json.get("complementary_material", {})
                save_versioned_content(
                    db,
                    project,
                    provider_record.id,
                    "complementary_material",
                    material.get("material_title") or "Material complementar",
                    material_json,
                    generation_language,
                )
                counts["complementary_materials"] += 1
                add_educational_log(db, project, current_user, job, "Material complementar gerado")
            except Exception as exc:
                add_educational_log(
                    db,
                    project,
                    current_user,
                    job,
                    "Falha ao gerar material complementar",
                    level="error",
                    context_json={"error": str(exc)},
                )
                raise RuntimeError("Falha ao gerar material complementar com IA. Tente novamente em instantes.") from exc

        try:
            update_processing_job(
                db,
                job,
                80,
                "Gerando apresentacao",
                "Gerando apresentacao pronta a partir dos conteudos educacionais",
            )
            course_summaries = [
                content.content_json or {} for content in get_latest_contents(db, project, "course_summary", limit=3)
            ]
            lesson_scripts = [
                content.content_json or {} for content in get_latest_contents(db, project, "lesson_script")
            ]
            complementary_materials = [
                content.content_json or {} for content in get_latest_contents(db, project, "complementary_material")
            ]
            system_prompt, user_prompt = build_presentation_deck_prompt(
                project,
                document_analysis,
                course_structure,
                course_summaries,
                lesson_scripts,
                complementary_materials,
                generation_language,
            )
            presentation_json = call_ai_json(
                db,
                ai_provider,
                project,
                job,
                provider_record.id,
                "generate_presentation_deck",
                PRESENTATION_DECK_PROMPT_VERSION,
                system_prompt,
                user_prompt,
                generation_language,
            )
            save_versioned_content(
                db,
                project,
                provider_record.id,
                "presentation_deck",
                presentation_json.get("presentation_title") or "Apresentacao do curso",
                presentation_json,
                generation_language,
            )
            counts["presentation_decks"] += 1
            add_educational_log(db, project, current_user, job, "Apresentacao gerada")
        except Exception as exc:
            add_educational_log(
                db,
                project,
                current_user,
                job,
                "Falha ao gerar apresentacao",
                level="error",
                context_json={"error": str(exc)},
            )
            raise RuntimeError("Falha ao gerar apresentacao com IA. Tente novamente em instantes.") from exc

        update_processing_job(db, job, 90, "Salvando conteudos", "Salvando conteudos educacionais")
        project.processing_status = "educational_content_generated"
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.result_json = {"contents_created": counts}
        add_educational_log(
            db,
            project,
            current_user,
            job,
            message="Geração educacional concluída",
            context_json=counts,
        )
        update_processing_job(db, job, 100, "Finalizado", "Conteudos educacionais gerados")
        db.commit()
        return {
            "project_id": project.id,
            "processing_status": project.processing_status,
            "message": (
                "Conteúdos educacionais iniciais gerados com sucesso. "
                "Nesta versão foram gerados os primeiros roteiros, quizzes, materiais e a apresentacao."
            ),
            "contents_created": counts,
        }
    except Exception as exc:
        project.processing_status = "failed"
        job.status = "failed"
        job.error_message = str(exc)
        job.message = "Falha ao gerar conteudos educacionais"
        job.finished_at = datetime.now(UTC)
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            level="error",
            message="Falha ao gerar conteudos educacionais",
            context_json={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


def list_educational_content(db: Session, current_user: User, project_id: UUID) -> dict[str, list[GeneratedContent]]:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    contents = db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == current_user.organization_id,
            GeneratedContent.content_type.in_(
                ["lesson_script", "module_quiz", "complementary_material", "course_summary", "presentation_deck"]
            ),
        )
        .order_by(GeneratedContent.content_type.asc(), GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().all()

    grouped: dict[str, list[GeneratedContent]] = {
        "lesson_scripts": [],
        "module_quizzes": [],
        "complementary_materials": [],
        "course_summaries": [],
        "presentation_decks": [],
    }
    type_map = {
        "lesson_script": "lesson_scripts",
        "module_quiz": "module_quizzes",
        "complementary_material": "complementary_materials",
        "course_summary": "course_summaries",
        "presentation_deck": "presentation_decks",
    }
    for content in contents:
        grouped[type_map[content.content_type]].append(content)

    grouped["lesson_scripts"].sort(
        key=lambda item: (
            get_content_metadata_number(item, "module_number"),
            get_content_metadata_number(item, "lesson_number"),
            item.created_at,
        )
    )
    grouped["module_quizzes"].sort(
        key=lambda item: (
            get_content_metadata_number(item, "module_number"),
            item.created_at,
        )
    )
    grouped["complementary_materials"].sort(key=lambda item: item.created_at)
    grouped["course_summaries"].sort(key=lambda item: (item.version, item.created_at))
    grouped["presentation_decks"].sort(key=lambda item: (item.version, item.created_at))

    return grouped
