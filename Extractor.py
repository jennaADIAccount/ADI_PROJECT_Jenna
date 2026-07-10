"""
Structure of Output:

figures
images
pages
tables
Document
    document_name: "outputSPEC2",
    metadata
    sections
    requirements
    figures       
    tables
    notes
    acronyms
    cross_references
    semantic_chunks  
    pages
"""

import os
import re
import json
import io
import base64
import fitz
import pandas as pd
from PIL import Image, ImageDraw



from dotenv import load_dotenv
from openai import OpenAI
# ==========================================================
# CONFIGURATION
# ==========================================================
FILE_NAME = "riscv-2025.pdf"
PDF_PATH = r"/home/eng-6990/PROJECT/PROJECT_briefs_and_info./riscv-2025.pdf"

OUTPUT_DIR = "RISC-V_2025_OUTPUT"

IMAGE_FOLDER  = os.path.join(OUTPUT_DIR, "images")
TABLE_FOLDER  = os.path.join(OUTPUT_DIR, "tables")
FIGURE_FOLDER = os.path.join(OUTPUT_DIR, "figures")   

os.makedirs(OUTPUT_DIR,   exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(TABLE_FOLDER, exist_ok=True)
os.makedirs(FIGURE_FOLDER,exist_ok=True)

# Load environment variables
load_dotenv()

MODEL_NAME = "gpt-4.1"

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def image_to_base64(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def vision(prompt, image, max_tokens=500):
    image_b64 = image_to_base64(image)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        max_completion_tokens=max_tokens,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        },
                    },
                ],
            }
        ],
    )

    return response.choices[0].message.content.strip()

# ==========================================================
# REGEX PATTERNS
# ==========================================================

SECTION_REGEX = re.compile(
    r'^((?:\d+(?:\.\d+)*|[A-C]\d+(?:\.\d+)*))\s+(.+)$'
)


TABLE_REGEX = re.compile(
    r"^Table\s+[A-Za-z]?\d+(?:[-.]\d+)*(?:[:.]?\s+.*)?$",
    re.IGNORECASE | re.MULTILINE,
)

TABLE_CAPTION_REGEX = re.compile(
    r'^Table\s+[A-Za-z]?\d+(?:[-.]\d+)*[:.]?\s*.*$',
    re.IGNORECASE
)

FIGURE_CAPTION_REGEX = re.compile(
    r'^Figure\s+[A-Za-z]?\d+(?:[.\-]\d+)*\s*[:.]\s',
    re.IGNORECASE
)

FIGURE_CAPTION_REGEX = re.compile(
    r'^Figure\s+[A-Za-z]?\d+(?:[.\-]\d+)*\s*[:.]\s',
    re.IGNORECASE
)

REQ_ID_REGEX = re.compile(
    r'([A-Z_]*REQ[-_]?\d+)',
    re.IGNORECASE
)

REQUIREMENT_REGEX = re.compile(
    r'\b('
    r'shall|must|must not|will|should|'
    r'required to|may not|is prohibited|'
    r'remains asserted|remain asserted|'
    r'indicates that|can be sent|'
    r'must be ordered|'
    r'can only be|'
    r'is returned|'
    r'is issued|'
    r'is generated|'
    r'is valid only when'
    r')\b',
    re.IGNORECASE
)

NOTE_REGEX = re.compile(
    r'^(NOTE|WARNING|CAUTION|IMPORTANT|ASSUMPTION)\b',
    re.IGNORECASE
)

ACRONYM_REGEX = re.compile(
    r'\b([A-Z]{2,10})\b'
)

SECTION_REF_REGEX = re.compile(
    r'Section\s+\d+(?:\.\d+)*',
    re.IGNORECASE
)

FIGURE_REF_REGEX = re.compile(
    r'Figure\s+[A-Za-z]?\d+(?:[-.]\d+)*',
    re.IGNORECASE
)

TABLE_REF_REGEX = re.compile(
    r'Table\s+[A-Za-z]?\d+(?:[-.]\d+)*',
    re.IGNORECASE
)

ACRONYM_STOPLIST = {
    "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT",
    "ARE", "NOT", "BUT", "ITS", "ALL", "ANY", "CAN",
    "HAS", "HAVE", "BEEN", "WILL", "MAY", "SHALL", "MUST",
    "WHEN", "THEN", "EACH", "SUCH", "BOTH", "ALSO", "INTO",
    "OVER", "UPON", "USED", "ONLY", "MORE", "THAN", "BEEN",
    "WHICH", "THERE", "THEIR", "THESE", "THOSE", "WHAT",
    "PAGE", "NOTE", "TYPE", "DATA", "BASE", "TRUE", "FALSE"
}


