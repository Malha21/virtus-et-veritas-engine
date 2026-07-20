import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_provider import AIProvider
from app.models.ai_request import AIRequest
from app.models.generated_content import GeneratedContent
from app.models.processing_job import ProcessingJob
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.prompts import (
    COURSE_STRUCTURE_PROMPT_VERSION,
    DOCUMENT_ANALYSIS_PROMPT_VERSION,
    build_course_structure_expansion_prompt,
    build_course_structure_prompt,
    build_document_analysis_prompt,
)
from app.providers.ai import (
    AIProviderRequest,
    AIProviderResponse,
    get_ai_provider,
    resolve_default_model,
    resolve_provider_key,
    resolve_provider_name,
)
from app.services.processing_service import add_processing_log, update_processing_job
from app.services.project_service import get_project_by_id
from app.services.user_ai_credential_service import resolve_generation_api_key, resolve_generation_base_url

MAX_INITIAL_TEXT_CHARS = 60000
MEDIUM_LARGE_TEXT_CHARS = 45000
MIN_MODULES_FOR_MEDIUM_LARGE_DOCUMENT = 5
MIN_LESSONS_FOR_MEDIUM_LARGE_DOCUMENT = 15


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def get_document_analysis_payload(document_analysis: dict[str, Any]) -> dict[str, Any]:
    payload = document_analysis.get("document_analysis")
    return payload if isinstance(payload, dict) else document_analysis


def count_course_structure_items(course_structure: dict[str, Any]) -> tuple[int, int]:
    course = course_structure.get("course") if isinstance(course_structure, dict) else {}
    modules = as_list(course.get("modules") if isinstance(course, dict) else [])
    lesson_count = 0
    for module in modules:
        if not isinstance(module, dict):
            continue
        lesson_count += len(as_list(module.get("lessons")))
    return len(modules), lesson_count


def get_course_module_titles(course_structure: dict[str, Any]) -> list[str]:
    course = course_structure.get("course") if isinstance(course_structure, dict) else {}
    modules = as_list(course.get("modules") if isinstance(course, dict) else [])
    titles: list[str] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        title = module.get("title")
        module_number = module.get("module_number")
        if isinstance(title, str) and title.strip():
            prefix = f"Modulo {module_number}: " if module_number else ""
            titles.append(f"{prefix}{title.strip()}")
    return titles


def count_document_sequence_items(document_analysis: dict[str, Any]) -> int:
    analysis = get_document_analysis_payload(document_analysis)
    sequence_count = len(as_list(analysis.get("document_sequence")))
    suggested_count = len(as_list(analysis.get("suggested_course_path")))
    return max(sequence_count, suggested_count)


def text_contains_table_of_contents(extracted_text: str) -> bool:
    lowered = extracted_text[:12000].lower()
    markers = [
        "sumario",
        "sumário",
        "introducao",
        "introdução",
        "capitulo",
        "capítulo",
        "o primeiro compromisso",
        "o segundo compromisso",
        "o terceiro compromisso",
        "o quarto compromisso",
    ]
    return sum(1 for marker in markers if marker in lowered) >= 3


def is_medium_or_large_document(document_analysis: dict[str, Any], extracted_text: str) -> bool:
    return (
        len(extracted_text) >= MEDIUM_LARGE_TEXT_CHARS
        or count_document_sequence_items(document_analysis) >= 5
        or text_contains_table_of_contents(extracted_text)
    )


def is_course_structure_insufficient(
    course_structure: dict[str, Any],
    document_analysis: dict[str, Any],
    extracted_text: str,
) -> bool:
    if not is_medium_or_large_document(document_analysis, extracted_text):
        return False
    module_count, lesson_count = count_course_structure_items(course_structure)
    return module_count < MIN_MODULES_FOR_MEDIUM_LARGE_DOCUMENT or lesson_count < MIN_LESSONS_FOR_MEDIUM_LARGE_DOCUMENT


