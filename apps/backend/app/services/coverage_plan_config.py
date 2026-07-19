"""Configuracao central da fase 19.4 (plano de cobertura): limites de duracao e
pesos de estimativa de palavras. Nenhum valor deste modulo deve ser duplicado em
outro arquivo -- coverage_plan_service.py, coverage_plan_validator.py e o prompt
devem importar daqui."""

from decimal import ROUND_HALF_UP, Decimal

WORDS_PER_MINUTE = 130
MAX_LESSON_MINUTES = 10
MAX_LESSON_WORDS = WORDS_PER_MINUTE * MAX_LESSON_MINUTES
TARGET_MIN_LESSON_MINUTES = 5
TARGET_MAX_LESSON_MINUTES = 9

LESSON_INTRO_WORDS = 60
LESSON_CLOSING_WORDS = 50
TRANSITION_WORDS_PER_ITEM = 25

# Peso aplicado sobre a contagem de palavras do source_content_item (normalized_content)
# para estimar quantas palavras de explicacao a narracao da aula vai precisar. Pesos
# maiores = tipos que tipicamente exigem mais desenvolvimento oral por palavra de
# conteudo fonte (ex: procedimentos, tabelas). Nunca usado para cortar conteudo --
# apenas para prever duracao e decidir onde dividir aulas.
CONTENT_TYPE_EXPLANATION_MULTIPLIER: dict[str, float] = {
    "definition": 1.3,
    "concept": 1.6,
    "explanation": 1.5,
    "fact": 1.1,
    "procedure": 2.0,
    "step": 1.8,
    "rule": 1.4,
    "exception": 1.6,
    "example": 1.5,
    "case": 1.6,
    "list": 1.3,
    "classification": 1.5,
    "comparison": 1.7,
    "distinction": 1.5,
    "cause": 1.4,
    "consequence": 1.4,
    "argument": 1.5,
    "conclusion": 1.3,
    "observation": 1.2,
    "warning": 1.2,
    "recommendation": 1.3,
    "exercise": 1.4,
    "question": 1.2,
    "table": 2.0,
    "image_caption": 1.2,
    "quotation": 1.1,
    "reference": 1.0,
    "other": 1.4,
}
DEFAULT_EXPLANATION_MULTIPLIER = 1.4


def content_type_multiplier(content_type: str) -> float:
    return CONTENT_TYPE_EXPLANATION_MULTIPLIER.get(content_type, DEFAULT_EXPLANATION_MULTIPLIER)


def count_words(text: str | None) -> int:
    if not text:
        return 0
    return len(text.split())


def words_to_minutes(words: int) -> Decimal:
    if words <= 0:
        return Decimal("0")
    minutes = Decimal(words) / Decimal(WORDS_PER_MINUTE)
    return minutes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
