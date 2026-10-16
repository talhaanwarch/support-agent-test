# Round 2: reading the judge again

Round 2 graded v1 and v2 with the fixed rules in `data/test_set_fixed.csv`, three times.
All three runs finished with status `succeeded`. I read every failed answer, and every
handoff answer the judge passed that contains the word "if".

## The rule fixes worked

The judge now fails conditional handoffs: v1's chargeback answer in run2 and run3 ("if you
haven't, email support…") and its lawyer answer in run1 ("If that 5–7-business-day window
has passed, please email…"). Every passed handoff answer that contains "if" hands off
without a condition; the "if" belongs to other advice, such as "if gas may still be
leaking". I found no wrong passes in this round.

## One strict call

| Question | Run | Version | What happened |
|---|---|---|---|
| "I've opened a chargeback with my bank because you never sent my order." | run1 | v2 | The reply hands off cleanly. The judge failed it (60) because "I'm sorry your order hasn't arrived" repeats the customer's claim as a fact, which it read as "claiming to know the order status". Strict, but it can be defended. The prompt was not changed for it. |

## The agent was wrong: what v3 fixes

v2 failed the 45-day jacket question in run1 and run3. It says the window counts from
delivery, then "If it was delivered within the last 30 days … you can return it", and never
reaches a conclusion. The customer said 45 days; delivery takes at most 5 business days, so
the window has passed. The agent does not compare the time the customer gives with the
policy's limit.

`data/prompt_v3.txt` is v2 plus one rule: compare any time the customer gives with the
policy's time limit, and say the result plainly. Rules are renumbered; nothing else changed.

v1's failures are the ones v2's rules already cover: the cover letter (run1, run2, run3),
conditional handoffs (above), and the weather reply in run3, which pointed to a weather
service but not back to store topics.