def get_active_ai_provider_record(db: Session, provider_type: str, provider_name: str) -> AIProvider:
    """Busca (ou cria) o registro de AIProvider correspondente ao provider_type
    pedido (o provedor escolhido no projeto, ou o padrao do sistema). Registros
    de provedores anteriores (ex.: uma geracao antiga feita com OpenAI) nao sao
    alterados nem removidos - o historico permanece identificado com o
    provider_type original.
    """
    provider = db.execute(
        select(AIProvider).where(
            AIProvider.provider_type == provider_type,
            AIProvider.status == "active",
        )
    ).scalar_one_or_none()

    if provider is None:
        provider = AIProvider(
            name=provider_name,
            provider_type=provider_type,
            status="active",
        )
        db.add(provider)
        db.flush()

    return provider


def get_latest_extracted_text_file(db: Session, project: Project) -> ProjectFile:
    project_file = db.execute(
        select(ProjectFile)
        .where(
            ProjectFile.project_id == project.id,
            ProjectFile.organization_id == project.organization_id,
            ProjectFile.extracted_text_path.is_not(None),
        )
        .order_by(ProjectFile.created_at.desc())
    ).scalars().first()

    if project_file is None or not project_file.extracted_text_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extraia o texto do PDF antes de gerar a estrutura com IA.",
        )

    return project_file


def load_extracted_text(project_file: ProjectFile) -> str:
    settings = get_settings()
    text_path = Path(settings.storage_path) / str(project_file.extracted_text_path)

    if not text_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Texto extraido nao encontrado no storage.",
        )

    extracted_text = text_path.read_text(encoding="utf-8").strip()
    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Texto extraido vazio.",
        )

    return extracted_text


def parse_json_content(content: str | None) -> dict[str, Any]:
    if not content:
        raise ValueError("Resposta de IA vazia.")

    clean_content = content.strip()
    if clean_content.startswith("```"):
        clean_content = clean_content.strip("`")
        clean_content = clean_content.removeprefix("json").strip()

    parsed = json.loads(clean_content)
    if not isinstance(parsed, dict):
        raise ValueError("Resposta de IA nao retornou um objeto JSON.")

    return parsed


def register_ai_request(
    db: Session,
    project_id: UUID,
    job_id: UUID,
    provider_id: UUID,
    request_type: str,
    prompt_version: str,
    response: AIProviderResponse,
    model_name: str,
    generation_language: str | None = None,
) -> AIRequest:
    usage = response.usage or {}
    ai_request = AIRequest(
        project_id=project_id,
        job_id=job_id,
        provider_id=provider_id,
        request_type=request_type,
        model_name=model_name,
        prompt_version=f"{prompt_version}:{generation_language}" if generation_language else prompt_version,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        status="success" if response.success else "failed",
        error_message=response.error,
    )
    db.add(ai_request)
    db.flush()
    return ai_request


def save_generated_content(
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
        version=1,
        language=generation_language,
        content_json=content_json,
        status="generated",
        created_by_ai_provider_id=provider_id,
    )
    db.add(content)
    db.flush()
    return content


