"""Generate NEET_Syllabus.xlsx from the data block embedded in read_this.txt.

Uses openpyxl (already a backend dependency) so it runs with no extra installs.
Re-running is idempotent — overwrites the .xlsx in place.

Usage:
    python generate_neet_syllabus.py
"""

import ast
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

HERE = Path(__file__).parent
SOURCE = HERE / "read_this.txt"
OUTPUT = HERE / "NEET_Syllabus.xlsx"

HEADERS = ["Subject", "Chapter", "Topic", "Subtopic"]


def extract_data_rows(text: str) -> list[list[str]]:
    """Pull the `data = [ ... ]` Python literal out of read_this.txt and eval it."""
    match = re.search(r"data\s*=\s*(\[.*?^\s*\])", text, re.DOTALL | re.MULTILINE)
    if not match:
        raise SystemExit("Could not locate `data = [ ... ]` block in read_this.txt")
    return ast.literal_eval(match.group(1))


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    rows = extract_data_rows(text)
    if not rows:
        raise SystemExit("No data rows extracted.")

    wb = Workbook()
    ws = wb.active
    ws.title = "NEET Syllabus"

    header_font = Font(bold=True)

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = Alignment(horizontal="left", vertical="center")

    for row in rows:
        padded = list(row) + [""] * (len(HEADERS) - len(row))
        ws.append(padded[: len(HEADERS)])

    widths = [16, 56, 64, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    ws.freeze_panes = "A2"

    wb.save(OUTPUT)

    by_subject: dict[str, int] = {}
    for r in rows:
        by_subject[r[0]] = by_subject.get(r[0], 0) + 1

    print(f"Wrote {OUTPUT} - {len(rows)} data rows")
    for subject, count in by_subject.items():
        print(f"  {subject}: {count} rows")


if __name__ == "__main__":
    main()
