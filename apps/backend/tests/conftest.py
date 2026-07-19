import hashlib
import io
import json
import re
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import engine
from app.models.coverage_plan import CoveragePlan
from app.models.coverage_plan_lesson import CoveragePlanLesson
from app.models.coverage_plan_module import CoveragePlanModule
from app.models.document_block import DocumentBlock
from app.models.document_page import DocumentPage
from app.models.generated_content import GeneratedContent
from app.models.lesson_source_item import LessonSourceItem
from app.models.organization import Organization
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.user import User
from app.providers.ai import AIProviderResponse


def make_pdf_bytes(pages: list[str | None], heading_pages: set[int] | None = None) -> bytes:
    """Gera um PDF real (via reportlab) com paginas de texto e, opcionalmente, paginas vazias (None)."""
    heading_pages = heading_pages or set()
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=letter)

    for page_index, text in enumerate(pages, start=1):
        if text:
            y = 750
            for line_index, line in enumerate(text.split("\n")):
                if line_index == 0 and page_index in heading_pages:
                    pdf_canvas.setFont("Helvetica-Bold", 20)
                    pdf_canvas.drawString(72, y, line)
                    pdf_canvas.setFont("Helvetica", 12)
                else:
                    pdf_canvas.drawString(72, y, line)
                y -= 18
        pdf_canvas.showPage()

    pdf_canvas.save()
    return buffer.getvalue()