def get_latest_document_analysis_content(db: Session, project: Project) -> GeneratedContent | None:
    return db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == project.organization_id,
            GeneratedContent.content_type == "document_analysis",
        )
        .order_by(GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().first()


def generate_project_structure(
    db: Session,
    current_user: User,
    project_id: UUID,
    generation_language: str = "pt-BR",
    job: ProcessingJob | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    project = get_project_by_id(db, current_user, project_id)
    project_file = get_latest_extracted_text_file(db, project)
    provider_key = resolve_provider_key(settings, project.ai_provider)
    provider_record = get_active_ai_provider_record(db, provider_key, resolve_provider_name(settings, provider_key))
    extracted_text = load_extracted_text(project_file)

    if job is None:
        job = ProcessingJob(
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_type="generate_course_structure",
            status="pending",
            attempts=0,
            max_attempts=1,
            progress=0,
            current_step="Aguardando geracao de estrutura",
            message="Job de estrutura criado",
            payload_json={"project_file_id": str(project_file.id), "text_chars": len(extracted_text)},
        )
        db.add(job)
        db.flush()
    else:
        job.payload_json = {
            **(job.payload_json or {}),
            "project_file_id": str(project_file.id),
            "text_chars": len(extracted_text),
        }

    user_api_key = resolve_generation_api_key(db, current_user, provider_key)
    user_base_url = resolve_generation_base_url(db, current_user, provider_key)
    ai_provider = get_ai_provider(settings, provider_key, api_key_override=user_api_key, base_url_override=user_base_url)

    try:
        job.status = "running"
        job.attempts = 1
        job.started_at = datetime.now(UTC)
        update_processing_job(db, job, 5, "Job iniciado", "Geracao de estrutura com IA iniciada")
        project.processing_status = "ai_generating_structure"
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            message="Geracao de estrutura com IA iniciada",
        )
        db.flush()

        update_processing_job(db, job, 20, "Texto do documento preparado", "Texto extraido carregado para estrutura")
        analysis_content = get_latest_document_analysis_content(db, project)

        if analysis_content and analysis_content.content_json:
            document_analysis = analysis_content.content_json
            update_processing_job(
                db,
                job,
                35,
                "Analise do documento localizada",
                "Usando analise inteligente do documento base como referencia principal",
            )
            add_processing_log(
                db,
                project_id=project.id,
                organization_id=current_user.organization_id,
                job_id=job.id,
                message="Analise do documento base encontrada e usada para gerar a estrutura",
                context_json={"document_analysis_id": str(analysis_content.id)},
            )
        else:
            system_prompt, user_prompt = build_document_analysis_prompt(project, extracted_text, generation_language)
            update_processing_job(db, job, 35, "Analise nao encontrada", "Gerando analise do documento antes da estrutura")
            analysis_response = ai_provider.generate_text(
                AIProviderRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=resolve_default_model(settings, provider_key),
                    max_retries=3,
                )
            )
            register_ai_request(
                db,
                project_id=project.id,
                job_id=job.id,
                provider_id=provider_record.id,
                request_type="analyze_document",
                prompt_version=DOCUMENT_ANALYSIS_PROMPT_VERSION,
                response=analysis_response,
                model_name=resolve_default_model(settings, provider_key),
                generation_language=generation_language,
            )
            if not analysis_response.success:
                raise RuntimeError(analysis_response.error or "Falha ao analisar documento com IA.")

            document_analysis = parse_json_content(analysis_response.content)
            analysis_content = save_generated_content(
                db,
                project=project,
                provider_id=provider_record.id,
                content_type="document_analysis",
                title="Analise do documento",
                content_json=document_analysis,
                generation_language=generation_language,
            )

        system_prompt, user_prompt = build_course_structure_prompt(
            project,
            document_analysis,
            extracted_text,
            generation_language,
        )
        structure_response = ai_provider.generate_text(
            AIProviderRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=resolve_default_model(settings, provider_key),
                max_retries=3,
            )
        )
        register_ai_request(
            db,
            project_id=project.id,
            job_id=job.id,
            provider_id=provider_record.id,
            request_type="generate_course_structure",
            prompt_version=COURSE_STRUCTURE_PROMPT_VERSION,
            response=structure_response,
            model_name=resolve_default_model(settings, provider_key),
            generation_language=generation_language,
        )
        if not structure_response.success:
            raise RuntimeError(structure_response.error or "Falha ao gerar estrutura do curso com IA.")

        course_structure = parse_json_content(structure_response.content)
        module_count, lesson_count = count_course_structure_items(course_structure)
        module_titles = get_course_module_titles(course_structure)
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            message="Estrutura inicial recebida da IA",
            context_json={
                "modules": module_count,
                "lessons": lesson_count,
                "module_titles": module_titles,
                "insufficient_retry": False,
            },
        )
        if is_course_structure_insufficient(course_structure, document_analysis, extracted_text):
            update_processing_job(
                db,
                job,
                68,
                "Estrutura superficial detectada",
                "Reexecutando geracao para expandir modulos e aulas",
            )
            add_processing_log(
                db,
                project_id=project.id,
                organization_id=current_user.organization_id,
                job_id=job.id,
                message="Estrutura inicial insuficiente; reexecutando geracao expandida",
                context_json={
                    "modules": module_count,
                    "lessons": lesson_count,
                    "module_titles": module_titles,
                    "insufficient_retry": True,
                },
            )
            expansion_system_prompt, expansion_user_prompt = build_course_structure_expansion_prompt(
                project,
                document_analysis,
                extracted_text,
                course_structure,
                generation_language,
            )
            expansion_response = ai_provider.generate_text(
                AIProviderRequest(
                    system_prompt=expansion_system_prompt,
                    user_prompt=expansion_user_prompt,
                    model=resolve_default_model(settings, provider_key),
                )
            )
            register_ai_request(
                db,
                project_id=project.id,
                job_id=job.id,
                provider_id=provider_record.id,
                request_type="expand_course_structure",
                prompt_version=COURSE_STRUCTURE_PROMPT_VERSION,
                response=expansion_response,
                model_name=resolve_default_model(settings, provider_key),
                generation_language=generation_language,
            )
            if not expansion_response.success:
                raise RuntimeError(expansion_response.error or "Falha ao expandir estrutura do curso com IA.")

            expanded_structure = parse_json_content(expansion_response.content)
            expanded_module_count, expanded_lesson_count = count_course_structure_items(expanded_structure)
            expanded_module_titles = get_course_module_titles(expanded_structure)
            if expanded_module_count >= module_count and expanded_lesson_count >= lesson_count:
                course_structure = expanded_structure
                add_processing_log(
                    db,
                    project_id=project.id,
                    organization_id=current_user.organization_id,
                    job_id=job.id,
                    message="Estrutura expandida recebida da IA",
                    context_json={
                        "modules": expanded_module_count,
                        "lessons": expanded_lesson_count,
                        "module_titles": expanded_module_titles,
                        "insufficient_retry": True,
                    },
                )

        update_processing_job(db, job, 75, "Estrutura recebida", "Estrutura do curso recebida da IA")
        final_module_count, final_lesson_count = count_course_structure_items(course_structure)
        final_module_titles = get_course_module_titles(course_structure)
        structure_content = save_generated_content(
            db,
            project=project,
            provider_id=provider_record.id,
            content_type="course_structure",
            title=course_structure.get("course", {}).get("title") or "Estrutura inicial do curso",
            content_json=course_structure,
            generation_language=generation_language,
        )

        update_processing_job(db, job, 90, "Salvando estrutura", "Salvando estrutura gerada")
        project.processing_status = "ai_structure_generated"
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.result_json = {
            "document_analysis_id": str(analysis_content.id),
            "course_structure_id": str(structure_content.id),
        }
        update_processing_job(db, job, 100, "Finalizado", "Estrutura gerada com sucesso")
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            message="Estrutura de curso gerada com sucesso",
            context_json={
                **job.result_json,
                "modules": final_module_count,
                "lessons": final_lesson_count,
                "module_titles": final_module_titles,
            },
        )
        db.commit()
        return {
            "project_id": project.id,
            "processing_status": project.processing_status,
            "message": "Estrutura gerada com sucesso",
            "contents": {
                "document_analysis_id": analysis_content.id,
                "course_structure_id": structure_content.id,
            },
        }
    except Exception as exc:
        project.processing_status = "failed"
        job.status = "failed"
        job.error_message = str(exc)
        job.message = "Falha ao gerar estrutura com IA"
        job.finished_at = datetime.now(UTC)
        add_processing_log(
            db,
            project_id=project.id,
            organization_id=current_user.organization_id,
            job_id=job.id,
            level="error",
            message="Falha ao gerar estrutura com IA",
            context_json={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
