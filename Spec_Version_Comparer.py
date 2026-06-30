"""
Engineering specification version comparator.

This script is designed to compare two JSON files created by:
Extractor(JSON UPDATED).py

It reports minimal, specific differences between versions and writes:
  - version_differences.csv
  - version_differences.json
  - version_differences.md

  Structure of Output:
 figures
 images
 pages
 tables
    document2.json
    document_name 
    metadata 
    total_pages 
    sections 
    requirements 
    pages 
    -raw page text
    -headings found on that page
    -requirements extracted from that page
    -figures, tables, images 
    notes, figures, tables, acronyms 






Example:
python3 SpecificationVersionComparator.py \
    old_output/document.json \
    new_output/document.json


python3 Spec_Version_Comparer.py /home/eng-6990/PROJECT/extractor/RISC-V_VER.1.json /home/eng-6990/PROJECT/extractor/RISC-V_VER.2.json


FILE_PATH = r"/home/eng-6990/PROJECT/RISC-V_VER.2"



RVB23 Profile Oct. 2024
RISC-V Profiles April 2023

"""

import argparse
import csv
import difflib
import hashlib
import json
import os
import re
from datetime import datetime


# ==========================================================
# CONFIGURATION
# ==========================================================

OUTPUT_DIR = "comparison_output"

DEFAULT_CSV_NAME = "version_differences.csv"
DEFAULT_JSON_NAME = "version_differences.json"
DEFAULT_MD_NAME   = "version_differences.md"

NUMBER_REGEX = re.compile(
    r"[-+]?\d+(?:\.\d+)?(?:\s*(?:%|v|a|hz|khz|mhz|ghz|ms|us|ns|s|kb|mb|gb|bit|bits|byte|bytes))?",
    re.IGNORECASE,
)

REFERENCE_REGEX = re.compile(
    r"\b(?:section|figure|fig\.?|table)\s+[A-Za-z]?\d+(?:[-.]\d+)*",
    re.IGNORECASE,
)

REQUIREMENT_WORD_REGEX = re.compile(
    r"\b(shall|must|will|should|required to|may not|is prohibited|may|can)\b",
    re.IGNORECASE,
)


# ==========================================================
# FILE HELPERS
# ==========================================================

def resolve_document_json(path):

    if os.path.isdir(path):
        candidate = os.path.join(path, "document.json")

        if os.path.exists(candidate):
            return candidate

    return path


def load_json(path):

    resolved_path = resolve_document_json(path)

    with open(
        resolved_path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f), resolved_path


def ensure_output_dir(path):

    os.makedirs(path, exist_ok=True)


# ==========================================================
# NORMALISATION
# ==========================================================

def clean_text(value):

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def stable_hash(value):

    normalised = clean_text(value).lower()

    return hashlib.sha1(
        normalised.encode("utf-8")
    ).hexdigest()[:12]


def similarity(old_value, new_value):

    return round(
        difflib.SequenceMatcher(
            None,
            clean_text(old_value).lower(),
            clean_text(new_value).lower()
        ).ratio(),
        4
    )


def first_changed_phrase(old_value, new_value):

    old_words = clean_text(old_value).split()
    new_words = clean_text(new_value).split()

    matcher = difflib.SequenceMatcher(
        None,
        old_words,
        new_words
    )

    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():

        if tag == "equal":
            continue

        old_phrase = " ".join(
            old_words[old_start:old_end]
        )

        new_phrase = " ".join(
            new_words[new_start:new_end]
        )

        return old_phrase, new_phrase

    return "", ""


def extract_numbers(text):

    return [
        clean_text(match.group(0)).lower()
        for match in NUMBER_REGEX.finditer(clean_text(text))
    ]


def extract_requirement_words(text):

    return [
        match.group(1).lower()
        for match in REQUIREMENT_WORD_REGEX.finditer(clean_text(text))
    ]


def extract_references(text):

    return [
        clean_text(match.group(0)).lower()
        for match in REFERENCE_REGEX.finditer(clean_text(text))
    ]


