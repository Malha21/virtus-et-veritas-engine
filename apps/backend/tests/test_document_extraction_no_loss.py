"""Teste de nao-perda: garante que a extracao e a normalizacao preservam todo
o conteudo relevante do PDF original (numeros, datas, titulos, itens de lista),
sem resumir, reescrever ou remover trechos silenciosamente."""

from sqlalchemy import select

from app.models.document_page import DocumentPage
from app.services.document_extraction_service import create_extraction_job, extract_document


KNOWN_NUMBERS = ["2026", "42", "1999"]
KNOWN_DATES = ["11/07/2026", "01/01/1999"]
KNOWN_TITLE = "RELATORIO ANUAL DE ATIVIDADES"
KNOWN_LIST_ITEMS = ["Primeiro item da lista", "Segundo item da lista", "Terceiro item da lista"]
KNOWN_NAME = "Joao da Silva Pereira"


def _build_no_loss_pdf():
    from tests.conftest import make_pdf_bytes

    page_one = "\n".join(
        [
            KNOWN_TITLE,
            f"Documento emitido em {KNOWN_DATES[0]}, referente ao ano de {KNOWN_NUMBERS[0]}.",
            f"Responsavel: {KNOWN_NAME}.",
        ]
    )
    page_two = "\n".join([f"- {item}" for item in KNOWN_LIST_ITEMS])
    page_three = f"Fundado em {KNOWN_DATES[1]}, com {KNOWN_NUMBERS[1]} unidades e codigo {KNOWN_NUMBERS[2]}."

    return make_pdf_bytes([page_one, page_two, page_three], heading_pages={1})


def test_extraction_preserves_all_known_content(db_session, current_user, project, written_pdf_files):
    import hashlib
    import uuid
    from pathlib import Path

    from app.core.config import get_settings
    from app.models.project_file import ProjectFile

    pdf_bytes = _build_no_loss_pdf()
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
        original_filename="relatorio.pdf",
        storage_path=relative_path.as_posix(),
        mime_type="application/pdf",
        file_size=len(pdf_bytes),
        checksum=hashlib.sha256(pdf_bytes).hexdigest(),
        status="uploaded",
    )
    db_session.add(project_file)
    db_session.flush()

    job = create_extraction_job(db_session, current_user, project, project_file)
    extract_document(db_session, current_user, job)

    pages = db_session.execute(
        select(DocumentPage)
        .where(DocumentPage.project_file_id == project_file.id)
        .order_by(DocumentPage.page_number.asc())
    ).scalars().all()

    assert len(pages) == 3

    full_raw = "\n".join(p.raw_text or "" for p in pages)
    full_normalized = "\n".join(p.normalized_text or "" for p in pages)

    for number in KNOWN_NUMBERS:
        assert number in full_raw, f"numero {number} ausente do raw_text"
        assert number in full_normalized, f"numero {number} ausente do normalized_text"

    for date in KNOWN_DATES:
        assert date in full_raw
        assert date in full_normalized

    assert KNOWN_TITLE in full_raw
    assert KNOWN_TITLE in full_normalized

    assert KNOWN_NAME in full_raw
    assert KNOWN_NAME in full_normalized

    for item in KNOWN_LIST_ITEMS:
        assert item in full_raw
        assert item in full_normalized

    # sequencia preservada: pagina 1 deve conter o titulo antes do conteudo da pagina 2
    assert full_normalized.index(KNOWN_TITLE) < full_normalized.index(KNOWN_LIST_ITEMS[0])
    assert full_normalized.index(KNOWN_LIST_ITEMS[0]) < full_normalized.index(KNOWN_LIST_ITEMS[1])
    assert full_normalized.index(KNOWN_LIST_ITEMS[1]) < full_normalized.index(KNOWN_LIST_ITEMS[2])


def test_normalization_word_count_does_not_drop_words(db_session, current_user, project, written_pdf_files):
    """A normalizacao pode juntar palavras quebradas por hifen, mas nao pode remover palavras inteiras."""
    import hashlib
    import uuid
    from pathlib import Path

    from app.core.config import get_settings
    from app.models.project_file import ProjectFile
    from tests.conftest import make_pdf_bytes

    text = "Uma frase completa com dez palavras distintas para validar contagem exata"
    pdf_bytes = make_pdf_bytes([text])

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
        original_filename="frase.pdf",
        storage_path=relative_path.as_posix(),
        checksum=hashlib.sha256(pdf_bytes).hexdigest(),
        status="uploaded",
    )
    db_session.add(project_file)
    db_session.flush()

    job = create_extraction_job(db_session, current_user, project, project_file)
    extract_document(db_session, current_user, job)

    page = db_session.execute(
        select(DocumentPage).where(DocumentPage.project_file_id == project_file.id)
    ).scalar_one()

    for word in text.split():
        assert word in page.normalized_text
