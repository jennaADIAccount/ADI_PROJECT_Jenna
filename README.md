## Analog Devices & APRILAI Project ##
# Intern 1 - Jenna Shaikh

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
3. Organises extracted content into document.jsona nd seperate files for images, figures, tables.

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


## How to Run


```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

Extractor

```bash
/home/eng-6990/PROJECT/extractor/.venv/bin/python "/home/eng-6990/PROJECT/extractor/(E)extractor improved changes.py"
```

Comparator

```bash
python3 Spec_Version_Comparer.py /home/eng-6990/PROJECT/extractor/RISC-V_VER.1.json /home/eng-6990/PROJECT/extractor/RISC-V_VER.2.json
```

Quality Checker

```bash
python3 extractor_quality_check.py \
  --json "/home/eng-6990/PROJECT/extractor/document.json" \
  --pdf "/home/eng-6990/PROJECT/PROJECT briefs and info./amba_axi_protocol_spec.pdf"
```

Additional Quality Checker Features:

```bash
  --csv path/to/requirements.csv \
  --gold-json path/to/gold_reference.json \
  --threshold 90 \
  --report-json path/to/output_report.json
```
