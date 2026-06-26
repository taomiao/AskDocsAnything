from __future__ import annotations

import argparse
import json
import sys

from askdocsanything.agent import AskDocsAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="askdocs",
        description="Ask document-grounded questions with Codex and return cited answers.",
    )
    parser.add_argument("workdir", help="File or directory containing documents to query.")
    parser.add_argument("prompt", nargs="?", help="Single query. Use --query for batch mode.")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Batch query. Can be provided multiple times.",
    )
    parser.add_argument("--model", help="Codex model name.")
    parser.add_argument("--codex-bin", default="codex", help="Path to the Codex CLI binary.")
    parser.add_argument("--timeout", type=int, default=900, help="Codex timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print full JSON response.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    queries = args.queries or []
    if args.prompt:
        queries.insert(0, args.prompt)
    if not queries:
        parser.error("provide a query as PROMPT or at least one --query")

    agent = AskDocsAgent(
        codex_bin=args.codex_bin,
        model=args.model,
        timeout_seconds=args.timeout,
    )
    try:
        response = agent.ask(workdir=args.workdir, queries=queries)
    except Exception as exc:
        print(f"askdocs failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
        return 0

    for index, result in enumerate(response.results, start=1):
        if len(response.results) > 1:
            print(f"[{index}] {result.query}")
        print(result.answer)
        if result.citations:
            print("Sources:")
            for citation in result.citations:
                location = f" ({citation.location})" if citation.location else ""
                quote = f": {citation.quote}" if citation.quote else ""
                print(f"- {citation.file}{location}{quote}")
        if index < len(response.results):
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
