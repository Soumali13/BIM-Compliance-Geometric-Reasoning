from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Authority = Literal[
    "NBC_2020",
    "QCC_B11_R2",
    "QUEBEC_2015_2022",
    "QUEBEC_2020_ABOVE",
    "MTL_11_018",
    "MTL_11_018_X",
]
PatchAction = Literal["add", "replace", "exception", "override"]

AUTHORITY_PRIORITY = {
    "NBC_2020": 1,
    "QCC_B11_R2": 2,
    "QUEBEC_2015_2022": 3,
    "QUEBEC_2020_ABOVE": 3,
    "MTL_11_018": 4,
    "MTL_11_018_X": 5,
}

AUTHORITY_JURISDICTION = {
    "NBC_2020": "Canada",
    "QCC_B11_R2": "Quebec",
    "QUEBEC_2015_2022": "Quebec",
    "QUEBEC_2020_ABOVE": "Quebec",
    "MTL_11_018": "Montreal",
    "MTL_11_018_X": "Montreal",
}

AUTHORITY_DEFAULT_PATCH_ACTION = {
    "NBC_2020": "add",
    "QCC_B11_R2": "replace",
    "QUEBEC_2015_2022": "replace",
    "QUEBEC_2020_ABOVE": "replace",
    "MTL_11_018": "override",
    "MTL_11_018_X": "override",
}


class SceneElement(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    label: str


class Scene(BaseModel):
    room_id: str
    room_type: str
    elements: list[SceneElement]


class GeometricFact(BaseModel):
    parameter: str
    value: float
    unit: str
    source_element: str
    source_measurement: str
    description: str


class ArticleChunk(BaseModel):
    article: str
    article_id: str | None = None
    title: str
    section: str
    section_title: str
    text: str
    source_pages: list[int] = Field(default_factory=list)
    source_pdf: str
    authority: Authority = "QCC_B11_R2"
    jurisdiction: str | None = None
    priority: int | None = None
    effective_date: str | None = None
    amends_article_id: str | None = None
    patch_action: PatchAction | None = None
    applies_if: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.article_id is None:
            self.article_id = self.article
        if self.priority is None:
            self.priority = AUTHORITY_PRIORITY[self.authority]
        if self.jurisdiction is None:
            self.jurisdiction = AUTHORITY_JURISDICTION[self.authority]
        if self.patch_action is None:
            self.patch_action = AUTHORITY_DEFAULT_PATCH_ACTION[self.authority]


class CodeConstraint(BaseModel):
    article: str
    title: str
    parameter: str
    operator: Literal[">=", "<=", ">", "<", "=="]
    value: float
    unit: str
    citation_text: str
    room_types: list[str] = Field(default_factory=list)
    authority: Authority = "QCC_B11_R2"
    jurisdiction: str | None = None
    priority: int | None = None
    effective_date: str | None = None
    amends_article: str | None = None
    patch_action: PatchAction | None = None
    applies_if: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.priority is None:
            self.priority = AUTHORITY_PRIORITY[self.authority]
        if self.jurisdiction is None:
            self.jurisdiction = AUTHORITY_JURISDICTION[self.authority]
        if self.patch_action is None:
            self.patch_action = AUTHORITY_DEFAULT_PATCH_ACTION[self.authority]


class RuleTraceEntry(BaseModel):
    article: str
    title: str
    authority: Authority
    jurisdiction: str
    priority: int
    effective_date: str | None = None
    patch_action: PatchAction
    operator: str
    value: float
    unit: str


class ResolvedConstraint(BaseModel):
    constraint: CodeConstraint
    override_trace: list[RuleTraceEntry] = Field(default_factory=list)
    overridden_articles: list[str] = Field(default_factory=list)


class ComplianceCheck(BaseModel):
    article: str
    title: str
    parameter: str
    source_element: str | None = None
    source_measurement: str | None = None
    fact_value: float | None = None
    fact_unit: str | None = None
    operator: str
    required_value: float
    required_unit: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    reason: str
    expected_element_types: list[str] = Field(default_factory=list)
    active_authority: Authority = "QCC_B11_R2"
    active_jurisdiction: str = "Quebec"
    override_trace: list[RuleTraceEntry] = Field(default_factory=list)


class ComplianceCitation(BaseModel):
    article: str
    title: str
    authority: Authority = "QCC_B11_R2"


class ComplianceFinding(BaseModel):
    citations: list[ComplianceCitation]
    parameter: str
    source_element: str | None = None
    source_measurement: str | None = None
    fact_value: float | None = None
    fact_unit: str | None = None
    operator: str
    required_value: float
    required_unit: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    reason: str
    expected_element_types: list[str] = Field(default_factory=list)
    active_authority: Authority = "QCC_B11_R2"
    active_jurisdiction: str = "Quebec"
    override_trace: list[RuleTraceEntry] = Field(default_factory=list)


class FindingExplanation(BaseModel):
    parameter: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    explanation: str


class LLMReasoning(BaseModel):
    generation_mode: Literal["deterministic", "llm", "deterministic_fallback"]
    summary: str
    precedence_explanation: str
    recommended_next_measurements: list[str] = Field(default_factory=list)
    finding_explanations: list[FindingExplanation] = Field(default_factory=list)
    prompt_context: dict[str, Any] = Field(default_factory=dict)


class AuditReport(BaseModel):
    scene_id: str
    room_type: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    passed: bool
    checks: list[ComplianceFinding]
    unmatched_facts: list[GeometricFact] = Field(default_factory=list)
    llm_reasoning: LLMReasoning | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