# ==========================================================
# DIFFERENCE CLASSIFICATION
# ==========================================================

def classify_modified_text(old_value, new_value):

    old_numbers = extract_numbers(old_value)
    new_numbers = extract_numbers(new_value)

    if old_numbers != new_numbers:
        return "numeric_value_change"

    old_requirement_words = extract_requirement_words(old_value)
    new_requirement_words = extract_requirement_words(new_value)

    if old_requirement_words != new_requirement_words:
        return "requirement_strength_change"

    old_references = extract_references(old_value)
    new_references = extract_references(new_value)

    if old_references != new_references:
        return "cross_reference_change"

    old_text = clean_text(old_value).lower()
    new_text = clean_text(new_value).lower()

    if old_text and new_text:
        score = similarity(old_text, new_text)

        if score >= 0.90:
            return "minor_wording_change"

        if score >= 0.65:
            return "substantive_wording_change"

    return "content_change"


def make_change(
    change_id,
    area,
    change_type,
    difference_category,
    identifier,
    old_value,
    new_value,
    section=None,
    page=None,
    detail=None,
):

    if detail is None:
        old_phrase, new_phrase = first_changed_phrase(
            old_value,
            new_value
        )

        if old_phrase or new_phrase:
            detail = (
                f"Changed '{old_phrase}' to '{new_phrase}'"
            )
        else:
            detail = change_type.replace("_", " ")

    return {
        "change_id": change_id,
        "area": area,
        "change_type": change_type,
        "difference_category": difference_category,
        "identifier": identifier,
        "section": section,
        "page": page,
        "old_value": clean_text(old_value),
        "new_value": clean_text(new_value),
        "detail": detail,
        "similarity": similarity(old_value, new_value),
    }


# ==========================================================
# INDEXING
# ==========================================================

def requirement_key(requirement, fallback_index):

    req_id = clean_text(requirement.get("id"))

    if req_id:
        return req_id

    section = clean_text(requirement.get("section")) or "no_section"
    text_hash = stable_hash(requirement.get("text"))

    return f"{section}:{text_hash}:{fallback_index}"


def indexed_items(items, key_function):

    indexed = {}

    for index, item in enumerate(items or [], start=1):
        key = key_function(item, index)
        indexed[key] = item

    return indexed


def simple_text_key(field_name):

    def key_function(item, fallback_index):
        text_hash = stable_hash(item.get(field_name))
        return f"{text_hash}:{fallback_index}"

    return key_function


def section_key(section, fallback_index):

    section_id = clean_text(section.get("id"))

    if section_id:
        return section_id

    return f"title:{stable_hash(section.get('title'))}:{fallback_index}"


def page_key(page, fallback_index):

    number = page.get("page_number")

    if number is not None:
        return str(number)

    return str(fallback_index)


def table_key(table, fallback_index):

    csv_file = clean_text(table.get("csv_file"))

    if csv_file:
        return csv_file

    page = clean_text(table.get("page"))

    return f"page_{page}:table_{fallback_index}"


def metadata_items(metadata):

    return {
        key: clean_text(value)
        for key, value in (metadata or {}).items()
    }


# ==========================================================
# COMPARISON
# ==========================================================

