"""Print every number in the article from the raw run files.

Reads results/<round>/run*.json (written by 02_run.py, never edited by hand),
joins each answer to its group (`category`) from data/test_set.csv by the
question text, and prints Markdown tables:

  1. Pass count per group, per run, per prompt version.
  2. The same pass counts summed over all runs of the round.
  3. The average score of each prompt version in each run (this is the
     number the AcruxCore run report shows).

A "pass" is the judge's own `passed` verdict. An answer with no verdict
(the agent or the judge errored) is counted as "unscored", never as a pass.

Usage:
  python scripts/03_tally.py                    # every round folder, to stdout
  python scripts/03_tally.py round2 round3      # only these folders
  python scripts/03_tally.py --write            # also write results/tally.md
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
GROUPS = ["policy", "pressure", "handoff", "no-data", "off-topic"]


def load_categories():
    with open(ROOT / "data" / "test_set.csv", newline="") as f:
        return {row["question"]: row["category"] for row in csv.DictReader(f)}


def version_label(cell):
    """The report calls the baseline 'production'; name it by the version it points to."""
    return "v1 (production)" if cell["variantLabel"] == "production" else cell["variantLabel"]


def tally_round(folder, categories):
    runs = sorted(folder.glob("run*.json"))
    if not runs:
        raise SystemExit(f"{folder}: no run*.json files")

    # passes[run][version][group] -> count; totals per version and group
    passes = {}
    avg = {}
    counts = {}
    versions = []
    warnings = []
    for path in runs:
        data = json.loads(path.read_text())
        name = path.stem
        status = data.get("status", data["report"].get("status"))
        if status != "succeeded":
            warnings.append(f"{name} ended with status '{status}'; its numbers may be incomplete.")
        passes[name] = defaultdict(lambda: defaultdict(int))
        counts[name] = defaultdict(lambda: defaultdict(int))
        for cell in data["report"]["cells"]:
            label = version_label(cell)
            if label not in versions:
                versions.append(label)
            avg.setdefault(name, {})[label] = cell["avgScore"]
            examples = data["cells"][cell["cellKey"]]["examples"]
            for ex in examples:
                question = ex["input"]["question"]
                if question not in categories:
                    raise SystemExit(f"{path}: question not in data/test_set.csv: {question!r}")
                group = categories[question]
                counts[name][label][group] += 1
                counts[name][label]["unscored"] += ex["passed"] is None
                passes[name][label][group] += ex["passed"] is True
    return runs, versions, passes, counts, avg, warnings


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def render_round(folder, categories):
    runs, versions, passes, counts, avg, warnings = tally_round(folder, categories)
    names = [p.stem for p in runs]
    lines = [f"## {folder.name}", ""]
    lines += [f"**Warning:** {w}" for w in warnings] + ([""] if warnings else [])

    for name in names:
        rows = []
        for group in GROUPS:
            rows.append([group] + [f"{passes[name][v][group]} of {counts[name][v][group]}" for v in versions])
        rows.append(["**all**"] + [
            f"**{sum(passes[name][v][g] for g in GROUPS)} of {sum(counts[name][v][g] for g in GROUPS)}**"
            for v in versions])
        lines += [f"### {name}: answers the judge passed", "", table(["group"] + versions, rows), ""]
        unscored = {v: counts[name][v]["unscored"] for v in versions if counts[name][v]["unscored"]}
        if unscored:
            lines += [f"Unscored answers (counted as not passed): {unscored}", ""]

    rows = []
    for group in GROUPS:
        rows.append([group] + [
            f"{sum(passes[n][v][group] for n in names)} of {sum(counts[n][v][group] for n in names)}"
            for v in versions])
    rows.append(["**all**"] + [
        f"**{sum(passes[n][v][g] for n in names for g in GROUPS)} of "
        f"{sum(counts[n][v][g] for n in names for g in GROUPS)}**" for v in versions])
    lines += [f"### All {len(names)} runs together: answers the judge passed", "",
              table(["group"] + versions, rows), ""]

    rows = [[n] + [f"{avg[n][v]:.1f}" if avg[n].get(v) is not None else "–" for v in versions] for n in names]
    lines += ["### Average score per run (the number on the run report)", "",
              table(["run"] + versions, rows), ""]
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folders = [RESULTS / a for a in args] if args else sorted(
        p for p in RESULTS.iterdir() if p.is_dir() and p.name.startswith("round"))
    if not folders:
        raise SystemExit("No round folders in results/. Run scripts/02_run.py first.")
    categories = load_categories()
    text = "# Tally\n\nGenerated by `scripts/03_tally.py` from the raw files in `results/`. " \
           "Do not edit by hand.\n\n" + "\n".join(render_round(f, categories) for f in folders)
    print(text)
    if "--write" in sys.argv:
        (RESULTS / "tally.md").write_text(text)


if __name__ == "__main__":
    main()
