from __future__ import annotations

import json
from pathlib import Path

from geometric_reasoner.shared_data_models import ArticleChunk, GeometricFact, Scene

INDEX_VERSION = 2
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_MODEL_CACHE: dict[str, object] = {}


def article_lookup_key(authority: str, article: str) -> str:
    return f"{authority}:{article}"


def article_chunk_key(article: ArticleChunk) -> str:
    return article_lookup_key(article.authority, article.article)


def build_article_index_text(article: ArticleChunk) -> str:
    return " ".join(
        part
        for part in [
            article.authority,
            article.article_id or article.article,
            article.title,
            article.text,
        ]
        if part
    )


def build_query_text(
    scene: Scene,
    facts: list[GeometricFact],
    *,
    jurisdiction_hint: str | None = None,
) -> str:
    query_parts = [scene.room_type]
    if jurisdiction_hint:
        query_parts.append(jurisdiction_hint)
    query_parts.extend(sorted({fact.parameter for fact in facts}))
    query_parts.extend(sorted({fact.description for fact in facts}))
    return " ".join(query_parts)


def _model_cache_key(model_name: str, *, local_files_only: bool) -> str:
    return f"{model_name}|local_only={int(local_files_only)}"


def _get_sentence_transformer(
    model_name: str = DEFAULT_MODEL_NAME,
    *,
    local_files_only: bool = True,
):
    cache_key = _model_cache_key(model_name, local_files_only=local_files_only)
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required for vector retrieval. "
            "Install it and rebuild the article embedding index."
        ) from exc

    try:
        model = SentenceTransformer(model_name, local_files_only=local_files_only)
    except OSError as exc:
        mode = "local cache only" if local_files_only else "remote download enabled"
        raise RuntimeError(
            f"Unable to load sentence-transformer model {model_name!r} in {mode} mode."
        ) from exc
    _MODEL_CACHE[cache_key] = model
    return model


def _encode_texts(
    texts: list[str],
    *,
    model_name: str,
    local_files_only: bool = True,
) -> list[list[float]]:
    if not texts:
        return []

    model = _get_sentence_transformer(model_name, local_files_only=local_files_only)
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def _dot_product(left: list[float], right: list[float]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))


def build_article_vector_index(
    articles: list[ArticleChunk],
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    allow_download: bool = False,
) -> dict:
    article_texts = [build_article_index_text(article) for article in articles]
    article_embeddings = _encode_texts(
        article_texts,
        model_name=model_name,
        local_files_only=not allow_download,
    )

    indexed_articles: list[dict] = []
    for article, embedding in zip(articles, article_embeddings, strict=True):
        indexed_articles.append(
            {
                "key": article_chunk_key(article),
                "authority": article.authority,
                "article": article.article,
                "article_id": article.article_id or article.article,
                "title": article.title,
                "priority": article.priority,
                "embedding": embedding,
            }
        )

    embedding_dimension = len(article_embeddings[0]) if article_embeddings else 0
    return {
        "version": INDEX_VERSION,
        "index_type": "sentence_transformer",
        "model_name": model_name,
        "article_count": len(articles),
        "embedding_dimension": embedding_dimension,
        "articles": indexed_articles,
    }


def load_article_vector_index(index_path: str | Path) -> dict:
    return json.loads(Path(index_path).read_text(encoding="utf-8"))


def write_article_vector_index(index_path: str | Path, payload: dict) -> None:
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    Path(index_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def compatible_index_for_articles(index_payload: dict, articles: list[ArticleChunk]) -> bool:
    indexed_keys = {entry["key"] for entry in index_payload.get("articles", [])}
    article_keys = {article_chunk_key(article) for article in articles}
    return indexed_keys == article_keys


def score_query_against_index(query_text: str, index_payload: dict) -> dict[str, float]:
    model_name = index_payload.get("model_name", DEFAULT_MODEL_NAME)
    query_embeddings = _encode_texts([query_text], model_name=model_name, local_files_only=True)
    if not query_embeddings:
        return {}
    query_embedding = query_embeddings[0]

    scores: dict[str, float] = {}
    for article in index_payload.get("articles", []):
        embedding = article.get("embedding", [])
        if not embedding:
            continue
        similarity = _dot_product(query_embedding, embedding)
        if similarity > 0.0:
            scores[article["key"]] = similarity
    return scores
