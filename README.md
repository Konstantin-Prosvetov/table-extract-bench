# table-extract-bench

A methodology-first comparison of PDF table extraction approaches: `pdfplumber`,
`camelot` (lattice and stream flavors), and an OCR path built on `pytesseract`.

This is not a leaderboard. The output is not "X is the best tool" — it's a
rubric, a reproducible run of that rubric against a controlled set of PDFs,
and an honest account of where each tool breaks. If you need to pick a tool
for a specific kind of document, the per-case breakdown below is the useful
part; the aggregate numbers are not.

## Why this exists

Extraction tool comparisons online are almost always "I ran tool X on my PDF
and it worked/didn't." That tells you nothing about *why*, and nothing about
whether it generalizes to your documents. This repo instead:

1. Builds a small, controlled set of synthetic PDFs, each isolating one
   specific structural difficulty (merged cells, no ruling lines, a scan with
   no text layer, a table split across pages, ...).
2. Defines what "correct extraction" means for each of them, upfront, as
   ground truth.
3. Scores every tool against every fixture with the same rubric.
4. Reports where each tool's score comes from — not just the number.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

System dependencies (not pip-installable):
- **Ghostscript** (`gs`) — required by `camelot`.
- **poppler-utils** (`pdftoppm`, used via `pdf2image`) — required by the OCR path.
- **Tesseract OCR** with the `eng`, `vie`, and `chi_sim` language packs —
  required by the OCR path (fixture 9 mixes English, Vietnamese, and Chinese).

On Debian/Ubuntu:
```bash
apt-get install ghostscript poppler-utils tesseract-ocr tesseract-ocr-vie tesseract-ocr-chi-sim
```

`tabula-py` is **not** included — see "What this methodology does not
measure" below for why, and what that leaves untested.

## Reproducing

```bash
python scripts/generate_pdfs.py   # writes pdfs/ and ground_truth/ (deterministic, seed=42)
python scripts/run_benchmark.py   # writes results/results.csv and results/results.md
pytest tests/                     # unit tests for the scoring logic itself
```

The PDFs and results in this repo are already generated and committed, so
you don't need to run anything to read the results — only to reproduce or
extend them.

## The fixtures

10 synthetic, single-purpose PDFs in `pdfs/`, each with hand-authored ground
truth in `ground_truth/`. All content (project names, prices, IDs) is
invented for this benchmark — nothing here comes from a real document.

| id | what it stresses |
|---|---|
| `01_clean_borders` | Baseline: full grid lines, single page, plain English. |
| `02_borderless` | No ruling lines at all — columns exist only as whitespace alignment. |
| `03_merged_cells` | A two-level header built with real cell spans (`SPAN` in the PDF, not just visual alignment). |
| `04_multirow_header` | Header cells wrap onto two lines (`\n` inside the cell), no spans involved. |
| `05_rotated_page` | Landscape content with the page's `/Rotate` flag set to 90 — content stream is untouched, only the display rotation differs (this is how real "sideways scanned" PDFs usually work). |
| `06_scanned_no_text` | The clean table rendered to a bitmap and re-embedded as an image-only PDF page — no text layer, OCR is the only path in. |
| `07_scanned_noisy` | Same idea as 06, degraded with a slight skew, Gaussian blur, and grain — simulates a poor photocopy/fax-quality scan. |
| `08_table_two_pages` | One logical table split across two pages, header row repeated on page 2 (as real exports commonly do). |
| `09_mixed_languages` | Vietnamese diacritics, Chinese, and Japanese script mixed with Latin text in the same table. |
| `10_sparse_empty_cells` | Genuinely empty cells (missing values), testing whether column alignment survives blanks. |

## The rubric

Full definitions and the exact computation live in
[`src/tebench/metrics.py`](src/tebench/metrics.py) (each metric's docstring
*is* its specification — this section is the prose version).

- **cell_recall** — of the ground-truth cells with a value, what fraction
  did the tool capture *somewhere* in its output (position not considered)?
  Matching is exact-first, then fuzzy (`difflib` ratio ≥ 0.85) to tolerate
  OCR noise; each extracted cell can satisfy at most one ground-truth cell,
  so an extractor can't inflate its score by repeating values.
- **value_accuracy** — of the cells that were found at all, what fraction
  were an *exact* match rather than a fuzzy one? This separates "did the
  tool see this value" from "did it transcribe it correctly."