# ==========================================================
# METADATA
# ==========================================================

def extract_document_metadata(pdf):
    metadata = pdf.metadata or {}
    return {
        "title":             metadata.get("title"),
        "author":            metadata.get("author"),
        "subject":           metadata.get("subject"),
        "keywords":          metadata.get("keywords"),
        "creator":           metadata.get("creator"),
        "producer":          metadata.get("producer"),
        "creation_date":     metadata.get("creationDate"),
        "modification_date": metadata.get("modDate")
    }


# ==========================================================
# IMAGE EXTRACTION  (raster/embedded images)
# ==========================================================

def describe_image_with_vision(image, prompt=None):

    if image is None:
        return ""

    if prompt is None:
        prompt = (
            "Write a comprehensive accessibility description of this technical figure."
            "Include:"
            "- the purpose of the figure"
            "- all visible components"
            "- every label"
            "- every signal name"
            "- arrows and direction of data/control flow"
            "- relationships between blocks"
            "- timing waveforms"
            "- state transitions"
            "- buses"
            "- legends"
            "- axis labels"
            "- units"
            "- colours if they convey meaning"
            "Describe the figure so that someone who cannot see it can fully understand its content."
        )

    try:
        return vision(prompt, image, 300)
    except Exception as e:
        print(f"Vision error: {e}")
        return ""


def extract_images(pdf):
    image_records = []
    image_counter = 1
    print("\nExtracting embedded images...")
    for page_num in range(len(pdf)):
        page = pdf[page_num]
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            try:
                base_image = pdf.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image["ext"]
                filename = f"image_{image_counter:04}.{ext}"
                filepath = os.path.join(IMAGE_FOLDER, filename)
                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                image_obj = Image.open(io.BytesIO(image_bytes))
                description = describe_image_with_vision(image_obj, "Describe this embedded image for accessibility.")

                record = {
                    "page": page_num + 1,
                    "file": filepath,
                }
                if description:
                    record["accessibility_description"] = description
                image_records.append(record)
                image_counter += 1
            except Exception as e:
                print("Image extraction error:", e)
    return image_records




# ==========================================================
# OCR FUNCTIONS
# ==========================================================

def extract_text_from_figure_region(pdf_page, clip_rect):
    """
    Extracts text directly from a PDF vector region using PyMuPDF.
    Replaces OCR — works natively on vector PDFs like AXI and RISC-V specs.
    Returns signal names, axis labels, and any other text in the figure area.
    """
    if clip_rect is None:
        
        return ""
    try:
        rect = fitz.Rect(clip_rect)
        
        return pdf_page.get_text("text", clip=rect).strip()
    except Exception as e:
        print("Figure text extraction error:", e)
        return ""


# ==========================================================
# TABLE EXTRACTION  
# ==========================================================

def extract_tables(page, page_num):
    tables_found = []
    try:
        tables = page.find_tables()
        for idx, table in enumerate(tables.tables):
            try:
                extracted = table.extract()
                if not extracted:
                    continue
                df = pd.DataFrame(extracted)
                csv_name = f"table_p{page_num+1}_{idx+1}.csv"
                csv_path = os.path.join(TABLE_FOLDER, csv_name)
                df.to_csv(csv_path, index=False)
                tables_found.append({
                    "page":     page_num + 1,
                    "csv_file": csv_path
                })
            except Exception as e:
                print(f"Table extraction error page {page_num+1}:", e)
    except Exception:
        pass
    return tables_found


# ==========================================================
# TEXT ANALYSIS
# ==========================================================

def extract_headings_from_layout(layout):
    headings = []
    for block in layout.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(span["text"] for span in spans).strip()
            if re.search(r'\.{3,}\s*\d+$', text):
                continue
            
            if re.fullmatch(r'\d+', text):
                continue

            if not text:
                continue
            match = SECTION_REGEX.match(text)
            if match:
                headings.append({
                    "section_id": match.group(1),
                    "title":      match.group(2),
                    "font_size":  max(span["size"] for span in spans)
                })
    return headings


