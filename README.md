#  Analog Devices & APRILAI Project

This repository is part of the **APRIL AI Hub Summer Internship Programme (AI for Productive Research & Innovation in Electronics)** and supports a research project funded by **Analog Devices**.

---

# :mag: Table of Contents

- [Overview](#overview)
- [Supported Specifications](#supported-specifications)
- [Repository Workflow](#repository-workflow)
- [Repository Modules](#repository-modules)
  - [Extractor](#extractor)
  - [Quality Checker](#quality-checker)
  - [Comparator](#comparator)
- [Quality Evaluation Metrics](#quality-evaluation-metrics)
  - [Completeness](#1-completeness)
  - [Accuracy](#2-accuracy)
  - [Table/Figure Capture](#3-tablefigure-capture)
- [Output Files](#output-files)
- [How to Run](#how-to-run)

---

# Overview

This project develops an AI-driven pipeline capable of:

- Extracting and parsing semiconductor specifications.
- Identifying and categorising inconsistencies and ambiguities between specification versions.
- Automatically generating a Verification Plan (vPlan).
- Identifying coverage gaps between a specification and its derived vPlan.

---

# :file_folder: Supported Specifications

Currently supported specification families include:

- **AMBA AXI Protocol Specification**
- **RISC-V Ratified ISA Specifications**

---

# Repository Workflow
    
  ```
                Specification PDF
                        │
                        ▼
                +----------------+
                |   Extractor    |
                +----------------+
                        │
                        ▼
                 document.json
                 tables/
                 figures/
                 images/
                 requirements.csv
                        │
                        ├──────────────► Comparator
                        │                   │
                        │                   ▼
                        │            Change Report
                        │
                        ▼
                 Quality Checker
                        │
                        ▼
                Quality Metrics
                 (Completeness,
                    Accuracy,
              Table/Figure Capture)
```

---

# Repository Modules

| Module | Input | Output | Purpose |
|--------|-------|--------|---------|
| **Extractor** | Specification PDF | `document.json`, figures, tables, images, CSV | Parses & structures specification content. |
| **Quality Checker** | Specification PDF, Extraction output, (Optional) Gold JSON | JSON, CSV, Markdown reports | Evaluates extraction quality using completeness, accuracy, and table/figure capture metrics. |
| **Comparator** | 2 Extracted Versions of Specification JSON | JSON, CSV, Markdown reports | Detects added, removed, and modified content between specification versions. |

---



## :page_facing_up: Task 1: Extractor

The Extractor is responsible for converting specification PDFs into a structured representation.

---

###  Core Responsibilities

* **Data Ingestion:** Accepts technical specification documents such as AMBA AXI or RISC-V ISA files .
* **Content Extraction:** Extracts text layers, structural tables, layout markers, and embedded graphics .
* **Data Encoding:** Automatically maps and organizes all parsed elements into a single, unified `document.json` file .
* **Asset Isolation:** Segregates data types to produce separate outputs for images, cropped figures, and tabular CSV files.

---

###  Key Features

#### 1. Figure Isolation & Asset Generation
* **AI-Guided Cropping:** Locates figure captions and uses a vision model to verify whether the corresponding figure lives above or below the caption.
* **Vector Snapping:** Refines bounding boxes by aligning them with the PDF's internal vector paths and lines, striving for minimal figure cut offs.
* **Smart Descriptions:** Contextualizes every extracted diagram via GPT-4, generating clear, accessible summaries detailing waveforms, registers, and block relationships.

#### 2. Native Text & Automated Rule Classifier
* **Label Capture:** Extracts text directly from figure boundaries using the PDF's vector layer, keeping signal names, bus tags, and axis markers perfectly readable without relying on standard OCR.
* **Requirement Classification:** Scans text for mandatory project constraints (phrases using *shall*, *must*, or *should*) and automatically sorts them into functional buckets like *Security, Performance, Protocol,* or *Memory*.

#### 3. Structural Hierarchy & Table Extraction
* **Table-to-CSV Conversion:** Programmatically discovers tables embedded within the pages and exports them as individual, clean CSV spreadsheets.
* **Document Mapping:** Automatically cross-references acronyms, design notes, and systemic citations while cleanly dividing the document into a logical parent-child section tree based on structural headings.
---



## :bar_chart: Task 2: Quality Checker

The Quality Checker evaluates the quality of an extracted specification.

### Inputs

- Specification PDF
- Extracted JSON
- Optional CSV outputs
- Optional **Gold JSON** reference

> **Gold JSON** is a manually verified reference extraction used as ground truth for evaluating extraction quality using direct F1-based comparisons.

### Outputs

Quality reports in:

- JSON
- CSV
- Markdown

---

# Quality Evaluation Metrics

The extraction quality is evaluated across three independent dimensions:

- **Completeness**
- **Accuracy**
- **Table/Figure Capture**

---

# 1. Completeness

Measures whether the extractor captured all expected content from the source document.

## Checks

| Metric | Description |
|---------|-------------|
| **Required JSON Field Score** | All expected top-level keys (sections, requirements, figures, tables, etc.) are present. |
| **Page Coverage Score** | Number of extracted pages matches the source document. |
| **Text Coverage Score** | Extracted text length closely matches the source PDF text (character count). |
| **Semantic Chunk Coverage Score** | Number of semantic chunks is consistent with the document/page structure. |
| **Record Field Completeness Score** | Required fields for every extracted object are populated (e.g. `text`, `caption`, `page`). |
| **CSV Presence Score** | If CSV output is expected, CSV files exist and are non-empty. |

## Completeness Function

```text
completeness = mean(
    required_json_field_score,
    page_coverage_score,
    text_coverage_score,
    semantic_chunk_coverage_score,
    record_field_completeness_score,
    csv_presence_score
)
```

---

# 2. Accuracy

Measures whether the extracted information is correct.

## Without a Gold JSON

When no reference extraction is available, accuracy is estimated using heuristic validation.

### Checks

| Metric | Description |
|---------|-------------|
| **Page Text Fidelity Score** | Extracted text closely matches the raw PDF text. |
| **Requirement Traceability Score** | Every extracted requirement can be located in the source PDF. |
| **Category Consistency Score** | Automatically classified requirement categories agree with extracted categories. |
| **Page Number Accuracy Score** | Page numbers are valid and correctly assigned. |
| **JSON Internal Consistency Score** | Cross-checks internal references between requirements, pages, captions, tables, and figures. |
| **CSV/JSON Consistency Score** | CSV output matches the extracted JSON. |

### Accuracy Function

```text
accuracy = mean(
    page_text_fidelity_score,
    requirement_traceability_score,
    category_consistency_score,
    page_number_accuracy_score,
    json_internal_consistency_score,
    csv_json_consistency_score
)
```

---

## With a Gold JSON

When a reference extraction is supplied (`--gold-json`), direct comparisons replace heuristic validation.

### Checks

| Metric | Description |
|---------|-------------|
| **Requirement F1 Score** | Precision, recall, and F1 of extracted requirements against the reference. |
| **Figure Caption F1 Score** | Accuracy of extracted figure captions. |
| **Table Caption F1 Score** | Accuracy of extracted table captions. |
| **Page Text Fidelity Score** | Comparison between extracted page text and the reference page text. |
| **JSON Internal Consistency Score** | Structural validation of the extracted JSON. |

---

## Understanding the $F_1$ Score

The **$F_1$ Score** is a single metric used to evaluate how well a classification model performs.

The $F_1$ score measures the balance between two goals:
* **Precision:** Making sure your positive predictions are highly accurate (avoiding false alarms).
* **Recall:** Making sure you actually find *all* the real positive cases (avoiding missed targets).


### Formula for F1

The $F_1$ score is the mean of Precision and Recall:

$$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

$$\text{Precision} = \frac{\text{True Positives}}{\text{Total Captured Items}}$$

$$\text{Recall} = \frac{\text{True Positives}}{\text{Total Expected Items}}$$

$$\text{True Positives} = \sum_{k \in K} \min(\text{Expected}_{k}, \text{Captured}_{k})$$
$${\text{Expected = PyMuPDF Capturing}}$$
$${\text{Captured = Actual Output from Extraction}}$$

---

### GOLD JSON Function

```text
accuracy = mean(
    requirement_f1_score,
    figure_caption_f1_score,
    table_caption_f1_score,
    page_text_fidelity_score,
    json_internal_consistency_score
)
```

---

# 3. Table/Figure Capture

Measures how well tables and figures are detected, captioned, and exported.

## Checks

| Metric | Description |
|---------|-------------|
| **Table Detection F1 Score** | Extracted table count compared against PyMuPDF table detection. |
| **Table Caption F1 Score** | Extracted table captions compared against captions detected in the PDF. |
| **Table File Existence Score** | Expected CSV/table files exist and are non-empty. |
| **Figure Caption F1 Score** | Extracted figure captions compared against captions detected in the PDF. |
| **Image Capture F1 Score** | Extracted image count compared against embedded images detected by PyMuPDF. |

## Table/Figure Capture Function

```text
table_figure_capture = mean(
    table_detection_f1_score,
    table_caption_f1_score,
    table_file_existence_score,
    figure_caption_f1_score,
    image_capture_f1_score
)
```

---

# Overall Evaluation

The evaluation framework reports three independent quality scores.

| Score | Measures |
|--------|----------|
| **Completeness** | Whether all expected document content was extracted. |
| **Accuracy** | Whether the extracted content is correct and internally consistent. |
| **Table/Figure Capture** | Whether tables, figures, captions, and exported files were correctly captured. |

When a **Gold JSON** is supplied, the accuracy metric switches from heuristic validation to direct reference-based evaluation using F1 scores while retaining structural consistency checks.

---



## :chart_with_upwards_trend: :chart_with_downwards_trend: Task 3: Comparator

The Comparator analyzes two extracted specification versions side-by-side to identify evolutionary changes, wording modifications, and structural updates.

### 📋 Core Responsibilities

#### 1. Identity & Cross-Version Matching
* **Unique Tracking:** Builds a unique identifier for every extracted item.
* **Position-Independent Matching:** Matches equivalent content across versions, even when document positions or page numbers change.

#### 2. Change Detection & Similarity Analysis
* **Mutation Detection:** Detects added, removed, and modified content between the specification versions.
* **Reasoning Inference:** Attempts to infer likely reasons for detected modifications.
* **Page Similarity Calculation:** Calculates similarity percentages between corresponding pages using an old-to-new text ratio:
  
  $$\text{similarity} = \frac{2 \times (\text{number of matching characters})}{\text{total characters in both strings combined}}$$

* **Change Categorization Rules:** Based on the calculated similarity score, changes are categorized using the following logic:
  * **`≥ 0.90`** → `"minor_wording_change"`  
  * **`≥ 0.65`** → `"substantive_wording_change"`
  * **Below that** → Falls back to `"content_change"` *(unless numbers, requirement words, or references changed first, which are checked before similarity and take priority)*
---

# Output Files

```text
Extractor
├── document.json
├── requirements.csv
├── figures/
├── tables/
└── images/

Quality Checker
├── report.json
├── report.csv
└── report.md

Comparator
├── comparison.json
├── comparison.csv
└── comparison.md
```

---

# How to Run

## Extractor

```bash
python extractor.py --input data/input.json
```

## Comparator

```bash
python Spec_Version_Comparer.py VER_1_specification.json VER_2_specification.json
```

## Quality Checker

```bash
python extractor_quality_check.py \
    --json data/document.json \
    --pdf docs/spec.pdf
```

### Additional Quality Checker Options

```bash
--csv path/to/requirements.csv
--gold-json path/to/gold_reference.json
--threshold 90
--report-json path/to/output_report.json
```
