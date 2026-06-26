from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

QueryStatus = Literal["answered", "partial", "not_found", "error"]
ValueType = Literal[
    "string",
    "number",
    "integer",
    "boolean",
    "date",
    "datetime",
    "date_range",
    "json",
    "null",
]
EvidenceOperation = Literal["locate", "extract", "normalize", "derive", "validate"]


@dataclass(frozen=True)
class DocumentInfo:
    path: str
    kind: str
    size_bytes: int

    @classmethod
    def from_path(cls, root: Path, path: Path, kind: str) -> "DocumentInfo":
        stat = path.stat()
        return cls(
            path=path.relative_to(root).as_posix(),
            kind=kind,
            size_bytes=stat.st_size,
        )


@dataclass(frozen=True)
class Citation:
    file: str
    location: str
    quote: str = ""
    confidence: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        confidence = data.get("confidence")
        return cls(
            file=str(data.get("file", "")),
            location=str(data.get("location", "")),
            quote=str(data.get("quote", "")),
            confidence=float(confidence) if isinstance(confidence, int | float) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "file": self.file,
            "location": self.location,
            "quote": self.quote,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(frozen=True)
class StructuredValue:
    value_type: ValueType
    text_value: str | None = None
    number_value: float | None = None
    integer_value: int | None = None
    boolean_value: bool | None = None
    date_value: str | None = None
    datetime_value: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    json_value: str | None = None
    unit: str | None = None
    display_value: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StructuredValue":
        if not isinstance(data, dict):
            return cls(value_type="null", display_value="")
        value_type = data.get("value_type", "null")
        if value_type not in {
            "string",
            "number",
            "integer",
            "boolean",
            "date",
            "datetime",
            "date_range",
            "json",
            "null",
        }:
            value_type = "null"
        return cls(
            value_type=value_type,
            text_value=_optional_str(data.get("text_value")),
            number_value=_optional_float(data.get("number_value")),
            integer_value=_optional_int(data.get("integer_value")),
            boolean_value=data.get("boolean_value") if isinstance(data.get("boolean_value"), bool) else None,
            date_value=_optional_str(data.get("date_value")),
            datetime_value=_optional_str(data.get("datetime_value")),
            start_date=_optional_str(data.get("start_date")),
            end_date=_optional_str(data.get("end_date")),
            json_value=_optional_str(data.get("json_value")),
            unit=_optional_str(data.get("unit")),
            display_value=str(data.get("display_value", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_type": self.value_type,
            "text_value": self.text_value,
            "number_value": self.number_value,
            "integer_value": self.integer_value,
            "boolean_value": self.boolean_value,
            "date_value": self.date_value,
            "datetime_value": self.datetime_value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "json_value": self.json_value,
            "unit": self.unit,
            "display_value": self.display_value,
        }


@dataclass(frozen=True)
class EvidenceStep:
    step_index: int
    operation: EvidenceOperation
    description: str
    file: str | None = None
    location: str | None = None
    quote: str | None = None
    extracted_value: str | None = None
    normalized_value: str | None = None
    transformation: str | None = None
    confidence: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceStep":
        operation = data.get("operation", "extract")
        if operation not in {"locate", "extract", "normalize", "derive", "validate"}:
            operation = "extract"
        confidence = data.get("confidence")
        return cls(
            step_index=_optional_int(data.get("step_index")) or 0,
            operation=operation,
            description=str(data.get("description", "")),
            file=_optional_str(data.get("file")),
            location=_optional_str(data.get("location")),
            quote=_optional_str(data.get("quote")),
            extracted_value=_optional_str(data.get("extracted_value")),
            normalized_value=_optional_str(data.get("normalized_value")),
            transformation=_optional_str(data.get("transformation")),
            confidence=float(confidence) if isinstance(confidence, int | float) else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "operation": self.operation,
            "description": self.description,
            "file": self.file,
            "location": self.location,
            "quote": self.quote,
            "extracted_value": self.extracted_value,
            "normalized_value": self.normalized_value,
            "transformation": self.transformation,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class QueryResult:
    query: str
    answer: str
    status: QueryStatus
    value: StructuredValue = field(default_factory=lambda: StructuredValue(value_type="null"))
    citations: list[Citation] = field(default_factory=list)
    evidence_chain: list[EvidenceStep] = field(default_factory=list)
    reasoning_summary: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryResult":
        raw_citations = data.get("citations", [])
        citations = [
            Citation.from_dict(item)
            for item in raw_citations
            if isinstance(item, dict)
        ]
        raw_evidence_chain = data.get("evidence_chain", [])
        evidence_chain = [
            EvidenceStep.from_dict(item)
            for item in raw_evidence_chain
            if isinstance(item, dict)
        ]
        status = data.get("status", "error")
        if status not in {"answered", "partial", "not_found", "error"}:
            status = "error"
        return cls(
            query=str(data.get("query", "")),
            answer=str(data.get("answer", "")),
            status=status,
            value=StructuredValue.from_dict(data.get("value")),
            citations=citations,
            evidence_chain=evidence_chain,
            reasoning_summary=str(data.get("reasoning_summary", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "status": self.status,
            "value": self.value.to_dict(),
            "citations": [citation.to_dict() for citation in self.citations],
            "evidence_chain": [step.to_dict() for step in self.evidence_chain],
            "reasoning_summary": self.reasoning_summary,
        }


@dataclass(frozen=True)
class AskDocsResponse:
    workdir: str
    results: list[QueryResult]
    documents: list[DocumentInfo]
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workdir": self.workdir,
            "results": [result.to_dict() for result in self.results],
            "documents": [
                {
                    "path": document.path,
                    "kind": document.kind,
                    "size_bytes": document.size_bytes,
                }
                for document in self.documents
            ],
            "raw_response": self.raw_response,
        }


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None
