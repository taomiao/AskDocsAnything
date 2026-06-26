#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  osascript -e 'display alert "AskDocsAnything" message "Please select a file or folder first."'
  exit 1
fi

if [ -n "${ASKDOCS_BIN:-}" ]; then
  ASKDOCS_COMMAND=("$ASKDOCS_BIN")
else
  ASKDOCS_COMMAND=("${ASKDOCS_PYTHON:-python3}" -m askdocsanything.cli)
fi
OUTPUT_DIR="${TMPDIR:-/tmp}/AskDocsAnything"
mkdir -p "$OUTPUT_DIR"

QUERY="$(osascript <<'APPLESCRIPT'
set dialogResult to display dialog "Enter your AskDocsAnything query:" default answer "" buttons {"Cancel", "Ask"} default button "Ask"
text returned of dialogResult
APPLESCRIPT
)"

if [ -z "$QUERY" ]; then
  exit 0
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_FILE="$OUTPUT_DIR/result-$TIMESTAMP.json"
LOG_FILE="$OUTPUT_DIR/result-$TIMESTAMP.log"

{
  echo "AskDocsAnything"
  echo "Query: $QUERY"
  echo "Selected paths:"
  printf '  %s\n' "$@"
  echo
} > "$LOG_FILE"

if [ "$#" -eq 1 ]; then
  if "${ASKDOCS_COMMAND[@]}" "$1" "$QUERY" --json > "$OUTPUT_FILE" 2>> "$LOG_FILE"; then
    open -a TextEdit "$OUTPUT_FILE"
    exit 0
  fi
else
  {
    echo "{"
    echo '  "results_by_path": ['
  } > "$OUTPUT_FILE"

  first=1
  for selected_path in "$@"; do
    path_output="$OUTPUT_DIR/path-result-$TIMESTAMP-$first.json"
    if "${ASKDOCS_COMMAND[@]}" "$selected_path" "$QUERY" --json > "$path_output" 2>> "$LOG_FILE"; then
      if [ "$first" -ne 1 ]; then
        echo "," >> "$OUTPUT_FILE"
      fi
      python3 - "$selected_path" "$path_output" >> "$OUTPUT_FILE" <<'PY'
import json
import sys

selected_path = sys.argv[1]
payload_path = sys.argv[2]
with open(payload_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)
print(json.dumps({"path": selected_path, "response": payload}, ensure_ascii=False, indent=4), end="")
PY
      first=$((first + 1))
    fi
  done

  {
    echo
    echo "  ]"
    echo "}"
  } >> "$OUTPUT_FILE"

  if [ "$first" -gt 1 ]; then
    open -a TextEdit "$OUTPUT_FILE"
    exit 0
  fi
fi

osascript -e 'display alert "AskDocsAnything failed" message "Open the log file for details."' || true
open -a TextEdit "$LOG_FILE"
exit 1
