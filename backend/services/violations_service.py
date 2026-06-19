import csv
from pathlib import Path

CSV_PATH = Path(
    "../ai-model/outputs/violations/violations_log.csv"
)


def get_violations():
    violations = []

    if not CSV_PATH.exists():
        return violations

    with open(CSV_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            violations.append(row)

    return violations