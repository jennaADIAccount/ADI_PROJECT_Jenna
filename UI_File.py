"""
Specification Toolchain Dashboard
==================================

Single-page Streamlit dashboard that wires together the three pieces of the
toolchain:

    1. Extractor.py        -> turns a spec PDF into a structured document.json
    2. Comparator.py       -> diffs two document.json files ("Inconsistency Check")
    3. Quality_Check.py    -> scores a document.json for completeness / accuracy /
                               table & figure capture ("Quality Checker")

...plus a placeholder "V-Plan Related Material Filter" section. That module
(VPlan.py) doesn't exist yet -- the hook below is intentionally minimal. Once
a VPlan.py that exposes `filter_material(document, requirement_text)` is
dropped next to this file, the pipeline will call straight into it. Until
then this section renders a clearly-labelled placeholder preview so the rest
of the UI can be built and demoed end-to-end.
"""

import json
import os
import tempfile
import types
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st
from openai import OpenAI

import Comparator
import Quality_Check

# Extractor.py builds its OpenAI client at IMPORT time
# (client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])), so importing it
# with no key set would crash the app before the sidebar can even render.
# Seed a placeholder so import succeeds; the sidebar swaps in the real
# client once the user enters a key.
os.environ.setdefault("OPENAI_API_KEY", "placeholder-set-key-in-sidebar")
import Extractor

# VPlan.py doesn't exist yet -- optional future module, see docstring above.
try:
    import VPlan
except ImportError:
    VPlan = None


# ==========================================================
# PAGE CONFIG + THEME
# ==========================================================

