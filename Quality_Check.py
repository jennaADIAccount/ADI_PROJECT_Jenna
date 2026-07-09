
"""
  python3 "/home/eng-6990/PROJECT/extractor/extractor_quality_check.py" \
    --json "/home/eng-6990/PROJECT/extractor/RISC-V_VER.2.json/document.json" \
    --pdf "/home/eng-6990/PROJECT/RISC-V_VER.2.pdf"



Quality checker for engineering specification extractor outputs.

The checker reports three final percentages and pass/fail labels:

1. Completeness percentage
   Formula:
       completeness = mean(
           required_json_field_score,
           page_coverage_score,
           text_coverage_score,
           semantic_chunk_coverage_score,
           record_field_completeness_score,
           csv_presence_score
       )

2. Accuracy percentage
   Formula without a gold/reference JSON:
       accuracy = mean(
           page_text_fidelity_score,
           requirement_traceability_score,
           category_consistency_score,
           page_number_accuracy_score,
           json_internal_consistency_score,
           csv_json_consistency_score
       )

   Formula with --gold-json: can input a gold reference document to use for quality check 
       accuracy = mean(
           requirement_f1_score,
           figure_caption_f1_score,
           table_caption_f1_score,
           page_text_fidelity_score,
           json_internal_consistency_score
       )

3. Table/figure capture percentage
   Formula:
       table_figure_capture = mean(
           table_detection_f1_score,
           table_caption_f1_score,
           table_file_existence_score,
           figure_caption_f1_score,
           image_capture_f1_score
       )

Each percentage is marked "pass" if it is >= --threshold, otherwise "fail".
The default threshold is 95%.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - handled at runtime
    fitz = None


REQUIRED_TOP_LEVEL_KEYS = {
    "document_name",
    "metadata",
    "total_pages",
    "sections",
    "requirements",
    "figures",
    "tables",
    "notes",
    "acronyms",
    "cross_references",
    "semantic_chunks",
    "pages",
}

VALID_REQUIREMENT_CATEGORIES = {
    "Performance",
    "Electrical",
    "Environmental",
    "Safety",
    "Interface",
    "Functional",
}

FIGURE_REGEX = re.compile(r"\b(?:Figure|Fig\.?)\s+([A-Za-z]?\d+(?:[-.]\d+)*)", re.IGNORECASE)
TABLE_REGEX = re.compile(r"\bTable\s+([A-Za-z]?\d+(?:[-.]\d+)*)", re.IGNORECASE)
REQUIREMENT_REGEX = re.compile(
    r"\b(shall|must|will|should|required to|may not|is prohibited)\b",
    re.IGNORECASE,
)


@dataclass
class Score:
    name: str
    percentage: float
    formula: str
    details: dict[str, Any]


def normalise_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\uf05a", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def pct(numerator: float, denominator: float, *, empty_is: float = 100.0) -> float:
    if denominator == 0:
        return empty_is
    return max(0.0, min(100.0, 100.0 * numerator / denominator))


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 100.0
    return sum(values) / len(values)


def f1_from_counters(expected: Counter[str], captured: Counter[str]) -> float:
    expected_total = sum(expected.values())
    captured_total = sum(captured.values())
    if expected_total == 0 and captured_total == 0:
        return 100.0
    if expected_total == 0 or captured_total == 0:
        return 0.0

    true_positive = sum(min(expected[key], captured[key]) for key in expected.keys() | captured.keys())
    precision = true_positive / captured_total if captured_total else 0.0
    recall = true_positive / expected_total if expected_total else 0.0
    if precision + recall == 0:
        return 0.0
    return 100.0 * (2 * precision * recall) / (precision + recall)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object at the top level")
    return data


def read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def infer_pdf_path(json_path: Path, document: dict[str, Any]) -> Path | None:
    doc_name = document.get("document_name")
    candidates: list[Path] = []
    if isinstance(doc_name, str) and doc_name:
        candidates.extend(
            [
                json_path.parent / doc_name,
                json_path.parent.parent / doc_name,
                json_path.parent.parent.parent / doc_name,
            ]
        )

    stem = json_path.parent.name.removesuffix(".json")
    if stem:
        candidates.extend(
            [
                json_path.parent / f"{stem}.pdf",
                json_path.parent.parent / f"{stem}.pdf",
                json_path.parent.parent.parent / f"{stem}.pdf",
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def open_pdf(pdf_path: Path | None):
    if pdf_path is None:
        return None
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for PDF-based checks. Install with: pip install pymupdf")
    return fitz.open(str(pdf_path))


def pdf_page_texts(pdf) -> list[str]:
    if pdf is None:
        return []
    return [page.get_text("text") for page in pdf]


def expected_captions(page_texts: list[str], regex: re.Pattern[str]) -> Counter[str]:
    found: Counter[str] = Counter()
    for page_index, text in enumerate(page_texts, start=1):
        for match in regex.finditer(text):
            found[f"{page_index}:{normalise_text(match.group(0))}"] += 1
    return found


def captured_captions(document: dict[str, Any], key: str, caption_key: str = "caption") -> Counter[str]:
    found: Counter[str] = Counter()
    for page in document.get("pages", []) if isinstance(document.get("pages"), list) else []:
        page_number = page.get("page_number")
        for item in page.get(key, []) if isinstance(page.get(key), list) else []:
            caption = item.get(caption_key) if isinstance(item, dict) else None
            if caption:
                found[f"{page_number}:{normalise_text(caption)}"] += 1
    return found


def page_count_counter(items: Iterable[Any], page_key: str = "page") -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        if isinstance(item, dict) and item.get(page_key) is not None:
            counts[str(item.get(page_key))] += 1
    return counts


def expected_table_counts(pdf) -> Counter[str]:
    counts: Counter[str] = Counter()
    if pdf is None:
        return counts
    for page_index, page in enumerate(pdf, start=1):
        try:
            tables = page.find_tables()
            table_count = len(tables.tables)
            if table_count:
                counts[str(page_index)] = table_count
        except Exception:
            continue
    return counts


def expected_image_counts(pdf) -> Counter[str]:
    counts: Counter[str] = Counter()
    if pdf is None:
        return counts
    for page_index, page in enumerate(pdf, start=1):
        try:
            image_count = len(page.get_images(full=True))
            if image_count:
                counts[str(page_index)] = image_count
        except Exception:
            continue
    return counts


def all_page_requirements(document: dict[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    pages = document.get("pages", [])
    if not isinstance(pages, list):
        return requirements
    for page in pages:
        page_number = page.get("page_number") if isinstance(page, dict) else None
        for req in page.get("requirements", []) if isinstance(page.get("requirements"), list) else []:
            if isinstance(req, dict):
                copied = dict(req)
                copied["_page_number"] = page_number
                requirements.append(copied)
    return requirements


def requirement_counter(requirements: Iterable[dict[str, Any]]) -> Counter[str]:
    values: Counter[str] = Counter()
    for req in requirements:
        text = normalise_text(req.get("text"))
        category = normalise_text(req.get("category"))
        if text:
            values[f"{category}|{text}"] += 1
    return values


def classify_requirement(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["latency", "throughput", "timing", "frequency", "bandwidth"]):
        return "Performance"
    if any(word in lower for word in ["voltage", "current", "power"]):
        return "Electrical"
    if any(word in lower for word in ["temperature", "humidity"]):
        return "Environmental"
    if any(word in lower for word in ["safety", "hazard", "fault"]):
        return "Safety"
    if any(word in lower for word in ["interface", "spi", "uart", "i2c", "can"]):
        return "Interface"
    return "Functional"

def collect_covered_pages(document: dict[str, Any]) -> set[int]:
    covered_pages: set[int] = set()

    def add_page(value: Any) -> None:
        page_num = None
        if isinstance(value, int):
            page_num = value
        elif isinstance(value, str) and value.strip().lstrip("-").isdigit():
            page_num = int(value)
        if page_num is not None and page_num >= 1:
            covered_pages.add(page_num)

    def process_chunk(chunk: dict[str, Any]) -> None:
        pages_in_chunk = chunk.get("pages")
        if isinstance(pages_in_chunk, list):
            for p in pages_in_chunk:
                add_page(p)

        single_page = chunk.get("page")
        if single_page is not None:
            add_page(single_page)

        start, end = chunk.get("page_start"), chunk.get("page_end")
        if isinstance(start, int) and isinstance(end, int) and end >= start:
            covered_pages.update(range(start, end + 1))

    top_level_chunks = document.get("semantic_chunks", [])
    if isinstance(top_level_chunks, list):
        for chunk in top_level_chunks:
            if isinstance(chunk, dict):
                process_chunk(chunk)

    pages = document.get("pages", [])
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                continue
            nested_chunks = page.get("semantic_chunks", [])
            if isinstance(nested_chunks, list):
                for chunk in nested_chunks:
                    if isinstance(chunk, dict):
                        process_chunk(chunk)
                        if not any(k in chunk for k in ("pages", "page", "page_start")):
                            add_page(page.get("page_number"))

    return covered_pages

def score_completeness(
    document: dict[str, Any],
    pdf_page_texts_value: list[str],
    csv_rows: list[dict[str, str]],
    csv_path: Path | None,
) -> Score:
    required_json_field_score = pct(
        len(REQUIRED_TOP_LEVEL_KEYS.intersection(document.keys())),
        len(REQUIRED_TOP_LEVEL_KEYS),
    )

    pages = document.get("pages", [])
    pages = pages if isinstance(pages, list) else []
    expected_page_count = len(pdf_page_texts_value) or int(document.get("total_pages") or 0)
    page_coverage_score = pct(len(pages), expected_page_count)

    output_text_chars = sum(len(page.get("text", "")) for page in pages if isinstance(page, dict))
    source_text_chars = sum(len(text) for text in pdf_page_texts_value)
    text_coverage_score = pct(min(output_text_chars, source_text_chars), source_text_chars)

    covered_pages = collect_covered_pages(document)
    semantic_chunk_coverage_score = pct(len(covered_pages), expected_page_count)

    record_scores: list[float] = []
    
    for key, fields in {
        "requirements": {"text", "category"},
        "figures": {"caption"},
        "tables": {"page", "csv_file"},
    }.items():
        records = document.get(key, [])
        if not isinstance(records, list) or not records:
            continue
        checks = 0
        passed = 0
        for record in records:
            if not isinstance(record, dict):
                checks += len(fields)
                continue
            for field in fields:
                checks += 1
                if record.get(field) not in (None, ""):
                    passed += 1
        record_scores.append(pct(passed, checks))
    record_field_completeness_score = mean(record_scores)

    if csv_path is None:
        csv_presence_score = 100.0
    else:
        csv_presence_score = 100.0 if csv_path.is_file() and csv_rows else 0.0

    component_scores = {
        "required_json_field_score": required_json_field_score,
        "page_coverage_score": page_coverage_score,
        "text_coverage_score": text_coverage_score,
        "semantic_chunk_coverage_score": semantic_chunk_coverage_score,
        "record_field_completeness_score": record_field_completeness_score,
        "csv_presence_score": csv_presence_score,
    }

    return Score(
        name="completeness",
        percentage=mean(component_scores.values()),
        formula="mean(required_json_field, page_coverage, text_coverage, semantic_chunk_coverage, record_field_completeness, csv_presence)",
        details=component_scores,
    )


def score_accuracy(
    document: dict[str, Any],
    pdf_page_texts_value: list[str],
    csv_rows: list[dict[str, str]],
    gold_document: dict[str, Any] | None,
) -> Score:
    pages = document.get("pages", [])
    pages = pages if isinstance(pages, list) else []

    fidelity_scores = []
    for index, source_text in enumerate(pdf_page_texts_value):
        output_text = pages[index].get("text", "") if index < len(pages) and isinstance(pages[index], dict) else ""
        fidelity_scores.append(100.0 * SequenceMatcher(None, normalise_text(source_text), normalise_text(output_text)).ratio())
    page_text_fidelity_score = mean(fidelity_scores)

    top_requirements = document.get("requirements", [])
    top_requirements = top_requirements if isinstance(top_requirements, list) else []
    page_requirements = all_page_requirements(document)
    all_source_text = normalise_text("\n".join(pdf_page_texts_value))

    traceable = 0
    for req in top_requirements:
        text = normalise_text(req.get("text") if isinstance(req, dict) else "")
        if text and text in all_source_text:
            traceable += 1
    requirement_traceability_score = pct(traceable, len(top_requirements))

    category_matches = 0
    category_checks = 0
    for req in top_requirements:
        if not isinstance(req, dict):
            continue
        text = req.get("text")
        category = req.get("category")
        if text and category:
            category_checks += 1
            if category == classify_requirement(str(text)) and category in VALID_REQUIREMENT_CATEGORIES:
                category_matches += 1
    category_consistency_score = pct(category_matches, category_checks)

    expected_pages = set(range(1, len(pdf_page_texts_value) + 1))
    output_pages = {page.get("page_number") for page in pages if isinstance(page, dict)}
    page_number_accuracy_score = pct(len(expected_pages.intersection(output_pages)), len(expected_pages))

    internal_checks = {
        "requirements_match_page_aggregation": requirement_counter(top_requirements) == requirement_counter(page_requirements),
        "figures_match_page_aggregation": Counter(
            normalise_text(item.get("caption")) for item in document.get("figures", []) if isinstance(item, dict) and item.get("caption")
        )
        == Counter(
            normalise_text(item.get("caption")) for page in pages if isinstance(page, dict) for item in page.get("figures", []) if isinstance(item, dict) and item.get("caption")
        ),
        "tables_have_valid_pages": all(
            isinstance(item, dict) and item.get("page") in output_pages
            for item in document.get("tables", [])
            if isinstance(document.get("tables"), list)
        ),
    }
    json_internal_consistency_score = pct(sum(internal_checks.values()), len(internal_checks))

    csv_json_consistency_score = 100.0
    if csv_rows:
        json_texts = Counter(normalise_text(req.get("text")) for req in top_requirements if isinstance(req, dict) and req.get("text"))
        csv_text_values = Counter()
        for row in csv_rows:
            text = row.get("text") or row.get("requirement") or row.get("Requirement") or row.get("Text")
            if text:
                csv_text_values[normalise_text(text)] += 1
        csv_json_consistency_score = f1_from_counters(json_texts, csv_text_values) if csv_text_values else 0.0

    if gold_document is not None:
        gold_requirements = gold_document.get("requirements", [])
        gold_requirements = gold_requirements if isinstance(gold_requirements, list) else []
        requirement_f1_score = f1_from_counters(requirement_counter(gold_requirements), requirement_counter(top_requirements))
        figure_caption_f1_score = f1_from_counters(
            Counter(normalise_text(item.get("caption")) for item in gold_document.get("figures", []) if isinstance(item, dict) and item.get("caption")),
            Counter(normalise_text(item.get("caption")) for item in document.get("figures", []) if isinstance(item, dict) and item.get("caption")),
        )
        table_caption_f1_score = f1_from_counters(
            Counter(normalise_text(item.get("caption")) for item in gold_document.get("tables", []) if isinstance(item, dict) and item.get("caption")),
            Counter(normalise_text(item.get("caption")) for item in document.get("tables", []) if isinstance(item, dict) and item.get("caption")),
        )
        component_scores = {
            "requirement_f1_score": requirement_f1_score,
            "figure_caption_f1_score": figure_caption_f1_score,
            "table_caption_f1_score": table_caption_f1_score,
            "page_text_fidelity_score": page_text_fidelity_score,
            "json_internal_consistency_score": json_internal_consistency_score,
        }
        formula = "mean(requirement_f1, figure_caption_f1, table_caption_f1, page_text_fidelity, json_internal_consistency)"
    else:
        component_scores = {
            "page_text_fidelity_score": page_text_fidelity_score,
            "requirement_traceability_score": requirement_traceability_score,
            "category_consistency_score": category_consistency_score,
            "page_number_accuracy_score": page_number_accuracy_score,
            "json_internal_consistency_score": json_internal_consistency_score,
            "csv_json_consistency_score": csv_json_consistency_score,
        }
        formula = "mean(page_text_fidelity, requirement_traceability, category_consistency, page_number_accuracy, json_internal_consistency, csv_json_consistency)"

    return Score(name="accuracy", percentage=mean(component_scores.values()), formula=formula, details=component_scores)


def score_table_figure_capture(document: dict[str, Any], pdf, pdf_page_texts_value: list[str], json_path: Path) -> Score:
    expected_tables_by_page = expected_table_counts(pdf)
    captured_tables_by_page = page_count_counter(document.get("tables", []) if isinstance(document.get("tables"), list) else [], "page")
    table_detection_f1_score = f1_from_counters(expected_tables_by_page, captured_tables_by_page)

    expected_table_caption_values = expected_captions(pdf_page_texts_value, TABLE_REGEX)
    captured_table_caption_values = captured_captions(document, "table_captions")
    table_caption_f1_score = f1_from_counters(expected_table_caption_values, captured_table_caption_values)

    table_records = document.get("tables", [])
    table_records = table_records if isinstance(table_records, list) else []
    existing_files = 0
    for table in table_records:
        if not isinstance(table, dict):
            continue
        csv_file = table.get("csv_file")
        if not csv_file:
            continue
        candidate = Path(csv_file)
        if not candidate.is_absolute():
            candidate = json_path.parent.parent / candidate
        if candidate.is_file():
            existing_files += 1
    table_file_empty_score = 100.0 if sum(expected_tables_by_page.values()) == 0 else 0.0
    table_file_existence_score = pct(existing_files, len(table_records), empty_is=table_file_empty_score)

    expected_figure_caption_values = expected_captions(pdf_page_texts_value, FIGURE_REGEX)
    captured_figure_caption_values = captured_captions(document, "figures")
    figure_caption_f1_score = f1_from_counters(expected_figure_caption_values, captured_figure_caption_values)

    expected_images_by_page = expected_image_counts(pdf)
    captured_images = []
    pages = document.get("pages", [])
    for page in pages if isinstance(pages, list) else []:
        captured_images.extend(page.get("images", []) if isinstance(page, dict) and isinstance(page.get("images"), list) else [])
    captured_images_by_page = page_count_counter(captured_images, "page")
    image_capture_f1_score = f1_from_counters(expected_images_by_page, captured_images_by_page)

    component_scores = {
        "table_detection_f1_score": table_detection_f1_score,
        "table_caption_f1_score": table_caption_f1_score,
        "table_file_existence_score": table_file_existence_score,
        "figure_caption_f1_score": figure_caption_f1_score,
        "image_capture_f1_score": image_capture_f1_score,
    }

    return Score(
        name="table_figure_capture",
        percentage=mean(component_scores.values()),
        formula="mean(table_detection_f1, table_caption_f1, table_file_existence, figure_caption_f1, image_capture_f1)",
        details=component_scores,
    )


def status(percentage: float, threshold: float) -> str:
    return "pass" if percentage >= threshold else "fail"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    json_path = Path(args.json).expanduser().resolve()
    document = load_json(json_path)

    pdf_path = Path(args.pdf).expanduser().resolve() if args.pdf else infer_pdf_path(json_path, document)
    pdf = open_pdf(pdf_path)
    source_page_texts = pdf_page_texts(pdf)

    csv_path = Path(args.csv).expanduser().resolve() if args.csv else None
    csv_rows = read_csv_rows(csv_path)

    gold_document = load_json(Path(args.gold_json).expanduser().resolve()) if args.gold_json else None

    scores = [
        score_completeness(document, source_page_texts, csv_rows, csv_path),
        score_accuracy(document, source_page_texts, csv_rows, gold_document),
        score_table_figure_capture(document, pdf, source_page_texts, json_path),
    ]

    score_report = {
        score.name: {
            "percentage": round(score.percentage, 2),
            "status": status(score.percentage, args.threshold),
            "formula": score.formula,
            "details": {key: round(value, 2) for key, value in score.details.items()},
        }
        for score in scores
    }
    overall_percentage = mean(score.percentage for score in scores)

    return {
        "inputs": {
            "json": str(json_path),
            "pdf": str(pdf_path) if pdf_path else None,
            "csv": str(csv_path) if csv_path else None,
            "gold_json": str(Path(args.gold_json).expanduser().resolve()) if args.gold_json else None,
            "threshold": args.threshold,
        },
        "scores": score_report,
        "overall_percentage": round(overall_percentage, 2),
        "overall_status": status(overall_percentage, args.threshold),
    }


def print_report(report: dict[str, Any]) -> None:
    print("Extractor Quality Check")
    print("=======================")
    print(f"JSON: {report['inputs']['json']}")
    print(f"PDF:  {report['inputs']['pdf'] or 'not supplied/found'}")
    if report["inputs"]["csv"]:
        print(f"CSV:  {report['inputs']['csv']}")
    if report["inputs"]["gold_json"]:
        print(f"Gold: {report['inputs']['gold_json']}")
    print()

    for name, score in report["scores"].items():
        print(f"{name}: {score['percentage']:.2f}% - {score['status']}")
        print(f"  formula: {score['formula']}")
        for detail_name, detail_value in score["details"].items():
            print(f"  {detail_name}: {detail_value:.2f}%")
        print()

    print(f"overall: {report['overall_percentage']:.2f}% - {report['overall_status']}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check extractor JSON/CSV output quality.")
    parser.add_argument("--json", required=True, help="Path to extractor document.json output.")
    parser.add_argument("--pdf", help="Path to the source PDF. If omitted, the checker tries to infer it.")
    parser.add_argument("--csv", help="Optional extractor CSV output to compare with JSON requirements.")
    parser.add_argument("--gold-json", help="Optional manually checked reference JSON for true accuracy/F1 scoring.")
    parser.add_argument("--threshold", type=float, default=95.0, help="Pass/fail threshold percentage. Default: 95.")
    parser.add_argument("--report-json", help="Optional path to write the quality report as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = build_report(args)
    print_report(report)

    if args.report_json:
        output_path = Path(args.report_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")

    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