- **structure_score** — how close the extracted table's row/column counts
  are to the ground truth's, averaged over rows and columns. A crude but
  explicit shape check.
- **extraction_success** — did the tool return anything at all, without
  raising? Recorded independently of the score, because a clean crash is a
  different failure mode than a low score.
- **runtime_sec** — wall-clock time for one extraction call, one run. Not a
  speed benchmark (see limitations) — an order-of-magnitude signal only.

## Results

Full tables: [`results/results.md`](results/results.md) /
[`results/results.csv`](results/results.csv) (auto-generated by
`scripts/run_benchmark.py`, do not hand-edit). Summary of `cell_recall`:

| case | pdfplumber | camelot-lattice | camelot-stream | ocr-tesseract |
|---|---|---|---|---|
| 01_clean_borders | 1.00 | 1.00 | 1.00 | 0.92 |
| 02_borderless | 0.00 | 0.00 | 1.00 | 0.53 |
| 03_merged_cells | 0.87 | 0.87 | 0.87 | 0.70 |
| 04_multirow_header | 1.00 | 1.00 | 0.91 | 0.64 |
| 05_rotated_page | 1.00 | 1.00 | 1.00 | 0.88 |
| 06_scanned_no_text | 0.00 | 0.00 | 0.00 | 0.91 |
| 07_scanned_noisy | 0.00 | 0.00 | 0.00 | 0.00 |
| 08_table_two_pages | 1.00 | 1.00 | 1.00 | 0.80 |
| 09_mixed_languages | 0.91 | 0.94 | 0.94 | 0.60 |
| 10_sparse_empty_cells | 1.00 | 1.00 | 1.00 | 0.67 |

### What actually happened, case by case

- **Clean, ruled tables (01, 04, 08, 10):** `pdfplumber` and both `camelot`
  flavors are effectively interchangeable — near-perfect recall, accuracy,
  and structure. This is the case every tool is designed for; it's not a
  differentiator.
- **No ruling lines (02):** `pdfplumber`'s default table-detection and
  `camelot-lattice` both require visible lines to find cell boundaries —
  they return nothing (`cell_recall = 0.00`), not a partial result.
  `camelot-stream`, which infers columns from text alignment instead of
  lines, handles it perfectly. This is the clearest tool-selection signal in
  the whole set: **if a document has no ruling lines, lattice-family methods
  are not a "worse option," they are not an option.**
- **Merged header cells (03):** all three PDF-native paths land at the same
  `cell_recall = 0.87` and `value_accuracy = 1.00` — they capture the merged
  cell's text once rather than once per spanned column, so cells that should
  logically repeat (e.g. a quarter label over two sub-columns) come back
  missing on one side. None of the three "solves" spans; they just don't
  corrupt the values they do get.
- **Page rotation (05):** `camelot` (both flavors) and `pdfplumber` all
  extract full, correct content — `pdfplumber`'s `structure_score` dips to
  0.71 purely because its row/column count differs slightly from ground
  truth, not because values were wrong (`value_accuracy = 1.00`). All three
  correctly account for the page's `/Rotate` flag; this was not guaranteed
  going in.
- **Scans (06, 07):** `pdfplumber` and `camelot` score exactly `0.00` on
  both — expected, they operate on the PDF's text layer and there isn't
  one. OCR is the only path that produces anything. On the clean scan (06)
  it recovers 91% of cells at 85% accuracy. On the degraded scan (07) it
  gets **zero** — not a low score, an empty result. That's not a rendering
  problem (see next section): Tesseract's default automatic page
  segmentation (`psm=3`) found *no text blocks at all* on the blurred,
  slightly skewed, grainy version, even though the same region, cropped and
  OCR'd in isolation, is still legible. Forcing a fixed single-block mode
  (`psm=6`) does recover partial, still-garbled text — the content isn't
  destroyed, but the default configuration gives up on it. **A noisy scan
  doesn't just degrade OCR accuracy — it can make automatic segmentation
  fail outright**, which is a distinct failure mode from "OCR made
  mistakes."
- **Mixed languages (09):** `camelot` edges `pdfplumber` on recall (0.94 vs
  0.91), and OCR trails badly at 0.60 — Vietnamese diacritics and CJK
  characters are exactly where a general-purpose reconstruction heuristic
  (see below) is weakest, independent of Tesseract's own multi-language
  accuracy.

