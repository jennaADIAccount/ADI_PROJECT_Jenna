# ADI_PROJECT_Jenna
Repo. for my tasks (Extractor, Comparator and Quality Check script)

Extractor (input specification and its content is extracted, parsed and categorised)
/home/eng-6990/PROJECT/extractor/.venv/bin/python "/home/eng-6990/PROJECT/extractor/(E)extractor improved changes.py"

Comparator (input 2 versions of a specification and text based differences stated in output, in CSV, JSON, MD format)
python3 Spec_Version_Comparer.py /home/eng-6990/PROJECT/extractor/RISC-V_VER.1.json /home/eng-6990/PROJECT/extractor/RISC-V_VER.2.json

Quality Check (input source pdf and extraction, compares based off that, unless input GOLDEN JSON (golden spec.) for extraction to be compared to)
python3 extractor_quality_check.py --json path/to/document.json --pdf path/to/source.pdf
Additional commands:
  --csv path/to/requirements.csv \
  --gold-json path/to/gold_reference.json \
  --threshold 90 \
  --report-json path/to/output_report.json
