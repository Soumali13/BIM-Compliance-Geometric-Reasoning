from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from geometric_reasoner.constraint_derivation import derive_constraints_for_article
from geometric_reasoner.shared_data_models import (
    AUTHORITY_PRIORITY,
    ArticleChunk,
    CodeConstraint,
    GeometricFact,
    ResolvedConstraint,
    RuleTraceEntry,
    Scene,
)
from geometric_reasoner.vector_retrieval import (
    article_chunk_key,
    build_article_vector_index,
    build_query_text,
    compatible_index_for_articles,
    load_article_vector_index,
    score_query_against_index,
)

AUTHORITY_NAME_MAP = {
    "nbc_2020": "NBC_2020",
    "qcc_b11_r2": "QCC_B11_R2",
    "quebec_b11_r2": "QCC_B11_R2",
    "quebec_2015-2022": "QUEBEC_2015_2022",
    "quebec_2015_2022": "QUEBEC_2015_2022",
    "quebec_2020_above": "QUEBEC_2020_ABOVE",
    "mtl_11_018": "MTL_11_018",
    "montreal_11_018": "MTL_11_018",
    "mtl_11_018_x": "MTL_11_018_X",
    "montreal_11_018_x": "MTL_11_018_X",
}

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VECTOR_INDEX = ROOT / "data" / "artifacts" / "vector_index" / "article_chunks_index.json"
DEFAULT_HYBRID_TOP_K = 12
VECTOR_WEIGHT = 0.7
OVERLAP_WEIGHT = 0.3


@dataclass(frozen=True)
class ScoredArticle:
    article: ArticleChunk
    overlap_score: float
    similarity_score: float
    final_score: float


def _normalize_authority_name(raw: str) -> str:
    return AUTHORITY_NAME_MAP.get(raw.lower(), raw)


def _article_precedence_key(article: ArticleChunk) -> tuple[int, str]:
    return (article.priority or AUTHORITY_PRIORITY[article.authority], article.article)


def _constraint_precedence_key(constraint: CodeConstraint) -> tuple[int, str, str]:
    return (constraint.priority or AUTHORITY_PRIORITY[constraint.authority], constraint.effective_date or "0000-00-00", constraint.article)


def _constraint_rank(constraint: CodeConstraint) -> tuple[int, str]:
    return (constraint.priority or AUTHORITY_PRIORITY[constraint.authority], constraint.effective_date or "0000-00-00")


def _resolved_constraint_slot(constraint: CodeConstraint) -> tuple[str, str, str]:
    return (constraint.parameter, constraint.operator, constraint.unit)


def _rule_trace(constraint: CodeConstraint) -> RuleTraceEntry:
    return RuleTraceEntry(
        article=constraint.article,
        title=constraint.title,
        authority=constraint.authority,
        jurisdiction=constraint.jurisdiction or "Canada",
        priority=constraint.priority or AUTHORITY_PRIORITY[constraint.authority],
        effective_date=constraint.effective_date,
        patch_action=constraint.patch_action or "add",
        operator=constraint.operator,
        value=constraint.value,
        unit=constraint.unit,
    )


def _load_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_rulebook(rulebook_path: str | Path) -> list[CodeConstraint]:
    payload = _load_json(rulebook_path)

    constraints: list[CodeConstraint] = []
    for article in payload["articles"]:
        article_authority = _normalize_authority_name(article.get("authority", "QCC_B11_R2"))
        for constraint in article["constraints"]:
            constraints.append(
                CodeConstraint(
                    article=article["article"],
                    title=article["title"],
                    parameter=constraint["parameter"],
                    operator=constraint["operator"],
                    value=float(constraint["value"]),
                    unit=constraint["unit"],
                    citation_text=article["text"],
                    room_types=article.get("room_types", []),
                    authority=article_authority,
                    jurisdiction=article.get("jurisdiction"),
                    priority=article.get("priority"),
                    effective_date=article.get("effective_date"),
                    amends_article=article.get("amends_article") or article.get("amends_article_id"),
                    patch_action=article.get("patch_action"),
                    applies_if=article.get("applies_if", {}),
                )
            )
    return constraints


def _load_article_chunk_file(chunks_path: str | Path, *, authority: str | None = None, jurisdiction: str | None = None) -> list[ArticleChunk]:
    payload = _load_json(chunks_path)
    if payload.get("target_language") not in {None, "en"}:
        return []
    normalized_authority = _normalize_authority_name(authority or payload.get("authority", "QCC_B11_R2"))
    default_jurisdiction = jurisdiction or payload.get("jurisdiction")

    articles: list[ArticleChunk] = []
    for article in payload["articles"]:
        merged = {
            "authority": normalized_authority,
            "jurisdiction": default_jurisdiction,
            **article,
        }
        if "authority" in article:
            merged["authority"] = _normalize_authority_name(article["authority"])
        articles.append(ArticleChunk.model_validate(merged))
    return articles