st.set_page_config(
    page_title="Specification Toolchain",
    page_icon="\U0001F4D1",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COLORS = {
    "blue": {"main": "#2563eb", "bg": "#eff6ff", "border": "#bfdbfe"},
    "green": {"main": "#16a34a", "bg": "#f0fdf4", "border": "#bbf7d0"},
    "orange": {"main": "#ea580c", "bg": "#fff7ed", "border": "#fed7aa"},
    "purple": {"main": "#7c3aed", "bg": "#f5f3ff", "border": "#ddd6fe"},
    "red": {"main": "#dc2626", "bg": "#fef2f2", "border": "#fecaca"},
}

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.block-container {
    padding-top: 1.6rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

/* ---------- generic panel ---------- */
.panel {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 18px 20px 20px 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
.panel-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.05rem;
    font-weight: 800;
    padding-bottom: 12px;
    margin-bottom: 14px;
    border-bottom: 1px solid #eef0f3;
}
.panel-header .badge-icon {
    width: 30px; height: 30px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px;
}
.section-label {
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: #6b7280;
    text-transform: uppercase;
    margin: 4px 0 8px 0;
}

/* ---------- pipeline step cards ---------- */
.step-card {
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 14px;
    border: 1px solid;
    display: flex;
    gap: 12px;
    align-items: flex-start;
}
.step-icon {
    width: 34px; height: 34px;
    min-width: 34px;
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
    color: white;
    font-weight: 700;
}
.step-title {
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 3px;
}
.step-desc {
    font-size: 0.82rem;
    color: #4b5563;
    line-height: 1.35;
}
.step-status {
    margin-left: auto;
    font-size: 0.68rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    white-space: nowrap;
}

/* ---------- results section ---------- */
.result-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}
.result-title {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 1.0rem;
    font-weight: 800;
}
.result-title .icon-box {
    width: 26px; height: 26px;
    border-radius: 7px;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px;
}
.output-path-label {
    font-size: 0.72rem;
    color: #9ca3af;
    font-weight: 600;
    text-align: right;
    margin-bottom: 2px;
}
.meta-box {
    background: #f9fafb;
    border: 1px solid #eef0f3;
    border-radius: 10px;
    padding: 12px 14px;
}
.meta-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.82rem;
    padding: 5px 0;
    border-bottom: 1px solid #f0f1f3;
}
.meta-row:last-child { border-bottom: none; }
.meta-row .k { color: #6b7280; }
.meta-row .v { font-weight: 600; color: #111827; }

.placeholder-banner {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a5b13;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.8rem;
    margin-bottom: 10px;
}

.page-pill {
    display: block;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 6px;
    border: 1px solid #e5e7eb;
    background: #fafafa;
    color: #374151;
}
.page-pill.active {
    background: #fff7ed;
    border-color: #ea580c;
    color: #ea580c;
}

.legend-box {
    border: 1px solid #eef0f3;
    border-radius: 10px;
    padding: 12px 14px;
    background: #fafafa;
}
.legend-title { font-size: 0.78rem; font-weight: 700; color: #6b7280; margin-bottom: 8px; }
.legend-row { display:flex; align-items:center; gap:8px; font-size:0.82rem; margin-bottom:6px; color:#374151;}
.legend-swatch { width: 12px; height: 12px; border-radius: 3px; }

.diff-pane {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 12px 14px;
    line-height: 1.7;
    font-size: 0.86rem;
    max-height: 340px;
    overflow-y: auto;
    background: #fff;
}
.diff-pane-header {
    font-size: 0.78rem;
    font-weight: 700;
    color: #374151;
    margin-bottom: 8px;
}

/* ---------- quality checker ---------- */
.gauge-wrap { display:flex; flex-direction:column; align-items:center; }
.gauge {
    width: 128px; height: 128px; border-radius: 50%;
    display:flex; align-items:center; justify-content:center;
}
.gauge-inner {
    width: 98px; height: 98px; border-radius: 50%;
    background: #ffffff;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
}
.gauge-value { font-size: 1.9rem; font-weight: 800; color: #111827; line-height:1; }
.gauge-max { font-size: 0.72rem; color: #9ca3af; font-weight:600; }
.gauge-label {
    margin-top: 8px;
    font-size: 0.82rem;
    font-weight: 700;
    padding: 2px 12px;
    border-radius: 999px;
}

.stat-box { text-align:left; }
.stat-label { font-size: 0.78rem; color:#6b7280; font-weight:600; margin-bottom:4px;}
.stat-value { font-size: 1.35rem; font-weight:800; color:#111827; margin-bottom:6px;}
.stat-bar-track { background:#eef0f3; border-radius: 999px; height:7px; width:100%; overflow:hidden; }
.stat-bar-fill { height:100%; border-radius:999px; }

.issue-row { display:flex; gap:8px; align-items:flex-start; font-size:0.84rem; margin-bottom:9px; color:#374151;}
.issue-icon { font-size: 0.9rem; margin-top:1px; }

.run-btn-wrap button {
    background: #2563eb !important;
    color: white !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 0.6rem 0 !important;
}
.file-row {
    display:flex; align-items:center; justify-content:space-between;
    background:#fafafa; border:1px solid #eef0f3; border-radius:9px;
    padding:8px 10px; margin-bottom:8px; font-size:0.85rem;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==========================================================
# SMALL HTML HELPERS
# ==========================================================

def panel_header(icon, title, color):
    c = COLORS[color]
    st.markdown(
        f"""<div class="panel-header" style="color:{c['main']}">
        <span class="badge-icon" style="background:{c['bg']};border:1px solid {c['border']}">{icon}</span>
        {title}
        </div>""",
        unsafe_allow_html=True,
    )


def step_card(icon, title, desc, color, status_text, status_done):
    c = COLORS[color]
    status_bg = "#dcfce7" if status_done else "#f3f4f6"
    status_fg = "#15803d" if status_done else "#6b7280"
    st.markdown(
        f"""
        <div class="step-card" style="background:{c['bg']};border-color:{c['border']}">
            <div class="step-icon" style="background:{c['main']}">{icon}</div>
            <div style="flex:1">
                <div class="step-title" style="color:{c['main']}">{title}</div>
                <div class="step-desc">{desc}</div>
            </div>
            <div class="step-status" style="background:{status_bg};color:{status_fg}">{status_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def result_title_row(icon, title, color, output_path):
    c = COLORS[color]
    col_title, col_path = st.columns([2.4, 2])
    with col_title:
        st.markdown(
            f"""<div class="result-title" style="color:{c['main']}">
            <span class="icon-box" style="background:{c['bg']};border:1px solid {c['border']}">{icon}</span>
            {title}</div>""",
            unsafe_allow_html=True,
        )
    with col_path:
        st.markdown(
            "<div class='output-path-label'>OUTPUT PATH</div>",
            unsafe_allow_html=True,
        )
        st.code(output_path, language=None)


def meta_box(rows):
    html = "<div class='meta-box'>"
    for k, v in rows:
        html += f"<div class='meta-row'><span class='k'>{k}</span><span class='v'>{v}</span></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def gauge(percentage, size_label):
    percentage = max(0, min(100, percentage))
    if percentage >= 90:
        color, tint, label = "#16a34a", "#dcfce7", "Excellent"
    elif percentage >= 75:
        color, tint, label = "#16a34a", "#dcfce7", "Good"
    elif percentage >= 60:
        color, tint, label = "#ea580c", "#ffedd5", "Fair"
    else:
        color, tint, label = "#dc2626", "#fee2e2", "Poor"

    st.markdown(
        f"""
        <div class="gauge-wrap">
            <div class="gauge" style="background: conic-gradient({color} {percentage}%, #eef0f3 0)">
                <div class="gauge-inner">
                    <span class="gauge-value">{percentage:.0f}</span>
                    <span class="gauge-max">/{size_label}</span>
                </div>
            </div>
            <span class="gauge-label" style="background:{tint};color:{color}">{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_bar(label, percentage, color):
    st.markdown(
        f"""
        <div class="stat-box">
            <div class="stat-label">{label}</div>
            <div class="stat-value" style="color:{color}">{percentage:.0f}%</div>
            <div class="stat-bar-track">
                <div class="stat-bar-fill" style="width:{max(0,min(100,percentage))}%;background:{color}"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_color(pct):
    if pct >= 90:
        return "#16a34a"
    if pct >= 75:
        return "#65a30d"
    if pct >= 60:
        return "#ea580c"
    return "#dc2626"


def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"


def render_word_diff(old_text, new_text):
    """Word-level diff -> HTML with removed words struck-through in red on the
    old side and added words highlighted green on the new side."""
    old_words = old_text.split()
    new_words = new_text.split()
    matcher = SequenceMatcher(None, old_words, new_words)

    old_parts, new_parts = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = " ".join(old_words[i1:i2])
        new_chunk = " ".join(new_words[j1:j2])
        if tag == "equal":
            old_parts.append(old_chunk)
            new_parts.append(new_chunk)
        elif tag == "delete":
            old_parts.append(f'<span style="background:#fecaca;text-decoration:line-through">{old_chunk}</span>')
        elif tag == "insert":
            new_parts.append(f'<span style="background:#bbf7d0">{new_chunk}</span>')
        elif tag == "replace":
            old_parts.append(f'<span style="background:#fecaca;text-decoration:line-through">{old_chunk}</span>')
            new_parts.append(f'<span style="background:#bbf7d0">{new_chunk}</span>')

    return " ".join(old_parts), " ".join(new_parts)


# ==========================================================
# BACKEND HOOKS
# ==========================================================

def run_extraction(pdf_path, label):
    """Run Extractor.parse_pdf on a saved PDF, isolating each run in its own
    temp folder by monkeypatching Extractor's module-level output globals."""
    out_dir = os.path.join(os.path.dirname(pdf_path), f"{label}_extract_output")
    image_dir = os.path.join(out_dir, "images")
    table_dir = os.path.join(out_dir, "tables")
    figure_dir = os.path.join(out_dir, "figures")
    for d in (image_dir, table_dir, figure_dir):
        os.makedirs(d, exist_ok=True)

    Extractor.OUTPUT_DIR = out_dir
    Extractor.IMAGE_FOLDER = image_dir
    Extractor.TABLE_FOLDER = table_dir
    Extractor.FIGURE_FOLDER = figure_dir

    Extractor.parse_pdf(pdf_path)

    json_path = os.path.join(out_dir, "document.json")
    with open(json_path, "r", encoding="utf-8") as f:
        document = json.load(f)
    return document, json_path


def run_vplan_filter(document, requirement_text):
    """Hook for the not-yet-built VPlan module. See module docstring."""
    if VPlan is not None and hasattr(VPlan, "filter_material"):
        return VPlan.filter_material(document, requirement_text), True

    # --- placeholder branch: VPlan.py hasn't been written yet ---
    candidate_sections = [
        s for s in document.get("sections", [])
        if Extractor.is_valid_vplan_section(s.get("id"))
    ][:5]

    if not candidate_sections:
        candidate_sections = document.get("sections", [])[:3]

    placeholder = {
        "document": document.get("document_name"),
        "vplan_related_material": [
            {"section": s.get("id", "?"), "content": (s.get("title") or "")[:80]}
            for s in candidate_sections
        ],
        "metadata": {"total_items": len(candidate_sections)},
    }
    return placeholder, False


def run_inconsistency_check(old_document, new_document):
    return Comparator.compare_documents(old_document, new_document)


def run_quality_check(json_path, pdf_path):
    args = types.SimpleNamespace(
        json=json_path,
        pdf=pdf_path,
        csv=None,
        gold_json=None,
        threshold=95.0,
    )
    return Quality_Check.build_report(args)


# ==========================================================
# SESSION STATE
# ==========================================================

if "excluded_files" not in st.session_state:
    st.session_state.excluded_files = set()
if "results" not in st.session_state:
    st.session_state.results = None
if "selected_page" not in st.session_state:
    st.session_state.selected_page = None


# ==========================================================
# SIDEBAR -- API KEY
# ==========================================================

with st.sidebar:
    st.subheader("Extractor settings")
    api_key_input = st.text_input(
        "OpenAI API key",
        type="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
        help="Needed for PDF extraction -- the extractor calls the OpenAI vision API for each figure/image. Not needed if you upload already-extracted document.json files.",
    )
    if api_key_input and not api_key_input.startswith("placeholder"):
        os.environ["OPENAI_API_KEY"] = api_key_input
        Extractor.client = OpenAI(api_key=api_key_input)

    st.divider()
    st.caption(
        "V-Plan module status: "
        + ("**connected** (VPlan.py found)" if VPlan is not None else "**not connected** -- showing placeholder output")
    )


st.title("\U0001F4D1 Specification Toolchain")
st.caption("Extraction \u2192 V-Plan Filtering \u2192 Inconsistency Check \u2192 Quality Check, in one pipeline.")

col_input, col_pipeline, col_results = st.columns([1.05, 1.05, 2.5], gap="large")


# ==========================================================
# COLUMN 1 -- INPUT
# ==========================================================

with col_input:
    with st.container(border=False):
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        panel_header("\U0001F4C1", "INPUT", "blue")

        st.markdown('<div class="section-label">1. Select Files</div>', unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "Choose Files",
            type=["pdf", "json"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            help="Upload the OLD spec first, then the NEW spec. PDFs will be extracted automatically; document.json files are used as-is.",
        )

        active_files = [f for f in (uploaded_files or []) if f.name not in st.session_state.excluded_files]

        st.markdown(
            f'<div class="section-label" style="margin-top:14px">Selected Files ({len(active_files)})</div>',
            unsafe_allow_html=True,
        )

        if not active_files:
            st.caption("No files selected yet.")
        else:
            for f in active_files:
                icon = "\U0001F4C4" if f.name.lower().endswith(".pdf") else "\U0001F5C2\uFE0F"
                row_col, btn_col = st.columns([5, 1])
                with row_col:
                    st.markdown(
                        f"""<div class="file-row">
                        <span>{icon} {f.name}</span>
                        <span style="color:#9ca3af">{human_size(f.size)}</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                with btn_col:
                    if st.button("\u2715", key=f"remove_{f.name}", help="Remove file"):
                        st.session_state.excluded_files.add(f.name)
                        st.rerun()

        st.markdown('<div class="section-label" style="margin-top:14px">2. User Requirement (Natural Language)</div>', unsafe_allow_html=True)
        requirement_text = st.text_area(
            "requirement",
            placeholder="Enter your requirements in natural language...",
            max_chars=2000,
            height=160,
            label_visibility="collapsed",
        )
        st.caption("Describe what information you want to extract, filter, or what inconsistencies you want to check.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="run-btn-wrap">', unsafe_allow_html=True)
        run_clicked = st.button("\u25B6  Run Pipeline", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if len(active_files) != 2 and run_clicked:
            st.error("Please select exactly two files -- an old spec and a new spec -- to run the full pipeline.")

        st.markdown('</div>', unsafe_allow_html=True)


# ==========================================================
# COLUMN 2 -- PIPELINE STEPS
# ==========================================================

done = st.session_state.results is not None

with col_pipeline:
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    step_card(
        "\U0001F4C4", "Extraction",
        "Extract content from the selected files and convert to structured JSON.",
        "blue", "DONE" if done else "PENDING", done,
    )
    step_card(
        "\U0001F53D", "V-Plan Related Material Filter",
        "Filter and extract verification-plan related materials and output as JSON.",
        "green", "DONE" if done else "PENDING", done,
    )
    step_card(
        "\u2696\uFE0F", "Inconsistency Check",
        "Compare documents and identify inconsistencies between versions.",
        "orange", "DONE" if done else "PENDING", done,
    )
    step_card(
        "\U0001F6E1\uFE0F", "Quality Checker",
        "Assess the quality and completeness of extracted data and highlight issues.",
        "purple", "DONE" if done else "PENDING", done,
    )


# ==========================================================
# PIPELINE EXECUTION
# ==========================================================

if run_clicked and len(active_files) == 2:
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            documents, json_paths, pdf_paths = [], [], []

            for label, f in zip(("old", "new"), active_files):
                dest = Path(tmp_dir) / f"{label}_{f.name}"
                dest.write_bytes(f.getvalue())

                if f.name.lower().endswith(".pdf"):
                    if os.environ.get("OPENAI_API_KEY", "").startswith("placeholder"):
                        st.error("Enter your OpenAI API key in the sidebar to extract PDFs, or upload document.json files instead.")
                        st.stop()
                    with st.spinner(f"Extracting {label} PDF (this calls the vision model per figure)..."):
                        document, json_path = run_extraction(str(dest), label)
                    pdf_path = str(dest)
                else:
                    with open(dest, "r", encoding="utf-8") as fh:
                        document = json.load(fh)
                    json_path = str(dest)
                    pdf_path = None

                documents.append(document)
                json_paths.append(json_path)
                pdf_paths.append(pdf_path)

            old_document, new_document = documents
            old_json_path, new_json_path = json_paths
            _, new_pdf_path = pdf_paths

            with st.spinner("Filtering V-Plan related material..."):
                vplan_result, vplan_connected = run_vplan_filter(new_document, requirement_text)

            with st.spinner("Checking for inconsistencies..."):
                changes = run_inconsistency_check(old_document, new_document)

            with st.spinner("Running quality checks..."):
                quality_report = run_quality_check(new_json_path, new_pdf_path)

            # persist artifacts to a stable location so widgets can re-read
            # them across reruns (the TemporaryDirectory above is cleaned up
            # once this block exits)
            persist_dir = Path(tempfile.mkdtemp(prefix="pipeline_results_"))
            old_extract_path = persist_dir / "extraction_old.json"
            new_extract_path = persist_dir / "extraction_new.json"
            vplan_path = persist_dir / "vplan_material.json"
            inconsistency_path = persist_dir / "inconsistencies.json"
            quality_path = persist_dir / "quality_report.json"

            old_extract_path.write_text(json.dumps(old_document, indent=2, ensure_ascii=False), encoding="utf-8")
            new_extract_path.write_text(json.dumps(new_document, indent=2, ensure_ascii=False), encoding="utf-8")
            vplan_path.write_text(json.dumps(vplan_result, indent=2, ensure_ascii=False), encoding="utf-8")
            inconsistency_path.write_text(json.dumps(changes, indent=2, ensure_ascii=False), encoding="utf-8")
            quality_path.write_text(json.dumps(quality_report, indent=2, ensure_ascii=False), encoding="utf-8")

            st.session_state.results = {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "old_document": old_document,
                "new_document": new_document,
                "old_name": active_files[0].name,
                "new_name": active_files[1].name,
                "new_extract_path": str(new_extract_path),
                "new_extract_size": new_extract_path.stat().st_size,
                "vplan_result": vplan_result,
                "vplan_connected": vplan_connected,
                "vplan_path": str(vplan_path),
                "vplan_size": vplan_path.stat().st_size,
                "changes": changes,
                "inconsistency_path": str(inconsistency_path),
                "quality_report": quality_report,
                "quality_path": str(quality_path),
            }
            st.session_state.selected_page = None
            st.rerun()

    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")


# ==========================================================
# COLUMN 3 -- RESULTS
# ==========================================================

with col_results:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    panel_header("\U0001F4C4", "RESULTS", "purple")

    results = st.session_state.results

    if results is None:
        st.info("Select an old and new spec on the left, then click **Run Pipeline** to see results here.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # ---------------- Extraction ----------------
        result_title_row("\U0001F4C4", "Extraction Result", "blue", "/results/" + Path(results["new_extract_path"]).name)
        preview_col, meta_col = st.columns([2.4, 1.3])
        with preview_col:
            st.caption("Extracted JSON File Preview (new document)")
            st.code(json.dumps(results["new_document"], indent=2, ensure_ascii=False)[:1200] + "\n...", language="json")
        with meta_col:
            meta_box([
                ("File Name", Path(results["new_extract_path"]).name),
                ("File Size", human_size(results["new_extract_size"])),
                ("Total Pages", results["new_document"].get("total_pages", "?")),
                ("Generated At", results["generated_at"]),
            ])

        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

        # ---------------- V-Plan filter ----------------
        result_title_row("\U0001F53D", "V-Plan Related Material Filter Result", "green", "/results/" + Path(results["vplan_path"]).name)
        if not results["vplan_connected"]:
            st.markdown(
                "<div class='placeholder-banner'>\u26A0\uFE0F VPlan.py hasn't been added to the project yet -- "
                "this is a placeholder preview built from tagged sections in the extracted JSON. "
                "Drop in a <code>VPlan.py</code> exposing <code>filter_material(document, requirement_text)</code> "
                "to replace this with real output.</div>",
                unsafe_allow_html=True,
            )
        preview_col2, meta_col2 = st.columns([2.4, 1.3])
        with preview_col2:
            st.caption("Filtered JSON File Preview")
            st.code(json.dumps(results["vplan_result"], indent=2, ensure_ascii=False)[:1200], language="json")
        with meta_col2:
            meta_box([
                ("File Name", Path(results["vplan_path"]).name),
                ("File Size", human_size(results["vplan_size"])),
                ("Total Items", results["vplan_result"].get("metadata", {}).get("total_items", "?")),
                ("Generated At", results["generated_at"]),
            ])

        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

        # ---------------- Inconsistency check ----------------
        result_title_row("\u2696\uFE0F", "Inconsistency Check Result", "orange", "/results/" + Path(results["inconsistency_path"]).name)

        changes = results["changes"]
        # page identifiers can come through as either int or str depending on
        # which part of Comparator produced the change -- normalise to str so
        # "1" and 1 don't become two distinct (but identically-labelled) entries
        pages_with_changes = sorted(
            {str(c["page"]) for c in changes if c.get("page") not in (None, "")},
            key=lambda v: (int(v) if v.isdigit() else float("inf"), v),
        )

        if not changes:
            st.success("No differences were found between the old and new document.")
        elif not pages_with_changes:
            st.info(f"{len(changes)} change(s) found, but none are tied to a specific page (see metadata/section-level changes below).")
            with st.expander("View non-page-specific changes"):
                st.json(changes[:50])
        else:
            list_col, diff_col, legend_col = st.columns([1, 2.6, 1])

            with list_col:
                st.markdown("<div class='section-label'>Pages with Inconsistencies</div>", unsafe_allow_html=True)
                if st.session_state.selected_page not in pages_with_changes:
                    st.session_state.selected_page = pages_with_changes[0]
                for p in pages_with_changes:
                    is_active = p == st.session_state.selected_page
                    arrow = "\u25B8 " if is_active else ""
                    label = f"{arrow}Page {p}"
                    if st.button(label, key=f"page_btn_{p}", use_container_width=True):
                        st.session_state.selected_page = p
                        st.rerun()

            selected_page = st.session_state.selected_page

            old_pages = {p.get("page_number"): p.get("text", "") for p in results["old_document"].get("pages", [])}
            new_pages = {p.get("page_number"): p.get("text", "") for p in results["new_document"].get("pages", [])}

            with diff_col:
                st.markdown(f"<div class='section-label'>Differences for Page {selected_page}</div>", unsafe_allow_html=True)
                try:
                    page_num = int(selected_page)
                except (TypeError, ValueError):
                    page_num = None

                old_text = old_pages.get(page_num, "")
                new_text = new_pages.get(page_num, "")
                old_html, new_html = render_word_diff(old_text, new_text)

                sub_old, sub_new = st.columns(2)
                with sub_old:
                    st.markdown(f"<div class='diff-pane-header'>Original ({results['old_name']})</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='diff-pane'>{old_html or '<i>No text on this page.</i>'}</div>", unsafe_allow_html=True)
                with sub_new:
                    st.markdown(f"<div class='diff-pane-header'>New Version ({results['new_name']})</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='diff-pane'>{new_html or '<i>No text on this page.</i>'}</div>", unsafe_allow_html=True)

            with legend_col:
                st.markdown(
                    """<div class="legend-box">
                    <div class="legend-title">LEGEND</div>
                    <div class="legend-row"><span class="legend-swatch" style="background:#fecaca"></span>Removed</div>
                    <div class="legend-row"><span class="legend-swatch" style="background:#bbf7d0"></span>Added</div>
                    <div class="legend-row"><span class="legend-swatch" style="background:#fde68a"></span>Modified</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            with st.expander(f"All {len(changes)} tracked changes"):
                st.dataframe(changes, use_container_width=True)

        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

        # ---------------- Quality checker ----------------
        result_title_row("\U0001F6E1\uFE0F", "Quality Checker Result", "purple", "/results/" + Path(results["quality_path"]).name)

        report = results["quality_report"]
        scores = report["scores"]

        gauge_col, stats_col, issues_col = st.columns([1, 2, 1.4])

        with gauge_col:
            st.markdown("<div class='section-label' style='text-align:center'>Quality Overview</div>", unsafe_allow_html=True)
            gauge(report["overall_percentage"], "100")

        with stats_col:
            st.markdown("<br>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            score_defs = [
                ("Completeness", scores.get("completeness", {}).get("percentage", 0)),
                ("Accuracy (vs. source)", scores.get("accuracy", {}).get("percentage", 0)),
                ("Table & Figure Capture", scores.get("table_figure_capture", {}).get("percentage", 0)),
            ]
            for box, (label, pct) in zip((b1, b2, b3), score_defs):
                with box:
                    stat_bar(label, pct, score_color(pct))

        with issues_col:
            st.markdown("<div class='section-label'>Top Issues</div>", unsafe_allow_html=True)
            issues = []
            for score_name, score_data in scores.items():
                for detail_name, detail_value in score_data.get("details", {}).items():
                    if detail_value < report["inputs"]["threshold"]:
                        friendly = detail_name.replace("_score", "").replace("_", " ").title()
                        severity = "\U0001F534" if detail_value < 60 else "\u26A0\uFE0F"
                        issues.append((severity, friendly, detail_value))
            issues.sort(key=lambda x: x[2])
            if not issues:
                st.markdown("<div class='issue-row'>\u2705 No issues above the threshold.</div>", unsafe_allow_html=True)
            else:
                for severity, friendly, value in issues[:6]:
                    st.markdown(
                        f"<div class='issue-row'><span class='issue-icon'>{severity}</span>"
                        f"<span>{friendly} <span style='color:#9ca3af'>({value:.0f}%)</span></span></div>",
                        unsafe_allow_html=True,
                    )
            with st.expander("View Full Report"):
                st.json(report)

        st.markdown('</div>', unsafe_allow_html=True)
