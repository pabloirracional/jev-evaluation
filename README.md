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

A full run of the current suites uses 616,563 input tokens for 1,352 calls, about **456 input tokens per call**, and costs **$0.026**. For the same job, a large LLM would read the same text and questions and write back a short JSON answer. The table assumes **456 input + 100 output tokens** for each LLM, at standard list prices (September 2026):

| Model | Price per 1M tokens (input / output) | Cost per call | 1,352 calls (one full run) | 1 million calls | vs Jev |
|---|---|---|---|---|---|
| **Jev** (TypeSafe) | $0.042 / not charged | $0.000019 | $0.026 | $19 | 1x |
| GPT-6 Luna (OpenAI) | $0.10 / $0.50 | $0.000096 | $0.13 | $96 | 5x |
| Claude Haiku 4.5 (Anthropic) | $1 / $5 | $0.00096 | $1.29 | $956 | 50x |
| Claude Sonnet 5 (Anthropic) | $2 / $10 | $0.0019 | $2.59 | $1,912 | 100x |
| GPT-6 Sol (OpenAI) | $2 / $10 | $0.0019 | $2.59 | $1,912 | 100x |
| Claude Opus 5.5 (Anthropic) | $4 / $20 | $0.0038 | $5.17 | $3,824 | 200x |
| GPT-6 Astra (OpenAI) | $10 / $50 | $0.0096 | $12.93 | $9,560 | 499x |

This is a floor for the LLMs. Reasoning models such as Claude Opus 5.5 and GPT-6 Astra also spend "thinking" tokens before they answer, and those are billed as output, so the real gap is usually wider. Against the flagship models, our estimate (200x to 499x) is in the same range as TypeSafe's 444.6x.

### Speed

- **Per call:** Jev answered in **411 ms** (median) and 622 ms at p95 in our run through the Vercel AI Gateway. TypeSafe's example puts an LLM at 8.566 s for a similar task, about 21x slower than our median.
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
| 03 | `llm_answer_check` | Verify the output | Whether a chatbot answer is supported by the source, contradicts it, or doesn't answer the question | `supported` · `contradicts` · `answers` yes/no | 114 | 99.1% |
| 04 | `extraction_check` | Verify the output | Whether a field extracted from an invoice matches the document, including swapped digits and mixed-up fields | `matches` yes/no | 105 | 100% |
| 05 | `rag_relevance` | Filter | How much a retrieved passage helps answer a question: directly, partly, same topic only, or not at all | `relevance` score | 108 | 94.4% |
| 06 | `same_product` | Filter | Whether two catalog listings are the same product or a different variant (size, voltage, version, quantity, accessory) | `same_product` yes/no | 105 | 100% |
| 07 | `model_routing` | Route | Canned answer, cheap LLM, advanced LLM or human agent, plus how hard the request is | `route` choice · `difficulty` score | 112 | 98.0% |
| 08 | `marketplace_moderation` | Filter | Approve a listing or block it as counterfeit, prohibited or a misleading claim | `decision` choice | 106 | 98.1% |
| 09 | `smart_home` | Triage | Turn a voice command into action + room, including negation and non-commands | `action` · `room` choice | 105 | 95.1% |
| 10 | `churn_risk` | Triage | How close a customer is to canceling, and whether they mention a competitor or ask for a discount | `risk` score · 2 yes/no | 122 | 99.2% |
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

Run of 2026-09-24, all 1,352 cases, model `jev-latest`, through the Vercel AI Gateway. Suites 03, 07 and 10 were rerun the same day after rewording one weak question in each (see [Rewording three questions](#rewording-three-questions)).

| Metric | Result |
|---|---|
| **Overall accuracy** | **98.0%** (2,781 of 2,839 answers) |
| Choice questions | 96.8% (550 of 568) |
| Yes / no questions | 99.5% (1,405 of 1,412) |
| Score questions | 96.2% (826 of 859) |
| Average confidence | 0.93 when right, 0.65 when wrong |
| Latency per call | median 411 ms, p95 622 ms |
| Cost of the full run | $0.026 (616,563 input tokens) |

### Where Jev is reliable

- **Mechanical checks are perfect:** extracted fields, same product, and every case on TypeSafe's own known-weakness list scored 100%.
- **Yes / no questions are near perfect once they're well defined:** 99.5% across all suites.
- **Classification is strong:** LLM answer check 99.1%, churn risk 99.2%, resume screening 99.0%, moderation 98.1%, input guardrails 97.8%.
- **Routing decisions are right:** the route was right in 111 of 112 cases.
- **Confidence tracks errors:** wrong answers average 0.65 confidence against 0.93 for right ones, so a confidence cutoff sends most errors to a second opinion.

### Rewording three questions

The first full run scored 96.4%. Three questions caused most of the errors, and in each case the wording was ambiguous rather than Jev being wrong. We reworded only the question text, kept every case and expected answer the same, and reran those suites:

| Question | Before | After | Accuracy of the suite |
|---|---|---|---|
| `answers` (LLM answer check) | "The answer responds to the question asked" | "…gives a direct reply to the question that was asked, whether or not that reply is correct. Saying the information is not available, or talking about a different topic, does not count as a reply" | 94.0% → **99.1%** |
| `difficulty` (routing) | Levels "Trivial / Simple / Requires reasoning / Very complex" | "Judge the task itself, not how long or short the message is", with a concrete example for each level (look up a fact, short text task, expert reasoning, large multi-part work) | 87.8% → **96.4%** |
| `mentions_competitor` (churn risk) | "The customer mentions a competing service" | "…names a specific competing company or service. Vague references without a name, such as 'another app' … do not count" | 97.5% → **99.2%** |

Overall accuracy went from 96.4% to 97.9%. The lesson: Jev follows the question literally, so precise wording with examples matters more than anything else.

### Where it still fails

1. **Scores run high.** Most severity, relevance and difficulty errors are Jev going above the expected range, not below it.
2. **Keywords mislead it.** "Refund" in a thank-you note became a refund request; "discount" in a coupon bug went to sales; a supplier's invoice to the company went to billing.
3. **Past events read as commands.** "Yesterday the light stayed on all night" became "turn off the light", with 0.98 confidence.
4. **General rule over the exception.** When a chatbot answer applies a general rule and ignores an exception in the source (the late-rescheduling fee, the cats-only-on-Wednesdays rule), Jev sometimes rates it as supported.
5. **Counterfeit slang.** "Mirror line" and "top grade" listings were approved.

The new definitions also exposed three mistakes in our own expected answers: "give me a synonym", "say this in German", "affect or effect?" and "the plural of cactus" are level-1 text tasks, but their expected range said level 0. We corrected those four ranges to level 1 (0.4–1.6). Jev's answers didn't change; only the scoring did. That raised routing from 96.4% to 98.0% and the total to **98.0%**. The four routing errors left are one route (a 40-page contract review sent to a human instead of the advanced model) and three difficulty scores rated above level 2.

### Recommendations

- Use Jev to classify, check and filter. Use a large LLM for text, reasoning and anything with vague criteria.
- Write every question precisely, with examples for each option or level, and test new wording against these suites.
- Send answers below about 0.7 confidence to a larger model or a person.
- Tune the cutoff of each yes / no question with this data instead of always using 0.5.
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