def load_article_chunks(chunks_path: str | Path) -> list[ArticleChunk]:
    path = Path(chunks_path)
    payload = _load_json(path)

    if "corpora" in payload:
        root = path.resolve().parents[2]
        chunks: list[ArticleChunk] = []
        for corpus in payload["corpora"]:
            authority = _normalize_authority_name(corpus["authority"])
            jurisdiction = corpus.get("jurisdiction")
            for file_path in corpus["files"]:
                if not file_path.endswith("_articles.json"):
                    continue
                chunks.extend(_load_article_chunk_file(root / file_path, authority=authority, jurisdiction=jurisdiction))
        return chunks

    return _load_article_chunk_file(path)


def _applicable_article_constraints(scene: Scene, article: ArticleChunk) -> list[CodeConstraint]:
    return [
        constraint
        for constraint in derive_constraints_for_article(article)
        if not constraint.room_types or scene.room_type in constraint.room_types
    ]


def _normalized_overlap_score(
    fact_parameters: set[str],
    article_constraints: list[CodeConstraint],
) -> float:
    total_query_parameters = max(1, len(fact_parameters))
    constraint_parameters = {constraint.parameter for constraint in article_constraints}
    matched_parameters = len(fact_parameters & constraint_parameters)
    return matched_parameters / total_query_parameters


_VECTOR_INDEX_CACHE: dict | None = None
_VECTOR_INDEX_CACHE_KEYS: set[str] | None = None


def _get_vector_index(articles: list[ArticleChunk]) -> dict:
    global _VECTOR_INDEX_CACHE, _VECTOR_INDEX_CACHE_KEYS

    article_keys = {article_chunk_key(article) for article in articles}
    if _VECTOR_INDEX_CACHE is not None and _VECTOR_INDEX_CACHE_KEYS == article_keys:
        return _VECTOR_INDEX_CACHE

    if DEFAULT_VECTOR_INDEX.exists():
        payload = load_article_vector_index(DEFAULT_VECTOR_INDEX)
        if compatible_index_for_articles(payload, articles):
            _VECTOR_INDEX_CACHE = payload
            _VECTOR_INDEX_CACHE_KEYS = article_keys
            return payload

    payload = build_article_vector_index(articles)
    _VECTOR_INDEX_CACHE = payload
    _VECTOR_INDEX_CACHE_KEYS = article_keys
    return payload


def matches_scope(
    scene: Scene,
    constraint: CodeConstraint,
    *,
    parameter: str | None = None,
    jurisdiction: str | None = None,
) -> bool:
    if parameter is not None and constraint.parameter != parameter:
        return False
    if constraint.room_types and scene.room_type not in constraint.room_types:
        return False
    if jurisdiction and constraint.jurisdiction not in {jurisdiction, "Canada"}:
        return False
    applies_room_type = constraint.applies_if.get("room_type")
    if applies_room_type and applies_room_type != scene.room_type:
        return False
    return True


def find_applicable_constraints(
    scene: Scene,
    parameter: str,
    rulebook: list[CodeConstraint],
) -> list[CodeConstraint]:
    return [
        constraint
        for constraint in rulebook
        if matches_scope(scene, constraint, parameter=parameter)
    ]


def resolve_applicable_constraints(
    scene: Scene,
    constraints: list[CodeConstraint],
    *,
    parameter: str | None = None,
    jurisdiction: str | None = None,
) -> list[ResolvedConstraint]:
    applicable = [
        constraint
        for constraint in constraints
        if matches_scope(scene, constraint, parameter=parameter, jurisdiction=jurisdiction)
    ]

    grouped: dict[tuple[str, str, str], list[CodeConstraint]] = {}
    for constraint in applicable:
        grouped.setdefault(_resolved_constraint_slot(constraint), []).append(constraint)

    resolved: list[ResolvedConstraint] = []
    for slot in sorted(grouped):
        group = sorted(grouped[slot], key=_constraint_precedence_key)
        winning_rank = _constraint_rank(group[-1])
        active_constraints = [constraint for constraint in group if _constraint_rank(constraint) == winning_rank]
        overridden = [constraint for constraint in group if _constraint_rank(constraint) != winning_rank]
        trace = [_rule_trace(constraint) for constraint in group]

        for active in active_constraints:
            resolved.append(
                ResolvedConstraint(
                    constraint=active,
                    override_trace=trace,
                    overridden_articles=[constraint.article for constraint in overridden],
                )
            )

    return resolved


