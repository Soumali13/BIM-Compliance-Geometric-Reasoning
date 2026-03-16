from __future__ import annotations

from operator import eq, ge, gt, le, lt

from geometric_reasoner.bim_normalized_models import NormalizedProject, NormalizedSpace
from geometric_reasoner.constraint_derivation import derive_constraints_from_articles
from geometric_reasoner.extraction import (
    compliance_room_type_for_normalized_space,
    element_types_for_parameter,
    expected_element_types_for_room,
    extract_geometric_facts,
    extract_geometric_facts_from_normalized_space,
    normalized_space_to_scene,
)
from geometric_reasoner.research import find_applicable_constraints, resolve_applicable_constraints, retrieve_relevant_articles
from geometric_reasoner.research import (
    retrieve_relevant_articles_hybrid,
    retrieve_relevant_articles_overlap,
    retrieve_relevant_articles_vector,
)
from geometric_reasoner.shared_data_models import (
    ArticleChunk,
    AuditReport,
    CodeConstraint,
    ComplianceCheck,
    ComplianceCitation,
    ComplianceFinding,
    GeometricFact,
    ResolvedConstraint,
    Scene,
)
from geometric_reasoner.llm_reasoner import generate_audit_reasoning


OPERATORS = {
    ">=": ge,
    "<=": le,
    ">": gt,
    "<": lt,
    "==": eq,
}


def _evaluate_fact(fact: GeometricFact, resolved_constraint: ResolvedConstraint) -> ComplianceCheck:
    constraint = resolved_constraint.constraint
    comparator = OPERATORS[constraint.operator]
    passed = comparator(fact.value, constraint.value)

    if passed:
        reason = f"{fact.description} satisfies the requirement."
        status = "PASS"
    else:
        relation = {
            ">=": "below minimum",
            ">": "not above minimum threshold",
            "<=": "above maximum",
            "<": "not below maximum threshold",
            "==": "does not match required value",
        }[constraint.operator]
        reason = f"{fact.description} is {relation}."
        status = "FAIL"

    return ComplianceCheck(
        article=constraint.article,
        title=constraint.title,
        parameter=fact.parameter,
        source_element=fact.source_element,
        source_measurement=fact.source_measurement,
        fact_value=fact.value,
        fact_unit=fact.unit,
        operator=constraint.operator,
        required_value=constraint.value,
        required_unit=constraint.unit,
        status=status,
        reason=reason,
        active_authority=constraint.authority,
        active_jurisdiction=constraint.jurisdiction or "Canada",
        override_trace=resolved_constraint.override_trace,
    )


def _build_missing_fact_checks(
    scene: Scene,
    constraints: list[ResolvedConstraint],
    facts: list[GeometricFact],
) -> list[ComplianceCheck]:
    known_parameters = {fact.parameter for fact in facts}
    present_element_types = {element.type for element in scene.elements}
    expected_element_types = expected_element_types_for_room(scene.room_type)
    missing_checks: list[ComplianceCheck] = []

    for resolved_constraint in constraints:
        constraint = resolved_constraint.constraint
        if constraint.parameter in known_parameters:
            continue

        candidate_element_types = element_types_for_parameter(constraint.parameter)
        if not candidate_element_types:
            continue

        relevant_element_types = sorted(candidate_element_types & (present_element_types | expected_element_types))
        if not relevant_element_types:
            continue

        missing_checks.append(
            ComplianceCheck(
                article=constraint.article,
                title=constraint.title,
                parameter=constraint.parameter,
                operator=constraint.operator,
                required_value=constraint.value,
                required_unit=constraint.unit,
                status="UNKNOWN",
                reason=f"Required fact for {constraint.parameter} was not found in the scene.",
                expected_element_types=relevant_element_types,
                active_authority=constraint.authority,
                active_jurisdiction=constraint.jurisdiction or "Canada",
                override_trace=resolved_constraint.override_trace,
            )
        )

    return missing_checks


