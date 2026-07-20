import logging
import re
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.market_bestseller import MarketBestseller

logger = logging.getLogger(__name__)

PUBLISHNEWS_SOURCE = "publishnews"
MONTHLY_RANKING_URL = "https://www.publishnews.com.br/ranking-nielsen/mensal/0/{year}-{month:02d}/0/0"

# Meses em portugues, como aparecem no <title> da pagina (ex.: "Julho de 2026").
MONTH_NAMES_PT = [
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


class MarketInsightFetchError(Exception):
    pass


def _parse_volume(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _extract_category(block) -> str | None:
    category_div = block.find("div", class_="pn-ranking-livro-categoria")
    if category_div is None:
        return None
    strong = category_div.find("strong")
    text = strong.get_text(strip=True) if strong else category_div.get_text(strip=True)
    return text or None


def parse_bestsellers_html(html: str, period_label: str) -> list[dict]:
    """Extrai a lista de livros do ranking geral do PublishNews a partir do HTML da pagina.

    Estrutura real (confirmada em 2026-07-19): cada posicao do ranking e um
    bloco `.pn-ranking-livros-posicao` contendo numero, volume de vendas e os
    dados do livro (nome/autor/editora/categoria) em elementos filhos com
    classes fixas do site. Se o site mudar o HTML, este parser para de achar
    blocos e retorna lista vazia (ver uso em fetch_and_store_bestsellers).
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict] = []

    for position in soup.find_all("div", class_="pn-ranking-livros-posicao"):
        number_div = position.find("div", class_="pn-ranking-livros-posicao-numero")
        volume_div = position.find("div", class_="pn-ranking-livros-posicao-volume")
        name_div = position.find("div", class_="pn-ranking-livro-nome")
        author_div = position.find("div", class_="pn-ranking-livro-autor")
        publisher_div = position.find("div", class_="pn-ranking-livro-editora")

        if number_div is None or name_div is None:
            continue

        try:
            rank = int(number_div.get_text(strip=True))
        except ValueError:
            continue

        title = name_div.get_text(strip=True)
        if not title:
            continue

        entries.append(
            {
                "rank": rank,
                "title": title,
                "author": author_div.get_text(strip=True) if author_div else None,
                "publisher": publisher_div.get_text(strip=True) if publisher_div else None,
                "category": _extract_category(position),
                "sales_volume": _parse_volume(volume_div.get_text(strip=True) if volume_div else None),
                "period_label": period_label,
            }
        )

    return entries


def fetch_bestsellers_html(reference_date: datetime | None = None) -> tuple[str, str]:
    reference_date = reference_date or datetime.now(UTC)
    url = MONTHLY_RANKING_URL.format(year=reference_date.year, month=reference_date.month)
    period_label = f"{MONTH_NAMES_PT[reference_date.month - 1]} de {reference_date.year}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
    }
    try:
        response = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MarketInsightFetchError(f"Falha ao buscar ranking do PublishNews: {exc}") from exc

    return response.text, period_label


def fetch_and_store_bestsellers(db: Session) -> int:
    """Busca o ranking mensal atual e substitui o snapshot armazenado.

    Nunca levanta excecao para o chamador (job agendado): falhas de rede ou
    de parsing (site fora do ar, HTML mudou) sao logadas e a funcao retorna
    0, mantendo os dados do snapshot anterior intactos no banco.
    """
    try:
        html, period_label = fetch_bestsellers_html()
        entries = parse_bestsellers_html(html, period_label)
    except MarketInsightFetchError as exc:
        logger.warning("Nao foi possivel buscar insights de mercado: %s", exc)
        return 0

    if not entries:
        logger.warning("Parser de insights de mercado nao encontrou nenhum livro no HTML retornado.")
        return 0

    db.execute(delete(MarketBestseller).where(MarketBestseller.source == PUBLISHNEWS_SOURCE))
    for entry in entries:
        db.add(
            MarketBestseller(
                source=PUBLISHNEWS_SOURCE,
                period_type="mensal",
                period_label=entry["period_label"],
                rank=entry["rank"],
                title=entry["title"],
                author=entry["author"],
                publisher=entry["publisher"],
                category=entry["category"],
                sales_volume=entry["sales_volume"],
            )
        )
    db.commit()
    logger.info("Insights de mercado atualizados: %d livros (%s).", len(entries), entries[0]["period_label"])
    return len(entries)


def get_top_books(db: Session, limit: int = 10) -> list[MarketBestseller]:
    statement = (
        select(MarketBestseller)
        .where(MarketBestseller.source == PUBLISHNEWS_SOURCE)
        .order_by(MarketBestseller.rank.asc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def get_top_themes(db: Session, limit: int = 10) -> list[dict]:
    statement = (
        select(
            MarketBestseller.category,
            func.coalesce(func.sum(MarketBestseller.sales_volume), 0).label("total_volume"),
            func.count(MarketBestseller.id).label("book_count"),
        )
        .where(MarketBestseller.source == PUBLISHNEWS_SOURCE, MarketBestseller.category.is_not(None))
        .group_by(MarketBestseller.category)
        .order_by(func.coalesce(func.sum(MarketBestseller.sales_volume), 0).desc())
        .limit(limit)
    )
    rows = db.execute(statement).all()
    return [
        {"category": row.category, "total_volume": row.total_volume, "book_count": row.book_count}
        for row in rows
    ]


def get_last_updated(db: Session) -> datetime | None:
    statement = (
        select(MarketBestseller.fetched_at)
        .where(MarketBestseller.source == PUBLISHNEWS_SOURCE)
        .order_by(MarketBestseller.fetched_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def get_period_label(db: Session) -> str | None:
    statement = (
        select(MarketBestseller.period_label)
        .where(MarketBestseller.source == PUBLISHNEWS_SOURCE)
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()
