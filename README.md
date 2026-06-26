# AskDocsAnything

AskDocsAnything is a small Python SDK and CLI for using Codex as a document-grounded AI agent.
Each query runs against a caller-specified file or working directory and returns structured answers with evidence.

Supported document extensions:

- PowerPoint: `.ppt`, `.pptx`
- Word: `.doc`, `.docx`
- Excel: `.xls`, `.xlsx`, `.csv`, `.tsv`
- PDF: `.pdf`
- Web/text: `.html`, `.htm`, `.md`, `.markdown`, `.txt`
- Images: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`, `.tif`, `.tiff`

## Install for local development

```bash
python -m pip install -e .
```

## Python usage

```python
from askdocsanything import AskDocsAgent

agent = AskDocsAgent()

result = agent.ask(
    workdir="/path/to/documents",
    queries=[
        "2024 Q4 的总收入是多少？",
        "哪个客户贡献最高？请给出来源。",
    ],
)

for item in result.results:
    print(item.query)
    print(item.answer)
    print(item.value.value_type, item.value.date_value, item.value.number_value)
    for citation in item.citations:
        print(citation.file, citation.location, citation.quote)
    for step in item.evidence_chain:
        print(step.step_index, step.operation, step.file, step.extracted_value, step.normalized_value)
```

Each result includes a database-friendly `value` object:

```json
{
  "value_type": "date_range",
  "text_value": null,
  "number_value": null,
  "integer_value": null,
  "boolean_value": null,
  "date_value": null,
  "datetime_value": null,
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "json_value": null,
  "unit": null,
  "display_value": "2026-06"
}
```

For a numeric query such as `Total PPARG target genes (curated)的值是多少`, Codex is instructed to return `value_type="number"` or `value_type="integer"` and put the normalized value into `number_value` or `integer_value`.

For list/object answers, `json_value` is a JSON-encoded string so it can be stored in a database `JSON` or `TEXT` column without breaking the Codex structured-output schema.

Each result also includes an `evidence_chain` array for auditability:

```json
[
  {
    "step_index": 1,
    "operation": "extract",
    "description": "Read the metric row from the CSV.",
    "file": "pparg_target_analysis_summary.csv",
    "location": "row 2",
    "quote": "Total PPARG target genes (curated),65",
    "extracted_value": "65",
    "normalized_value": "65",
    "transformation": "Parsed CSV Value column as integer.",
    "confidence": 0.99
  }
]
```

`citations` are the compact final sources for display. `evidence_chain` is the fuller provenance trail for database storage, debugging, and audits.

## CLI usage

```bash
askdocs /path/to/documents "总结这批文档中的关键收入数据，并给出处"
```

You can also query a single supported file:

```bash
askdocs /path/to/report.pdf "这份报告的发布日期是什么？" --json
```

Batch mode:

```bash
askdocs /path/to/documents \
  --query "2024 Q4 的总收入是多少？" \
  --query "哪个客户贡献最高？"
```

JSON output:

```bash
askdocs /path/to/documents "列出所有风险项" --json
```

## macOS Finder Quick Action

Install the Finder right-click action:

```bash
scripts/install_macos_finder_quick_action.sh
```

Then use Finder:

```text
Right-click a file or folder -> Quick Actions -> AskDocsAnything
```

The action opens a small AskDocsAnything window, prompts for a query, shows an indeterminate progress bar while Codex is running, and renders the answer plus full JSON in the same window.

Logs and generated result files are written to:

```text
~/Library/Logs/AskDocsAnything/
```

If the action does not appear or seems stale, restart Finder:

```bash
killall Finder
```

## How it works

The SDK builds a manifest of supported files in the requested working directory, asks Codex to inspect only that directory, and requires the final answer to match a JSON Schema. Codex is instructed to cite exact source files and locations, and to mark answers as `not_found` instead of guessing.

By default it calls:

```bash
codex exec --cd <workdir> --skip-git-repo-check --sandbox read-only --ephemeral
```

You can pass a custom Codex binary or model:

```python
agent = AskDocsAgent(codex_bin="/Applications/Codex.app/Contents/Resources/codex", model="gpt-5")
```
