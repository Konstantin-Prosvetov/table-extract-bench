#!/usr/bin/env python3
"""Generate the synthetic PDF fixtures and matching ground truth for the benchmark.

All content is invented. No data, names, or addresses from any real source
are used anywhere in this repository.

Usage:
    python scripts/generate_pdfs.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs"
GT_DIR = ROOT / "ground_truth"
PDF_DIR.mkdir(exist_ok=True)
GT_DIR.mkdir(exist_ok=True)

random.seed(42)

BASIC_STYLE = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
])

NO_GRID_STYLE = TableStyle([
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LEFTPADDING", (0, 0), (-1, -1), 10),
])


def save_gt(case_id: str, rows: list[list[str]], **meta):
    gt = {"id": case_id, "n_rows": len(rows), "n_cols": len(rows[0]) if rows else 0, "rows": rows, **meta}
    (GT_DIR / f"{case_id}.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")


def build_simple_doc(path: Path, table_rows, style=BASIC_STYLE, colwidths=None, pagesize=A4):
    doc = SimpleDocTemplate(str(path), pagesize=pagesize,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    t = Table(table_rows, colWidths=colwidths)
    t.setStyle(style)
    doc.build([t])


# ---------------------------------------------------------------------------
# 01 — clean table, full grid, single page
# ---------------------------------------------------------------------------
def case_01_clean_borders():
    header = ["Lot ID", "District", "Unit Type", "Area (m2)", "Price (USD)", "Status"]
    districts = ["Riverside", "Northgate", "Old Quarter", "Lakeview", "Hillcrest"]
    units = ["Studio", "1BR", "2BR", "3BR", "Penthouse"]
    statuses = ["Available", "Reserved", "Sold"]
    rows = [header]
    for i in range(1, 13):
        rows.append([
            f"LOT-{i:03d}",
            random.choice(districts),
            random.choice(units),
            str(random.randint(28, 180)),
            f"{random.randint(45, 620) * 1000:,}",
            random.choice(statuses),
        ])
    case_id = "01_clean_borders"
    build_simple_doc(PDF_DIR / f"{case_id}.pdf", rows)
    save_gt(case_id, rows, description="Clean single table, full grid lines, one page, plain English headers.")
    return case_id


# ---------------------------------------------------------------------------
# 02 — borderless table (whitespace-aligned, no ruling lines)
# ---------------------------------------------------------------------------
def case_02_borderless():
    header = ["Project", "City", "Buyers", "Avg. Price/m2"]
    rows = [header]
    projects = ["Sunview Towers", "Emerald Court", "Harbor Point", "Cedar Residences",
                "Palm Grove", "Skyline Plaza", "Willow Creek", "Marina Bay Homes"]
    cities = ["Coastal City", "Highland Town", "Delta City"]
    rows_data = rows[:]
    for p in projects:
        rows.append([p, random.choice(cities), str(random.randint(3, 210)),
                     f"{random.randint(900, 4200)}"])
    case_id = "02_borderless"
    build_simple_doc(PDF_DIR / f"{case_id}.pdf", rows, style=NO_GRID_STYLE)
    save_gt(case_id, rows, description="Table with no ruling lines at all — columns separated only by whitespace.")
    return case_id


# ---------------------------------------------------------------------------
# 03 — merged header cells (SPAN)
# ---------------------------------------------------------------------------
def case_03_merged_cells():
    rows = [
        ["Project", "Q1 2026", "", "Q2 2026", ""],
        ["", "Units Sold", "Revenue (k$)", "Units Sold", "Revenue (k$)"],
        ["Sunview Towers", "14", "980", "19", "1,340"],
        ["Emerald Court", "8", "560", "11", "790"],
        ["Harbor Point", "22", "1,650", "17", "1,190"],
        ["Cedar Residences", "5", "310", "9", "605"],
        ["Palm Grove", "12", "845", "14", "990"],
    ]
    case_id = "03_merged_cells"
    style = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (3, 0), (4, 0)),
        ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#dddddd")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    build_simple_doc(PDF_DIR / f"{case_id}.pdf", rows, style=style)
    # ground truth: logical (flattened) header for scoring purposes
    logical = [
        ["Project", "Q1 2026 Units Sold", "Q1 2026 Revenue (k$)", "Q2 2026 Units Sold", "Q2 2026 Revenue (k$)"],
        ["Sunview Towers", "14", "980", "19", "1,340"],
        ["Emerald Court", "8", "560", "11", "790"],
        ["Harbor Point", "22", "1,650", "17", "1,190"],
        ["Cedar Residences", "5", "310", "9", "605"],
        ["Palm Grove", "12", "845", "14", "990"],
    ]
    save_gt(case_id, logical, description="Two-level merged header (SPAN across quarter, sub-columns for metric); "
                                           "one merged row label spanning the header block.",
            raw_rows=rows)
    return case_id


# ---------------------------------------------------------------------------
# 04 — multi-row (wrapped) header, no merges, just long header text
# ---------------------------------------------------------------------------
def case_04_multirow_header():
    header = ["Unit\nCode", "Floor\nLevel", "Area\n(m2)", "Price per m2\n(USD)", "Contract\nDate", "Buyer\nNationality"]
    rows = [header]
    nats = ["Domestic", "Foreign - Region A", "Foreign - Region B", "Foreign - Region C"]
    for i in range(1, 11):
        rows.append([
            f"U-{i:03d}", str(random.randint(2, 28)), str(random.randint(35, 140)),
            str(random.randint(900, 3600)), f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            random.choice(nats),
        ])
    case_id = "04_multirow_header"
    build_simple_doc(PDF_DIR / f"{case_id}.pdf", rows)
    flat_header = [h.replace("\n", " ") for h in header]
    save_gt(case_id, [flat_header] + rows[1:],
            description="Header cells wrap onto two lines within a single header row (no SPAN, just \\n in text).")
    return case_id


# ---------------------------------------------------------------------------
# 05 — rotated page (page /Rotate = 90, content laid out for landscape read)
# ---------------------------------------------------------------------------
def case_05_rotated_page():
    header = ["Building", "Wing", "Units", "Occupied", "Vacant", "Occupancy %"]
    rows = [header]
    buildings = ["Tower A", "Tower B", "Tower C", "Tower D", "Tower E", "Tower F", "Tower G"]
    for b in buildings:
        units = random.randint(40, 160)
        occ = random.randint(10, units)
        rows.append([b, random.choice(["North", "South", "East", "West"]), str(units), str(occ),
                     str(units - occ), f"{occ/units*100:.1f}"])
    case_id = "05_rotated_page"
    tmp_path = PDF_DIR / f"_tmp_{case_id}.pdf"
    build_simple_doc(tmp_path, rows, pagesize=landscape(A4))
    # Re-open and set the page /Rotate flag to 90, simulating a real-world
    # "rotated scan" PDF where the content stream is untouched but the
    # viewer/consumer must account for page.rotation.
    doc = fitz.open(str(tmp_path))
    page = doc[0]
    page.set_rotation(90)
    doc.save(PDF_DIR / f"{case_id}.pdf")
    doc.close()
    tmp_path.unlink()
    save_gt(case_id, rows, description="Landscape table with page /Rotate=90 set (text stream unchanged, "
                                        "page displayed rotated — tests whether extractors honor page rotation).")
    return case_id


# ---------------------------------------------------------------------------
# 06 — scanned page, no text layer (image-only PDF)
# ---------------------------------------------------------------------------
def _render_table_to_image(rows, style=BASIC_STYLE, pagesize=A4, dpi=200) -> Image.Image:
    tmp_path = PDF_DIR / "_tmp_render.pdf"
    build_simple_doc(tmp_path, rows, style=style, pagesize=pagesize)
    doc = fitz.open(str(tmp_path))
    pix = doc[0].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    tmp_path.unlink()
    return img


def _image_only_pdf(img: Image.Image, out_path: Path, dpi: int):
    # Page size must be in points (1/72 inch), not pixels — convert using
    # the dpi the image was actually rendered at, or the page ends up
    # physically enormous and re-rasterizing it (e.g. via pdf2image at a
    # normal dpi) produces a huge, sparse image that breaks OCR page
    # segmentation for reasons unrelated to image quality.
    width_pt = img.width * 72 / dpi
    height_pt = img.height * 72 / dpi
    img.save(out_path.with_suffix(".png"))
    doc = fitz.open()
    rect = fitz.Rect(0, 0, width_pt, height_pt)
    page = doc.new_page(width=width_pt, height=height_pt)
    page.insert_image(rect, filename=str(out_path.with_suffix(".png")))
    doc.save(out_path)
    doc.close()
    out_path.with_suffix(".png").unlink()


def case_06_scanned_no_text():
    header = ["Ref", "Location", "Type", "Size (m2)", "Value (USD)"]
    rows = [header]
    for i in range(1, 9):
        rows.append([f"REF-{i:02d}", random.choice(["Block A", "Block B", "Block C"]),
                     random.choice(["Flat", "Duplex", "Studio"]),
                     str(random.randint(30, 150)), f"{random.randint(40, 400) * 1000:,}"])
    case_id = "06_scanned_no_text"
    dpi = 200
    img = _render_table_to_image(rows, dpi=dpi)
    _image_only_pdf(img, PDF_DIR / f"{case_id}.pdf", dpi=dpi)
    save_gt(case_id, rows, description="Same table rendered to a bitmap and embedded as an image-only PDF page — "
                                        "no text layer at all, requires OCR.")
    return case_id


# ---------------------------------------------------------------------------
# 07 — noisy / low-quality scan (blur + grain + slight skew)
# ---------------------------------------------------------------------------
def case_07_scanned_noisy():
    header = ["Ref", "Location", "Type", "Size (m2)", "Value (USD)"]
    rows = [header]
    for i in range(1, 9):
        rows.append([f"REF-{i:02d}", random.choice(["Block D", "Block E", "Block F"]),
                     random.choice(["Flat", "Duplex", "Studio"]),
                     str(random.randint(30, 150)), f"{random.randint(40, 400) * 1000:,}"])
    case_id = "07_scanned_noisy"
    dpi = 150
    img = _render_table_to_image(rows, dpi=dpi)
    img = img.rotate(1.6, expand=True, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(radius=1.1))
    noise = Image.effect_noise(img.size, 28).convert("L").convert("RGB")
    img = Image.blend(img, noise, alpha=0.12)
    _image_only_pdf(img, PDF_DIR / f"{case_id}.pdf", dpi=dpi)
    save_gt(case_id, rows, description="Degraded scan: slight skew, Gaussian blur and grain layered on top of the "
                                        "rendered table image — simulates a poor photocopy/fax-quality source.")
    return case_id


# ---------------------------------------------------------------------------
# 08 — one logical table split across two pages
# ---------------------------------------------------------------------------
def case_08_two_pages():
    header = ["Entry", "Project", "District", "Contract No.", "Date"]
    rows = [header]
    for i in range(1, 23):
        rows.append([str(i), random.choice(["Sunview Towers", "Emerald Court", "Harbor Point"]),
                     random.choice(["Riverside", "Northgate", "Lakeview"]),
                     f"CT-{2025000+i}", f"2025-{random.randint(1,12):02d}-{random.randint(1,28):02d}"])
    case_id = "08_table_two_pages"
    doc = SimpleDocTemplate(str(PDF_DIR / f"{case_id}.pdf"), pagesize=A4,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    split_at = 13  # header + 12 rows on page 1, header repeated + rest on page 2
    t1 = Table(rows[:split_at])
    t1.setStyle(BASIC_STYLE)
    t2 = Table([header] + rows[split_at:])
    t2.setStyle(BASIC_STYLE)
    doc.build([t1, PageBreak(), t2])
    save_gt(case_id, rows, description="Logical table split across two pages; header row is repeated at the top "
                                        "of page 2 (as is common in real exports).",
            spans_pages=True, header_repeated_on_page_2=True)
    return case_id


# ---------------------------------------------------------------------------
# 09 — mixed languages / scripts in the same table
# ---------------------------------------------------------------------------
def case_09_mixed_languages():
    header = ["Mã căn", "Project", "国籍 (Nationality)", "Diện tích (m2)", "Giá (USD)"]
    rows = [header,
            ["A-101", "Sunview Towers", "Hàn Quốc", "68", "142,000"],
            ["A-102", "Sunview Towers", "中国", "75", "158,500"],
            ["B-204", "Emerald Court", "Việt Nam", "54", "98,000"],
            ["B-207", "Emerald Court", "日本", "82", "171,200"],
            ["C-310", "Harbor Point", "Singapore", "61", "121,900"],
            ["C-315", "Harbor Point", "Đài Loan", "70", "139,400"],
            ]
    case_id = "09_mixed_languages"
    build_simple_doc(PDF_DIR / f"{case_id}.pdf", rows)
    save_gt(case_id, rows, description="Vietnamese diacritics, Chinese and Japanese script mixed with Latin text "
                                        "in the same table.")
    return case_id


# ---------------------------------------------------------------------------
# 10 — sparse table with genuinely empty cells
# ---------------------------------------------------------------------------
def case_10_sparse_empty_cells():
    header = ["Unit", "Buyer Type", "Mortgage Bank", "Notary Date", "Notes"]
    rows = [header,
            ["U-01", "Individual", "Bank A", "2025-03-11", ""],
            ["U-02", "Individual", "", "2025-03-14", "Cash purchase"],
            ["U-03", "Corporate", "Bank B", "", ""],
            ["U-04", "Individual", "Bank A", "2025-04-02", ""],
            ["U-05", "Corporate", "", "", "Pending documents"],
            ["U-06", "Individual", "Bank C", "2025-04-19", ""],
            ]
    case_id = "10_sparse_empty_cells"
    build_simple_doc(PDF_DIR / f"{case_id}.pdf", rows)
    save_gt(case_id, rows, description="Table with genuinely empty cells (missing mortgage bank / date / notes) — "
                                        "tests whether extractors keep column alignment when cells are blank.")
    return case_id


CASES = [
    case_01_clean_borders,
    case_02_borderless,
    case_03_merged_cells,
    case_04_multirow_header,
    case_05_rotated_page,
    case_06_scanned_no_text,
    case_07_scanned_noisy,
    case_08_two_pages,
    case_09_mixed_languages,
    case_10_sparse_empty_cells,
]


def main():
    generated = []
    for fn in CASES:
        case_id = fn()
        generated.append(case_id)
        print(f"generated {case_id}")
    print(f"\n{len(generated)} PDF fixtures written to {PDF_DIR}")
    print(f"{len(generated)} ground-truth files written to {GT_DIR}")


if __name__ == "__main__":
    main()
