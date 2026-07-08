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
FILE_NAME = "pg70-100.pdf"
PDF_PATH = r"/home/eng-6990/PROJECT/PROJECT_briefs_and_info./pg70-100.pdf"

OUTPUT_DIR = "RISCV-2026-PG70-100_output"

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
    r'(Table)\s+([A-Za-z]?\d+(?:[-.]\d+)*)',
    re.IGNORECASE
)

TABLE_CAPTION_REGEX = re.compile(
    r'^Table\s+[A-Za-z]?\d+(?:[-.]\d+)*\.(?:\s|$)',
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


def find_figure_captions(pdf_page):
    """
    Find figure caption lines using PyMuPDF text extraction, then locate
    their exact rect on the page with search_for(). This anchors the whole
    pipeline to a known point instead of scanning the entire page.
    """
    text = pdf_page.get_text("text")
    captions = []

    for line in text.splitlines():
        line = line.strip()
        if not line or not FIGURE_CAPTION_REGEX.match(line):
            continue

        hits = pdf_page.search_for(line)
        if not hits:
            short_match = re.match(
                r'(Figure\s+[A-Za-z]?\d+(?:[.\-]\d+)*)', line, re.IGNORECASE
            )
            search_text = short_match.group(1) if short_match else line
            hits = pdf_page.search_for(search_text)

        if hits:
            captions.append({"caption": line, "rect": hits[-1]})

    return captions


def build_search_window(pdf_page, caption_rect, window_pt=200,
                         upper_bound=None, lower_bound=None, position=None):
    """
    Build a search region around the caption, but clamp it so it never
    crosses into a neighboring caption's territory. upper_bound/lower_bound
    are absolute y-limits (typically the midpoint to the previous/next
    caption on the page) that prevent two nearby figures from sharing
    the same window and producing duplicate crops.
    """
    full_rect = pdf_page.rect
    
    if position == "above":
        up_pt, down_pt = window_pt, window_pt * 0.15
    elif position == "below":
        up_pt, down_pt = window_pt * 0.15, window_pt
    else:
        up_pt, down_pt = window_pt, window_pt * 0.8
    
    y0 = max(full_rect.y0, caption_rect.y0 - window_pt)
    y1 = min(full_rect.y1, caption_rect.y1 + window_pt * 0.8)

    if upper_bound is not None:
        y0 = max(y0, upper_bound)
    if lower_bound is not None:
        y1 = min(y1, lower_bound)

    return fitz.Rect(full_rect.x0, y0, full_rect.x1, y1)


def _rects_touch_or_close(r1, r2, tol=8):
    expanded = fitz.Rect(r1.x0 - tol, r1.y0 - tol, r1.x1 + tol, r1.y1 + tol)
    return expanded.intersects(r2)


def find_geometric_bbox(
    pdf_page,
    search_window,
    caption_rect,
    seed_bbox=None,
    figure_position=None,
    min_overlap_ratio=0.5,
    touch_tol=40 #16 -> 20
):
    """
    Refine the bbox chosen by vision with local PDF geometry only.

    The vision result is the source of truth for which figure belongs to
    this caption. Geometry is used only to snap/expand the crop to nearby
    vector drawings, embedded images, and labels, which keeps neighboring
    figures from being merged in dense engineering specs.
    """
    drawings = pdf_page.get_drawings()
    candidate_rects = []

    for d in drawings:
        r = d.get("rect")
        if not r or r.is_empty:
            continue
        if not r.intersects(search_window):
            continue
        if r.intersects(caption_rect):
            continue

        overlap = r & search_window
        overlap_ratio = (overlap.get_area() / r.get_area()) if r.get_area() > 0 else 0
        if overlap_ratio < min_overlap_ratio:
            continue

        candidate_rects.append(overlap)

    image_rects = []
    for img in pdf_page.get_images(full=True):
        xref = img[0]
        try:
            for r in pdf_page.get_image_rects(xref):
                if not r.intersects(search_window) or r.intersects(caption_rect):
                    continue
                overlap = r & search_window
                overlap_ratio = (overlap.get_area() / r.get_area()) if r.get_area() > 0 else 0
                if overlap_ratio < min_overlap_ratio:
                    continue
                image_rects.append(overlap)
        except Exception:
            pass

    all_rects = candidate_rects + image_rects
    if seed_bbox is None:
        return None

    seed = fitz.Rect(seed_bbox)
    seed &= search_window
    if seed.is_empty:
        return None

    if figure_position == "above":
        all_rects = [r for r in all_rects if r.y1 <= caption_rect.y0]
    elif figure_position == "below":
        all_rects = [r for r in all_rects if r.y0 >= caption_rect.y1]

    expanded_seed = fitz.Rect(
        seed.x0 - touch_tol * 2,
        seed.y0 - touch_tol * 2,
        seed.x1 + touch_tol * 2,
        seed.y1 + touch_tol * 2,
    )
    overlapping = [r for r in all_rects if r.intersects(expanded_seed)]

    if overlapping:
        region = fitz.Rect(overlapping[0])
        for r in overlapping[1:]:
            region |= r
        region |= seed
        remaining = [r for r in all_rects if r not in overlapping]
    else:
        region = fitz.Rect(seed)
        remaining = all_rects

    # Nearby text labels (signal names, block labels) that sit just outside
    # the vector geometry but are visually part of the figure. Excluded:
    # anything overlapping the caption itself.
    label_rects = [
        fitz.Rect(b[:4]) for b in pdf_page.get_text("blocks")
        if fitz.Rect(b[:4]).intersects(search_window)
        and not fitz.Rect(b[:4]).intersects(caption_rect)
    ]

    # ---- Grow by touching/overlapping drawings AND nearby text labels ----
    changed = True
    while changed:
        changed = False
        still_pending = []
        for r in remaining:
            if _rects_touch_or_close(region, r, tol=touch_tol):
                region |= r
                changed = True
            else:
                still_pending.append(r)
        remaining = still_pending

        still_pending = []
        for r in label_rects:
            if _rects_touch_or_close(region, r, tol=touch_tol):
                region |= r
                changed = True
            else:
                still_pending.append(r)
        label_rects = still_pending

    bbox = region
    pad_x = max(12, bbox.width * 0.04)
    pad_y = max(12, bbox.height * 0.06)

    bbox.x0 = max(pdf_page.rect.x0, bbox.x0 - pad_x)
    bbox.y0 = max(pdf_page.rect.y0, bbox.y0 - pad_y)
    bbox.x1 = min(pdf_page.rect.x1, bbox.x1 + pad_x)
    bbox.y1 = min(pdf_page.rect.y1, bbox.y1 + pad_y)
    return bbox


def classify_figure_position(pdf_page, caption_rect, context_pt=350, scale=4):
    """
    FIRST vision call — classification only, nothing else.
 
    Crops a moderate, symmetric vertical strip centered on the caption
    (outlined in red so the model has an unambiguous anchor) and asks a
    single question: relative to that caption, is the figure it describes
    above, below, overlapping/adjacent, or not visible in this crop at all.
 
    Keeping this call cheap and narrowly scoped means the model is never
    asked to do two things at once (decide direction AND find a precise
    box in a noisy, oversized image). The direction decided here is what
    lets the second call crop tightly to just the correct side.
    """
    full_rect = pdf_page.rect
    y0 = max(full_rect.y0, caption_rect.y0 - context_pt)
    y1 = min(full_rect.y1, caption_rect.y1 + context_pt)
    strip = fitz.Rect(full_rect.x0, y0, full_rect.x1, y1)
 
    mat = fitz.Matrix(scale, scale)
    pix = pdf_page.get_pixmap(matrix=mat, clip=strip, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
 
    caption_px = (
        int((caption_rect.x0 - strip.x0) * scale),
        int((caption_rect.y0 - strip.y0) * scale),
        int((caption_rect.x1 - strip.x0) * scale),
        int((caption_rect.y1 - strip.y0) * scale),
    )
    draw = ImageDraw.Draw(img)
    draw.rectangle(caption_px, outline="red", width=max(3, scale))
 
    prompt = (
        "This is a cropped section of a technical PDF page, "
        f"{pix.width}x{pix.height} pixels. The caption outlined in red "
        "belongs to a figure — a diagram, block diagram, waveform, "
        "register layout, plot, timing diagram, or other engineering "
        "graphic.\n\n"
        "Relative to the red caption box, is the figure it describes:\n"
        "- ABOVE the red box\n"
        "- BELOW the red box\n"
        "- OVERLAPPING or immediately adjacent to the red box (e.g. beside it)\n"
        "- NOT VISIBLE anywhere in this crop\n\n"
        'Respond with ONLY one word: "above", "below", "overlapping", or "none".'
    )
 
    try:
        answer = vision(prompt, img, max_tokens=5).strip().lower()
    except Exception as e:
        print("Position classification error:", e)
        return "none"
 
    for label in ("above", "below", "overlapping", "none"):
        if label in answer:
            return label
    return "none"
 
 



 
def locate_figure_via_vision(pdf_page, search_window, caption, caption_rect, figure_position, scale=6):
    """
    SECOND vision call — precise localization only.
 
    By this point, `figure_position` has already been decided by
    classify_figure_position(), and `search_window` has already been
    cropped tightly to that side of the caption. This call's only job is
    to find the exact bounding box of the figure's graphical artwork
    within that narrow, already-correct region — it is not asked to
    reconsider direction.
    """
    mat = fitz.Matrix(scale, scale)
    pix = pdf_page.get_pixmap(matrix=mat, clip=search_window, alpha=False)
    crop_img = Image.open(io.BytesIO(pix.tobytes("png")))
 
    caption_px = (
        int((caption_rect.x0 - search_window.x0) * scale),
        int((caption_rect.y0 - search_window.y0) * scale),
        int((caption_rect.x1 - search_window.x0) * scale),
        int((caption_rect.y1 - search_window.y0) * scale),
    )
    draw = ImageDraw.Draw(crop_img)
    draw.rectangle(caption_px, outline="red", width=max(3, scale))
 
    buf = io.BytesIO()
    crop_img.save(buf, format="PNG")
    crop_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
 
    prompt = (
        "You are given a cropped region of a technical specification PDF "
        f"page, rendered at {pix.width}x{pix.height} pixels. The caption "
        f'outlined in red reads: "{caption}". This region has already been '
        f"narrowed to the {figure_position} side of that caption, where "
        "the figure it describes is known to be located.\n\n"
        "This crop contains exactly one figure belonging to the red-boxed "
        "caption. Locate only the graphical artwork directly associated "
        "with the highlighted caption.\n\n"
        "The figure consists of diagrams, block diagrams, waveforms, "
        "register layouts, plots, timing diagrams, arrows, connectors, "
        "axes, or other engineering graphics.\n\n"
        "Ignore all paragraphs.\n"
        "Ignore all body text.\n"
        "Ignore references such as \"see Figure 3-2\".\n"
        "Ignore headers.\n"
        "Ignore footers.\n"
        "Ignore page numbers.\n\n"
        "Return a bounding box that encloses ALL graphical components "
        "belonging to this figure. Do NOT return a paragraph.\n\n"
        "The figure may be separated from its caption by one or more "
        "explanatory paragraphs. Those paragraphs are NOT part of the "
        "figure. Continue searching past them until you find the actual "
        "graphical artwork associated with the caption.\n\n"
        "Return the smallest rectangle that completely contains every "
        "graphical element belonging to the figure. If in doubt, make the "
        "box slightly larger rather than risk cropping off any part of "
        "the figure.\n\n"
        "Respond with ONLY a JSON object (no markdown fences, no extra "
        "text) in exactly this form:\n"
        '{"found": true|false, "confidence": 0.0, '
        '"x0": int, "y0": int, "x1": int, "y1": int}\n\n'
        "x0,y0,x1,y1 are pixel coordinates relative to THIS cropped image "
        "(top-left origin), bounding the figure only. confidence is 0.0 "
        "to 1.0.\n\n"
        'If no graphical artwork exists in this crop, return '
        '{"found": false, "confidence": 0.0, "x0": null, "y0": null, '
        '"x1": null, "y1": null}'
    )
 
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_completion_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{crop_b64}"}},
                    ],
                }
            ],
        )
        raw = response.choices[0].message.content
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        result = json.loads(match.group())
    except Exception as e:
        print("Vision localization error:", e)
        return None
 
    if not result.get("found", False):
        return None
    if None in (result.get("x0"), result.get("y0"), result.get("x1"), result.get("y1")):
        return None
 
    try:
        result_x0 = float(result["x0"])
        result_y0 = float(result["y0"])
        result_x1 = float(result["x1"])
        result_y1 = float(result["y1"])
    except (TypeError, ValueError):
        return None
 
    # crop-local pixels -> page-absolute PDF points
    x0 = search_window.x0 + result_x0 / scale
    y0 = search_window.y0 + result_y0 / scale
    x1 = search_window.x0 + result_x1 / scale
    y1 = search_window.y0 + result_y1 / scale
 
    bbox = fitz.Rect(x0, y0, x1, y1)
    bbox &= search_window
 
    if bbox.is_empty or bbox.width < 15 or bbox.height < 15:
        return None
 
    try:
        confidence = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
 
    return {
        "bbox": bbox,
        "position": figure_position,
        "confidence": max(0.0, min(1.0, confidence)),
    }
 
 
