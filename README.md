# ADI_PROJECT_Jenna
Repo. for my tasks (Extractor, Comparator and Quality Check script)

-Extractor (input specification and its content is extracted, parsed and categorised)
    /home/eng-6990/PROJECT/extractor/.venv/bin/python "/home/eng-6990/PROJECT/extractor/(E)extractor improved changes.py"

How It Works:

1. Ingests Specification (AMBA AXI or RISC-V ISA)

2. Extracts & parses information
   
3. Organises extracted content into a document.json and seperate files for images, figures, tables.

-Comparator (input 2 versions of a specification and text based differences stated in output, in CSV, JSON, MD format)
    python3 Spec_Version_Comparer.py /home/eng-6990/PROJECT/extractor/RISC-V_VER.1.json /home/eng-6990/PROJECT/extractor/RISC-V_VER.2.json

How It Works:

1. Normalises text

2. Builds unique key for each item so can match identical items across versions even if it has different position

3. Checks if item was removed, added, modified for all types of content in file

4. Script attempts a guess at modification reasons

5. Detected changes -> Report = in 3 formats, CSV, JSON, MD


-Quality Check (input source pdf and extraction, compares based off that, unless input GOLDEN JSON (golden spec.) for extraction to be compared to)
    python3 extractor_quality_check.py --json path/to/document.json --pdf path/to/source.pdf

How It Works:

1. Input PDF Spec. and extraction of it
   
2. Checks quality (completeness, accuracy, table/figure capture)
   
OR can input GOLDEN JSON (Golden Spec.) for extraction to be compared to

3. Report of changes as output, in format of CSV, JSON, MD
   
    
Additional commands:
  --csv path/to/requirements.csv \
  --gold-json path/to/gold_reference.json \
  --threshold 90 \
  --report-json path/to/output_report.json
