"""Simple Tkinter GUI for reviewing claim predictions."""

from __future__ import annotations

import argparse
import csv
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk

from .orchestrate.data_io import resolve_image_path, split_image_paths

try:  # Optional, used only for inline JPEG previews.
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageTk = None


FILTER_FIELDS = ["claim_status", "claim_object", "risk_flags", "severity"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ReviewApp:
    def __init__(self, root: tk.Tk, predictions_path: Path) -> None:
        self.root = root
        self.root.title("HackerRank Orchestrate Review")
        self.predictions_path = predictions_path
        self.rows = read_rows(predictions_path)
        self.filtered = self.rows
        self.current_index = 0
        self.preview_image = None

        self.filters = {field: tk.StringVar(value="all") for field in FILTER_FIELDS}
        self._build_layout()
        self._refresh_filters()
        self._refresh_list()
        self._show_row(0)

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text=f"Predictions: {self.predictions_path}").pack(side=tk.LEFT)
        ttk.Button(top, text="Open CSV", command=self._choose_csv).pack(side=tk.RIGHT)

        filter_bar = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        filter_bar.pack(fill=tk.X)
        for field in FILTER_FIELDS:
            ttk.Label(filter_bar, text=field).pack(side=tk.LEFT, padx=(0, 4))
            box = ttk.Combobox(
                filter_bar,
                textvariable=self.filters[field],
                width=22,
                state="readonly",
            )
            box.pack(side=tk.LEFT, padx=(0, 12))
            box.bind("<<ComboboxSelected>>", lambda _event: self._apply_filters())
            setattr(self, f"{field}_box", box)

        body = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body, padding=8)
        self.tree = ttk.Treeview(
            left,
            columns=("user_id", "object", "status", "risk", "severity"),
            show="headings",
            height=24,
        )
        headings = {
            "user_id": "User",
            "object": "Object",
            "status": "Status",
            "risk": "Risk",
            "severity": "Severity",
        }
        for column, label in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=120, stretch=True)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        body.add(left, weight=1)

        right = ttk.Frame(body, padding=8)
        self.detail = tk.Text(right, wrap=tk.WORD, width=82, height=22)
        self.detail.pack(fill=tk.BOTH, expand=True)

        image_frame = ttk.Frame(right)
        image_frame.pack(fill=tk.X, pady=(8, 0))
        self.image_label = ttk.Label(image_frame, text="Image preview")
        self.image_label.pack(fill=tk.X)
        self.image_buttons = ttk.Frame(image_frame)
        self.image_buttons.pack(fill=tk.X, pady=(4, 0))
        body.add(right, weight=2)

    def _choose_csv(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose predictions CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if filename:
            self.predictions_path = Path(filename)
            self.rows = read_rows(self.predictions_path)
            self.filtered = self.rows
            self._refresh_filters()
            self._refresh_list()
            self._show_row(0)

    def _refresh_filters(self) -> None:
        for field in FILTER_FIELDS:
            values = sorted({row.get(field, "") for row in self.rows if row.get(field, "")})
            box = getattr(self, f"{field}_box")
            box["values"] = ["all", *values]
            self.filters[field].set("all")

    def _apply_filters(self) -> None:
        self.filtered = []
        for row in self.rows:
            keep = True
            for field, var in self.filters.items():
                selected = var.get()
                value = row.get(field, "")
                if selected != "all" and selected not in value:
                    keep = False
                    break
            if keep:
                self.filtered.append(row)
        self._refresh_list()
        self._show_row(0)

    def _refresh_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.filtered):
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    row.get("user_id", ""),
                    row.get("claim_object", ""),
                    row.get("claim_status", ""),
                    row.get("risk_flags", ""),
                    row.get("severity", ""),
                ),
            )

    def _on_select(self, _event: object) -> None:
        selected = self.tree.selection()
        if selected:
            self._show_row(int(selected[0]))

    def _show_row(self, index: int) -> None:
        if not self.filtered:
            self.detail.delete("1.0", tk.END)
            self.detail.insert(tk.END, "No rows match the selected filters.")
            return
        self.current_index = max(0, min(index, len(self.filtered) - 1))
        row = self.filtered[self.current_index]
        self.detail.delete("1.0", tk.END)
        fields = [
            "user_id",
            "claim_object",
            "claim_status",
            "issue_type",
            "object_part",
            "severity",
            "evidence_standard_met",
            "valid_image",
            "risk_flags",
            "supporting_image_ids",
            "user_claim",
            "evidence_standard_met_reason",
            "claim_status_justification",
            "image_paths",
        ]
        self.detail.insert(tk.END, "\n\n".join(f"{field}:\n{row.get(field, '')}" for field in fields))
        self._render_images(row)

    def _render_images(self, row: dict[str, str]) -> None:
        for child in self.image_buttons.winfo_children():
            child.destroy()
        paths = split_image_paths(row.get("image_paths", ""))
        if not paths:
            self.image_label.configure(text="No images listed", image="")
            return
        for image_path in paths:
            resolved = resolve_image_path(image_path)
            ttk.Button(
                self.image_buttons,
                text=f"Open {Path(image_path).stem}",
                command=lambda p=resolved: webbrowser.open(p.as_uri()),
            ).pack(side=tk.LEFT, padx=(0, 6))
        if Image is None or ImageTk is None:
            self.image_label.configure(
                text="Install Pillow for inline JPEG previews. Use the buttons to open images.",
                image="",
            )
            return
        first = resolve_image_path(paths[0])
        if not first.exists():
            self.image_label.configure(text=f"Missing image: {first}", image="")
            return
        img = Image.open(first)
        img.thumbnail((720, 420))
        self.preview_image = ImageTk.PhotoImage(img)
        self.image_label.configure(image=self.preview_image, text="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review prediction CSV results.")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path("output.csv"),
        help="Predictions CSV to inspect.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.predictions.exists():
        print(f"Predictions CSV not found: {args.predictions}", file=sys.stderr)
        return 1
    root = tk.Tk()
    root.geometry("1280x760")
    ReviewApp(root, args.predictions)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
