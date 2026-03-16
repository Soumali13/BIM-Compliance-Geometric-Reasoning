from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

from geometric_reasoner.shared_data_models import (
    ArticleChunk,
    AuditReport,
    ComplianceFinding,
    FindingExplanation,
    GeometricFact,
    LLMReasoning,
)


DEFAULT_OPENAI_MODEL = "gpt-oss-1.0-mini"
DEFAULT_SNIPPET_LENGTH = 300
DEFAULT_OPENAI_TIMEOUT_SECONDS = 45.0
ROOT = Path(__file__).resolve().parents[2]
SECRETS_TOML = ROOT / "secrets.toml"


def _compact_excerpt(text: str, limit: int = DEFAULT_SNIPPET_LENGTH) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _active_rules(report: AuditReport) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for finding in report.checks:
        rules.append(
            {
                "parameter": finding.parameter,
                "article": ",".join(citation.article for citation in finding.citations),
                "authority": finding.active_authority,
                "jurisdiction": finding.active_jurisdiction,
                "operator": finding.operator,
                "value": finding.required_value,
                "unit": finding.required_unit,
            }
        )
    return rules


def _overridden_rules(report: AuditReport) -> list[dict[str, Any]]:
    overridden: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, float, str]] = set()
    for finding in report.checks:
        for trace in finding.override_trace[:-1]:
            key = (trace.authority, trace.article, trace.operator, trace.value, trace.unit)
            if key in seen:
                continue
            seen.add(key)
            overridden.append(
                {
                    "authority": trace.authority,
                    "article": trace.article,
                    "title": trace.title,
                    "patch_action": trace.patch_action,
                    "operator": trace.operator,
                    "value": trace.value,
                    "unit": trace.unit,
                }
            )
    return overridden


def build_reasoning_prompt_context(
    report: AuditReport,
    facts: list[GeometricFact],
    retrieved_articles: list[ArticleChunk],
) -> dict[str, Any]:
    missing_facts = [finding.parameter for finding in report.checks if finding.status == "UNKNOWN"]
    return {
        "scene_id": report.scene_id,
        "room_type": report.room_type,
        "status": report.status,
        "facts_used": [
            {
                "parameter": fact.parameter,
                "value": fact.value,
                "unit": fact.unit,
                "source_element": fact.source_element,
                "source_measurement": fact.source_measurement,
                "description": fact.description,
            }
            for fact in facts
        ],
        "active_resolved_rules": _active_rules(report),
        "overridden_rules": _overridden_rules(report),
        "findings": [
            {
                "parameter": finding.parameter,
                "status": finding.status,
                "reason": finding.reason,
                "operator": finding.operator,
                "required_value": finding.required_value,
                "required_unit": finding.required_unit,
                "fact_value": finding.fact_value,
                "fact_unit": finding.fact_unit,
            }
            for finding in report.checks
        ],
        "missing_facts": _dedupe_preserve_order(missing_facts),
        "retrieved_article_snippets": [
            {
                "authority": article.authority,
                "article": article.article,
                "title": article.title,
                "snippet": _compact_excerpt(article.text),
            }
            for article in retrieved_articles[:8]
        ],
    }


def _recommended_measurements(report: AuditReport) -> list[str]:
    recommended = [finding.parameter for finding in report.checks if finding.status == "UNKNOWN"]
    if not recommended and report.unmatched_facts:
        recommended.extend(fact.parameter for fact in report.unmatched_facts)
    return _dedupe_preserve_order(recommended)


def _deterministic_finding_explanations(report: AuditReport) -> list[FindingExplanation]:
    explanations: list[FindingExplanation] = []
    for finding in report.checks:
        if finding.status == "PASS":
            explanation = (
                f"{finding.parameter} passed because the measured value "
                f"{finding.fact_value:.1f} {finding.fact_unit} met the active "
                f"{finding.active_authority} requirement of {finding.operator} "
                f"{finding.required_value:.1f} {finding.required_unit}."
            )
        elif finding.status == "FAIL":
            explanation = (
                f"{finding.parameter} failed because the measured value "
                f"{finding.fact_value:.1f} {finding.fact_unit} did not satisfy the active "
                f"{finding.active_authority} requirement of {finding.operator} "
                f"{finding.required_value:.1f} {finding.required_unit}."
            )
        else:
            expected_from = ", ".join(finding.expected_element_types) or "the model"
            explanation = (
                f"{finding.parameter} is unknown because the required measurement was not found "
                f"from {expected_from}, so the active {finding.active_authority} rule could not be evaluated."
            )
        explanations.append(
            FindingExplanation(
                parameter=finding.parameter,
                status=finding.status,
                explanation=explanation,
            )
        )
    return explanations


def _deterministic_summary(report: AuditReport) -> str:
    if report.status == "PASS":
        return (
            f"The {report.room_type.lower()} passed because every evaluated measurement "
            "satisfied the active precedence-resolved rule set."
        )
    if report.status == "FAIL":
        failing = _dedupe_preserve_order([finding.parameter for finding in report.checks if finding.status == "FAIL"])
        return (
            f"The {report.room_type.lower()} failed because one or more active requirements were violated, "
            f"including {', '.join(failing[:3])}."
        )

    missing = _recommended_measurements(report)
    if missing:
        return (
            f"The {report.room_type.lower()} is unknown because required evidence is missing, "
            f"including {', '.join(missing[:3])}."
        )
    return f"The {report.room_type.lower()} is unknown because the available data was insufficient for a complete determination."