@pytest.fixture()
def db_session():
    """Sessao de teste isolada por SAVEPOINT: tudo e revertido ao final, mesmo com commits internos."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def organization(db_session):
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    return org


def _make_project(db_session, organization, title="Curso Teste"):
    user = User(
        organization_id=organization.id,
        name="Tester",
        email=f"{uuid.uuid4().hex}@test.local",
        password_hash="hashed",
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        organization_id=organization.id,
        owner_id=user.id,
        title=title,
        slug=f"{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture()
def project(db_session, organization):
    return _make_project(db_session, organization)


@pytest.fixture()
def current_user(db_session, project):
    return db_session.get(User, project.owner_id)


@pytest.fixture()
def other_project(db_session, organization):
    return _make_project(db_session, organization, title="Outro Curso")


@pytest.fixture()
def other_organization(db_session):
    org = Organization(name="Outra Organização", slug=f"other-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture()
def other_org_project(db_session, other_organization):
    return _make_project(db_session, other_organization, title="Curso de Outra Organização")


@pytest.fixture()
def other_org_current_user(db_session, other_org_project):
    return db_session.get(User, other_org_project.owner_id)


def _make_project_file(db_session, project):
    project_file = ProjectFile(
        project_id=project.id,
        organization_id=project.organization_id,
        file_type="source_pdf",
        original_filename="documento.pdf",
        storage_path=f"/storage/{uuid.uuid4().hex}.pdf",
    )
    db_session.add(project_file)
    db_session.flush()
    return project_file


@pytest.fixture()
def project_file(db_session, project):
    return _make_project_file(db_session, project)


@pytest.fixture()
def other_project_file(db_session, other_project):
    return _make_project_file(db_session, other_project)


@pytest.fixture()
def written_pdf_files():
    """Rastreia arquivos reais escritos em disco durante o teste para limpeza garantida."""
    paths: list[Path] = []
    yield paths
    for path in paths:
        path.unlink(missing_ok=True)


def _write_real_project_file(db_session, project, pdf_bytes: bytes, written_pdf_files: list[Path]) -> ProjectFile:
    settings = get_settings()
    relative_path = Path("test-fixtures", f"{uuid.uuid4().hex}.pdf")
    absolute_path = Path(settings.storage_path) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(pdf_bytes)
    written_pdf_files.append(absolute_path)

    project_file = ProjectFile(
        project_id=project.id,
        organization_id=project.organization_id,
        file_type="source_pdf",
        original_filename="documento-teste.pdf",
        storage_path=relative_path.as_posix(),
        mime_type="application/pdf",
        file_size=len(pdf_bytes),
        checksum=hashlib.sha256(pdf_bytes).hexdigest(),
        status="uploaded",
    )
    db_session.add(project_file)
    db_session.flush()
    return project_file


@pytest.fixture()
def real_project_file(db_session, project, written_pdf_files):
    pdf_bytes = make_pdf_bytes(
        [
            "1. Introducao\nEste e o paragrafo inicial do documento de teste.\nEle contem numeros como 2026 e 42.",
            "- Item de lista um\n- Item de lista dois\n- Item de lista tres",
            None,
            "Figura 1: Legenda de exemplo\nOutro paragrafo apos a legenda, com data 11/07/2026.",
        ],
        heading_pages={1},
    )
    return _write_real_project_file(db_session, project, pdf_bytes, written_pdf_files)


@pytest.fixture()
def corrupted_project_file(db_session, project, written_pdf_files):
    return _write_real_project_file(db_session, project, b"not a real pdf file", written_pdf_files)


def _make_lesson_content(db_session, project, title="Aula 1"):
    content = GeneratedContent(
        project_id=project.id,
        organization_id=project.organization_id,
        content_type="lesson_script",
        title=title,
        version=1,
        content_json={"lesson_script": {"lesson_title": title}},
    )
    db_session.add(content)
    db_session.flush()
    return content


@pytest.fixture()
def lesson_content(db_session, project):
    return _make_lesson_content(db_session, project)


@pytest.fixture()
def other_lesson_content(db_session, project):
    return _make_lesson_content(db_session, project, title="Aula 2")


# --------------------------------------------------------------------------
# Fase 19.3 - fixtures de paginas/blocos ja extraidos (sem depender de PDF real)
# e um provedor de IA falso e deterministico (sem chamada de rede).
# --------------------------------------------------------------------------

def _make_extracted_project_file(db_session, project, filename="documento-extraido.pdf") -> ProjectFile:
    project_file = ProjectFile(
        project_id=project.id,
        organization_id=project.organization_id,
        file_type="source_pdf",
        original_filename=filename,
        storage_path=f"test-fixtures/{uuid.uuid4().hex}.pdf",
        checksum=uuid.uuid4().hex,
        status="uploaded",
    )
    db_session.add(project_file)
    db_session.flush()
    return project_file


@pytest.fixture()
def inventory_project_file(db_session, project):
    return _make_extracted_project_file(db_session, project)


@pytest.fixture()
def other_inventory_project_file(db_session, other_project):
    return _make_extracted_project_file(db_session, other_project, filename="outro-documento.pdf")


@pytest.fixture()
def other_org_inventory_project_file(db_session, other_org_project):
    return _make_extracted_project_file(db_session, other_org_project, filename="documento-outra-organizacao.pdf")


def add_extracted_page(
    db_session,
    project_file,
    page_number: int,
    blocks_text: list[tuple[str, str]],
    *,
    extraction_status: str = "extracted",
    requires_ocr: bool = False,
) -> tuple[DocumentPage, list[DocumentBlock]]:
    """blocks_text: lista de (block_type, source_text) na ordem de leitura da pagina."""
    page = DocumentPage(
        project_file_id=project_file.id,
        page_number=page_number,
        raw_text="\n".join(text for _, text in blocks_text),
        normalized_text="\n".join(text for _, text in blocks_text),
        character_count=sum(len(text) for _, text in blocks_text),
        word_count=sum(len(text.split()) for _, text in blocks_text),
        extraction_status=extraction_status,
        extraction_method="native_pdf_text",
        has_text=bool(blocks_text),
        requires_ocr=requires_ocr,
    )
    db_session.add(page)
    db_session.flush()

    blocks: list[DocumentBlock] = []
    for index, (block_type, text) in enumerate(blocks_text):
        block = DocumentBlock(
            project_file_id=project_file.id,
            page_id=page.id,
            block_code=f"P{page_number:04d}-B{index + 1:04d}",
            block_type=block_type,
            block_order=index,
            source_text=text,
            normalized_text=text,
        )
        db_session.add(block)
        blocks.append(block)

    db_session.flush()
    return page, blocks


BLOCK_MARKER_RE = re.compile(
    r"\[(?P<code>P\d{4}-B\d{4}) \| pagina (?P<page>\d+) \| tipo heuristico: (?P<type>\w+)\]\n"
    r"(?P<text>.*?)(?=\n\n\[P\d{4}-B\d{4}|\n\nPara cada unidade|\Z)",
    re.DOTALL,
)
CHUNK_ID_RE = re.compile(r"Chunk: (CHUNK-\d+)")


def default_chunk_ai_response(user_prompt: str, chunk_id: str) -> dict:
    """Resposta 'perfeita' padrao: um item por bloco, com source_text identico ao
    bloco (garante ancoragem 100%). Usada quando o teste nao define um override."""
    items = []
    for index, match in enumerate(BLOCK_MARKER_RE.finditer(user_prompt), start=1):
        text = match.group("text").strip()
        if not text:
            continue
        items.append(
            {
                "temporary_id": f"TMP-{index:04d}",
                "title": text.splitlines()[0][:80],
                "normalized_content": text,
                "source_text": text,
                "content_type": "concept",
                "importance": "relevant",
                "page_start": int(match.group("page")),
                "page_end": int(match.group("page")),
                "source_block_codes": [match.group("code")],
                "source_order": index,
                "depends_on_temporary_ids": [],
                "possible_duplicate": False,
                "possible_fragment": False,
                "requires_review": False,
                "review_reason": None,
            }
        )
    return {"chunk_id": chunk_id, "items": items, "chunk_warnings": [], "unprocessed_content": []}


@pytest.fixture()
def fake_ai_provider(monkeypatch):
    """Substitui OpenAIProvider por um dublê deterministico (sem rede) dentro do
    modulo source_inventory_service. Testes podem popular
    fake_ai_provider['chunk_overrides'][chunk_id] / ['coverage_overrides'][chunk_id]
    com payloads especificos; caso contrario um item por bloco e gerado automaticamente."""
    from app.services import source_inventory_service as svc

    state = {"chunk_overrides": {}, "coverage_overrides": {}, "calls": []}

    class FakeOpenAIProvider:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, request):
            state["calls"].append(request)
            match = CHUNK_ID_RE.search(request.user_prompt)
            chunk_id = match.group(1) if match else "CHUNK-UNKNOWN"

            if "Compare o texto-fonte" in request.system_prompt:
                override = state["coverage_overrides"].get(chunk_id)
                payload = override if override is not None else {
                    "chunk_id": chunk_id,
                    "coverage_status": "complete",
                    "missing_content": [],
                    "warnings": [],
                }
            else:
                override = state["chunk_overrides"].get(chunk_id)
                payload = override if override is not None else default_chunk_ai_response(request.user_prompt, chunk_id)

            return AIProviderResponse(
                success=True,
                content=json.dumps(payload),
                usage={"input_tokens": 100, "output_tokens": 100},
            )

    monkeypatch.setattr(svc, "get_ai_provider", lambda settings: FakeOpenAIProvider(settings))
    return state


# --------------------------------------------------------------------------
# Fase 19.4 - fixtures do plano de cobertura: source_content_items construidos
# diretamente (sem depender do inventario da fase 19.3) e um provedor de IA
# falso e deterministico que organiza os itens do lote em aulas de teste.
# --------------------------------------------------------------------------

def make_source_item(
    db_session,
    project,
    project_file,
    *,
    item_code: str,
    title: str,
    normalized_content: str,
    content_type: str = "concept",
    importance: str = "relevant",
    status: str = "approved",
    source_order: int | None = None,
    page_start: int = 1,
    page_end: int = 1,
):
    from app.models.source_content_item import SourceContentItem

    item = SourceContentItem(
        project_id=project.id,
        project_file_id=project_file.id,
        item_code=item_code,
        title=title,
        source_text=normalized_content,
        normalized_content=normalized_content,
        content_type=content_type,
        importance=importance,
        status=status,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order if source_order is not None else page_start * 1000,
    )
    db_session.add(item)
    db_session.flush()
    return item


COVERAGE_PLAN_ITEM_CODE_RE = re.compile(r"\[(SRC-\d+) \|")
COVERAGE_PLAN_BATCH_ID_RE = re.compile(r"Lote: (BATCH-\d+)")


def default_coverage_plan_ai_response(user_prompt: str, items_per_lesson: int = 4) -> dict:
    """Resposta 'perfeita' padrao: agrupa os itens do lote (na ordem em que aparecem
    no prompt) em aulas de ate `items_per_lesson` itens, dentro de um unico modulo."""
    codes = COVERAGE_PLAN_ITEM_CODE_RE.findall(user_prompt)
    lessons = []
    for index in range(0, len(codes), items_per_lesson):
        group = codes[index : index + items_per_lesson]
        lesson_number = index // items_per_lesson + 1
        lessons.append(
            {
                "temporary_id": f"LES-TMP-{lesson_number:04d}",
                "title": f"Aula {lesson_number}",
                "description": "Aula de teste gerada pelo duble de IA.",
                "learning_objective": "Compreender os itens cobertos.",
                "lesson_order": lesson_number,
                "estimated_word_count": 100,
                "estimated_duration_minutes": 1,
                "source_items": [
                    {
                        "source_item_id": code,
                        "source_order_in_lesson": item_index + 1,
                        "is_required": True,
                        "relationship_type": "primary",
                    }
                    for item_index, code in enumerate(group)
                ],
                "grouping_reason": "Agrupamento sequencial de teste.",
                "dependencies": [],
                "requires_review": False,
                "warnings": [],
            }
        )

    modules = (
        [
            {
                "temporary_id": "MOD-TMP-0001",
                "title": "Módulo Gerado",
                "description": "Módulo de teste.",
                "learning_objective": "Cobrir os itens do lote.",
                "module_order": 1,
                "lessons": lessons,
            }
        ]
        if lessons
        else []
    )

    return {
        "plan_version": 1,
        "modules": modules,
        "mapped_source_item_ids": codes,
        "unmapped_source_item_ids": [],
        "duplicate_mappings": [],
        "warnings": [],
    }


@pytest.fixture()
def fake_coverage_plan_ai_provider(monkeypatch):
    """Substitui OpenAIProvider por um dublê deterministico dentro de
    coverage_plan_service. Testes podem popular
    fake_coverage_plan_ai_provider['batch_overrides'][batch_id] com um payload
    especifico; caso contrario o agrupamento sequencial padrao e usado."""
    from app.services import coverage_plan_service as svc

    state = {"batch_overrides": {}, "calls": []}

    class FakeOpenAIProvider:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, request):
            state["calls"].append(request)
            match = COVERAGE_PLAN_BATCH_ID_RE.search(request.user_prompt)
            batch_id = match.group(1) if match else "BATCH-UNKNOWN"
            override = state["batch_overrides"].get(batch_id)
            payload = override if override is not None else default_coverage_plan_ai_response(request.user_prompt)
            return AIProviderResponse(
                success=True,
                content=json.dumps(payload),
                usage={"input_tokens": 100, "output_tokens": 100},
            )

    monkeypatch.setattr(svc, "get_ai_provider", lambda settings: FakeOpenAIProvider(settings))
    return state


# --------------------------------------------------------------------------
# Fase 19.5 - fixtures da geracao individual das aulas: uma CoveragePlanLesson
# pronta para roteirizar (plano + modulo + aula + itens vinculados) e um
# provedor de IA falso e deterministico que gera um roteiro fiel aos
# normalized_content dos itens realmente enviados no prompt.
# --------------------------------------------------------------------------

@pytest.fixture()
def coverage_plan_lesson_ready(db_session, project, project_file):
    """Plano de cobertura minimo, ja em status 'ready_for_review', com uma unica
    aula (3 source_content_items reais, 2 obrigatorios e 1 complementar) pronta
    para a fase 19.5 gerar o roteiro."""
    plan = CoveragePlan(
        project_id=project.id,
        project_file_id=project_file.id,
        version=1,
        status="ready_for_review",
        inventory_item_count=3,
        inventory_fingerprint="test-fingerprint",
        total_modules=1,
        total_lessons=1,
        total_items=3,
        mapped_items=3,
    )
    db_session.add(plan)
    db_session.flush()

    module = CoveragePlanModule(
        coverage_plan_id=plan.id,
        project_id=project.id,
        title="Módulo 1",
        description="Descrição do módulo de teste.",
        learning_objective="Compreender os fundamentos do módulo.",
        module_order=1,
        status="planned",
        plan_version=1,
    )
    db_session.add(module)
    db_session.flush()

    lesson = CoveragePlanLesson(
        coverage_plan_id=plan.id,
        module_id=module.id,
        title="Aula de Teste",
        description="Descrição da aula de teste.",
        learning_objective="Compreender os itens desta aula.",
        lesson_order=1,
        target_duration_minutes=Decimal("5"),
        estimated_duration_minutes=Decimal("3"),
        estimated_word_count=390,
        source_item_count=3,
        status="planned",
        plan_version=1,
    )
    db_session.add(lesson)
    db_session.flush()

    items = [
        make_source_item(
            db_session,
            project,
            project_file,
            item_code="SRC-0001",
            title="Definição de X",
            normalized_content="X é definido como um conceito central, registrado no ano de 2026.",
            content_type="definition",
            importance="essential",
            source_order=1,
        ),
        make_source_item(
            db_session,
            project,
            project_file,
            item_code="SRC-0002",
            title="Regra de Y",
            normalized_content="A regra de Y estabelece que o procedimento deve seguir 42 etapas obrigatórias.",
            content_type="rule",
            importance="essential",
            source_order=2,
        ),
        make_source_item(
            db_session,
            project,
            project_file,
            item_code="SRC-0003",
            title="Exemplo de Z",
            normalized_content="Um exemplo prático de Z mostra a aplicação real do conceito no cotidiano.",
            content_type="example",
            importance="relevant",
            source_order=3,
        ),
    ]

    links = []
    for order, (item, required) in enumerate(zip(items, [True, True, False], strict=True), start=1):
        link = LessonSourceItem(
            coverage_plan_lesson_id=lesson.id,
            source_item_id=item.id,
            coverage_type="planned_primary" if required else "planned_supporting",
            source_order_in_lesson=order,
            is_required=required,
        )
        db_session.add(link)
        links.append(link)
    db_session.flush()

    return {"plan": plan, "module": module, "lesson": lesson, "items": items, "links": links}


LESSON_SCRIPT_ITEM_RE = re.compile(
    r"\[codigo: (?P<code>SRC-\d+)[^\]]*\]\n"
    r"Titulo: (?P<title>.*?)\n"
    r"Conteudo normalizado: (?P<content>.*?)"
    r"(?=\n\n\[codigo:|\n\nTodos os itens|\Z)",
    re.DOTALL,
)


def default_lesson_script_ai_response(user_prompt: str) -> dict:
    """Resposta 'perfeita' padrao: roteiro composto integralmente pelo titulo +
    normalized_content de cada item realmente presente no prompt (fidelidade
    garantida por construcao), cobrindo todos os codigos declarados."""
    matches = list(LESSON_SCRIPT_ITEM_RE.finditer(user_prompt))
    covered = []
    development_parts = []
    key_points = []
    for match in matches:
        code = match.group("code")
        title = match.group("title").strip()
        content = match.group("content").strip()
        development_parts.append(f"{title}. {content}")
        key_points.append(title)
        covered.append(
            {
                "source_item_id": code,
                "coverage_description": f"Explicado integralmente a partir de: {title}.",
                "coverage_type": "full",
            }
        )

    opening = "Nesta aula vamos compreender, de forma clara e organizada, os conceitos apresentados a seguir."
    development = " ".join(development_parts)
    closing = "Encerramos esta aula recapitulando os pontos principais que acabamos de estudar."
    script = f"{opening} {development} {closing}".strip()
    word_count = len(script.split())

    return {
        "lesson_title": "Aula de Teste",
        "learning_objective": "Compreender os itens cobertos nesta aula.",
        "generation_status": "completed",
        "target_duration_minutes": 5,
        "estimated_duration_minutes": round(word_count / 130, 2),
        "word_count": word_count,
        "opening": opening,
        "development": development,
        "closing": closing,
        "script": script,
        "summary": "Resumo de teste cobrindo os itens da aula.",
        "key_points": key_points,
        "covered_source_items": covered,
        "uncovered_source_items": [],
        "source_pages": [],
        "source_block_codes": [],
        "unsupported_claims_declared": [],
        "requires_split": False,
        "split_reason": None,
        "warnings": [],
    }


@pytest.fixture()
def fake_lesson_generation_ai_provider(monkeypatch):
    """Substitui OpenAIProvider por um dublê deterministico dentro de
    lesson_generation_service. Testes podem definir
    fake_lesson_generation_ai_provider['response_override'] com um dict fixo ou
    uma funcao (user_prompt) -> dict; caso contrario o roteiro fiel padrao e
    gerado automaticamente a partir dos itens realmente presentes no prompt."""
    from app.services import lesson_generation_service as svc

    state: dict = {"response_override": None, "calls": []}

    class FakeOpenAIProvider:
        def __init__(self, settings):
            self.settings = settings

        def generate_text(self, request):
            state["calls"].append(request)
            override = state["response_override"]
            if callable(override):
                payload = override(request.user_prompt)
            elif override is not None:
                payload = override
            else:
                payload = default_lesson_script_ai_response(request.user_prompt)
            return AIProviderResponse(
                success=True,
                content=json.dumps(payload),
                usage={"input_tokens": 100, "output_tokens": 100},
            )

    monkeypatch.setattr(svc, "get_ai_provider", lambda settings: FakeOpenAIProvider(settings))
    return state