### An OCR bug that was actually a fixture bug, and what fixing it changed

The OCR path initially scored nowhere near this on several fixtures — including
`01_clean_borders`, a plain digital PDF, not even a scan. Investigating: at
300 dpi, Tesseract's default segmentation found **zero** text blocks on a
small table centered on an otherwise-blank A4 page, even though cropping the
same region and re-running OCR on it in isolation worked perfectly. Dropping
to 200 dpi fixed it across the board. Separately, the image-only PDFs for
cases 06/07 were generated with a real bug: the source image's *pixel*
dimensions were used directly as the PDF page's *point* dimensions, producing
a physically enormous page (points ≠ pixels) that, once re-rasterized for
OCR, triggered the same empty-segmentation failure by a different route. Both
are fixed in the current `scripts/generate_pdfs.py` /
`src/tebench/extractors.py`; the numbers above are post-fix. This is included
here deliberately: a benchmark's own measurement pipeline is exactly the
kind of thing that produces confident, wrong conclusions if a configuration
bug like this ships unnoticed.

## What this methodology does not measure

Being explicit about this is the actual point of the repo, not an
afterthought:

- **`cell_recall` is position-independent.** It checks whether a
  ground-truth value shows up anywhere in the tool's output, not whether it
  landed in the right row/column. A tool that found every value but
  transposed two columns would score identically to one that got everything
  in the right place. `structure_score` catches gross shape mismatches, but
  it operates on row/column *counts*, not a cell-by-cell position check —
  there is no metric here for "right values, wrong grid."
- **`structure_score` penalizes the OCR path unfairly relative to the
  PDF-native tools.** The OCR grid reconstruction in
  `src/tebench/extractors.py` clusters word x-centers into columns, which
  over-segments almost every table (e.g. it produced 16 inferred columns for
  a 6-column table on fixture 01, partly because a misread grid-line glyph
  was tokenized as a stray `"|"` column of its own). That drags
  `structure_score` for `ocr-tesseract` down to roughly 0.5 across nearly
  every fixture regardless of whether the actual cell content was recovered
  well. Read `structure_score` for OCR as "the reconstruction heuristic is
  weak," not as "Tesseract can't find tables" — those are different claims
  and this metric conflates them.
- **One fixture per difficulty is not a sample.** A single clean-scan and a
  single noisy-scan fixture tell you those two points work or don't; they
  don't establish a trend across scan quality. Real confidence about "how
  much blur/skew before OCR breaks" would need a sweep, not two anchor
  points.
- **`runtime_sec` is one run, on one (probably shared, possibly loaded)
  machine, with no warmup.** It's useful for spotting a tool that's 50x
  slower, not for comparing anything within the same order of magnitude.
- **The fuzzy-match threshold (0.85) is a judgment call**, not a derived
  constant. Lowering it would raise every OCR recall number without the
  underlying transcription getting any better.
- **`tabula-py` was not tested** — it requires a JVM, which wasn't available
  in the environment this was built in, and installing one just to cover one
  more tool felt like it would produce a "we ran it once" result no more
  trustworthy than not running it. That's a real gap: tabula uses a
  different underlying extraction approach (it wraps a Java library,
  `tabula-java`) and could behave differently on exactly the lattice/stream
  edge cases where `camelot`'s two flavors diverge here.
- **No test for multiple tables on one page, or a table embedded next to
  unrelated body text** — every fixture here is "one table, isolated on the
  page." Real documents are messier than that in ways this benchmark doesn't
  cover at all.
- **Ground truth was authored by the same person who built the fixtures.**
  There's no independent double-check that the ground truth itself is
  correct, which is a real source of systematic error this methodology
  can't self-detect.

## Repository layout

```
pdfs/                  10 synthetic PDF fixtures
ground_truth/           matching ground truth, one JSON per fixture
scripts/
  generate_pdfs.py      builds pdfs/ and ground_truth/ (deterministic)
  run_benchmark.py       runs every tool against every fixture, writes results/
src/tebench/
  extractors.py          uniform wrappers around each tool
  metrics.py              the rubric
tests/
  test_metrics.py         unit tests for the scoring logic
results/
  results.csv / results.md   full output of the last benchmark run
```

## License

MIT — see [LICENSE](LICENSE).
