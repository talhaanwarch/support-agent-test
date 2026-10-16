"""Run one round of the test and save every run's raw output.

A round compares one candidate prompt version against v1 (the `production`
alias) on one dataset, graded by JUDGE_MODEL with the `support-judge` prompt:

  round1   v2 vs v1   dataset kestrel-support-30        (first-draft grading rules)
  round2   v2 vs v1   dataset kestrel-support-30-fixed  (grading rules fixed after round 1)
  round3   v3 vs v1   dataset kestrel-support-30-fixed  (prompt fixed after round 2)

Each round is one experiment, run RUNS times. Every run is saved, unedited, as
results/<round>/run<N>.json: the run id, the report (what the dashboard shows)
and every answer with the judge's score, verdict and reason.

Usage:
  python scripts/02_run.py round1                # start runs until results/round1 has 3
  python scripts/02_run.py round1 --save RUN_ID  # save a run you started in the dashboard
"""
import json
import os
import sys
import time
import urllib.parse

from importlib import import_module

setup = import_module("01_setup")  # same .env loading and HTTP helper
call, items, ROOT = setup.call, setup.items, setup.ROOT

RUNS = int(os.environ.get("RUNS", 3))  # runs per round
ROUNDS = {
    "round1": ("v2", "kestrel-support-30"),
    "round2": ("v2", "kestrel-support-30-fixed"),
    "round3": ("v3", "kestrel-support-30-fixed"),
}


def find(path, name, key="name"):
    return next((x for x in items(call("GET", path, params={"limit": 100})) if x[key] == name), None)


def experiment_for(round_name):
    version_label, dataset_name = ROUNDS[round_name]
    name = f"{round_name}: {version_label} vs v1"
    existing = find("/experiments", name)
    if existing:
        return existing["id"]

    prompt = find("/prompts", setup.AGENT_PROMPT)
    judge = find("/prompts", setup.JUDGE_PROMPT)
    dataset = find("/datasets", dataset_name)
    if not (prompt and judge and dataset):
        raise SystemExit("Missing prompt, judge prompt or dataset. Run scripts/01_setup.py first.")
    number = int(version_label[1:])
    version = call("GET", f"/prompts/{prompt['id']}/versions/{number}")
    exp = call("POST", "/experiments", json={
        "name": name, "dataset_id": dataset["id"], "prompt_id": prompt["id"],
        "version_ids": [version["id"]], "models": [setup.AGENT_MODEL],
        "judge_model": setup.JUDGE_MODEL, "judge_prompt_id": judge["id"],
    })
    print(f"experiment  {name}: created")
    return exp["id"]


def wait_and_save(run_id, path):
    while True:
        run = call("GET", f"/runs/{run_id}")
        if run["status"] not in ("queued", "running"):
            break
        print(f"  {run_id[:8]} {run['status']} {run.get('results')}", flush=True)
        time.sleep(15)
    report = call("GET", f"/runs/{run_id}/report")
    cells = {c["cellKey"]: call("GET", f"/runs/{run_id}/cells/{urllib.parse.quote(c['cellKey'], safe='')}")
             for c in report["cells"]}
    path.write_text(json.dumps({"run_id": run_id, "status": run["status"], "report": report, "cells": cells},
                               indent=2, ensure_ascii=False) + "\n")
    summary = ", ".join(f"{c['variantLabel']} avg {c['avgScore']:.1f}" for c in report["cells"]
                        if c["avgScore"] is not None)
    print(f"saved       {path.relative_to(ROOT)} ({run['status']}; {summary})")


def next_path(folder):
    n = 1
    while (folder / f"run{n}.json").exists():
        n += 1
    return folder / f"run{n}.json", n


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ROUNDS:
        raise SystemExit(f"Usage: 02_run.py {{{'|'.join(ROUNDS)}}} [--save RUN_ID]")
    round_name = sys.argv[1]
    folder = ROOT / "results" / round_name
    folder.mkdir(parents=True, exist_ok=True)

    if "--save" in sys.argv:
        path, _ = next_path(folder)
        wait_and_save(sys.argv[sys.argv.index("--save") + 1], path)
        return

    experiment_id = experiment_for(round_name)
    while True:
        path, n = next_path(folder)
        if n > RUNS:
            print(f"{round_name}: {RUNS} runs saved")
            return
        run_id = call("POST", f"/experiments/{experiment_id}/runs")["run_id"]
        print(f"run         {round_name} run{n}: started {run_id}")
        wait_and_save(run_id, path)


if __name__ == "__main__":
    main()
