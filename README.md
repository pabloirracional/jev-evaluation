# Jev evaluation

A test suite that measures where TypeSafe's Jev model can replace a large LLM, where it can't, and how to use the two together. All cases are fictional and in English.

## What Jev is

Jev (TypeSafe, model `jev-latest`) is a small, specialized model. It does not write text or hold a conversation. It reads a text and answers **fixed questions about it** with structured values, plus a confidence for each answer:

| Question type | Jev returns | Counts as correct when |
|---|---|---|
| `choice` | One option from a list | It is the expected option (or one of the accepted ones) |
| `noul` (yes / no) | A probability from 0 to 1 | It falls on the expected side of 0.5 |
| `score` | A number from 0 to 3 | It falls within the expected range |

That makes Jev a **judge, not a writer**: it labels, checks and filters text at a volume and price where calling a large LLM for every item doesn't make sense.

## Jev or a large LLM?

Large general-purpose models, such as Claude Opus and GPT Astra, can do everything Jev does. The question is whether they're worth their cost and latency for each task.

**Use Jev when:**
- The answer is a label, a yes / no or a score, not free text: triage, routing, moderation, intent, "is this field correct?", "is this answer supported by the source?".
- Volume is high and every call has to be fast and cheap.
- You need a number to act on. Every answer has a probability and a confidence, so you can set cutoffs and send uncertain cases elsewhere.
- The same questions repeat on every item, which keeps results consistent and measurable.
- It sits in the path of every request, like an input guardrail or a check on an LLM's output.

**Use a large LLM when:**
- The output is text: replies, summaries, copy, code, explanations.
- The task needs reasoning or knowledge, not just reading.
- The criteria are vague or subjective. Jev follows the question literally.
- You want to predict a business outcome rather than describe what the text says.

**Using both together:**
1. **Triage and route:** Jev classifies every item, and the large LLM handles only the ones that need a written answer.
2. **Escalate by confidence:** Jev answers below a confidence cutoff go to the large LLM or a person.
3. **Guard the input:** Jev screens requests before they reach the large LLM.
4. **Verify the output:** Jev checks the large LLM's answer against the source, or checks fields it extracted.
5. **Let the large LLM write Jev's questions:** Jev is only as good as its questions, and these suites measure whether a new wording is better.

The suites below test each of these patterns.

## Cost and speed

### What TypeSafe claims

TypeSafe's website advertises Jev as **193.6x faster and 444.6x cheaper** than LLMs, "based on workflows for System One tasks". Its example task costs $0.000081 and takes 0.114 s on Jev, against $0.013880 and 8.566 s on an LLM. Jev's published price is **$42 per billion input tokens** ($0.042 per million).

### What one call costs in this suite

Our full run used 598,723 input tokens for 1,352 calls, about **443 input tokens per call**, and cost **$0.025**. For the same job, a large LLM would read the same text and questions and write back a short JSON answer. The table assumes **443 input + 100 output tokens** for each LLM, at standard list prices (September 2026):

| Model | Price per 1M tokens (input / output) | Cost per call | 1,352 calls (one full run) | 1 million calls | vs Jev |
|---|---|---|---|---|---|
| **Jev** (TypeSafe) | $0.042 / not charged | $0.000019 | $0.025 | $19 | 1x |
| GPT-6 Luna (OpenAI) | $0.10 / $0.50 | $0.000094 | $0.13 | $94 | 5x |
| Claude Haiku 4.5 (Anthropic) | $1 / $5 | $0.00094 | $1.27 | $943 | 51x |
| Claude Sonnet 5 (Anthropic) | $2 / $10 | $0.0019 | $2.55 | $1,886 | 101x |
| GPT-6 Sol (OpenAI) | $2 / $10 | $0.0019 | $2.55 | $1,886 | 101x |
| Claude Opus 5.5 (Anthropic) | $4 / $20 | $0.0038 | $5.10 | $3,772 | 203x |
| GPT-6 Astra (OpenAI) | $10 / $50 | $0.0094 | $12.75 | $9,430 | 507x |

