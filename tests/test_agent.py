from __future__ import annotations

import json
from pathlib import Path

import pytest

from askdocsanything.agent import AskDocsAgent
from askdocsanything.codex import CodexClient
from askdocsanything import codex as codex_module
from askdocsanything.documents import discover_documents


class FakeCodex(CodexClient):
    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompt = ""

    def run(self, *, prompt: str, workdir: str | Path, image_paths: list[Path] | None = None) -> str:
        self.prompt = prompt
        return json.dumps(self.response)


def test_discover_documents_filters_supported_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "deck.pptx").write_bytes(b"fake")
    (tmp_path / "ignore.bin").write_bytes(b"fake")

    documents = discover_documents(tmp_path)

    assert [document.path for document in documents] == ["deck.pptx", "notes.txt"]
    assert {document.kind for document in documents} == {"powerpoint", "text"}


def test_agent_returns_structured_response(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("Revenue was 42.", encoding="utf-8")
    fake = FakeCodex(
        {
            "results": [
                {
                    "query": "revenue?",
                    "answer": "Revenue was 42.",
                    "status": "answered",
                    "value": {
                        "value_type": "integer",
                        "text_value": None,
                        "number_value": None,
                        "integer_value": 42,
                        "boolean_value": None,
                        "date_value": None,
                        "datetime_value": None,
                        "start_date": None,
                        "end_date": None,
                        "json_value": None,
                        "unit": None,
                        "display_value": "42",
                    },
                    "citations": [
                        {
                            "file": "notes.txt",
                            "location": "line 1",
                            "quote": "Revenue was 42.",
                            "confidence": 0.98,
                        }
                    ],
                    "evidence_chain": [
                        {
                            "step_index": 1,
                            "operation": "extract",
                            "description": "Read the revenue value from the note.",
                            "file": "notes.txt",
                            "location": "line 1",
                            "quote": "Revenue was 42.",
                            "extracted_value": "42",
                            "normalized_value": "42",
                            "transformation": "Parsed as integer.",
                            "confidence": 0.98,
                        }
                    ],
                }
            ]
        }
    )
    agent = AskDocsAgent()
    agent.codex = fake

    response = agent.ask(workdir=tmp_path, queries="revenue?")

    assert response.results[0].answer == "Revenue was 42."
    assert response.results[0].value.value_type == "integer"
    assert response.results[0].value.integer_value == 42
    assert response.results[0].citations[0].file == "notes.txt"
    assert response.results[0].evidence_chain[0].normalized_value == "42"
    assert "notes.txt" in fake.prompt


def test_agent_rejects_unknown_citation(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    fake = FakeCodex(
        {
            "results": [
                {
                    "query": "q",
                    "answer": "a",
                    "status": "answered",
                    "value": {
                        "value_type": "null",
                        "text_value": None,
                        "number_value": None,
                        "integer_value": None,
                        "boolean_value": None,
                        "date_value": None,
                        "datetime_value": None,
                        "start_date": None,
                        "end_date": None,
                        "json_value": None,
                        "unit": None,
                        "display_value": "",
                    },
                    "citations": [{"file": "../secret.txt", "location": "", "quote": ""}],
                    "evidence_chain": [],
                }
            ]
        }
    )
    agent = AskDocsAgent()
    agent.codex = fake

    with pytest.raises(ValueError, match="outside the supported manifest"):
        agent.ask(workdir=tmp_path, queries="q")


def test_codex_client_places_stdin_prompt_marker_last(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_file = ""
    captured_command: list[str] = []

    class Completed:
        returncode = 0
        stderr = ""
        stdout = ""

    class FakeTempFile:
        name = str(tmp_path / "codex-output.json")

        def __enter__(self) -> "FakeTempFile":
            Path(self.name).write_text('{"results":[]}', encoding="utf-8")
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def seek(self, offset: int) -> None:
            return None

        def read(self) -> str:
            return Path(self.name).read_text(encoding="utf-8")

    def fake_run(command: list[str], **kwargs: object) -> Completed:
        nonlocal captured_command, output_file
        captured_command = command
        output_file = command[command.index("--output-last-message") + 1]
        Path(output_file).write_text('{"results":[]}', encoding="utf-8")
        return Completed()

    monkeypatch.setattr(codex_module.tempfile, "NamedTemporaryFile", lambda *args, **kwargs: FakeTempFile())
    monkeypatch.setattr(codex_module.subprocess, "run", fake_run)

    client = CodexClient(codex_bin="codex", model="gpt-5")
    response = client.run(prompt="hello", workdir=tmp_path)

    assert response == '{"results":[]}'
    assert captured_command[-1] == "-"
    assert captured_command[captured_command.index("--model") + 1] == "gpt-5"


def test_agent_parses_date_range_value(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("提交时间: 2026 年 6 月", encoding="utf-8")
    fake = FakeCodex(
        {
            "results": [
                {
                    "query": "scitrace的发布日期",
                    "answer": "提交/发布月份为 2026 年 6 月。",
                    "status": "partial",
                    "value": {
                        "value_type": "date_range",
                        "text_value": None,
                        "number_value": None,
                        "integer_value": None,
                        "boolean_value": None,
                        "date_value": None,
                        "datetime_value": None,
                        "start_date": "2026-06-01",
                        "end_date": "2026-06-30",
                        "json_value": None,
                        "unit": None,
                        "display_value": "2026-06",
                    },
                    "citations": [
                        {
                            "file": "paper.md",
                            "location": "line 1",
                            "quote": "提交时间: 2026 年 6 月",
                            "confidence": 0.92,
                        }
                    ],
                    "evidence_chain": [
                        {
                            "step_index": 1,
                            "operation": "extract",
                            "description": "Extract month-level submission time.",
                            "file": "paper.md",
                            "location": "line 1",
                            "quote": "提交时间: 2026 年 6 月",
                            "extracted_value": "2026 年 6 月",
                            "normalized_value": "2026-06-01/2026-06-30",
                            "transformation": "Converted month-only date to inclusive date range.",
                            "confidence": 0.92,
                        }
                    ],
                    "reasoning_summary": "Only month-level evidence was found.",
                }
            ]
        }
    )
    agent = AskDocsAgent()
    agent.codex = fake

    response = agent.ask(workdir=tmp_path, queries="scitrace的发布日期")

    assert response.results[0].value.value_type == "date_range"
    assert response.results[0].value.start_date == "2026-06-01"
    assert response.results[0].value.end_date == "2026-06-30"
    assert response.results[0].evidence_chain[0].operation == "extract"


def test_agent_rejects_unknown_evidence_chain_file(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    fake = FakeCodex(
        {
            "results": [
                {
                    "query": "q",
                    "answer": "a",
                    "status": "answered",
                    "value": {
                        "value_type": "string",
                        "text_value": "a",
                        "number_value": None,
                        "integer_value": None,
                        "boolean_value": None,
                        "date_value": None,
                        "datetime_value": None,
                        "start_date": None,
                        "end_date": None,
                        "json_value": None,
                        "unit": None,
                        "display_value": "a",
                    },
                    "citations": [
                        {
                            "file": "notes.txt",
                            "location": "line 1",
                            "quote": "hello",
                            "confidence": 0.8,
                        }
                    ],
                    "evidence_chain": [
                        {
                            "step_index": 1,
                            "operation": "extract",
                            "description": "Bad source.",
                            "file": "../secret.txt",
                            "location": "line 1",
                            "quote": "secret",
                            "extracted_value": "secret",
                            "normalized_value": "secret",
                            "transformation": None,
                            "confidence": 0.5,
                        }
                    ],
                    "reasoning_summary": "",
                }
            ]
        }
    )
    agent = AskDocsAgent()
    agent.codex = fake

    with pytest.raises(ValueError, match="evidence chain referenced"):
        agent.ask(workdir=tmp_path, queries="q")
