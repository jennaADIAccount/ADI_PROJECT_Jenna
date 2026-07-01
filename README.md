# Analog Devices & APRILAI Project ##
### Jenna Shaikh 

This repository is part of the **APRIL AI Hub** Summer Internship Programme (AI for Productive Research & Innovation in Electronics) and a research project funded by **Analog Devices**.

## Overview
This project is designed to develop an AI-driven tool capable of:

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
- Ingests Specification (AMBA AXI or RISC-V ISA)
- Extracts & parses information
- Organises extracted content into document.json and seperate files for images, figures, tables

### Task 2: Comparator
- Normalises text
- Builds unique key for each item so can match identical items across versions even if it has different position
- Checks if item was removed, added, modified for all types of content in file
- Script attempts a guess at modification reasons
- Detected changes -> Report = in 3 formats, CSV, JSON, MD

### Task 3: Quality Checker
- Input PDF Spec. and extraction of it
- Checks quality (completeness, accuracy, table/figure capture)
   OR can input GOLDEN JSON (Golden Spec.) for extraction to be compared to
- Report of changes as output, in format of CSV, JSON, MD



| Module | Input | Output | Purpose |
| --- | --- | --- | --- |
| Extractor | Specification PDF / JSON | `document.json`, Figures, Tables, Images | Parses and structures specification content |
| Comparator | `Specification.json`, `Extractor_Output.json` | CSV, JSON, MD | Detects added, removed, and modified items |
| Quality Checker | PDF, JSON, CSV, gold JSON | JSON | Measures extraction completeness and accuracy |



## How to Run

### Extractor
```bash
python extractor.py --input data/input.json
```

### Comparator
```bash
python Spec_Version_Comparer.py VER_1_specification.json VER_2_specification.json
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
