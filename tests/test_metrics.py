import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tebench.metrics import cell_similarity, normalize, score_extraction  # noqa: E402


def test_normalize_collapses_whitespace_and_case():
    assert normalize("  Lot   ID\n") == "lot id"
    assert normalize("Lot ID") == normalize("lot   id")


def test_normalize_handles_none_and_empty():
    assert normalize(None) == ""
    assert normalize("") == ""


def test_cell_similarity_identical_is_one():
    assert cell_similarity("Riverside", "Riverside") == 1.0


def test_cell_similarity_empty_strings_are_zero_not_one():
    # two empty cells matching each other would make cell_recall trivially
    # inflatable by an extractor that just emits blank cells everywhere.
    assert cell_similarity("", "") == 0.0


def test_perfect_extraction_scores_all_ones():
    gt = [["Lot", "Price"], ["A", "100"], ["B", "200"]]
    extracted = [[["Lot", "Price"], ["A", "100"], ["B", "200"]]]
    result = score_extraction(extracted, gt)
    assert result["cell_recall"] == 1.0
    assert result["value_accuracy"] == 1.0
    assert result["structure_score"] == 1.0
    assert result["extraction_success"] is True


def test_empty_extraction_scores_zero_and_not_success():
    gt = [["Lot", "Price"], ["A", "100"]]
    result = score_extraction([], gt)
    assert result["cell_recall"] == 0.0
    assert result["value_accuracy"] == 0.0
    assert result["extraction_success"] is False


def test_partial_recall_counts_missing_cells():
    gt = [["Lot", "Price", "District"], ["A", "100", "North"]]
    # extractor only captured half the cells
    extracted = [[["Lot", "Price"], ["A", "100"]]]
    result = score_extraction(extracted, gt)
    assert 0.0 < result["cell_recall"] < 1.0
    # everything it did capture was exact, so accuracy of the found subset is perfect
    assert result["value_accuracy"] == 1.0


def test_fuzzy_match_counts_toward_recall_but_not_accuracy():
    gt = [["District"], ["Riverside"]]
    # OCR-style typo: one character swapped
    extracted = [[["District"], ["Riversde"]]]
    result = score_extraction(extracted, gt)
    assert result["cell_recall"] == 1.0
    assert result["value_accuracy"] < 1.0
    assert result["fuzzy_matches"] == 1
    assert result["exact_matches"] == 1  # "District" header matched exactly


def test_duplicate_ground_truth_values_are_not_double_counted_from_one_extracted_cell():
    # ground truth has "Sold" twice; extractor must produce it twice to get full recall
    gt = [["Status"], ["Sold"], ["Sold"]]
    extracted = [[["Status"], ["Sold"]]]
    result = score_extraction(extracted, gt)
    assert result["cell_recall"] == round(2 / 3, 3)  # header + one "Sold" matched, second unmatched


def test_structure_score_penalizes_wrong_shape():
    gt = [["a", "b", "c"], ["1", "2", "3"], ["4", "5", "6"]]
    # extractor merged everything into one row
    extracted = [[["a", "b", "c", "1", "2", "3", "4", "5", "6"]]]
    result = score_extraction(extracted, gt)
    assert result["structure_score"] < 0.5


def test_multiple_extracted_tables_are_pooled_for_scoring():
    # e.g. a table a tool incorrectly split across two "tables" on one page
    gt = [["a", "b"], ["1", "2"], ["3", "4"]]
    extracted = [[["a", "b"], ["1", "2"]], [["3", "4"]]]
    result = score_extraction(extracted, gt)
    assert result["cell_recall"] == 1.0