def _deterministic_precedence_explanation(report: AuditReport) -> str:
    authorities = _dedupe_preserve_order(
        [trace.authority for finding in report.checks for trace in finding.override_trace]
        + [finding.active_authority for finding in report.checks]
    )
    if not authorities:
        return "No precedence override trace was available for this audit."
    if len(authorities) == 1:
        return f"The active rules came from {authorities[0]} with no higher-priority override applied."
    return (
        f"The active rule set followed the precedence chain {' -> '.join(authorities)}, "
        f"ending with {authorities[-1]} as the controlling authority where applicable."
    )


def _deterministic_reasoning(
    report: AuditReport,
    facts: list[GeometricFact],
    retrieved_articles: list[ArticleChunk],
    *,
    generation_mode: str = "deterministic",
) -> LLMReasoning:
    return LLMReasoning(
        generation_mode=generation_mode,
        summary=_deterministic_summary(report),
        precedence_explanation=_deterministic_precedence_explanation(report),
        recommended_next_measurements=_recommended_measurements(report),
        finding_explanations=_deterministic_finding_explanations(report),
        prompt_context=build_reasoning_prompt_context(report, facts, retrieved_articles),
    )


def _load_secrets_toml() -> dict[str, Any]:
    if not SECRETS_TOML.exists():
        return {}
    try:
        with SECRETS_TOML.open("rb") as handle:
            payload = tomllib.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _configured_openai_api_key() -> str | None:
    secrets = _load_secrets_toml()
    openai_section = secrets.get("openai", {})
    if isinstance(openai_section, dict):
        api_key = openai_section.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    return None


def _configured_openai_model() -> str:
    secrets = _load_secrets_toml()
    openai_section = secrets.get("openai", {})
    if isinstance(openai_section, dict):
        model = openai_section.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
    env_model = os.environ.get("GEOMETRIC_REASONER_OPENAI_MODEL")
    if env_model and env_model.strip():
        return env_model.strip()
    return DEFAULT_OPENAI_MODEL


def _configured_openai_timeout_seconds() -> float:
    secrets = _load_secrets_toml()
    openai_section = secrets.get("openai", {})
    if isinstance(openai_section, dict):
        timeout_value = openai_section.get("timeout_seconds")
        if isinstance(timeout_value, (int, float)) and timeout_value > 0:
            return float(timeout_value)
        if isinstance(timeout_value, str):
            try:
                parsed = float(timeout_value)
            except ValueError:
                parsed = 0.0
            if parsed > 0:
                return parsed
    env_timeout = os.environ.get("GEOMETRIC_REASONER_OPENAI_TIMEOUT_SECONDS")
    if env_timeout:
        try:
            parsed = float(env_timeout)
        except ValueError:
            parsed = 0.0
        if parsed > 0:
            return parsed
    return DEFAULT_OPENAI_TIMEOUT_SECONDS


def _normalize_recommended_measurements(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            normalized.append(value.strip())
            continue
        if isinstance(value, dict):
            parameter = value.get("parameter")
            if isinstance(parameter, str) and parameter.strip():
                normalized.append(parameter.strip())
    return _dedupe_preserve_order(normalized)


def _openai_reasoning(
    report: AuditReport,
    facts: list[GeometricFact],
    retrieved_articles: list[ArticleChunk],
) -> LLMReasoning:
    api_key = _configured_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in secrets.toml or the environment.")

    from openai import OpenAI

    prompt_context = build_reasoning_prompt_context(report, facts, retrieved_articles)
    client = OpenAI(api_key=api_key, timeout=_configured_openai_timeout_seconds())
    response = client.responses.create(
        model=_configured_openai_model(),
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You explain deterministic BIM compliance audits. "
                            "Do not change the audit status. "
                            "Return strict JSON with keys: summary, precedence_explanation, "
                            "recommended_next_measurements, finding_explanations. "
                            "Each finding explanation must include parameter, status, explanation."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(prompt_context, indent=2),
                    }
                ],
            },
        ],
    )
    payload = json.loads(response.output_text)
    return LLMReasoning(
        generation_mode="llm",
        summary=payload["summary"],
        precedence_explanation=payload["precedence_explanation"],
        recommended_next_measurements=_normalize_recommended_measurements(
            payload.get("recommended_next_measurements", [])
        ),
        finding_explanations=[FindingExplanation.model_validate(item) for item in payload.get("finding_explanations", [])],
        prompt_context=prompt_context,
    )


def generate_audit_reasoning(
    report: AuditReport,
    facts: list[GeometricFact],
    retrieved_articles: list[ArticleChunk],
    *,
    reasoning_mode: str = "deterministic",
) -> LLMReasoning:
    if report.status == "PASS":
        return _deterministic_reasoning(report, facts, retrieved_articles)

    if reasoning_mode == "llm":
        try:
            return _openai_reasoning(report, facts, retrieved_articles)
        except Exception:
            return _deterministic_reasoning(
                report,
                facts,
                retrieved_articles,
                generation_mode="deterministic_fallback",
            )

    return _deterministic_reasoning(report, facts, retrieved_articles)
