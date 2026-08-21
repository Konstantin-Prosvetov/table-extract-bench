"""Thin, uniform wrappers around each extraction tool.

Every wrapper returns the same shape regardless of the underlying library:
``list[Table]`` where ``Table = list[list[str]]`` (rows of cell strings,
``""`` for an empty cell). That common shape is what :mod:`tebench.metrics`
scores against the ground truth.

Wrappers must never raise: extraction failures are caught and reported as
zero tables, because "the tool crashed on this input" is itself a result
worth recording, not a benchmark bug.
"""
from __future__ import annotations

from pathlib import Path

Table = list  # list[list[str]]


def _clean_row(row) -> list[str]:
    return [("" if c is None else str(c)).strip() for c in row]


def extract_pdfplumber(pdf_path: Path) -> list[Table]:
    import pdfplumber

    tables: list[Table] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                for t in page.extract_tables():
                    tables.append([_clean_row(r) for r in t])
    except Exception:
        return []
    return tables


def extract_camelot(pdf_path: Path, flavor: str = "lattice") -> list[Table]:
    import camelot

    try:
        result = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)
    except Exception:
        return []
    tables: list[Table] = []
    for t in result:
        try:
            tables.append([_clean_row(r) for r in t.df.values.tolist()])
        except Exception:
            continue
    return tables


# --- OCR path -----------------------------------------------------------
#
# pytesseract on its own only returns a flat bag of words with bounding
# boxes — it has no notion of "table". The reconstruction below clusters
# words into rows by vertical proximity and into columns by horizontal
# proximity, which is a simple but real approach to recovering grid
# structure from OCR output (as opposed to a canned table-OCR product).

def extract_ocr(pdf_path: Path, lang: str = "eng+vie", dpi: int = 200) -> list[Table]:
    # 200 dpi, not 300: at 300 dpi tesseract's automatic page-segmentation
    # (psm 3) reliably finds zero text blocks on a small table centered on
    # an otherwise-blank A4 page, even though the glyphs themselves render
    # cleanly (verified by cropping and re-OCRing the same region in
    # isolation). 150-200 dpi segments correctly. This is a real, reportable
    # OCR-harness finding, not a rendering bug — see README.
    from pdf2image import convert_from_path
    import pytesseract

    try:
        pages = convert_from_path(str(pdf_path), dpi=dpi)
    except Exception:
        return []

    tables: list[Table] = []
    for page_img in pages:
        try:
            data = pytesseract.image_to_data(page_img, lang=lang, output_type=pytesseract.Output.DATAFRAME)
        except Exception:
            continue
        data = data.dropna(subset=["text"])
        data = data[data["text"].str.strip() != ""]
        if data.empty:
            continue
        grid = _reconstruct_grid(data)
        if grid:
            tables.append(grid)
    return tables


def _reconstruct_grid(data) -> Table:
    words = data.to_dict("records")
    if not words:
        return []
    words.sort(key=lambda w: (w["top"], w["left"]))

    row_thresh = max(float(data["height"].median()) * 0.7, 5.0)
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    current_top = None
    for w in words:
        if current_top is None or abs(w["top"] - current_top) <= row_thresh:
            current_row.append(w)
            current_top = w["top"] if current_top is None else (current_top + w["top"]) / 2
        else:
            rows.append(current_row)
            current_row = [w]
            current_top = w["top"]
    if current_row:
        rows.append(current_row)

    x_centers = sorted(w["left"] + w["width"] / 2 for w in words)
    col_bounds = _cluster_1d(x_centers)
    if not col_bounds:
        return []

    grid: list[list[str]] = []
    for row in rows:
        row.sort(key=lambda w: w["left"])
        cells = [""] * len(col_bounds)
        for w in row:
            xc = w["left"] + w["width"] / 2
            col_idx = _assign_column(xc, col_bounds)
            cells[col_idx] = (cells[col_idx] + " " + str(w["text"])).strip()
        grid.append(cells)
    return grid


def _cluster_1d(values: list[float], gap_ratio: float = 2.5) -> list[float]:
    if not values:
        return []
    gaps = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
    threshold = max(median_gap * gap_ratio, 20.0)
    clusters = [[values[0]]]
    for v in values[1:]:
        if v - clusters[-1][-1] <= threshold:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _assign_column(x: float, col_bounds: list[float]) -> int:
    best_idx, best_dist = 0, float("inf")
    for i, cb in enumerate(col_bounds):
        d = abs(x - cb)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


EXTRACTORS = {
    "pdfplumber": lambda p: extract_pdfplumber(p),
    "camelot-lattice": lambda p: extract_camelot(p, flavor="lattice"),
    "camelot-stream": lambda p: extract_camelot(p, flavor="stream"),
    "ocr-tesseract": lambda p: extract_ocr(p),
}
