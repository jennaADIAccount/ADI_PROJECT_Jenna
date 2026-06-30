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

   FEATURES:
-Converts any value to lowercase string to be easily digested -averages 3 scores (accuracy, completeness, table/figure capture) -f1 score = comparison function for captions & requirements (everything captured exist in source -did i capture everything in source), extracts raw text from every page of extraction output to use for text comparisons -classifies requirements based on related words

Formulas for Scores:

Completeness = did extractor capture everything needed? (main keys present?=sections, requirements, figures, etc. ) (compares page count) (text extracted matches character count?) (amount of semantic chunks as pages?) (for every main key are key fields non-empty, i.e text, caption, page) (is csv is expected is it present and non-empty?)
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
       
Accuracy = is extractor output actually correct? without GOLDEN JSON (how similar is extracted text to raw text) (is each requirement found exact in pdf text) (does my keyword classifier guess category thats same as actual categories) (are page numbers 1-n) (3 cross-checks for internal consistency = compares requirement list and per-page list w/ requirements in it for consistency, same for captions and tables/figures ) (do CSV and JSON file produced match) 
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
      
GOLDEN JSON = replaces above with direct F1 comparisons against requirement F1, figure caption, table caption = but with the GOLDEN JSON ones, text fidelity (how well extractor followed parsing instructions), internal consistency
   Formula with --gold-json:         can input a gold reference document to use for quality check 
       accuracy = mean(
           requirement_f1_score,
           figure_caption_f1_score,
           table_caption_f1_score,
           page_text_fidelity_score,
           json_internal_consistency_score
       )
       
Table/figure capture = Were tables and figures properly detected, captioned, and saved? (does table count match PyMuPDF built-in table count) (do table captions match captions found by regex in PDF) (are CSV files prodcuced in extraction output actually exist/non-empty) (do figure captions match ones found by regex in PDF) (does image count match PyMuPDF built-in image embedded count)
3. Table/figure capture percentage
   Formula:
       table_figure_capture = mean(
           table_detection_f1_score,
           table_caption_f1_score,
           table_file_existence_score,
           figure_caption_f1_score,
           image_capture_f1_score
       )


-returns pass/fail for each category of score based on 95% threshold, assembles final report with scores, statuses, formulas and breakdowns in terminal
TOTAL = Accuracy+Completeness+Table/Fig. Capture
TOTAL >= 95% (default threshold) = PASS =/ FAIL = back to extractor/refinement

   
    
Additional commands:
  --csv path/to/requirements.csv \
  --gold-json path/to/gold_reference.json \
  --threshold 90 \
  --report-json path/to/output_report.json
