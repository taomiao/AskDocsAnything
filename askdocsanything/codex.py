from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


class CodexExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodexClient:
    codex_bin: str = "codex"
    model: str | None = None
    timeout_seconds: int = 900

    def run(
        self,
        *,
        prompt: str,
        workdir: str | Path,
        image_paths: list[Path] | None = None,
    ) -> str:
        schema_path = files("askdocsanything").joinpath("codex_answer.schema.json")
        with tempfile.NamedTemporaryFile("r", suffix=".json", delete=True) as output:
            command = [
                self.codex_bin,
                "exec",
                "--cd",
                str(Path(workdir).expanduser().resolve()),
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                output.name,
                "--color",
                "never",
            ]
            if self.model:
                command.extend(["--model", self.model])
            for image_path in image_paths or []:
                command.extend(["--image", str(image_path)])
            command.append("-")

            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            output.seek(0)
            message = output.read().strip()
            if completed.returncode != 0:
                details = completed.stderr.strip() or completed.stdout.strip()
                raise CodexExecutionError(f"Codex failed with exit code {completed.returncode}: {details}")
            return message or completed.stdout.strip()
