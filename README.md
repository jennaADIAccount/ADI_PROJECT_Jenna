#  Analog Devices & APRILAI Project

This repository contains an AI-driven pipeline for extracting, comparing, and evaluating engineering specification documents. It is part of the **APRIL AI Hub Summer Internship Programme (AI for Productive Research & Innovation in Electronics)** and supports a research project funded by **Analog Devices**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Supported Specifications](#supported-specifications)
- [Pipeline Workflow](#pipeline-workflow)
- [Module Details](#module-details)
  - [Extractor](#Extractor)
  - [Comparator](#Comparator)
  - [Quality Checker](#Quality-Checker)
- [Output Files](#output-files)
- [Usage](#usage)

---

## Overview

This project develops an **AI-driven pipeline** capable of:

- **Extracting** and parsing semiconductor specifications from PDFs
- **Structuring** specifications into machine-readable JSON with metadata, sections, requirements, figures, and tables
- **Comparing** specification versions to identify evolutionary changes, wording modifications, and structural updates
- **Evaluating** extraction quality across completeness, accuracy, and figure/table capture dimensions
- **Generating** verification plans and identifying coverage gaps

---

## Repository Structure

```
├── Extractor.py              # PDF parsing & structured data extraction
├── Comparator.py             # Version comparison & change detection
├── Quality_Check.py          # Extraction quality evaluation
├── UI_File.py                # User interface (UI)
└── README.md                 # This file
```

**Output Directories:**
- `{SPEC_NAME}_OUTPUT/` - Extractor outputs
  - `document.json` - Structured specification data
  - `figures/` - Isolated figures and diagrams
  - `tables/` - CSV files for tables
  - `images/` - Embedded images

- `comparison_output/` - Comparator outputs
  - `version_differences.json` - Detailed change report
  - `version_differences.csv`
  - `version_differences.md` 

---
## Repository Workflow
    
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

## Supported Specifications

Currently tested with:

- **AMBA AXI Protocol Specification**
- **RISC-V ISA Specifications**

---

## Module Details

## 🔍 Extractor

**Purpose:** Converts specification PDFs into structured JSON with extracted content and metadata.

**Input:** 
- Technical specification PDF (AMBA AXI, RISC-V ISA, etc.)

**Output:**
- `document.json` - Complete structured document
- `figures/` - Isolated figures with descriptions
- `tables/` - CSV files extracted from tables
- `images/` - Embedded images with accessibility descriptions

**Key Capabilities:**

| Feature | Description |
|---------|-------------|
| **Text Extraction** | Extracts text layers, structural elements, and layout markers from PDFs |
| **Figure Isolation** | Detects figure captions and crops figures with refined bounding boxes; generates AI-powered accessibility descriptions (*Figure extraction is an unstable function due to the vision model*) |
| **Table Extraction** | Discovers and exports tables as clean CSV spreadsheets |
| **Requirement Classification** | Identifies mandatory constraints (shall, must, should) and categorizes by type (Performance, Security, Protocol, etc.) |
| **Acronym Extraction** | Identifies and lists technical acronyms and abbreviations |
| **Section Hierarchy** | Builds logical document structure with parent-child section relationships |
| **Semantic Chunking** | Groups content by section and page for better organization |
| **Metadata Capture** | Extracts PDF metadata (title, author, creation date, etc.) |

**Technical Details:**
- Uses **PyMuPDF (fitz)** for PDF parsing and native text extraction
- Uses **OpenAI GPT-4** for vision-based figure descriptions and accessibility text
- Applies **regex patterns** for requirement and acronym detection
---

## 📊 Comparator

**Purpose:** Analyzes two specification versions to identify and categorize changes.

**Input:**
- Two `document.json` files (old and new versions)

**Output:**
- `JSON`
- `CSV`
- `MD`

**Change Detection:**

The Comparator identifies and categorizes changes using:
- **Numeric value changes** - Changes in numbers, percentages, frequencies, etc.
- **Requirement strength changes** - Modifications to mandatory language (shall → must)
- **Cross-reference changes** - Section/figure/table references changed
- **Wording changes** - Minor (≥90% similar) or substantive (≥65% similar)
- **Content changes** - Major structural or content modifications

**Change Classification:**
- ✅ **Added** - New items in the new version
- ❌ **Removed** - Items no longer in the new version
- ✏️ **Modified** - Items changed between versions

---

## ✅ Quality Checker

**Purpose:** Evaluates the quality of extracted specifications across three dimensions.

**Input:**
- `document.json` (extracted specification)
- `spec.pdf` (source PDF)
- `gold_reference.json` (optional - manually verified reference)

**Output:**
- Quality report (JSON, CSV, Markdown)
- Three quality scores with pass/fail status

---

## **Quality Metrics:**

| Metric | Measures |
|--------|----------|
| **Completeness** | Whether all expected document content was extracted |
| **Accuracy** | Whether extracted content is correct and internally consistent; uses F1 scoring if Gold Reference inputted|
| **Table/Figure Capture** | Whether tables, figures, and embedded images were correctly detected and exported |

**Completeness Checks:**
- Required JSON fields present
- Page count accuracy
- Text coverage (character count)
- Record field completeness

**Accuracy Checks (without Gold Reference):**
- Page text fidelity (Raw Text vs. Extracted Text)
- Requirement traceability
- Category consistency
- Page number accuracy
- JSON internal consistency

**Accuracy Checks (with Gold Reference):**
- Requirement F1 score
- Figure caption F1 score
- Table caption F1 score
- Page text fidelity (Raw Text vs. Extracted Text)
- JSON internal consistency

**Table/Figure Capture Checks:**
- Table detection F1 score (vs. PyMuPDF)
- Table caption accuracy
- Table file existence
- Figure caption accuracy
- Image capture F1 score

---

## Quality Metrics Formula

---

### Completeness

```text
= mean(required_json_fields, page_coverage, text_coverage,
       record_field_completeness, semantic_chunk_coverage)
```

### Metric Breakdown

| **Metric**                    | **Calculation / Check**                                                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Required JSON Fields**      | Checks that all required top-level keys exist in the JSON. **Calculation:** Number of required fields found ÷ 12 × 100 |
| **Page Coverage**             | Number of pages in JSON ÷ Number of pages in PDF × 100                                                                 |
| **Text Coverage**             | Characters extracted ÷ Characters in the original PDF × 100                                                            |
| **Semantic Chunk Coverage**   | Number of pages covered by chunks ÷ Total PDF pages × 100                                                              |
| **Record Field Completeness** | Checks that required fields are populated. **Calculation:** Filled required fields ÷ Total required fields × 100       |
               

### Required JSON Fields

| Required field     | Purpose                                      |
| ------------------ | -------------------------------------------- |
| `document_name`    | Name of the source document                  |
| `metadata`         | Document metadata (author, title, etc.)      |
| `total_pages`      | Total number of pages                        |
| `sections`         | Document section hierarchy                   |
| `requirements`     | All extracted requirements                   |
| `figures`          | All extracted figures                        |
| `tables`           | All extracted tables                         |
| `notes`            | Notes extracted from the document            |
| `acronyms`         | List of acronyms and meanings                |
| `cross_references` | Internal references (e.g. "see Section 3.2") |
| `semantic_chunks`  | Semantic chunks used for retrieval/search    |
| `pages`            | Per-page extracted content                   |

### Record Field Completeness

| Record Type      | Required Fields    |
| ---------------- | ------------------ |
| **Requirements** | `text`, `category` |
| **Figures**      | `caption`          |
| **Tables**       | `page`, `csv_file` |

### Final Score

Average of all **6** metrics.

---

### Accuracy (Without Gold Reference)

```text
= mean(page_text_fidelity, requirement_traceability,
       category_consistency, page_number_accuracy,
       json_internal_consistency)
```

### Metric Breakdown

| **Metric**                    | **Calculation / Check**                                                                                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Page Text Fidelity**        | Similarity % of every page, then average of all page similarity percentages.                                                                                   |
| **Requirement Traceability**  | Requirements found in PDF ÷ Total extracted requirements × 100                                                                                                 |
| **Category Consistency**      | Does the assigned category match the requirement text? The script guesses a category using keywords. **Calculation:** Correct categories ÷ Total checked × 100 |
| **Page Number Accuracy**      | Correct page numbers ÷ Total pages × 100                                                                                                                       |
| **JSON Internal Consistency** | Performs three internal consistency checks (see below). **Calculation:** Passed checks ÷ 3 × 100                                                               |

### JSON Internal Consistency Checks

| Check                            | Description                                                                                    |
| -------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Requirements match**           | The top-level requirements list should exactly match the requirements stored inside each page. |
| **Figures match**                | The top-level figure list should match the figures inside each page.                           |
| **Tables reference valid pages** | Every table should point to an existing page.                                                  |

### Final Score

Average of all **6** metrics.

---

### Accuracy (With Gold Reference)

```text
= mean(requirement_f1, figure_caption_f1, table_caption_f1,
       page_text_fidelity, json_internal_consistency)
```

### Metric Breakdown

| Metric             | Expected Data    | Extracted Data | What is Compared?           |
| ------------------ | ---------------- | -------------- | --------------------------- |
| Requirement F1     | Gold JSON        | Extracted JSON | Requirement category + text |
| Figure Caption F1  | PDF or Gold JSON | Extracted JSON | Figure captions/labels      |
| Table Caption F1   | PDF or Gold JSON | Extracted JSON | Table captions/labels       |
| Table Detection F1 | PDF              | Extracted JSON | Number of tables per page   |
| Image Capture F1   | PDF              | Extracted JSON | Number of images per page   |

### Calculation

* Average these **5**.
* Calculate the F1 score for all these tests with the `f1_from_counters()` function, which measures how well extracted items match expected items (Check F1 Formula).

---

### Table/Figure Capture

```text
= mean(table_detection_f1, table_caption_f1, table_file_existence,
       figure_caption_f1, image_capture_f1)
```

### Metric Breakdown

| **Metric**               | **Calculation / Check**                                              |
| ------------------------ | -------------------------------------------------------------------- |
| **Table Detection F1**   | Compare expected tables, compare extracted tables.                   |
| **Table Caption F1**     | Compare expected table captions, compare extracted table captions.   |
| **Table File Existence** | Existing CSV files ÷ Total tables × 100                              |
| **Figure Caption F1**    | Compare expected figure captions, compare extracted figure captions. |
| **Image Capture F1**     | Compare expected image count, compare extracted image count.         |

### Calculation

* Calculate the F1 score for each of these metrics.
* Average all **5** metrics.


### Formula for F1

The $F_1$ score is the mean of Precision and Recall:

$$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

$$\text{Precision} = \frac{\text{True Positives}}{\text{Total Captured Items}}$$

$$\text{Recall} = \frac{\text{True Positives}}{\text{Total Expected Items}}$$

$$\text{True Positives} = \sum_{k \in K} \min(\text{Expected}_{k}, \text{Captured}_{k})$$
$${\text{Expected = PyMuPDF Capturing}}$$
$${\text{Captured = Actual Output from Extraction}}$$

---

## Usage

### Prerequisites
```bash
pip install pymupdf pandas openai python-dotenv pillow
```

Set up environment variable:
```bash
export OPENAI_API_KEY="your-api-key"
```

### Extractor
```bash
python Extractor.py
```

Configure in `Extractor.py`:
```python
FILE_NAME = "your_spec.pdf"
PDF_PATH = r"/path/to/spec.pdf"
OUTPUT_DIR = "SPEC_OUTPUT"
```

### Comparator
```bash
python Comparator.py path/to/old_document.json path/to/new_document.json
```

**Options:**
```bash
--output-dir comparison_output
--csv-name version_differences.csv
--json-name version_differences.json
--md-name version_differences.md
```

### Quality Checker
```bash
python Quality_Check.py \
    --json data/document.json \
    --pdf docs/spec.pdf
```

**Options:**
```bash
--gold-json path/to/gold_reference.json      # Use manual reference for F1 scoring
--threshold 95                                # Pass threshold (default: 95%)
--report-json path/to/output_report.json     # Save report as JSON
```

---

## UI Interface
- Provides graphical interface for Extractor, Comparator, V-Plan Generator and Quality Checker workflows.

<img width="1535" height="1024" alt="ChatGPT Image Jul 11, 2026, 04_04_48 PM" src="https://github.com/user-attachments/assets/152915bf-316f-468d-b5f9-b339673379ad" />


```bash
python UI_File.py
```
---

## Performance Considerations

- **Large PDFs (100+ pages):** Extract may take 5-10 minutes depending on complexity
- **Vision API calls:** Uses OpenAI GPT-4; costs scale with page count
- **Gold reference:** Provides ground-truth F1-based scoring (requires manual verification)

---