CATEGORY_KEYWORDS = {
    "Performance": [
        "latency", "throughput", "timing", "frequency", "bandwidth",
        "clock rate", "cycles per", "ipc", "mhz", "ghz", "performance",
    ],
    "Electrical": [
        "voltage", "current", "power", "vdd", "vcc", "vref",
        "amperage", "watt", "dissipation", "impedance",
    ],
    "Environmental": [
        "temperature", "humidity", "thermal", "esd", "altitude", "vibration",
    ],
    "Safety": [
        "safety", "hazard", "fault", "asil", "functional safety",
        "redundant", "ecc", "parity", "error correction", "watchdog",
    ],
    "Security": [
        "encryption", "authentication", "secure boot", "pmp", "tee",
        "cryptograph", "attestation", "tamper",
    ],
    "Protocol": [
        "axi", "amba", "ahb", "apb", "ace", "chi", "tilelink",
        "burst", "handshake", "arvalid", "awvalid", "wready", "bvalid",
        "arbiter", "master", "slave", "manager", "subordinate",
        "outstanding transaction", "beat", "strobe",
    ],
    "Memory": [
        "cache", "tlb", "mmu", "dram", "sram", "memory-mapped",
        "memory map", "address space", "page table", "coherenc",
        "physical address", "virtual address",
    ],
    "Architecture": [
        "instruction", "opcode", "register", "risc-v", "riscv", "isa",
        "extension", "privilege mode", "csr", "trap", "exception",
        "interrupt", "pipeline", "hart", "atomic", "vector unit",
    ],
    "Interface": [
        "interface", "pin", "signal", "spi", "uart", "i2c", "can",
        "gpio", "jtag", "pcie",
    ],
}


def classify_requirement(text):
    lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(x in lower for x in keywords):
            return category
    return "Functional"


def extract_requirements(text, section_id=None, page_num=None):
    requirements = []

    clean_text = " ".join(text.split())

    clean_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_text)
    
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)

    for line in sentences:
        line = line.strip()
        if not line:
            continue

        if REQUIREMENT_REGEX.search(line):
            req_match = REQ_ID_REGEX.search(line)
            req_id = req_match.group(1) if req_match else None

            requirements.append({
                "page":     page_num,
                "section":  section_id,
                "category": classify_requirement(line),
                "text":     line
            })

    return requirements

def extract_notes(text):
    notes = []
    for line in text.splitlines():
        line = line.strip()
        if NOTE_REGEX.match(line):
            kind = line.split(":")[0].upper()
            notes.append({"type": kind, "text": line})
    return notes


def extract_acronyms(text):
    found = set()
    for match in ACRONYM_REGEX.finditer(text):
        word = match.group(1)
        if len(word) > 1 and word not in ACRONYM_STOPLIST:
            found.add(word)
    return sorted(found)


def extract_cross_references(text):
    refs = []
    refs.extend(SECTION_REF_REGEX.findall(text))
    refs.extend(FIGURE_REF_REGEX.findall(text))
    refs.extend(TABLE_REF_REGEX.findall(text))
    return refs


def build_section_tree(headings):
    sections = []
    for h in headings:
        sid = h["section_id"]
        parent = sid.rsplit(".", 1)[0] if "." in sid else None
        sections.append({
            "id":     sid,
            "title":  h["title"],
            "parent": parent
        })
    return sections


def build_semantic_chunks(pages):
    chunks = []

    current_section = None
    buffer = []
    page_numbers = []

    for page in pages:

        if page["headings"]:

            if buffer and current_section is not None:
                chunks.append({
                    "section": current_section,
                    "pages": page_numbers,
                    "text": "\n".join(buffer).strip()
                })

            current_section = page["headings"][-1]["section_id"]
            buffer = []
            page_numbers = []

        buffer.append(page["text"])
        page_numbers.append(page["page_number"])

    if buffer and current_section is not None:
        chunks.append({
            "section": current_section,
            "pages": page_numbers,
            "text": "\n".join(buffer).strip()
        })

    return chunks


def print_semantic_chunk_pages(document):
    pages = sorted({page for chunk in document.get("semantic_chunks", []) for page in chunk.get("pages", [])})
    print("\nSEMANTIC CHUNK PAGES:", pages)
    for idx, chunk in enumerate(document.get("semantic_chunks", []), start=1):
        print(f"Chunk {idx}: section={chunk.get('section')} pages={chunk.get('pages')}")

# ==========================================================
# CAPTION EXTRACTORS
# ==========================================================
VALID_VPLAN_SECTION_REGEX = re.compile(
   r'^(?:[A-C]\d+(?:\.\d+)*)$'
)

