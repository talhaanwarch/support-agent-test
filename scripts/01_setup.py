"""Create everything the test needs in an AcruxCore team, or check it is there.

Find-or-create, so it is safe to run again: each object is looked up by name
first, and only made when missing. That lets you do a step in the dashboard
and still run this script afterwards to check the result.

Creates:
  - two credentials: OpenRouter (agent) and z.ai (judge), both OpenAI-compatible
  - two models: AGENT_MODEL and JUDGE_MODEL, under the same names
  - prompt `kestrel-support-agent`: one version per data/prompt_v*.txt file,
    with the `production` alias on v1 (the baseline every round compares to)
  - prompt `support-judge`: one version (data/judge_prompt_*.txt), `production`
  - dataset `kestrel-support-30` from data/test_set.csv, in one bulk call
  - with the `fixed` step (after round 1): data/test_set_fixed.csv, built from
    data/test_set.csv and data/grading_fixes.json, and dataset
    `kestrel-support-30-fixed` from it

Usage:
  python scripts/01_setup.py                 # every step (reads .env in the repo root)
  python scripts/01_setup.py models prompts  # only some steps: models, prompts, dataset, fixed
"""
import csv
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env()
BASE = os.environ["ACRUXCORE_BASE_URL"].rstrip("/")
HEADERS = {"Authorization": f"Bearer {os.environ['ACRUXCORE_API_KEY']}"}
AGENT_MODEL = os.environ.get("AGENT_MODEL", "openai/gpt-6-luna")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "glm-5.3")
AGENT_PROMPT = "kestrel-support-agent"
JUDGE_PROMPT = "support-judge"


def call(method, path, **kw):
    r = requests.request(method, f"{BASE}{path}", headers=HEADERS, timeout=60, **kw)
    if r.status_code >= 400:
        raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text}")
    return r.json() if r.text else None


def items(body):
    return body["data"] if isinstance(body, dict) and "data" in body else body


def agent_messages(name):
    policy = (DATA / "policy.md").read_text().strip()
    system = (DATA / name).read_text().replace("{{ policy }}", policy).strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": "{{ question }}"}]


def judge_messages():
    return [
        {"role": "system", "content": (DATA / "judge_prompt_system.txt").read_text().strip()},
        {"role": "user", "content": (DATA / "judge_prompt_user.txt").read_text().strip()},
    ]


def credential(label, base_url, key):
    for c in items(call("GET", "/gateway/connections")):
        if c["label"] == label:
            print(f"credential  {label}: exists")
            return c["id"]
    c = call("POST", "/gateway/connections", json={
        "provider": "openai_compatible", "label": label, "apiKey": key, "config": {"base_url": base_url}})
    print(f"credential  {label}: created")
    return c["id"]


def model(name, credential_id, openrouter_price=False):
    found = next((m for m in items(call("GET", "/gateway/models")) if m["publicName"] == name), None)
    if found:
        print(f"model       {name}: exists")
    else:
        found = call("POST", "/gateway/models",
                     json={"publicName": name, "upstreamModel": name, "credentialId": credential_id})
        print(f"model       {name}: created")
    # A model the gateway has no price for records its cost as null. Copy the
    # price from OpenRouter's public model list so the Usage page shows spend.
    if openrouter_price and found.get("inputPricePerM") is None:
        listing = requests.get("https://openrouter.ai/api/v1/models", timeout=60).json()["data"]
        price = next((m["pricing"] for m in listing if m["id"] == name), None)
        if price:
            per_m = {"inputPricePerM": round(float(price["prompt"]) * 1e6, 6),
                     "outputPricePerM": round(float(price["completion"]) * 1e6, 6)}
            call("PATCH", f"/gateway/models/{found['id']}", json=per_m)
            print(f"model       {name}: price set from OpenRouter ({per_m})")