def _group_checks(checks: list[ComplianceCheck]) -> list[ComplianceFinding]:
    grouped: dict[tuple, ComplianceFinding] = {}

    for check in checks:
        key = (
            check.parameter,
            check.source_element,
            check.source_measurement,
            check.fact_value,
            check.fact_unit,
            check.operator,
            check.required_value,
            check.required_unit,
            check.status,
            check.reason,
            tuple(check.expected_element_types),
            check.active_authority,
            check.active_jurisdiction,
            tuple(
                (
                    trace.authority,
                    trace.article,
                    trace.operator,
                    trace.value,
                    trace.unit,
                    trace.patch_action,
                )
                for trace in check.override_trace
            ),
        )

        if key not in grouped:
            grouped[key] = ComplianceFinding(
                citations=[ComplianceCitation(article=check.article, title=check.title, authority=check.active_authority)],
                parameter=check.parameter,
                source_element=check.source_element,
                source_measurement=check.source_measurement,
                fact_value=check.fact_value,
                fact_unit=check.fact_unit,
                operator=check.operator,
                required_value=check.required_value,
                required_unit=check.required_unit,
                status=check.status,
                reason=check.reason,
                expected_element_types=check.expected_element_types,
                active_authority=check.active_authority,
                active_jurisdiction=check.active_jurisdiction,
                override_trace=check.override_trace,
            )
            continue

        citations = grouped[key].citations
        if all(existing.article != check.article for existing in citations):
            citations.append(ComplianceCitation(article=check.article, title=check.title, authority=check.active_authority))

    for finding in grouped.values():
        finding.citations.sort(key=lambda citation: citation.article)

    return list(grouped.values())


