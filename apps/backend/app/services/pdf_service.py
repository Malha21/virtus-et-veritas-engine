from pathlib import Path

from pypdf import PdfReader


class PDFTextExtractionError(Exception):
    """Levantada tanto para falhas de extracao de PDF quanto de EPUB (nome
    mantido por compatibilidade com o restante do modulo)."""


def extract_text_from_pdf(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise PDFTextExtractionError("Arquivo PDF não encontrado no storage.")

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise PDFTextExtractionError("Não foi possível abrir o PDF enviado.") from exc

    page_texts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if cleaned:
            page_texts.append(cleaned)

    full_text = "\n\n".join(page_texts).strip()
    if not full_text:
        raise PDFTextExtractionError("Não encontramos texto extraível neste PDF.")

    return full_text


def extract_text_from_epub(epub_path: Path) -> str:
    from app.services.document_extraction_service import extract_epub_chapters

    if not epub_path.exists():
        raise PDFTextExtractionError("Arquivo EPUB não encontrado no storage.")

    try:
        chapters = extract_epub_chapters(epub_path)
    except Exception as exc:
        raise PDFTextExtractionError("Não foi possível abrir o EPUB enviado.") from exc

    chapter_texts: list[str] = []
    for chapter in chapters:
        text = chapter["raw_text"] or ""
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if cleaned:
            chapter_texts.append(cleaned)

    full_text = "\n\n".join(chapter_texts).strip()
    if not full_text:
        raise PDFTextExtractionError("Não encontramos texto extraível neste EPUB.")

    return full_text