def extract_page_figures(
    pdf_page,
    page_num,
    output_folder,
    section_id,
    scale=6,
    margin=70, #from 8 -> 50
    window_pt=500 # from 650 -> 800
):
    """
    Caption-first, two-stage vision pipeline:
      1. find caption (PyMuPDF)
      2. classify_figure_position(): cheap call, decides above/below/
         overlapping/none using a moderate symmetric context crop
      3. build a search window biased tightly toward that side
      4. locate_figure_via_vision(): detailed call, scoped to just that
         narrow window, returns the precise bounding box only
      5. PDF geometry refines/expands that vision-selected crop
      6. crop, extract vector text, describe, save
    """
    captions = find_figure_captions(pdf_page)
 
    # Ensure captions are ordered from top to bottom
    captions.sort(key=lambda c: c["rect"].y0)
 
    figures = []
 
    for idx, cap_info in enumerate(captions):
        caption = cap_info["caption"]
        caption_rect = cap_info["rect"]
 
        # ----------------------------------------------------
        # Prevent one figure from searching into another figure
        # by limiting the search window halfway between captions.
        # ----------------------------------------------------
        upper_bound = None
        lower_bound = None
 
        if idx > 0:
            prev_rect = captions[idx - 1]["rect"]
            upper_bound = (prev_rect.y1 + caption_rect.y0) / 2
 
        if idx < len(captions) - 1:
            next_rect = captions[idx + 1]["rect"]
            lower_bound = (caption_rect.y1 + next_rect.y0) / 2
 
        # ---- 1st vision call: classify position only ----
        figure_position = classify_figure_position(pdf_page, caption_rect)
        print(f"\n{caption}")
        print("figure_position:", figure_position)
 
        search_window = None
        vision_result = None
 
        if figure_position != "none":
            # ---- crop only that half, biased toward the determined side ----
            search_window = build_search_window(
                pdf_page,
                caption_rect,
                window_pt=window_pt,
                upper_bound=upper_bound,
                lower_bound=lower_bound,
                position=figure_position,
            )
 
            # ---- 2nd vision call: precise localization within that half ----
            vision_result = locate_figure_via_vision(
                pdf_page,
                search_window,
                caption,
                caption_rect,
                figure_position=figure_position,
                scale=scale
            )
 
        bbox = vision_result["bbox"] if vision_result else None
        vision_confidence = vision_result["confidence"] if vision_result else 0.0
 
        print("search_window:", tuple(search_window) if search_window else None)
        print("vision_bbox:", tuple(bbox) if bbox else None)
        print("vision_confidence:", vision_confidence)
 
        if bbox is not None:
            refined_bbox = find_geometric_bbox(
                pdf_page,
                search_window,
                caption_rect,
                seed_bbox=bbox,
                figure_position=figure_position,
            )
            if refined_bbox is not None:
                bbox = refined_bbox
                print("refined_bbox:", tuple(bbox))
 
        if bbox is None:
            print(f"FIGURE NOT LOCATED: {caption} on page {page_num + 1}")
            fig = {
                "caption": caption,
                "file": None,
                "clip_rect": None,
                "section": section_id,
                "page": page_num + 1,
                "ocr_text": "",
                "accessibility_description": "",
                "located_via": "none",
                "figure_position": figure_position,
                "vision_confidence": vision_confidence
            }
            fig["visual_requirement_hints"] = extract_visual_requirement_hints(fig)
            figures.append(fig)
            continue
 
        clip_rect = fitz.Rect(
            max(pdf_page.rect.x0, bbox.x0 - margin),
            max(pdf_page.rect.y0, bbox.y0 - margin),
            min(pdf_page.rect.x1, bbox.x1 + margin),
            min(pdf_page.rect.y1, bbox.y1 + margin)
        )
 
        print(
            f"FIGURE LOCATED: {caption} on page {page_num + 1} "
            f"via vision+geometry bbox={tuple(bbox)}"
        )
 
        mat = fitz.Matrix(scale, scale)
        pix = pdf_page.get_pixmap(matrix=mat, clip=clip_rect, alpha=False)
        cropped = Image.open(io.BytesIO(pix.tobytes("png")))
 
        safe_id = re.sub(r"[^\w\-]", "_", caption)[:40]
        filename = f"figure_p{page_num+1}_{idx+1}_{safe_id}.png"
        filepath = os.path.join(output_folder, filename)
        cropped.save(filepath)
 
        ocr_text = extract_text_from_figure_region(pdf_page, tuple(clip_rect))
 
        description = describe_image_with_vision(
            cropped,
            f"Describe this technical figure.\nCaption: {caption}"
        )
 
        fig = {
            "caption": caption,
            "file": filepath,
            "clip_rect": tuple(clip_rect),
            "section": section_id,
            "page": page_num + 1,
            "ocr_text": ocr_text,
            "accessibility_description": description,
            "located_via": "vision+geometry",
            "figure_position": figure_position,
            "vision_confidence": vision_confidence
        }
        fig["visual_requirement_hints"] = extract_visual_requirement_hints(fig)
 
        print("\nFIGURE:", fig["caption"])
        print("SECTION:", fig["section"])
        print("LOCATED VIA:", fig["located_via"])
        print("FIGURE POSITION:", fig["figure_position"])
        print("VISION CONFIDENCE:", fig["vision_confidence"])
        print("OCR TEXT:", fig["ocr_text"])
        print("HINTS:", fig["visual_requirement_hints"])
 
        figures.append(fig)
 
    return figures

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
        if TABLE_CAPTION_REGEX.match(line):
            tables.append({"caption": line})
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