def compare_indexed_area(
    old_index,
    new_index,
    area,
    text_field,
    changes,
    id_prefix,
):

    all_keys = sorted(
        set(old_index.keys()) | set(new_index.keys())
    )

    for key in all_keys:

        old_item = old_index.get(key)
        new_item = new_index.get(key)
        change_id = f"{id_prefix}-{len(changes)+1:04}"

        if old_item is None:
            changes.append(
                make_change(
                    change_id,
                    area,
                    "added",
                    f"{area}_added",
                    key,
                    "",
                    new_item.get(text_field),
                    section=new_item.get("section"),
                    page=new_item.get("page") or new_item.get("page_number"),
                    detail=f"Added {area}"
                )
            )
            continue

        if new_item is None:
            changes.append(
                make_change(
                    change_id,
                    area,
                    "removed",
                    f"{area}_removed",
                    key,
                    old_item.get(text_field),
                    "",
                    section=old_item.get("section"),
                    page=old_item.get("page") or old_item.get("page_number"),
                    detail=f"Removed {area}"
                )
            )
            continue

        old_value = old_item.get(text_field)
        new_value = new_item.get(text_field)

        if clean_text(old_value) != clean_text(new_value):
            changes.append(
                make_change(
                    change_id,
                    area,
                    "modified",
                    classify_modified_text(old_value, new_value),
                    key,
                    old_value,
                    new_value,
                    section=new_item.get("section") or old_item.get("section"),
                    page=(
                        new_item.get("page")
                        or old_item.get("page")
                        or new_item.get("page_number")
                        or old_item.get("page_number")
                    ),
                )
            )


def compare_sections(old_document, new_document, changes):

    old_sections = indexed_items(
        old_document.get("sections"),
        section_key
    )

    new_sections = indexed_items(
        new_document.get("sections"),
        section_key
    )

    all_keys = sorted(
        set(old_sections.keys()) | set(new_sections.keys())
    )

    for key in all_keys:

        old_section = old_sections.get(key)
        new_section = new_sections.get(key)
        change_id = f"CHG-{len(changes)+1:04}"

        if old_section is None:
            changes.append(
                make_change(
                    change_id,
                    "section",
                    "added",
                    "section_added",
                    key,
                    "",
                    new_section.get("title"),
                    section=key,
                    detail="Added section"
                )
            )
            continue

        if new_section is None:
            changes.append(
                make_change(
                    change_id,
                    "section",
                    "removed",
                    "section_removed",
                    key,
                    old_section.get("title"),
                    "",
                    section=key,
                    detail="Removed section"
                )
            )
            continue

        if clean_text(old_section.get("title")) != clean_text(new_section.get("title")):
            changes.append(
                make_change(
                    change_id,
                    "section",
                    "modified",
                    classify_modified_text(
                        old_section.get("title"),
                        new_section.get("title")
                    ),
                    key,
                    old_section.get("title"),
                    new_section.get("title"),
                    section=key,
                )
            )


def compare_metadata(old_document, new_document, changes):

    old_metadata = metadata_items(
        old_document.get("metadata")
    )

    new_metadata = metadata_items(
        new_document.get("metadata")
    )

    all_keys = sorted(
        set(old_metadata.keys()) | set(new_metadata.keys())
    )

    for key in all_keys:

        old_value = old_metadata.get(key, "")
        new_value = new_metadata.get(key, "")

        if old_value == new_value:
            continue

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "metadata",
                "modified",
                "metadata_change",
                key,
                old_value,
                new_value,
                detail=f"Metadata field changed: {key}"
            )
        )


def compare_acronyms(old_document, new_document, changes):

    old_acronyms = set(
        clean_text(value)
        for value in old_document.get("acronyms", [])
    )

    new_acronyms = set(
        clean_text(value)
        for value in new_document.get("acronyms", [])
    )

    for acronym in sorted(new_acronyms - old_acronyms):
        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "acronym",
                "added",
                "acronym_added",
                acronym,
                "",
                acronym,
                detail="Added acronym"
            )
        )

    for acronym in sorted(old_acronyms - new_acronyms):
        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "acronym",
                "removed",
                "acronym_removed",
                acronym,
                acronym,
                "",
                detail="Removed acronym"
            )
        )