def resolve_applicable_rule(
    scene: Scene,
    parameter: str,
    constraints: list[CodeConstraint],
    *,
    jurisdiction: str | None = None,
) -> ResolvedConstraint | None:
    resolved = resolve_applicable_constraints(scene, constraints, parameter=parameter, jurisdiction=jurisdiction)
    if not resolved:
        return None
    resolved.sort(key=lambda item: _constraint_precedence_key(item.constraint))
    return resolved[-1]


def retrieve_relevant_articles_overlap(
    scene: Scene,
    facts: list[GeometricFact],
    articles: list[ArticleChunk],
    *,
    top_k: int | None = None,
) -> list[ScoredArticle]:
    fact_parameters = {fact.parameter for fact in facts}
    ranked_articles: list[ScoredArticle] = []

    for article in articles:
        article_constraints = _applicable_article_constraints(scene, article)
        if not article_constraints:
            continue

        overlap_score = _normalized_overlap_score(fact_parameters, article_constraints)
        if overlap_score <= 0.0:
            continue

        ranked_articles.append(
            ScoredArticle(
                article=article,
                overlap_score=overlap_score,
                similarity_score=0.0,
                final_score=overlap_score,
            )
        )

    ranked_articles.sort(
        key=lambda item: (
            -item.overlap_score,
            -(item.article.priority or AUTHORITY_PRIORITY[item.article.authority]),
            item.article.article,
        )
    )
    return ranked_articles[:top_k] if top_k is not None else ranked_articles


def retrieve_relevant_articles_vector(
    scene: Scene,
    facts: list[GeometricFact],
    articles: list[ArticleChunk],
    *,
    top_k: int | None = DEFAULT_HYBRID_TOP_K,
) -> list[ScoredArticle]:
    fact_parameters = {fact.parameter for fact in facts}
    query_text = build_query_text(scene, facts)
    similarity_scores = score_query_against_index(query_text, _get_vector_index(articles))

    ranked_articles: list[ScoredArticle] = []
    for article in articles:
        article_constraints = _applicable_article_constraints(scene, article)
        if not article_constraints:
            continue

        similarity_score = similarity_scores.get(article_chunk_key(article), 0.0)
        if similarity_score <= 0.0:
            continue

        ranked_articles.append(
            ScoredArticle(
                article=article,
                overlap_score=_normalized_overlap_score(fact_parameters, article_constraints),
                similarity_score=similarity_score,
                final_score=similarity_score,
            )
        )

    ranked_articles.sort(
        key=lambda item: (
            -item.similarity_score,
            -(item.article.priority or AUTHORITY_PRIORITY[item.article.authority]),
            item.article.article,
        )
    )
    return ranked_articles[:top_k] if top_k is not None else ranked_articles


def retrieve_relevant_articles_hybrid(
    scene: Scene,
    facts: list[GeometricFact],
    articles: list[ArticleChunk],
    *,
    top_k: int | None = DEFAULT_HYBRID_TOP_K,
) -> list[ScoredArticle]:
    overlap_ranked = retrieve_relevant_articles_overlap(scene, facts, articles, top_k=None)
    vector_ranked = retrieve_relevant_articles_vector(scene, facts, articles, top_k=top_k)

    merged: dict[str, ScoredArticle] = {}
    for scored in overlap_ranked + vector_ranked:
        key = article_chunk_key(scored.article)
        existing = merged.get(key)
        if existing is None:
            merged[key] = scored
            continue
        merged[key] = ScoredArticle(
            article=scored.article,
            overlap_score=max(existing.overlap_score, scored.overlap_score),
            similarity_score=max(existing.similarity_score, scored.similarity_score),
            final_score=0.0,
        )

    hybrid_ranked: list[ScoredArticle] = []
    for scored in merged.values():
        final_score = VECTOR_WEIGHT * scored.similarity_score + OVERLAP_WEIGHT * scored.overlap_score
        hybrid_ranked.append(
            ScoredArticle(
                article=scored.article,
                overlap_score=scored.overlap_score,
                similarity_score=scored.similarity_score,
                final_score=final_score,
            )
        )

    hybrid_ranked.sort(
        key=lambda item: (
            -item.final_score,
            -(item.article.priority or AUTHORITY_PRIORITY[item.article.authority]),
            item.article.article,
        )
    )
    return hybrid_ranked[:top_k] if top_k is not None else hybrid_ranked


def retrieve_relevant_articles(
    scene: Scene,
    facts: list[GeometricFact],
    articles: list[ArticleChunk],
    *,
    retrieval_mode: str = "hybrid",
) -> list[ArticleChunk]:
    if retrieval_mode == "overlap":
        scored_articles = retrieve_relevant_articles_overlap(scene, facts, articles)
    elif retrieval_mode == "vector":
        scored_articles = retrieve_relevant_articles_vector(scene, facts, articles)
    else:
        scored_articles = retrieve_relevant_articles_hybrid(scene, facts, articles)
    return [scored.article for scored in scored_articles]
