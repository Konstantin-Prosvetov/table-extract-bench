"""The scoring rubric.

Five criteria, each with an explicit definition and a concrete measurement
procedure. This module is the "methodology" of the benchmark — the README
describes it in prose, this file is the ground truth for how it is actually
computed.

Criteria
--------

cell_recall
    Definition: the fraction of non-empty ground-truth cells whose value was
    found *somewhere* in the tool's output, regardless of position.
    Measurement: normalize every ground-truth and extracted cell (collapse
    whitespace, casefold), then greedily match each ground-truth cell against
    the pool of extracted cells — exact match first, then fuzzy match
    (difflib ratio >= FUZZY_THRESHOLD) to tolerate OCR noise. Each extracted
    cell can satisfy at most one ground-truth cell (consumed on match), so
    duplicate values can't inflate the score.

value_accuracy
    Definition: of the ground-truth cells that were found at all (recall),
    the fraction that were found as an *exact* normalized match rather than
    a fuzzy one. This separates "did the tool see this value" from "did it
    transcribe it correctly" — a tool can have high recall and low accuracy
    if it reliably locates cells but OCR-garbles their content.
    Measurement: exact_matches / (exact_matches + fuzzy_matches).

structure_score
    Definition: how closely the extracted table's shape (row count, column
    count) matches the ground truth, averaged over rows and columns.
    Measurement: 1 - min(|extracted - ground_truth| / ground_truth, 1) for
    rows and for columns, then averaged. Row/column counts are summed across
    all tables the tool returned for that document (so a table incorrectly
    split into two pieces is still comparable).

extraction_success
    Definition: whether the tool returned at least one non-empty table
    without raising an exception.
    Measurement: boolean, recorded regardless of the other scores (a tool
    that crashes gets 0 on everything else, but the crash itself is a
    distinct, reportable fact).

runtime_sec
    Definition: wall-clock time for the extraction call on that document.
    Measurement: time.perf_counter() around the call, single run (see
    README limitations — this is not a statistically robust benchmark of
    speed, just an order-of-magnitude signal).

See the README's "what this methodology does not measure" section for the
rubric's known blind spots (position-independence of cell_recall being the
main one).
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.85


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def cell_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def score_extraction(extracted_tables: list[list[list[str]]], gt_rows: list[list[str]]) -> dict:
    gt_cells = [normalize(c) for row in gt_rows for c in row if normalize(c)]
    total_gt = len(gt_cells)

    pool = [normalize(c) for t in extracted_tables for row in t for c in row if normalize(c)]

    exact_matches = 0
    fuzzy_matches = 0
    for gt_c in gt_cells:
        if gt_c in pool:
            pool.remove(gt_c)
            exact_matches += 1
            continue
        best_idx, best_ratio = None, 0.0
        for idx, cand in enumerate(pool):
            r = cell_similarity(gt_c, cand)
            if r > best_ratio:
                best_ratio, best_idx = r, idx
        if best_idx is not None and best_ratio >= FUZZY_THRESHOLD:
            pool.pop(best_idx)
            fuzzy_matches += 1

    found = exact_matches + fuzzy_matches
    cell_recall = found / total_gt if total_gt else 1.0
    value_accuracy = exact_matches / found if found else 0.0

    gt_n_rows = len(gt_rows)
    gt_n_cols = max((len(r) for r in gt_rows), default=0)
    ext_n_rows = sum(len(t) for t in extracted_tables)
    ext_n_cols = max((len(r) for t in extracted_tables for r in t), default=0)

    row_ratio = (1 - min(abs(ext_n_rows - gt_n_rows) / gt_n_rows, 1)) if gt_n_rows else 0.0
    col_ratio = (1 - min(abs(ext_n_cols - gt_n_cols) / gt_n_cols, 1)) if gt_n_cols else 0.0
    structure_score = (row_ratio + col_ratio) / 2

    return {
        "extraction_success": bool(extracted_tables) and total_gt > 0 and found > 0,
        "cell_recall": round(cell_recall, 3),
        "value_accuracy": round(value_accuracy, 3),
        "structure_score": round(structure_score, 3),
        "exact_matches": exact_matches,
        "fuzzy_matches": fuzzy_matches,
        "total_gt_cells": total_gt,
        "n_extracted_tables": len(extracted_tables),
        "extracted_rows": ext_n_rows,
        "extracted_cols": ext_n_cols,
        "gt_rows": gt_n_rows,
        "gt_cols": gt_n_cols,
    }