def compare_page_text(old_document, new_document, changes):

    old_pages = indexed_items(
        old_document.get("pages"),
        page_key
    )

    new_pages = indexed_items(
        new_document.get("pages"),
        page_key
    )

    all_keys = sorted(
        set(old_pages.keys()) | set(new_pages.keys()),
        key=lambda value: int(value) if value.isdigit() else value
    )

    for key in all_keys:

        old_page = old_pages.get(key)
        new_page = new_pages.get(key)

        if old_page is None:
            changes.append(
                make_change(
                    f"CHG-{len(changes)+1:04}",
                    "page",
                    "added",
                    "page_added",
                    key,
                    "",
                    new_page.get("text"),
                    page=key,
                    detail="Added page text"
                )
            )
            continue

        if new_page is None:
            changes.append(
                make_change(
                    f"CHG-{len(changes)+1:04}",
                    "page",
                    "removed",
                    "page_removed",
                    key,
                    old_page.get("text"),
                    "",
                    page=key,
                    detail="Removed page text"
                )
            )
            continue

        old_text = old_page.get("text")
        new_text = new_page.get("text")

        if clean_text(old_text) == clean_text(new_text):
            continue

        old_phrase, new_phrase = first_changed_phrase(
            old_text,
            new_text
        )

        changes.append(
            make_change(
                f"CHG-{len(changes)+1:04}",
                "page",
                "modified",
                classify_modified_text(old_text, new_text),
                key,
                old_phrase,
                new_phrase,
                page=key,
                detail="First changed phrase on page"
            )
        )


def compare_documents(old_document, new_document):

    changes = []

    compare_metadata(
        old_document,
        new_document,
        changes
    )

    compare_sections(
        old_document,
        new_document,
        changes
    )

    compare_indexed_area(
        indexed_items(
            old_document.get("requirements"),
            requirement_key
        ),
        indexed_items(
            new_document.get("requirements"),
            requirement_key
        ),
        "requirement",
        "text",
        changes,
        "CHG"
    )

    compare_indexed_area(
        indexed_items(
            old_document.get("notes"),
            simple_text_key("text")
        ),
        indexed_items(
            new_document.get("notes"),
            simple_text_key("text")
        ),
        "note",
        "text",
        changes,
        "CHG"
    )

    compare_indexed_area(
        indexed_items(
            old_document.get("figures"),
            simple_text_key("caption")
        ),
        indexed_items(
            new_document.get("figures"),
            simple_text_key("caption")
        ),
        "figure",
        "caption",
        changes,
        "CHG"
    )

    compare_indexed_area(
        indexed_items(
            old_document.get("tables"),
            table_key
        ),
        indexed_items(
            new_document.get("tables"),
            table_key
        ),
        "table",
        "csv_file",
        changes,
        "CHG"
    )

    compare_acronyms(
        old_document,
        new_document,
        changes
    )

    compare_page_text(
        old_document,
        new_document,
        changes
    )

    return changes


# ==========================================================
# OUTPUT
# ==========================================================

def write_csv(changes, csv_path):

    fieldnames = [
        "change_id",
        "area",
        "change_type",
        "difference_category",
        "identifier",
        "section",
        "page",
        "old_value",
        "new_value",
        "detail",
        "similarity",
    ]

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(changes)


def write_json_report(
    changes,
    json_path,
    old_path,
    new_path,
    old_document,
    new_document
):

    report = {
        "comparison_created": datetime.now().isoformat(timespec="seconds"),
        "old_document": {
            "path": old_path,
            "document_name": old_document.get("document_name"),
            "total_pages": old_document.get("total_pages"),
        },
        "new_document": {
            "path": new_path,
            "document_name": new_document.get("document_name"),
            "total_pages": new_document.get("total_pages"),
        },
        "summary": summarise_changes(changes),
        "changes": changes,
    }

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False
        )

