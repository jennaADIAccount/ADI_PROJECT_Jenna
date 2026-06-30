# Analog Devices & APRILAI Project ##
### Jenna Shaikh - Intern 1

## Overview
This project is designed to:

Develop an AI-driven tool capable of:
 - Extracting and parsing semiconductor specifications
 - Identifying and categorising inconsistencies and ambiguities between different versions of a specification
 - Generating a verification plan (vPlan) from the specification
 - Identifying coverage gaps between the specification and its derived vPlan


## Features
This project is specific to:
- AMBA AXI protocol specification : AMBA AXI Protocol Specification
- RISC‑V ISA specification : RISC-V Ratified Specifications Library :: RISC-V Ratified Specifications Library

## Tasks

### Task 1: Extractor
1. Ingests Specification (AMBA AXI or RISC-V ISA)
2. Extracts & parses information
3. Organises extracted content into document.jsona nd seperate files for images, figures, tables

### Task 2: Comparator
1. Normalises text
2. Builds unique key for each item so can match identical items across versions even if it has different position
3. Checks if item was removed, added, modified for all types of content in file
4. Script attempts a guess at modification reasons
5. Detected changes -> Report = in 3 formats, CSV, JSON, MD

### Task 3: Quality Checker
1. Input PDF Spec. and extraction of it
2. Checks quality (completeness, accuracy, table/figure capture)
   OR can input GOLDEN JSON (Golden Spec.) for extraction to be compared to
3. Report of changes as output, in format of CSV, JSON, MD



| Module | Input | Output | Purpose |
| --- | --- | --- | --- |
| Extractor | Specification PDF / JSON | `document.json`, Figures, Tables, Images | Parses and structures specification content |
| Comparator | `Specification.json`, `Extractor Output.json` | CSV, JSON, MD | Detects added, removed, and modified items |
| Quality Checker | PDF, JSON, CSV, gold JSON | JSON | Measures extraction completeness and accuracy |



## How to Run

### Extractor
```bash
python extractor.py --input data/input.json
```

### Comparator
```bash
python Spec_Version_Comparer.py --spec spec.json --extractor output.json
```

### Quality Checker
```bash
python extractor_quality_check.py \
  --json data/document.json \
  --pdf docs/spec.pdf
```

### Additional Quality Checker Features:
```bash
  --csv path/to/requirements.csv \
  --gold-json path/to/gold_reference.json \
  --threshold 90 \
  --report-json path/to/output_report.json
```