This is a floor for the LLMs. Reasoning models such as Claude Opus 5.5 and GPT-6 Astra also spend "thinking" tokens before they answer, and those are billed as output, so the real gap is usually wider. Against the flagship models, our estimate (203x to 507x) is in the same range as TypeSafe's 444.6x.

### Speed

- **Per call:** Jev answered in **425 ms** (median) and 627 ms at p95 in our run through the Vercel AI Gateway. TypeSafe's example puts an LLM at 8.566 s for a similar task, about 20x slower than our median.
- **Per run:** the limit is the gateway's rate limit, not Jev.

| Access | Rate limit | Full run (1,352 calls) |
|---|---|---|
| Vercel AI Gateway (what we use) | 30 requests per minute | about 50 minutes |
| TypeSafe API directly | 1,200 requests per minute | about 1 minute |

With direct access to the TypeSafe API, the whole suite would run about **40x faster**. That throughput is what makes it realistic to put Jev in front of every request: every ticket, every listing, every LLM answer.

## What we test

12 suites, 1,352 cases. Each suite is one use case: a set of questions, cases with the correct answer, and a note on what makes the hard cases hard.

| # | Suite | Pattern | What it checks | Questions | Cases | Accuracy |
|---|---|---|---|---|---|---|
| 01 | `support_triage` | Triage | Right team, severity and refund request in a single support ticket | `team` choice · `severity` score · `wants_refund` yes/no | 132 | 95.6% |
| 02 | `input_guardrails` | Guard the input | Jailbreak, dangerous request, medical advice, self-harm signal and severity, in one call | 4 yes/no · `severity` score | 125 | 97.8% |
| 03 | `llm_answer_check` | Verify the output | Whether a chatbot answer is supported by the source, contradicts it, or doesn't answer the question | `supported` · `contradicts` · `answers` yes/no | 114 | 94.0% |
| 04 | `extraction_check` | Verify the output | Whether a field extracted from an invoice matches the document, including swapped digits and mixed-up fields | `matches` yes/no | 105 | 100% |
| 05 | `rag_relevance` | Filter | How much a retrieved passage helps answer a question: directly, partly, same topic only, or not at all | `relevance` score | 108 | 94.4% |
| 06 | `same_product` | Filter | Whether two catalog listings are the same product or a different variant (size, voltage, version, quantity, accessory) | `same_product` yes/no | 105 | 100% |
| 07 | `model_routing` | Route | Canned answer, cheap LLM, advanced LLM or human agent, plus how hard the request is | `route` choice · `difficulty` score | 112 | 87.8% |
| 08 | `marketplace_moderation` | Filter | Approve a listing or block it as counterfeit, prohibited or a misleading claim | `decision` choice | 106 | 98.1% |
| 09 | `smart_home` | Triage | Turn a voice command into action + room, including negation and non-commands | `action` · `room` choice | 105 | 95.1% |
| 10 | `churn_risk` | Triage | How close a customer is to canceling, and whether they mention a competitor or ask for a discount | `risk` score · 2 yes/no | 122 | 97.5% |
| 11 | `resume_screening` | Filter | Score candidates on separate skills (Python, APIs, SQL, cloud) so code can weight them | 3 scores · `cloud` yes/no | 113 | 99.0% |
| 12 | `known_weaknesses` | Limits | TypeSafe's own list of known failures: negation, counting, dates, hex colors, hidden instructions, noise, literal reading | one yes/no or choice per case | 105 | 100% |

Accuracy counts every question checked, so a case with three questions counts three times.

Suites 04, 06, 09 and 12 are mostly generated by `tests/generate_cases.py`, because their right answer can be computed. The others are written by hand.

For every run we measure:
- **Accuracy** per question, per suite and overall.
- **Confidence** on correct vs wrong answers, to test whether a confidence cutoff catches errors.
- **Latency** (median and p95) and **cost** per run.
- **Stability**, with `--repeat 3`: whether the same case gets the same answer across runs.

## Results

Run of 2026-09-24, all 1,352 cases, model `jev-latest`, through the Vercel AI Gateway.

| Metric | Result |
|---|---|
| **Overall accuracy** | **96.4%** (2,738 of 2,839 answers) |
| Choice questions | 97% (550 of 568) |
| Yes / no questions | 98% (1,382 of 1,412) |
| Score questions | 94% (806 of 859) |
| Average confidence | 0.92 when right, 0.62 when wrong |
| Latency per call | median 425 ms, p95 627 ms |
| Cost of the full run | $0.025 (598,723 input tokens) |

