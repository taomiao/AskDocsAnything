from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from askdocsanything.codex import CodexClient
from askdocsanything.documents import discover_documents, image_paths
from askdocsanything.models import AskDocsResponse, QueryResult


class AskDocsAgent:
    def __init__(
        self,
        *,
        codex_bin: str = "codex",
        model: str | None = None,
        timeout_seconds: int = 900,
        max_attached_images: int = 8,
    ) -> None:
        self.codex = CodexClient(
            codex_bin=codex_bin,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        self.max_attached_images = max_attached_images

    def ask(self, *, workdir: str | Path, queries: str | Sequence[str]) -> AskDocsResponse:
        root = Path(workdir).expanduser().resolve()
        normalized_queries = [queries] if isinstance(queries, str) else list(queries)
        if not normalized_queries:
            raise ValueError("At least one query is required.")

        documents = discover_documents(root)
        if not documents:
            raise ValueError(f"No supported documents found in {root}.")

        prompt = self._build_prompt(root, normalized_queries, documents)
        attached_images = image_paths(root, documents, self.max_attached_images)
        raw_response = self.codex.run(
            prompt=prompt,
            workdir=root,
            image_paths=attached_images,
        )
        payload = self._parse_json(raw_response)
        results = [QueryResult.from_dict(item) for item in payload.get("results", [])]
        self._validate_results(results, documents)
        return AskDocsResponse(
            workdir=str(root),
            results=results,
            documents=documents,
            raw_response=raw_response,
        )

    def _build_prompt(self, root: Path, queries: list[str], documents: object) -> str:
        manifest = "\n".join(
            f"- {document.path} | type={document.kind} | bytes={document.size_bytes}"
            for document in documents
        )
        query_block = "\n".join(f"{index + 1}. {query}" for index, query in enumerate(queries))
        return f"""You are a document-grounded data QA agent.

Work only inside this directory:
{root}

Supported document manifest:
{manifest}

Queries:
{query_block}

Instructions:
- Answer every query using only evidence found in the listed local documents.
- Inspect the original files, not just the manifest.
- For PDF, Word, PowerPoint, Excel, HTML, Markdown, text, and image files, use whatever local tools are available in the Codex environment to extract exact values.
- If a file is binary, write small read-only Python snippets when useful to extract text, tables, slides, sheets, image metadata, or OCR-friendly context.
- Never guess. If the evidence is missing or ambiguous, set status to "not_found" or "partial" and explain what is missing.
- Populate the structured "value" object for database storage:
  - For exact dates, set value_type="date" and date_value to ISO YYYY-MM-DD.
  - For month-only or year-only dates, set value_type="date_range" with start_date and end_date covering the known interval. Example: "2026 年 6 月" -> start_date="2026-06-01", end_date="2026-06-30".
  - For numeric measurements or counts, set value_type="number" or "integer" and put the value in number_value or integer_value. Keep units in unit.
  - For booleans, set boolean_value. For lists or records, set json_value to a JSON-encoded string. For missing evidence, set value_type="null".
  - All non-applicable typed fields must be null, and display_value should contain the concise normalized value shown to users.
- Every factual answer must include citations. Cite file paths relative to the workdir.
- Use precise locations when possible: page, slide, sheet/cell range, heading, row, paragraph, image region, or line number.
- Include short evidence quotes or table snippets. Keep quotes brief.
- Populate "evidence_chain" with auditable steps:
  - Use operation="locate" for selecting the relevant file/section/table/image.
  - Use operation="extract" for the raw source value.
  - Use operation="normalize" when converting raw text into typed database fields, such as "2026 年 6 月" to start_date/end_date or "65" to integer_value=65.
  - Use operation="derive" for calculations or combining multiple sources.
  - Use operation="validate" for cross-checks or explaining why precision is partial.
  - Each step should include file, location, quote, extracted_value, normalized_value, transformation, and confidence when applicable. Use null for fields that do not apply.
- Return only JSON matching the provided schema. Do not wrap it in Markdown.
"""

    def _parse_json(self, raw_response: str) -> dict:
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Codex returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Codex response must be a JSON object.")
        return payload

    def _validate_results(self, results: list[QueryResult], documents: object) -> None:
        known_files = {document.path for document in documents}
        for result in results:
            for citation in result.citations:
                if citation.file not in known_files:
                    raise ValueError(
                        f"Codex cited a file outside the supported manifest: {citation.file}"
                    )
            for step in result.evidence_chain:
                if step.file is not None and step.file not in known_files:
                    raise ValueError(
                        f"Codex evidence chain referenced a file outside the supported manifest: {step.file}"
                    )
