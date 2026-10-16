# Testing an AI support agent before it answers customers

This repo holds a complete, repeatable test of a customer-support prompt: the test set,
the three prompt versions, the judge prompt, the scripts, every raw result, and the
screenshots. Every number below is printed by `scripts/03_tally.py` from the files in
`results/`; see [`results/tally.md`](results/tally.md).

The agent answers for a fictional outdoor-gear store ([`data/policy.md`](data/policy.md)).
The test runs on [AcruxCore](https://github.com/AcruxCore/AcruxCore), an open-source
LLM-ops platform: it stores the prompt versions and the test set, runs every question
through each version, and has a second model grade each answer.

## The setup

| | |
|---|---|
| Agent model | `openai/gpt-6-luna`, through OpenRouter |
| Judge model | `glm-5.3` (z.ai), with the judge prompt in [`data/judge_prompt_system.txt`](data/judge_prompt_system.txt) and [`data/judge_prompt_user.txt`](data/judge_prompt_user.txt) |
| Test set | 30 questions in five groups: policy (10), pressure (8), handoff (6), no-data (3), off-topic (3) |
| Grading | Each question has its own rule ("the reply must…, it must not…"). The judge sees the rule and the reply, not the question. |
| Runs | Every comparison is run three times, because the models answer differently each time |

The three prompts:

- **v1** ([`prompt_v1.txt`](data/prompt_v1.txt)) — a short demo prompt: be friendly, use the policy.
- **v2** ([`prompt_v2.txt`](data/prompt_v2.txt)) — v1 plus six rules: answer only from the policy, no exceptions, hand off chargebacks, lawyers, injuries and security problems, stay on store topics, be brief.
- **v3** ([`prompt_v3.txt`](data/prompt_v3.txt)) — v2 plus one rule, written after round 2: compare any time the customer gives with the policy's time limit, and say the result.

## The results

Answers the judge passed, over three runs (90 answers per version):

| Round | Grading rules | Candidate | v1 |
|---|---|---|---|
| 1 | first draft ([`test_set.csv`](data/test_set.csv)) | v2: 85 of 90 | 85 of 90 |
| 2 | fixed ([`test_set_fixed.csv`](data/test_set_fixed.csv)) | v2: 87 of 90 | 83 of 90 |
| 3 | fixed | v3: 90 of 90 | 84 of 90 |

**Round 1 was a tie, and the tie was wrong.** Reading every answer showed that the judge
passed 5 v1 answers it should have failed: v1 gave the support address only *if* something
was true, and the judge counted that as a handoff. Two of the first-draft rules also asked
for the wrong thing. [`results/round1/REVIEW.md`](results/round1/REVIEW.md) lists every case.

**Round 2 fixed four rules** ([`data/grading_fixes.json`](data/grading_fixes.json)) and
nothing else. v2 led by 4. Its one real failure was a customer who bought a jacket 45 days
ago: v2 said "if it was delivered within 30 days, you can return it" and never concluded.
See [`results/round2/REVIEW.md`](results/round2/REVIEW.md).

**Round 3 added one rule to the prompt** (v3). v3 passed all 90 answers, and answered the
45-day question correctly in all three runs. See [`results/round3/REVIEW.md`](results/round3/REVIEW.md).

Pass counts and the run report measure different things. The dashboard's run report shows
the **average score** of one run (for example 100.0 against 93.7 in round 3, run 1). The
table above counts **passed answers** over three runs. `results/tally.md` has both, per run.

## What this does not show

- One agent model and one judge model. A weaker agent model breaks v1's rules far more often.
- 30 questions. The groups are small: the handoff group has 6 questions, so 18 answers per version over three runs.
- The judge checks rules, not tone or helpfulness beyond them.
- The numbers will be different when you run it. The kind of result should be the same.

## Run it yourself

You need an AcruxCore account (the hosted service or a self-hosted copy), an OpenRouter key,
and a key for the judge model. Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.example .env              # fill in the keys
python scripts/01_setup.py        # credentials, models, prompts v1–v3, judge prompt, dataset
python scripts/01_setup.py fixed  # the second dataset, with the fixed rules
python scripts/02_run.py round1   # three runs each, saved to results/round<N>/
python scripts/02_run.py round2
python scripts/02_run.py round3
python scripts/03_tally.py --write
```

To use a different judge, register it under **Gateway → Models** and set `JUDGE_MODEL`.
Every step can also be done in the dashboard; the screenshots in [`screenshots/`](screenshots)
show each one. `01_setup.py` finds what already exists, so it can check a dashboard setup.

The commands above repeat this test as it ended. To run the method on your own agent,
stop after each round and read the answers: the fixes in `data/grading_fixes.json` and
`prompt_v3.txt` came from reading this run's results, and yours may need different ones.
`RUNS=1 python scripts/02_run.py round1` does a single run.

## Cost of this run

720 agent calls ($0.07 at OpenRouter's price for `gpt-6-luna`) and 726 judge calls
(350,419 input and 230,712 output tokens; z.ai coding plan, flat fee). That includes one
round 2 that was deleted and run again after a platform bug marked it failed.

## Files

```
data/       policy, prompts v1–v3, judge prompt, test set (first draft and fixed), the fixes
scripts/    01_setup.py, 02_run.py, 03_tally.py
results/    raw API output per run (never edited), REVIEW.md per round, tally.md
screenshots/ the dashboard at each step (1280x800)
```

MIT licence.
