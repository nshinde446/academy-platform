"""Organize study_material zips into a canonical extracted/ tree.

Reads every *.zip in ``study_material/`` and copies its files into
``study_material/extracted/<subject>/class-<N>/<chapter-slug>/<file>``
so the downstream ingest pipeline can use folder-name heuristics
instead of regex-parsing the original archive paths.

Usage:
    cd backend
    python scripts/organize_study_material.py --dry-run     # preview
    python scripts/organize_study_material.py               # write
    python scripts/organize_study_material.py --only ncert  # one zip

Layout written:
    study_material/extracted/
        physics/class-11/work-energy-and-power/<source-tag>--<file>.pdf
        physics/class-mixed/motion-in-a-straight-line/...
        chemistry/class-12/chemical-bonding-and-molecular-structure/...
        biology/class-11/morphology-of-flowering-plants/...
        mathematics/class-11/binomial-theorem/...
        unsorted/<source-tag>/<original-path>  # when subject/class can't be detected

PDFs are preferred; DOCX siblings go into a ``_docx/`` subfolder so the
ingest pipeline knows they exist but doesn't try to parse them as the
primary source.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent / "study_material"
DEST = ROOT / "extracted"


SUBJECT_PATTERNS = [
    ("physics", re.compile(r"\bphysics\b", re.I)),
    ("chemistry", re.compile(r"\b(chem(istry)?)\b", re.I)),
    ("biology", re.compile(r"\b(bio(logy)?)\b", re.I)),
    ("mathematics", re.compile(r"\b(math(s|ematic|ematics)?)\b", re.I)),
]


def detect_subject(path: str) -> str | None:
    for slug, pat in SUBJECT_PATTERNS:
        if pat.search(path):
            return slug
    return None


def detect_class(path: str) -> str:
    """Returns '11', '12', or 'mixed' (for 11+12 combined files)."""
    # Mixed first so "11th+12th" doesn't match the bare "11" rule below.
    if re.search(r"11\s*\+\s*12|xi\s*\+\s*xii|11th\s*\+\s*12th", path, re.I):
        return "mixed"
    if re.search(r"\bclass\s*11\b|\b11th\b|\bxi\b(?!i)", path, re.I):
        return "11"
    if re.search(r"\bclass\s*12\b|\b12th\b|\bxii\b", path, re.I):
        return "12"
    return "unknown"


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[_&]", " ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# Structural folder names that are never themselves chapters. Anything
# else (after stripping format/sample suffixes) is considered a chapter.
STRUCTURAL_FOLDERS = {
    "pdf",
    "ms word",
    "ms-word",
    "msword",
    "word",
    "pdf chemistry",
    "pdf maths",
    "pdf math",
    "pdf physics",
    "pdf biology",
    "11th+12th word",
    "11th+12th words",
    "xi+xii pdf",
    " 11th+12th word",
    " 11th+12th words",
    "class 11",
    "class 12",
    "class 11th",
    "class 12th",
    "ncert topic wise mcq",
    "chapter wise-dpp",
    "topic - wise dpp - sample",
    "jee_neet q-bank",
    " jee_neet q-bank",
    "jee _ neet chapterwise question bank",
    "jee (mains+adv) blockbuster q.b sample",
    "chemistry dpp samples",
    "physics dpp samples",
    "biology dpp samples",
    "maths  dpp samples",
    "maths dpp samples",
    "physics",
    "chemistry",
    "biology",
    "mathematic",
    "mathematics",
    "maths",
    "sample mathematics - daily practice paper",
    "sample mathematics - daily practice paper  ",
    "biology - daily practice paper sample",
    "chemistry - daily practice paper sample",
    "physics - daily practice paper sample",
    "jee-mains- physics - mcqs-sample",
    "jee- mains- chemistry -mcqs-sample",
    "jee-mains- maths - mcqs-sample",
    "neet - biology - mcqs-sample",
}


_FORMAT_SUFFIX_RE = re.compile(
    r"\s*[-–]\s*(samples?\s+(pdf|word)\s+format|"
    r"(pdf|ms[\s-]?word|word)\s+format\s+samples?|"
    r"samples?\s+(pdf|word)?\s+format|"
    r"daily\s+practice\s+paper\s+sample|"
    r"mcqs[-\s]*sample|"
    r"-?\s*samples?$|"
    r"contents?$)\s*$",
    re.I,
)


def clean_folder_name(name: str) -> str:
    """Strip format/sample noise from a folder name, returning what's
    left (e.g. 'Chemical Bonding _ & Molecular Structure - Samples PDF
    Format' → 'Chemical Bonding _ & Molecular Structure')."""
    cleaned = name.strip()
    # Iteratively strip format/sample suffixes (sometimes nested).
    for _ in range(3):
        new = _FORMAT_SUFFIX_RE.sub("", cleaned).strip()
        if new == cleaned:
            break
        cleaned = new
    return cleaned


def is_chapter_folder(folder_name: str) -> bool:
    """A folder is a chapter container if, after stripping format/sample
    noise, what remains is not one of our known structural folder names
    AND isn't just a class marker or subject name on its own.
    """
    name = folder_name.strip().lower()
    if not name:
        return False
    cleaned = clean_folder_name(folder_name).strip().lower()
    if not cleaned or cleaned in STRUCTURAL_FOLDERS:
        return False
    # Whole folder is just a class marker or subject?
    if detect_class(cleaned) != "unknown" and len(cleaned) < 25:
        return False
    if detect_subject(cleaned) and len(cleaned) < 18:
        return False
    return True


_FILENAME_NOISE_RE = re.compile(
    r"\s*[-–]?\s*("
    r"dpp[-\s]*\d+(?:\s*solutions?)?|"     # DPP - 5, DPP-9 SOLUTION
    r"solutions?|answers?|explanations?|"  # bare suffixes
    r"\d{2,4}|"                            # trailing question counts (500, 1000)
    r"q[-\s]*\d+|a[-\s]*\d+"               # Q-9, A-5
    r")\s*$",
    re.I,
)


def filename_looks_chapter(filename: str) -> bool:
    """A filename looks chapter-shaped if, after stripping DPP / solution
    / question-count noise, what's left is a multi-word topic name
    (e.g. 'MOTION IN A STRAIGHT LINE 500' → 'MOTION IN A STRAIGHT LINE')
    rather than just a generic 'DPP - 5' or 'dpp-2'.
    """
    stem = Path(filename).stem
    cleaned = stem
    for _ in range(3):
        new = _FILENAME_NOISE_RE.sub("", cleaned).strip(" -_.")
        if new == cleaned:
            break
        cleaned = new
    if not cleaned:
        return False
    # Reject sentinel filenames that aren't chapters.
    low = cleaned.lower()
    if low in {"contents", "content", "index", "answers", "solutions", "explanations"}:
        return False
    # Reject pure noise (e.g. "dpp", "sol")
    if low.replace("-", "").replace(" ", "") in {"dpp", "sol", "solution", "answer"}:
        return False
    # Must contain at least two word-ish tokens to count as a chapter.
    tokens = [t for t in re.split(r"\s+", cleaned) if t]
    return len(tokens) >= 2 and len(cleaned) >= 8


def clean_filename_stem(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = stem
    for _ in range(3):
        new = _FILENAME_NOISE_RE.sub("", cleaned).strip(" -_.")
        if new == cleaned:
            break
        cleaned = new
    return cleaned


def pick_chapter(parts: list[str], filename: str) -> str:
    """Prefer chapter-shaped FILENAME stems (NCERT and JEE_NEET layouts
    name files by chapter inside a generic subject/class folder).
    Otherwise walk path right-to-left and pick the deepest non-structural
    folder."""
    if filename_looks_chapter(filename):
        return slugify(clean_filename_stem(filename))
    for p in reversed(parts[:-1]):
        if is_chapter_folder(p):
            return slugify(clean_folder_name(p))
    fallback = clean_filename_stem(filename)
    return slugify(fallback) or "unspecified"


def is_supported(name: str) -> bool:
    return name.lower().endswith((".pdf", ".docx", ".doc"))


def source_tag(zip_filename: str) -> str:
    """Short slug for the source zip — embedded in extracted filenames."""
    name = Path(zip_filename).stem
    name = re.sub(r"-\d{8}T\d{6}Z-\d+-\d+$", "", name)  # strip Google Drive suffix
    return slugify(name)


def plan_extraction(zip_path: Path) -> list[tuple[str, Path]]:
    """Returns [(zip_member, destination_path)] for every supported file."""
    plan: list[tuple[str, Path]] = []
    src_tag = source_tag(zip_path.name)
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            if not is_supported(name):
                continue
            parts = [p.strip() for p in name.split("/") if p.strip()]
            if not parts:
                continue
            file_name = parts[-1]
            joined_path = " / ".join(parts)
            subject = detect_subject(joined_path)
            cls = detect_class(joined_path)

            if subject is None:
                dest = DEST / "unsorted" / src_tag / "/".join(parts)
            else:
                chapter_slug = pick_chapter(parts, file_name) or "unspecified"
                cls_dir = f"class-{cls}" if cls != "unknown" else "class-unknown"
                fmt_dir = "_docx" if name.lower().endswith((".docx", ".doc")) else ""
                dest_parts = [subject, cls_dir, chapter_slug]
                if fmt_dir:
                    dest_parts.append(fmt_dir)
                dest_parts.append(f"{src_tag}--{file_name}")
                dest = DEST.joinpath(*dest_parts)
            plan.append((name, dest))
    return plan


def main() -> int:
    # Force UTF-8 stdout so the arrow + emoji output works on cp1252 hosts.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Show plan without writing"
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Substring match on zip filename (e.g. 'ncert')",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing destinations",
    )
    args = parser.parse_args()

    if not ROOT.exists():
        print(f"ERROR: {ROOT} does not exist")
        return 1

    zips = sorted(p for p in ROOT.iterdir() if p.suffix.lower() == ".zip")
    if args.only:
        needle = args.only.lower()
        zips = [z for z in zips if needle in z.name.lower()]
    if not zips:
        print("No zips to process.")
        return 1

    stats: dict[str, dict] = defaultdict(
        lambda: {"files": 0, "pdf": 0, "docx": 0, "by_subject": defaultdict(int)}
    )
    grand_plan: list[tuple[Path, str, Path]] = []

    for z in zips:
        plan = plan_extraction(z)
        for member, dest in plan:
            grand_plan.append((z, member, dest))
            stats[z.name]["files"] += 1
            if member.lower().endswith(".pdf"):
                stats[z.name]["pdf"] += 1
            else:
                stats[z.name]["docx"] += 1
            try:
                stats[z.name]["by_subject"][dest.relative_to(DEST).parts[0]] += 1
            except ValueError:
                stats[z.name]["by_subject"]["??"] += 1

    print("=" * 64)
    print(f"Plan: {len(grand_plan):,} files from {len(zips)} zip(s)")
    print("=" * 64)
    for zname, s in stats.items():
        print(f"\n  {zname}")
        print(f"     {s['files']:>5} files  ({s['pdf']} PDF, {s['docx']} DOCX)")
        for sub, n in sorted(s["by_subject"].items(), key=lambda x: -x[1]):
            print(f"     {n:>5} → {sub}")

    if args.dry_run:
        print(f"\n[dry-run] would write under {DEST}")
        # Sample a few destination paths so the user can sanity-check.
        print("\nSample destinations (12 of plan):")
        seen_dirs: set[Path] = set()
        for _, _, dest in grand_plan:
            if dest.parent not in seen_dirs:
                seen_dirs.add(dest.parent)
                print(f"  {dest.relative_to(DEST)}")
                if len(seen_dirs) >= 12:
                    break
        return 0

    # Extract.
    written = 0
    skipped = 0
    for z, member, dest in grand_plan:
        if dest.exists() and not args.force:
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            with zf.open(member) as src, open(dest, "wb") as tgt:
                shutil.copyfileobj(src, tgt)
        written += 1
        if written % 50 == 0:
            print(f"  ...wrote {written} files")
    print(f"\nDone: {written} written, {skipped} skipped (already existed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
