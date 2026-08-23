#!/usr/bin/env bash
# VERIFY.sh — А-1/А-8 (AGENT_TASK_verify_and_night.md, vietnam-property-check repo).
#
# Пересчитывает метрики бенчмарка С НУЛЯ из фикстур/эталонов
# (scripts/run_benchmark.py) и сверяет результат с числами, заявленными в
# README.md ("Results at a glance"). Отдельно проверяет, что фикстуры
# ground_truth/*.json содержат корректные вьетнамские диакритики (NFC) —
# ошибка со шрифтом уже один раз испортила эталоны.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
  echo "ОШИБКА: .venv не найден — python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

PY=.venv/bin/python
if ! $PY -c "import pdfplumber, camelot, pytesseract, pandas" 2>/dev/null; then
  echo "ОШИБКА: зависимости .venv не установлены — pip install -r requirements.txt"
  exit 1
fi
if ! command -v tesseract >/dev/null || ! tesseract --list-langs 2>&1 | grep -q "^vie$"; then
  echo "ОШИБКА: tesseract или языковой пакет vie не установлен (apt-get install tesseract-ocr tesseract-ocr-vie)"
  exit 1
fi

$PY - "$@" <<'PYEOF'
import csv
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent if "__file__" in dir() else Path(".")
ROOT = Path(".").resolve()

violations = []

# 1. Пересчёт метрик с нуля
result = subprocess.run([".venv/bin/python", "scripts/run_benchmark.py"], capture_output=True, text=True)
if result.returncode != 0:
    print(f"ОШИБКА: run_benchmark.py упал:\n{result.stdout[-1000:]}\n{result.stderr[-1000:]}")
    sys.exit(1)

# 2. Читаем свежепосчитанные результаты
rows = list(csv.DictReader(open("results/results.csv")))
if not rows:
    print("ОШИБКА: results.csv пуст после пересчёта")
    sys.exit(1)
fresh = {(r["case"], r["tool"]): float(r["cell_recall"]) for r in rows}

# 3. Разбираем таблицу "Results at a glance" из README.md и сверяем
readme = Path("README.md").read_text(encoding="utf-8")
m = re.search(r"\| case \|.*?\n((?:\|.*\n)+)", readme)
if not m:
    print("ОШИБКА: не нашёл таблицу 'Results at a glance' в README.md")
    sys.exit(1)

table_lines = [l for l in m.group(1).splitlines() if l.strip().startswith("|") and "---" not in l]
tools = ["pdfplumber", "camelot-lattice", "camelot-stream", "ocr-tesseract"]
mismatches = []
checked = 0
for line in table_lines:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    case = cells[0]
    for tool, val_str in zip(tools, cells[1:]):
        checked += 1
        claimed = float(val_str)
        actual = fresh.get((case, tool))
        if actual is None:
            mismatches.append(f"{case}/{tool}: нет свежего результата")
        elif abs(actual - claimed) > 0.005:
            mismatches.append(f"{case}/{tool}: README={claimed} пересчёт={actual}")

print(f"=== table-extract-bench · сверка README vs пересчёт ===")
print(f"Ячеек в таблице README сверено:        {checked}")
print(f"Расхождений README vs пересчёт:        {len(mismatches)}   {'OK' if not mismatches else 'ОШИБКА'}")
if mismatches:
    violations.append("README расхождения: " + "; ".join(mismatches[:10]))

# 4. Вьетнамские диакритики в фикстурах — NFC, не битые/mojibake
gt_dir = Path("ground_truth")
bad_diacritics = []
for gt_path in sorted(gt_dir.glob("*.json")):
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    for row in gt.get("rows", []):
        for cell in row:
            if isinstance(cell, str) and unicodedata.normalize("NFC", cell) != cell:
                bad_diacritics.append(f"{gt_path.name}: {cell!r} не в NFC")
print(f"Фикстур проверено на диакритики:       {len(list(gt_dir.glob('*.json')))}")
print(f"Ячеек с некорректной нормализацией:    {len(bad_diacritics)}   {'OK' if not bad_diacritics else 'ОШИБКА'}")
if bad_diacritics:
    violations.append("Диакритики: " + "; ".join(bad_diacritics[:10]))

# 5. Тесты
test_result = subprocess.run([".venv/bin/python", "-m", "pytest", "tests/", "-q"], capture_output=True, text=True)
m2 = re.search(r"(\d+) passed", test_result.stdout)
m3 = re.search(r"(\d+) failed", test_result.stdout)
passed = int(m2.group(1)) if m2 else 0
failed = int(m3.group(1)) if m3 else 0
print(f"Тестов пройдено:                       {passed}/{passed+failed}   {'OK' if not failed else 'ОШИБКА'}")
if failed:
    violations.append(f"pytest: {failed} failed")

print()
if violations:
    print(f"НАРУШЕНО: {len(violations)}")
    for v in violations:
        print(f"  ✗ {v}")
    sys.exit(1)
print("Все проверки пройдены.")
sys.exit(0)
PYEOF
exit $?