def write_markdown_report(
    changes,
    md_path,
    old_path,
    new_path,
    old_document,
    new_document
):

    summary = summarise_changes(changes)
    now = datetime.now().isoformat(timespec="seconds")

    lines = []

    lines.append("# Specification Version Comparison Report\n")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Old document:** `{old_path}` — {old_document.get('document_name', 'unknown')} ({old_document.get('total_pages', '?')} pages)  ")
    lines.append(f"**New document:** `{new_path}` — {new_document.get('document_name', 'unknown')} ({new_document.get('total_pages', '?')} pages)\n")

    lines.append("---\n")
    lines.append("## Summary\n")
    lines.append(f"**Total changes:** {summary['total_changes']}\n")

    for summary_section, label in [
        ("by_area", "By Area"),
        ("by_change_type", "By Change Type"),
        ("by_difference_category", "By Difference Category"),
    ]:
        lines.append(f"### {label}\n")
        lines.append("| Category | Count |")
        lines.append("|---|---|")
        for key, count in sorted(summary[summary_section].items()):
            lines.append(f"| {key} | {count} |")
        lines.append("")

    lines.append("---\n")
    lines.append("## Changes\n")

    grouped = {}
    for change in changes:
        grouped.setdefault(change["area"], []).append(change)

    for area in sorted(grouped.keys()):
        lines.append(f"### {area.title()}\n")
        lines.append("| ID | Type | Category | Identifier | Section | Page | Detail | Similarity |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for c in grouped[area]:
            lines.append(
                f"| {c['change_id']} | {c['change_type']} | {c['difference_category']} "
                f"| {c['identifier']} | {c.get('section') or ''} | {c.get('page') or ''} "
                f"| {c['detail']} | {c['similarity']} |"
            )
        lines.append("")
        for c in grouped[area]:
            if c["old_value"] or c["new_value"]:
                lines.append(f"#### {c['change_id']} — {c['detail']}")
                if c["old_value"]:
                    lines.append(f"- **Old:** {c['old_value']}")
                if c["new_value"]:
                    lines.append(f"- **New:** {c['new_value']}")
                lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def summarise_changes(changes):

    summary = {
        "total_changes": len(changes),
        "by_area": {},
        "by_change_type": {},
        "by_difference_category": {},
    }

    for change in changes:

        for summary_key, change_key in [
            ("by_area", "area"),
            ("by_change_type", "change_type"),
            ("by_difference_category", "difference_category"),
        ]:
            value = change.get(change_key)
            summary[summary_key][value] = (
                summary[summary_key].get(value, 0) + 1
            )

    return summary


# ==========================================================
# RUN
# ==========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Compare two engineering specification JSON files "
            "created by Extractor(JSON UPDATED).py"
        )
    )

    parser.add_argument(
        "old_json",
        help="Path to the old document.json file, or a folder containing document.json"
    )

    parser.add_argument(
        "new_json",
        help="Path to the new document.json file, or a folder containing document.json"
    )

    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help="Folder where the CSV and JSON comparison reports will be written"
    )

    parser.add_argument(
        "--csv-name",
        default=DEFAULT_CSV_NAME,
        help="Name of the CSV output file"
    )

    parser.add_argument(
        "--json-name",
        default=DEFAULT_JSON_NAME,
        help="Name of the JSON output file"
    )

    parser.add_argument(
        "--md-name",
        default=DEFAULT_MD_NAME,
        help="Name of the Markdown output file"
    )

    args = parser.parse_args()

    ensure_output_dir(args.output_dir)

    old_document, old_path = load_json(args.old_json)
    new_document, new_path = load_json(args.new_json)

    changes = compare_documents(
        old_document,
        new_document
    )

    csv_path = os.path.join(
        args.output_dir,
        args.csv_name
    )

    json_path = os.path.join(
        args.output_dir,
        args.json_name
    )

    md_path = os.path.join(
        args.output_dir,
        args.md_name
    )

    write_csv(
        changes,
        csv_path
    )

    write_json_report(
            changes,
            json_path,
            old_path,
            new_path,
            old_document,
            new_document
        )

    write_markdown_report(
        changes,
        md_path,
        old_path,
        new_path,
        old_document,
        new_document
    )

    print("\n===================================")
    print("VERSION COMPARISON COMPLETE")
    print("===================================")
    print("Old JSON:", old_path)
    print("New JSON:", new_path)
    print("Total changes:", len(changes))
    print("CSV:", csv_path)
    print("JSON:", json_path)
    print("Markdown:", md_path)


if __name__ == "__main__":

    main()
