from __future__ import annotations

import json
import os
import queue
import threading
import time
import traceback
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Button, Frame, StringVar, Tk, Toplevel, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from askdocsanything.agent import AskDocsAgent

BG = "#071832"
PANEL = "#0d2345"
PANEL_2 = "#102b55"
INPUT_BG = "#1b3158"
TEXT = "#eef4ff"
MUTED = "#9aa8c7"
ACCENT = "#2f7cff"
ACCENT_DARK = "#1f63e5"
ACCENT_GLOW = "#7aa7ff"
SECONDARY_BG = "#102747"
SECONDARY_ACTIVE = "#173a68"
BORDER = "#294a78"
SUCCESS = "#70e4c1"
ERROR = "#ff9a76"
MONO = "Menlo"
UI_FONT = "Helvetica"


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else []
    if not paths:
        messagebox.showerror("AskDocsAnything", "Please select a file or folder first.")
        return 1

    app = FinderAskDocsApp(paths)
    app.run()
    return 0


class FinderAskDocsApp:
    def __init__(self, paths: list[str]) -> None:
        self.paths = paths
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.root = Tk()
        self.root.title("AskDocsAnything")
        self.root.geometry("640x420")
        self.root.minsize(560, 360)
        self.root.configure(bg=BG)

        self.status = StringVar(value="Ready")
        self.query = StringVar()
        self.last_query = ""
        self.last_response: object | None = None
        self.last_output_path: Path | None = None

        self._configure_style()
        self._build_ui()
        self._position_near_pointer(self.root, 640, 420)
        self._bring_to_front(self.root)

    def run(self) -> None:
        self.root.after(100, self._poll_events)
        self.root.mainloop()

    def _position_near_pointer(self, window: Tk | Toplevel, width: int, height: int) -> None:
        window.update_idletasks()
        pointer_x = window.winfo_pointerx()
        pointer_y = window.winfo_pointery()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()

        x = min(max(pointer_x + 18, 0), max(screen_w - width - 20, 0))
        y = min(max(pointer_y + 18, 0), max(screen_h - height - 60, 0))
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _bring_to_front(self, window: Tk | Toplevel) -> None:
        window.update_idletasks()
        window.attributes("-topmost", True)
        window.lift()
        window.focus_force()
        window.after(1200, lambda: window.attributes("-topmost", False))

    def _configure_style(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure("App.TFrame", background=BG)
        self.style.configure("Panel.TFrame", background=PANEL, borderwidth=1, relief="solid")
        self.style.configure("Title.TLabel", background=BG, foreground=TEXT, font=(UI_FONT, 20, "bold"))
        self.style.configure("Logo.TLabel", background=BG, foreground=ACCENT_GLOW, font=(UI_FONT, 26, "bold"))
        self.style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=(UI_FONT, 11))
        self.style.configure("Field.TLabel", background=BG, foreground="#c8d6f7", font=(UI_FONT, 11, "bold"))
        self.style.configure("Status.TLabel", background=BG, foreground=MUTED, font=(UI_FONT, 11))
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor="#163052",
            background=ACCENT,
            bordercolor="#163052",
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        self.style.configure(
            "TEntry",
            fieldbackground=INPUT_BG,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=10,
        )

    def _make_button(
        self,
        parent: Frame,
        *,
        text: str,
        command: object,
        variant: str = "secondary",
        width: int = 10,
        state: str = "normal",
    ) -> Button:
        if variant == "primary":
            bg = ACCENT
            fg = "#ffffff"
            active_bg = ACCENT_DARK
            disabled_bg = "#263b61"
        else:
            bg = SECONDARY_BG
            fg = TEXT
            active_bg = SECONDARY_ACTIVE
            disabled_bg = "#132541"

        return Button(
            parent,
            text=text,
            command=command,
            width=width,
            state=state,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            disabledforeground="#66789f",
            highlightthickness=1,
            highlightbackground=ACCENT if variant == "primary" else BORDER,
            highlightcolor=ACCENT_GLOW,
            relief="flat",
            bd=0,
            padx=12,
            pady=7,
            cursor="pointinghand",
            font=(UI_FONT, 12, "bold" if variant == "primary" else "normal"),
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(18, 16), style="App.TFrame")
        outer.pack(fill=BOTH, expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill=X)
        ttk.Label(header, text="A", style="Logo.TLabel").pack(side=LEFT, padx=(0, 10))
        ttk.Label(header, text="AskDocsAnything", style="Title.TLabel").pack(side=LEFT, anchor="center")

        ttk.Label(outer, text=self._selected_paths_text(), style="Subtitle.TLabel", wraplength=590, justify=LEFT).pack(
            anchor="w", pady=(8, 12)
        )

        query_row = ttk.Frame(outer, style="App.TFrame")
        query_row.pack(fill=X)
        ttk.Label(query_row, text="Query", style="Field.TLabel").pack(anchor="w")
        self.query_entry = ttk.Entry(query_row, textvariable=self.query)
        self.query_entry.pack(fill=X, pady=(4, 10))
        self.query_entry.focus_set()
        self.query_entry.bind("<Return>", lambda _event: self._start_query())

        controls = ttk.Frame(outer, style="App.TFrame")
        controls.pack(fill=X, pady=(0, 10))
        self.ask_button = self._make_button(
            controls, text="Ask", command=self._start_query, width=10, variant="primary"
        )
        self.ask_button.pack(side=LEFT)
        self.copy_button = self._make_button(
            controls, text="Copy", command=self._copy_output, width=10, state="disabled"
        )
        self.copy_button.pack(side=LEFT, padx=(8, 0))
        self.detail_button = self._make_button(
            controls, text="详细", command=self._open_detail_window, width=10, state="disabled"
        )
        self.detail_button.pack(side=LEFT, padx=(8, 0))
        self._make_button(controls, text="Close", command=self.root.destroy, width=10).pack(
            side=RIGHT
        )

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill=X, pady=(0, 8))
        ttk.Label(outer, textvariable=self.status, style="Status.TLabel").pack(anchor="w", pady=(0, 8))

        self.output = ScrolledText(
            outer,
            wrap="word",
            font=(UI_FONT, 13),
            height=9,
            relief="flat",
            borderwidth=0,
            background=PANEL,
            foreground=TEXT,
            insertbackground=TEXT,
            padx=14,
            pady=12,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self.output.pack(fill=BOTH, expand=True)
        self._configure_text_tags(self.output)
        self.output.insert(END, "Enter a query and click Ask.\n")

    def _configure_text_tags(self, widget: ScrolledText) -> None:
        widget.tag_configure("muted", foreground=MUTED, font=(UI_FONT, 11))
        widget.tag_configure("answer", foreground=TEXT, font=(UI_FONT, 14, "bold"), spacing3=8)
        widget.tag_configure("label", foreground="#b9c7e8", font=(UI_FONT, 11, "bold"))
        widget.tag_configure("value", foreground=SUCCESS, font=(UI_FONT, 12, "bold"))
        widget.tag_configure("source", foreground="#cbd7f2", font=(UI_FONT, 11))
        widget.tag_configure("error", foreground=ERROR, font=(UI_FONT, 12, "bold"))
        widget.tag_configure("mono", foreground=TEXT, font=(MONO, 12))

    def _selected_paths_text(self) -> str:
        if len(self.paths) == 1:
            return f"Selected: {self.paths[0]}"
        return "Selected:\n" + "\n".join(f"- {path}" for path in self.paths)

    def _start_query(self) -> None:
        query = self.query.get().strip()
        if not query:
            messagebox.showwarning("AskDocsAnything", "Please enter a query.")
            return

        self.ask_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.detail_button.configure(state="disabled")
        self.output.delete("1.0", END)
        self.output.insert(END, "Running AskDocsAnything...\n", "muted")
        self.status.set("Running Codex document query...")
        self.progress.start(12)

        worker = threading.Thread(target=self._run_query_worker, args=(query,), daemon=True)
        worker.start()

    def _run_query_worker(self, query: str) -> None:
        started = time.time()
        try:
            codex_bin = os.environ.get("ASKDOCS_CODEX_BIN") or "codex"
            agent = AskDocsAgent(codex_bin=codex_bin)
            if len(self.paths) == 1:
                response = agent.ask(workdir=self.paths[0], queries=query).to_dict()
            else:
                response = {
                    "results_by_path": [
                        {
                            "path": path,
                            "response": agent.ask(workdir=path, queries=query).to_dict(),
                        }
                        for path in self.paths
                    ]
                }
            elapsed = time.time() - started
            output_path = self._write_result(response)
            self.events.put(("success", (query, response, output_path, elapsed)))
        except Exception as exc:
            error = {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            output_path = self._write_result(error, suffix="error")
            self.events.put(("error", (error, output_path)))

    def _poll_events(self) -> None:
        try:
            event, payload = self.events.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_events)
            return

        self.progress.stop()
        self.ask_button.configure(state="normal")
        self.copy_button.configure(state="normal")

        if event == "success":
            query, response, output_path, elapsed = payload
            self.last_query = query
            self.last_response = response
            self.last_output_path = output_path
            self.detail_button.configure(state="normal")
            self.status.set(f"Done in {elapsed:.1f}s. Saved: {output_path}")
            self._show_response(query, response, output_path)
            self._bring_to_front(self.root)
        else:
            error, output_path = payload
            self.last_query = self.query.get().strip()
            self.last_response = error
            self.last_output_path = output_path
            self.detail_button.configure(state="normal")
            self.status.set(f"Failed. Log saved: {output_path}")
            self.output.delete("1.0", END)
            self.output.insert(END, "AskDocsAnything failed.\n\n", "error")
            self.output.insert(END, error["error"], "source")
            self._bring_to_front(self.root)

        self.root.after(100, self._poll_events)

    def _show_response(self, query: str, response: object, output_path: Path) -> None:
        self.output.delete("1.0", END)
        self.output.insert(END, "Query\n", "label")
        self.output.insert(END, f"{query}\n\n", "source")

        if isinstance(response, dict) and "results" in response:
            self._insert_compact_summary(response)
        elif isinstance(response, dict) and "results_by_path" in response:
            for item in response["results_by_path"]:
                self.output.insert(END, f"Path: {item.get('path')}\n")
                self._insert_compact_summary(item.get("response", {}))
                self.output.insert(END, "\n")

        self.output.insert(END, "\nSaved\n", "label")
        self.output.insert(END, f"{output_path}\n", "muted")

    def _insert_compact_summary(self, response: dict) -> None:
        for result in response.get("results", []):
            self.output.insert(END, f"{result.get('answer', '')}\n\n", "answer")
            value = result.get("value")
            if value:
                display_value = value.get("display_value") or _first_present_value(value)
                if display_value:
                    self.output.insert(END, "Value  ", "label")
                    self.output.insert(END, f"{display_value}\n", "value")
            citations = result.get("citations", [])
            if citations:
                first = citations[0]
                source = first.get("file", "")
                location = first.get("location", "")
                self.output.insert(END, "Source ", "label")
                self.output.insert(END, f"{source} {location}\n", "source")
            self.output.insert(END, "\n")

    def _insert_detailed_summary(self, widget: ScrolledText, response: dict) -> None:
        for result in response.get("results", []):
            widget.insert(END, f"Answer: {result.get('answer', '')}\n")
            widget.insert(END, f"Status: {result.get('status', '')}\n")
            value = result.get("value")
            if value:
                widget.insert(END, f"Value: {json.dumps(value, ensure_ascii=False)}\n")
            citations = result.get("citations", [])
            if citations:
                widget.insert(END, "Sources:\n")
                for citation in citations:
                    widget.insert(
                        END,
                        f"- {citation.get('file')} ({citation.get('location')}): {citation.get('quote')}\n",
                    )
            evidence_chain = result.get("evidence_chain", [])
            if evidence_chain:
                widget.insert(END, "Evidence chain:\n")
                for step in evidence_chain:
                    widget.insert(
                        END,
                        f"- {step.get('step_index')}. {step.get('operation')}: {step.get('description')}\n",
                    )
            widget.insert(END, "\n")

    def _open_detail_window(self) -> None:
        if self.last_response is None:
            return

        detail = Toplevel(self.root)
        detail.title("AskDocsAnything Details")
        detail.geometry("920x720")
        detail.minsize(760, 560)
        detail.configure(bg=BG)
        self._position_near_pointer(detail, 920, 720)
        self._bring_to_front(detail)

        outer = ttk.Frame(detail, padding=(18, 16), style="App.TFrame")
        outer.pack(fill=BOTH, expand=True)

        header = f"Query: {self.last_query}"
        if self.last_output_path is not None:
            header += f"\nSaved: {self.last_output_path}"
        ttk.Label(outer, text=header, justify=LEFT, anchor="w", style="Subtitle.TLabel").pack(fill=X, pady=(0, 10))

        text = ScrolledText(
            outer,
            wrap="word",
            font=(MONO, 12),
            relief="flat",
            borderwidth=0,
            background=PANEL,
            foreground=TEXT,
            padx=14,
            pady=12,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        text.pack(fill=BOTH, expand=True)
        self._configure_text_tags(text)

        response = self.last_response
        if isinstance(response, dict) and "results" in response:
            self._insert_detailed_summary(text, response)
        elif isinstance(response, dict) and "results_by_path" in response:
            for item in response["results_by_path"]:
                text.insert(END, f"Path: {item.get('path')}\n")
                self._insert_detailed_summary(text, item.get("response", {}))
                text.insert(END, "\n")

        text.insert(END, "\nFull JSON\n")
        text.insert(END, json.dumps(response, ensure_ascii=False, indent=2))

    def _copy_output(self) -> None:
        text = self.output.get("1.0", END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("Copied output to clipboard.")

    def _write_result(self, payload: object, suffix: str = "result") -> Path:
        output_dir = Path.home() / "Library" / "Logs" / "AskDocsAnything"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        path = output_dir / f"{suffix}-{timestamp}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def _first_present_value(value: dict) -> object:
    for key in (
        "text_value",
        "number_value",
        "integer_value",
        "boolean_value",
        "date_value",
        "datetime_value",
        "start_date",
        "json_value",
    ):
        item = value.get(key)
        if item is not None:
            return item
    return None


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
