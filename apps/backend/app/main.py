from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.ai import router as ai_router
from app.api.v1.audio import router as audio_router
from app.api.v1.auth import router as auth_router
from app.api.v1.contents import router as contents_router
from app.api.v1.course_exports import router as course_exports_router
from app.api.v1.coverage_plan import lessons_router as coverage_plan_lessons_router
from app.api.v1.coverage_plan import router as coverage_plan_router
from app.api.v1.document_analysis import router as document_analysis_router
from app.api.v1.document_extraction import router as document_extraction_router
from app.api.v1.educational_content import router as educational_content_router
from app.api.v1.exports import router as exports_router
from app.api.v1.files import router as files_router
from app.api.v1.health import router as health_router
from app.api.v1.instructor_assets import router as instructor_assets_router
from app.api.v1.instructor_profiles import router as instructor_profiles_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.lesson_generation import course_router as lesson_generation_course_router
from app.api.v1.lesson_generation import lesson_router as lesson_generation_lesson_router
from app.api.v1.market_insights import router as market_insights_router
from app.api.v1.processing import router as processing_router
from app.api.v1.project_video_settings import router as project_video_settings_router
from app.api.v1.projects import router as projects_router
from app.api.v1.public_assets import router as public_assets_router
from app.api.v1.source_inventory import router as source_inventory_router
from app.api.v1.user_ai_credentials import router as user_ai_credentials_router
from app.api.v1.video_avatars import router as video_avatars_router
from app.api.v1.video_pipeline import router as video_pipeline_router
from app.api.v1.videos import router as videos_router
from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health", tags=["health"])
def public_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "vve-engine",
    }


app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(admin_users_router, prefix=settings.api_prefix)
app.include_router(user_ai_credentials_router, prefix=settings.api_prefix)
app.include_router(projects_router, prefix=settings.api_prefix)
app.include_router(files_router, prefix=settings.api_prefix)
app.include_router(processing_router, prefix=settings.api_prefix)
app.include_router(contents_router, prefix=settings.api_prefix)
app.include_router(document_analysis_router, prefix=settings.api_prefix)
app.include_router(document_extraction_router, prefix=settings.api_prefix)
app.include_router(source_inventory_router, prefix=settings.api_prefix)
app.include_router(coverage_plan_router, prefix=settings.api_prefix)
app.include_router(coverage_plan_lessons_router, prefix=settings.api_prefix)
app.include_router(lesson_generation_lesson_router, prefix=settings.api_prefix)
app.include_router(lesson_generation_course_router, prefix=settings.api_prefix)
app.include_router(market_insights_router, prefix=settings.api_prefix)
app.include_router(ai_router, prefix=settings.api_prefix)
app.include_router(audio_router, prefix=settings.api_prefix)
app.include_router(instructor_assets_router, prefix=settings.api_prefix)
app.include_router(instructor_profiles_router, prefix=settings.api_prefix)
app.include_router(educational_content_router, prefix=settings.api_prefix)
app.include_router(jobs_router, prefix=settings.api_prefix)
app.include_router(exports_router, prefix=settings.api_prefix)
app.include_router(course_exports_router, prefix=settings.api_prefix)
app.include_router(videos_router, prefix=settings.api_prefix)
app.include_router(video_avatars_router, prefix=settings.api_prefix)
app.include_router(video_pipeline_router, prefix=settings.api_prefix)
app.include_router(project_video_settings_router, prefix=settings.api_prefix)
app.include_router(public_assets_router, prefix=settings.api_prefix)