### Where Jev is reliable

- **Mechanical checks are perfect:** extracted fields, same product, and every case on TypeSafe's own known-weakness list scored 100%.
- **Classification is strong:** moderation 98.1%, resume screening 99.0%, churn risk 97.5%, input guardrails 97.8%.
- **Routing decisions are right; difficulty scores aren't:** 23 of the 24 routing errors are in the `difficulty` score. The route itself was right in 111 of 112 cases.
- **Confidence tracks errors:** wrong answers average 0.62 confidence against 0.92 for right ones, so a confidence cutoff sends most errors to a second opinion.

### Where it fails, and why

1. **"Does the answer respond to the question?" (18 of the 20 errors in `llm_answer_check`).** Jev counts "I don't know" as an answer (0.76 to 0.89) and scores wrong-but-on-topic answers just under 0.5. It mixes up "answered" and "answered correctly". The question needs rewording; `supported` and `contradicts` are fine.
2. **Difficulty scores in routing (23 errors).** Jev gives near-zero difficulty to simple rewrites and translations, so our expected range is probably too high there. It also underrates short but hard technical questions (a JavaScript closure bug, a slow SQL subquery), which is a real error.
3. **Scores run high.** Most severity and relevance errors are Jev going above the expected range, not below it.
4. **Keywords mislead it.** "Refund" in a thank-you note became a refund request; "discount" in a coupon bug went to sales; a supplier's invoice to the company went to billing.
5. **Unnamed competitors.** "A similar app" or "another carrier" counted as mentioning a competitor (0.99). The question should say "names a specific competing service".
6. **Past events read as commands.** "Yesterday the light stayed on all night" became "turn off the light", with 0.98 confidence.
7. **Counterfeit slang.** "Mirror line" and "top grade" listings were approved.

### Recommendations

- Use Jev to classify, check and filter. Use a large LLM for text, reasoning and anything with vague criteria.
- Send answers below about 0.7 confidence to a larger model or a person.
- Tune the cutoff of each yes / no question with this data instead of always using 0.5.
- Reword the three weak questions (`answers`, `difficulty`, `mentions_competitor`) and rerun those suites.
- Run `--repeat 3` to measure stability. This hasn't been done yet.

## Setup

Requires Python 3.9+ and no extra packages.

1. Copy `.env.example` to `.env` in the project root:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Fill in `TYPESAFE_API_KEY` with your Vercel AI Gateway key (`vck_...`). Jev is called through the gateway; the URL and rate limit are already set.

Every script reads `.env` automatically. A variable already set in the terminal takes precedence over `.env`. `.env` is git-ignored: never commit it or paste keys into code.

## Running

```powershell
cd tests
python jev_tests.py list                          # show the suites
python jev_tests.py run                           # run everything; resumes where it stopped
python jev_tests.py run --suite support_triage    # one suite
python jev_tests.py run --repeat 3                # stability test
python jev_tests.py run --limit 5                 # quick test: only 5 calls
python jev_tests.py report                        # accuracy report, with every error listed
python build_artifact.py                          # results page: tests/results/jev-scoreboard.html
python generate_cases.py                          # regenerate the g_* cases of suites 04, 06, 09, 12
```

A full run is 1,352 calls. The Vercel AI Gateway allows 30 calls per minute, so the runner paces itself at 28 and a full run takes about 50 minutes. If a run stops, `run` picks up where it left off.

## Repository layout

| Path | What it is |
|---|---|
| `tests/suites/*.json` | The 12 suites: questions, cases and expected answers |
| `tests/jev_tests.py` | Test runner (`list`, `run`, `report`) |
| `tests/generate_cases.py` | Generates the computed cases for suites 04, 06, 09 and 12 |
| `tests/build_artifact.py` + `artifact_template.html` | Build the results page |
| `tests/results/` | Jev's answers and the results page, created by a run |
| `local_env.py` | Loads `.env` into the environment |
| `.env.example` | Template for `.env` |