def _final_status(checks: list[ComplianceFinding]) -> str:
    statuses = {check.status for check in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "PASS"


def _article_reference(article: ArticleChunk) -> str:
    return f"{article.authority}:{article.article}"


def audit_scene(
    scene: Scene,
    rulebook: list[CodeConstraint] | None = None,
    articles: list[ArticleChunk] | None = None,
    retrieval_mode: str = "hybrid",
    reasoning_mode: str = "deterministic",
) -> AuditReport:
    if rulebook is None and articles is None:
        raise ValueError("Either rulebook or articles must be provided.")

    facts = extract_geometric_facts(scene)
    retrieved_articles: list[ArticleChunk] = []
    retrieved_article_scores: list[dict] = []
    if articles is not None:
        if retrieval_mode == "overlap":
            scored_articles = retrieve_relevant_articles_overlap(scene, facts, articles, top_k=None)
        elif retrieval_mode == "vector":
            scored_articles = retrieve_relevant_articles_vector(scene, facts, articles)
        else:
            retrieval_mode = "hybrid"
            scored_articles = retrieve_relevant_articles_hybrid(scene, facts, articles)
        retrieved_articles = [scored.article for scored in scored_articles]
        retrieved_article_scores = [
            {
                "authority": scored.article.authority,
                "article": scored.article.article,
                "title": scored.article.title,
                "priority": scored.article.priority or 0,
                "overlap_score": round(scored.overlap_score, 6),
                "similarity_score": round(scored.similarity_score, 6),
                "final_score": round(scored.final_score, 6),
            }
            for scored in scored_articles
        ]
        rulebook = derive_constraints_from_articles(retrieved_articles)

    assert rulebook is not None
    constraint_source = "runtime_derived" if articles is not None else "prederived_rulebook"
    raw_checks: list[ComplianceCheck] = []
    unmatched_facts: list[GeometricFact] = []
    candidate_constraint_count = 0

    for fact in facts:
        candidate_constraint_count += len(find_applicable_constraints(scene, fact.parameter, rulebook))
        resolved_constraints = resolve_applicable_constraints(scene, rulebook, parameter=fact.parameter)
        if not resolved_constraints:
            unmatched_facts.append(fact)
            continue

        for resolved_constraint in resolved_constraints:
            raw_checks.append(_evaluate_fact(fact, resolved_constraint))

    all_resolved_constraints = resolve_applicable_constraints(scene, rulebook)
    raw_checks.extend(_build_missing_fact_checks(scene, all_resolved_constraints, facts))
    checks = _group_checks(raw_checks)
    status = _final_status(checks)
    report = AuditReport(
        scene_id=scene.room_id,
        room_type=scene.room_type,
        status=status,
        passed=status == "PASS",
        checks=checks,
        unmatched_facts=unmatched_facts,
        metadata={
            "constraint_source": constraint_source,
            "retrieval_mode": retrieval_mode if articles is not None else "none",
            "reasoning_mode": reasoning_mode,
            "fact_count": len(facts),
            "matched_constraint_count": candidate_constraint_count,
            "evaluated_rule_count": len(raw_checks),
            "finding_count": len(checks),
            "retrieved_article_count": len(retrieved_articles),
            "retrieved_articles": [_article_reference(article) for article in retrieved_articles],
            "retrieved_article_scores": retrieved_article_scores,
            "retrieved_authorities": sorted({article.authority for article in retrieved_articles}),
            "resolved_rule_count": len(all_resolved_constraints),
            "override_count": sum(1 for resolved in all_resolved_constraints if resolved.overridden_articles),
        },
    )
    report.llm_reasoning = generate_audit_reasoning(
        report,
        facts,
        retrieved_articles,
        reasoning_mode=reasoning_mode,
    )
    report.metadata["reasoning_generation_mode"] = report.llm_reasoning.generation_mode
    return report


def audit_normalized_space(
    space: NormalizedSpace,
    rulebook: list[CodeConstraint] | None = None,
    articles: list[ArticleChunk] | None = None,
    retrieval_mode: str = "hybrid",
    reasoning_mode: str = "deterministic",
) -> AuditReport:
    if rulebook is None and articles is None:
        raise ValueError("Either rulebook or articles must be provided.")

    compliance_room_type = compliance_room_type_for_normalized_space(space)
    if not compliance_room_type:
        raise ValueError(f"Normalized space {space.space_id} does not have a supported compliance room type.")

    scene_stub = normalized_space_to_scene(space)
    scene_stub.room_type = compliance_room_type
    facts = extract_geometric_facts_from_normalized_space(space)

    retrieved_articles: list[ArticleChunk] = []
    retrieved_article_scores: list[dict] = []
    if articles is not None:
        if retrieval_mode == "overlap":
            scored_articles = retrieve_relevant_articles_overlap(scene_stub, facts, articles, top_k=None)
        elif retrieval_mode == "vector":
            scored_articles = retrieve_relevant_articles_vector(scene_stub, facts, articles)
        else:
            retrieval_mode = "hybrid"
            scored_articles = retrieve_relevant_articles_hybrid(scene_stub, facts, articles)
        retrieved_articles = [scored.article for scored in scored_articles]
        retrieved_article_scores = [
            {
                "authority": scored.article.authority,
                "article": scored.article.article,
                "title": scored.article.title,
                "priority": scored.article.priority or 0,
                "overlap_score": round(scored.overlap_score, 6),
                "similarity_score": round(scored.similarity_score, 6),
                "final_score": round(scored.final_score, 6),
            }
            for scored in scored_articles
        ]
        rulebook = derive_constraints_from_articles(retrieved_articles)

    assert rulebook is not None
    constraint_source = "runtime_derived" if articles is not None else "prederived_rulebook"
    raw_checks: list[ComplianceCheck] = []
    unmatched_facts: list[GeometricFact] = []
    candidate_constraint_count = 0

    for fact in facts:
        candidate_constraint_count += len(find_applicable_constraints(scene_stub, fact.parameter, rulebook))
        resolved_constraints = resolve_applicable_constraints(scene_stub, rulebook, parameter=fact.parameter)
        if not resolved_constraints:
            unmatched_facts.append(fact)
            continue

        for resolved_constraint in resolved_constraints:
            raw_checks.append(_evaluate_fact(fact, resolved_constraint))

    all_resolved_constraints = resolve_applicable_constraints(scene_stub, rulebook)
    raw_checks.extend(_build_missing_fact_checks(scene_stub, all_resolved_constraints, facts))
    checks = _group_checks(raw_checks)
    status = _final_status(checks)
    report = AuditReport(
        scene_id=space.space_id,
        room_type=compliance_room_type,
        status=status,
        passed=status == "PASS",
        checks=checks,
        unmatched_facts=unmatched_facts,
        metadata={
            "constraint_source": constraint_source,
            "retrieval_mode": retrieval_mode if articles is not None else "none",
            "reasoning_mode": reasoning_mode,
            "fact_count": len(facts),
            "matched_constraint_count": candidate_constraint_count,
            "evaluated_rule_count": len(raw_checks),
            "finding_count": len(checks),
            "retrieved_article_count": len(retrieved_articles),
            "retrieved_articles": [_article_reference(article) for article in retrieved_articles],
            "retrieved_article_scores": retrieved_article_scores,
            "retrieved_authorities": sorted({article.authority for article in retrieved_articles}),
            "resolved_rule_count": len(all_resolved_constraints),
            "override_count": sum(1 for resolved in all_resolved_constraints if resolved.overridden_articles),
            "normalized_space_name": space.name,
            "source_room_type": space.room_type,
        },
    )
    report.llm_reasoning = generate_audit_reasoning(
        report,
        facts,
        retrieved_articles,
        reasoning_mode=reasoning_mode,
    )
    report.metadata["reasoning_generation_mode"] = report.llm_reasoning.generation_mode
    return report


def audit_normalized_project(
    project: NormalizedProject,
    rulebook: list[CodeConstraint] | None = None,
    articles: list[ArticleChunk] | None = None,
    retrieval_mode: str = "hybrid",
    reasoning_mode: str = "deterministic",
) -> list[AuditReport]:
    reports: list[AuditReport] = []
    for unit in project.units:
        for space in unit.spaces:
            if not compliance_room_type_for_normalized_space(space):
                continue
            reports.append(
                audit_normalized_space(
                    space,
                    rulebook=rulebook,
                    articles=articles,
                    retrieval_mode=retrieval_mode,
                    reasoning_mode=reasoning_mode,
                )
            )
    return reports
