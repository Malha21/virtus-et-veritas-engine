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
    build_complementary_material_prompt,
    build_course_summary_prompt,
    build_lesson_script_prompt,
    build_module_quiz_prompt,
)
from app.providers.ai import AIProviderRequest, OpenAIProvider
from app.services.ai_orchestrator_service import (
    get_latest_extracted_text_file,
    get_openai_provider_record,
    load_extracted_text,
    parse_json_content,
    register_ai_request,
)
from app.services.processing_service import add_processing_log
from app.services.project_service import get_project_by_id

EXCERPT_CHARS = 20000
MAX_LESSON_SCRIPTS_PER_RUN = 3
MAX_MODULE_QUIZZES_PER_RUN = 2
MAX_COMPLEMENTARY_MATERIALS_PER_RUN = 1


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

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_type="generate_educational_content",
        status="pending",
        attempts=0,
        max_attempts=1,
        payload_json={"course_structure_id": str(structure_content.id)},
    )
    db.add(job)
    db.flush()

    ai_provider = OpenAIProvider(get_settings())
    counts = {
        "lesson_scripts": 0,
        "module_quizzes": 0,
        "complementary_materials": 0,
        "course_summaries": 0,
    }

    try:
        job.status = "running"
        job.attempts = 1
        job.started_at = datetime.now(UTC)
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
            },
        )
        try:
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
        db.commit()
        return {
            "project_id": project.id,
            "processing_status": project.processing_status,
            "message": (
                "Conteúdos educacionais iniciais gerados com sucesso. "
                "Nesta versão foram gerados os primeiros roteiros, quizzes e materiais."
            ),
            "contents_created": counts,
        }
    except Exception as exc:
        project.processing_status = "failed"
        job.status = "failed"
        job.error_message = str(exc)
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
                ["lesson_script", "module_quiz", "complementary_material", "course_summary"]
            ),
        )
        .order_by(GeneratedContent.content_type.asc(), GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().all()

    grouped: dict[str, list[GeneratedContent]] = {
        "lesson_scripts": [],
        "module_quizzes": [],
        "complementary_materials": [],
        "course_summaries": [],
    }
    type_map = {
        "lesson_script": "lesson_scripts",
        "module_quiz": "module_quizzes",
        "complementary_material": "complementary_materials",
        "course_summary": "course_summaries",
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

    return grouped
