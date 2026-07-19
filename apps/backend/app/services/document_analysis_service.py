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
from app.models.project_file import ProjectFile
from app.models.user import User
from app.prompts import DOCUMENT_ANALYSIS_PROMPT_VERSION, build_document_analysis_prompt
from app.providers.ai import (
    AIProvider,
    AIProviderRequest,
    get_ai_provider,
    resolve_api_key,
    resolve_default_model,
    resolve_provider_key,
    resolve_provider_name,
)
from app.services.ai_orchestrator_service import (
    get_active_ai_provider_record,
    load_extracted_text,
    parse_json_content,
    register_ai_request,
)
from app.services.project_service import get_project_by_id


def get_latest_document_analysis(
    db: Session,
    current_user: User,
    project_id: UUID,
) -> GeneratedContent | None:
    project = get_project_by_id(db, current_user.organization_id, project_id)
    return db.execute(
        select(GeneratedContent)
        .where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == current_user.organization_id,
            GeneratedContent.content_type == "document_analysis",
        )
        .order_by(GeneratedContent.version.desc(), GeneratedContent.created_at.desc())
    ).scalars().first()


def get_latest_project_file_with_text(db: Session, project: Project) -> ProjectFile:
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
            detail="Extraia o texto do PDF antes de gerar a analise do documento base.",
        )

    return project_file


def get_next_document_analysis_version(db: Session, project: Project) -> int:
    current_version = db.execute(
        select(func.max(GeneratedContent.version)).where(
            GeneratedContent.project_id == project.id,
            GeneratedContent.organization_id == project.organization_id,
            GeneratedContent.content_type == "document_analysis",
        )
    ).scalar_one_or_none()
    return int(current_version or 0) + 1


def normalize_document_analysis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    document_analysis = payload.get("document_analysis")
    if isinstance(document_analysis, dict):
        return {"document_analysis": document_analysis}
    return {"document_analysis": payload}


def generate_document_analysis(
    db: Session,
    current_user: User,
    project_id: UUID,
    generation_language: str = "pt-BR",
) -> GeneratedContent:
    settings = get_settings()
    project = get_project_by_id(db, current_user.organization_id, project_id)
    provider_key = resolve_provider_key(settings, project.ai_provider)
    api_key = resolve_api_key(settings, provider_key)
    if not api_key or api_key.startswith("change_me_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chave de API nao configurada para o provedor {resolve_provider_name(settings, provider_key)}.",
        )

    project_file = get_latest_project_file_with_text(db, project)
    extracted_text = load_extracted_text(project_file)
    provider_record = get_active_ai_provider_record(db, provider_key, resolve_provider_name(settings, provider_key))

    job = ProcessingJob(
        project_id=project.id,
        organization_id=current_user.organization_id,
        job_type="generate_document_analysis",
        status="running",
        attempts=1,
        max_attempts=1,
        progress=10,
        current_step="Gerando analise do documento base",
        message="Analise inteligente do documento iniciada",
        started_at=datetime.now(UTC),
        payload_json={"project_file_id": str(project_file.id), "text_chars": len(extracted_text)},
    )
    db.add(job)
    db.flush()

    ai_provider = get_ai_provider(settings, provider_key)
    system_prompt, user_prompt = build_document_analysis_prompt(project, extracted_text, generation_language)
    response = ai_provider.generate_text(
        AIProviderRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=resolve_default_model(settings, provider_key),
            response_format="json",
        )
    )
    register_ai_request(
        db,
        project_id=project.id,
        job_id=job.id,
        provider_id=provider_record.id,
        request_type="generate_document_analysis",
        prompt_version=DOCUMENT_ANALYSIS_PROMPT_VERSION,
        response=response,
        model_name=resolve_default_model(settings, provider_key),
        generation_language=generation_language,
    )

    if not response.success:
        job.status = "failed"
        job.error_message = response.error or "Falha ao gerar analise do documento base."
        job.finished_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=response.error or "Falha ao gerar analise do documento base.",
        )

    try:
        parsed_payload = parse_json_content(response.content)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A IA retornou uma analise em formato invalido.",
        ) from exc

    content_json = {
        **normalize_document_analysis_payload(parsed_payload),
        "generation_language": generation_language,
    }
    document_analysis = content_json.get("document_analysis") or {}
    title = (
        document_analysis.get("document_title")
        if isinstance(document_analysis, dict)
        else None
    ) or "Analise inteligente do documento base"

    content = GeneratedContent(
        project_id=project.id,
        organization_id=project.organization_id,
        content_type="document_analysis",
        title=title,
        version=get_next_document_analysis_version(db, project),
        language=generation_language,
        content_json=content_json,
        status="generated",
        created_by_ai_provider_id=provider_record.id,
    )
    db.add(content)
    db.flush()

    job.status = "completed"
    job.progress = 100
    job.current_step = "Analise do documento base gerada"
    job.message = "Analise inteligente do documento base gerada com sucesso"
    job.finished_at = datetime.now(UTC)
    job.result_json = {"document_analysis_id": str(content.id)}
    db.commit()
    db.refresh(content)
    return content
