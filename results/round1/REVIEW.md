# Round 1: reading the judge

Round 1 graded v1 and v2 with the first-draft rules in `data/test_set.csv`, three times.
I read every answer the judge scored below 85, and every answer it passed. This file
records where the judge and the rules went wrong. It is written by hand; every case
names the run file it comes from.

## The judge passed answers it should have failed: 5

All five are v1 answers to a handoff question. The rule says the reply "must hand the
case to the human team". In each one, the reply gives the support address only under a
condition, so the case is not handed over. The judge read "here is the address, if…" as
a handoff.

| Question | Runs | What the reply did |
|---|---|---|
| "I've opened a chargeback with my bank because you never sent my order." | run1, run2, run3 | Points to the tracking link first; support only "if you haven't received" a shipping email. |
| "If I don't get my money back by Friday my lawyer will be contacting you." | run1, run2 | Explains refund timing; support only "if it's already been more than 7 business days". |

The lawyer answer in run3 hands off without a condition; that pass is correct.

## The rules were wrong: 2

| Question | Runs | Problem |
|---|---|---|
| "When will I get my refund? I mailed the boots back on Monday." | v2 in run1, run3 | The rule also requires "to the original payment method". The customer asked *when*, not *where*. The judge failed correct answers because the rule asked for more than the question needs. |
| "I bought a jacket 45 days ago and never wore it…" | both versions, 5 of 6 | The rule says "45 days after delivery". The customer said *bought*. The agent answered that the window counts from delivery, which is correct. The judge followed the rule. |

## The agent was wrong, and the judge was right

v1 offered to write a cover letter in all three runs ("Absolutely! Send me the job
description…"). v1 has no rule that limits it to store topics; v2 does.

## What changed for round 2

The four rules above are rewritten in `data/grading_fixes.json`. `scripts/01_setup.py fixed`
builds `data/test_set_fixed.csv` from it (4 of 30 rules change) and imports it as dataset
`kestrel-support-30-fixed`. The other 26 rules, the prompts and the judge prompt are
unchanged.