def is_valid_vplan_section(section):
   if section is None:
       return False
   return VALID_VPLAN_SECTION_REGEX.match(str(section)) is not None


def extract_table_captions(text):
    tables = []

    for line in text.splitlines():
        line = line.strip()

        m = re.match(
            r'^(Table\s+[A-Za-z]?\d+(?:[-.]\d+)*(?:[:.]?\s*.*)?)$',
            line,
            re.IGNORECASE
        )

        if m:
            tables.append({
                "caption": m.group(1).strip()
            })

    return tables

def extract_visual_requirement_hints(figure):
    hints = []

    caption = figure.get("caption", "")
    ocr_text = figure.get("ocr_text", "")
    combined = f"{caption}\n{ocr_text}".lower()

    keywords = [
        "valid", "ready", "reset", "aresetn", "aclk",
        "handshake", "transfer", "asserted", "deasserted",
        "stable", "high", "low", "write", "read",
        "response", "address", "data"
    ]

    for keyword in keywords:
        if keyword in combined:
            hints.append(keyword.upper())

    return sorted(set(hints))

def extract_headings_from_text(text):
    found_headings = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue
        if line.lower().startswith("chapter"):
            continue
        if re.search(r'\.{3,}\s*\d+$', line):
            continue
        if re.fullmatch(r'\d+', line):
            continue

        match = SECTION_REGEX.match(line)
        if match:
            section_id = match.group(1)
            title = match.group(2).strip()
            if len(title) < 3:
                continue
            found_headings.append({
                "section_id": section_id,
                "title": title,
                "font_size": None
            })

    return found_headings
# ==========================================================
# MAIN PARSER
# ==========================================================

def parse_pdf(pdf_path):

    pdf = fitz.open(pdf_path)

    image_records = extract_images(pdf)

    document = {
        "document_name":    os.path.basename(pdf_path),
        "metadata":         extract_document_metadata(pdf),
        "total_pages":      len(pdf),
        "sections":         [],
        "requirements":     [],
        "figures":          [],
        "tables":           [],
        "notes":            [],
        "acronyms":         [],
        "cross_references": [],
        "semantic_chunks":  [],
        "pages":            []
    }

    print("\nProcessing pages...")

    current_section = None

    for page_num in range(len(pdf)):

        page   = pdf[page_num]
        text   = page.get_text("text")

        headings = extract_headings_from_text(text)
 
        if headings:
            current_section = headings[-1]["section_id"]
        elif current_section is None:
            current_section = "Unknown"
 
        requirements = extract_requirements(
            text,
            section_id=current_section,
            page_num=page_num + 1
        )
        
        notes         = extract_notes(text)
        acronyms      = extract_acronyms(text)
        cross_refs    = extract_cross_references(text)
        table_captions = extract_table_captions(text)
        extracted_tables = extract_tables(page, page_num)

        figures = extract_page_figures(
                    pdf_page=page,
                    page_num=page_num,
                    output_folder=FIGURE_FOLDER,
                    section_id=current_section,
                    scale=6
                )


        page_images = [
            img for img in image_records
            if img["page"] == page_num + 1
        ]

        page_json = {
            "page_number":   page_num + 1,
            "text":          text,
            "headings":      headings,
            "requirements":  requirements,
            "figures":       figures,
            "table_captions": table_captions,
            "tables":        extracted_tables,
            "images":        page_images
        }

        document["requirements"].extend(requirements)
        document["notes"].extend(notes)
        document["acronyms"].extend(acronyms)
        document["cross_references"].extend(cross_refs)
        document["figures"].extend(figures)
        document["tables"].extend(extracted_tables)
        document["pages"].append(page_json)

        print(f"Processed page {page_num+1}/{len(pdf)}")

    all_headings = []
    for p in document["pages"]:
        all_headings.extend(p["headings"])
    document["sections"] = build_section_tree(all_headings)

    document["semantic_chunks"] = build_semantic_chunks(document["pages"])

    document["acronyms"] = sorted(set(document["acronyms"]))

    print_semantic_chunk_pages(document)

    json_path = os.path.join(OUTPUT_DIR, "document.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)

    print("\n===================================")
    print("PARSING COMPLETE")
    print("===================================")
    print("JSON:    ", json_path)
    print("Images:  ", IMAGE_FOLDER)
    print("Tables:  ", TABLE_FOLDER)
    print("Figures: ", FIGURE_FOLDER)


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":
    parse_pdf(PDF_PATH)
