"""Run from repository root: backend/.venv/bin/python data/evaluation/evaluate.py.

This measures offline rules on synthetic specification cases. It is not a
real-world LLM accuracy claim and does not call a paid model provider.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.classifier import classify_project  # noqa: E402


def evaluate():
    dataset = json.loads((Path(__file__).parent / "cases.json").read_text())
    counts = {key: 0 for key in ("category", "kind", "evidence_level", "tools")}
    details = []
    tp = fp = fn = 0
    for case in dataset["cases"]:
        actual = classify_project(case["description"], case["readme"], f"https://example.invalid/synthetic/{case['id']}")
        comparisons = {field: actual[field] == expected for field, expected in case["expected"].items()}
        for field, correct in comparisons.items():
            counts[field] += int(correct)
        predicted = actual["evidence_level"] == "explicit"
        expected = case["expected"]["evidence_level"] == "explicit"
        tp += int(predicted and expected)
        fp += int(predicted and not expected)
        fn += int(not predicted and expected)
        details.append({"id": case["id"], "correct": comparisons, "actual": {field: actual[field] for field in counts}, "expected": case["expected"]})
    n = len(details)
    result = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(), "dataset_type": dataset["dataset_type"],
        "method": "deterministic-rules-v1", "sample_count": n,
        "field_accuracy": {key: round(value / n, 4) for key, value in counts.items()},
        "explicit_precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "explicit_recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "limitation": "Synthetic specification cases only; these scores do not estimate real-world performance or validate an LLM provider. Human real-project review remains pending.",
        "cases": details,
    }
    (Path(__file__).parent / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, ensure_ascii=False, indent=2))
    return 0 if all(all(row["correct"].values()) for row in details) else 1


if __name__ == "__main__":
    raise SystemExit(evaluate())