def prompt(name, description, versions):
    """Create the prompt and commit any version in `versions` it does not have yet."""
    found = [p for p in items(call("GET", "/prompts", params={"limit": 100})) if p["name"] == name]
    p = found[0] if found else call("POST", "/prompts", json={"name": name, "description": description})
    have = items(call("GET", f"/prompts/{p['id']}/versions"))
    for i, (messages, model_name) in enumerate(versions, start=1):
        if i <= len(have):
            same = have_messages(p["id"], i) == messages
            print(f"prompt      {name} v{i}: exists{'' if same else '  (WARNING: text differs from data/)'}")
            continue
        call("POST", f"/prompts/{p['id']}/versions", json={"messages": messages, "model": model_name})
        print(f"prompt      {name} v{i}: committed")
    aliases = {a["alias"]: a for a in items(call("GET", f"/prompts/{p['id']}/aliases"))}
    if "production" not in aliases:
        call("POST", f"/prompts/{p['id']}/aliases/production/promote", json={"version_number": 1})
        print(f"prompt      {name}: production -> v1")
    return p["id"]


def have_messages(prompt_id, number):
    v = call("GET", f"/prompts/{prompt_id}/versions/{number}")
    return [{"role": m["role"], "content": m["content"]} for m in v["messages"]]


def dataset(name, csv_name):
    with open(DATA / csv_name, newline="") as f:
        rows = list(csv.DictReader(f))
    for d in items(call("GET", "/datasets", params={"limit": 100})):
        if d["name"] == name:
            print(f"dataset     {name}: exists ({d.get('exampleCount', '?')} examples)")
            return d["id"]
    d = call("POST", "/datasets", json={"name": name})
    # One call for all rows (bulk import). `category` goes in as a variable:
    # the agent prompt does not use it, and the tally reads it back from here.
    examples = [{"input": {"category": r["category"], "question": r["question"]}, "criteria": r["criteria"]}
                for r in rows]
    result = call("POST", f"/datasets/{d['id']}/examples/bulk", json={"examples": examples})
    print(f"dataset     {name}: created, {result['added']} examples")
    return d["id"]


def write_fixed_csv():
    """data/test_set.csv with the rules in data/grading_fixes.json swapped in (round 2 and 3)."""
    import json
    fixes = json.loads((DATA / "grading_fixes.json").read_text())
    with open(DATA / "test_set.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    unknown = set(fixes) - {r["question"] for r in rows}
    if unknown:
        raise SystemExit(f"grading_fixes.json names questions not in test_set.csv: {unknown}")
    with open(DATA / "test_set_fixed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["category", "question", "criteria"], lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "criteria": fixes.get(r["question"], r["criteria"])})
    print(f"data        test_set_fixed.csv: {len(fixes)} of {len(rows)} grading rules changed")


def main():
    steps = sys.argv[1:] or ["models", "prompts", "dataset"]
    if "models" in steps:
        openrouter = credential("OpenRouter", "https://openrouter.ai/api/v1", os.environ["OPENROUTER_API_KEY"])
        zai = credential("z.ai coding plan", os.environ["ZAI_BASE_URL"], os.environ["ZAI_API_KEY"])
        model(AGENT_MODEL, openrouter, openrouter_price=True)
        model(JUDGE_MODEL, zai)
    if "prompts" in steps:
        files = sorted(DATA.glob("prompt_v*.txt"), key=lambda f: int(f.stem.split("_v")[1]))
        prompt(AGENT_PROMPT, "Kestrel Outdoor support agent", [(agent_messages(f.name), AGENT_MODEL) for f in files])
        prompt(JUDGE_PROMPT, "Grades one support reply against its grading rules", [(judge_messages(), JUDGE_MODEL)])
    if "dataset" in steps:
        dataset("kestrel-support-30", "test_set.csv")
    if "fixed" in steps:
        write_fixed_csv()
        dataset("kestrel-support-30-fixed", "test_set_fixed.csv")


if __name__ == "__main__":
    main()
