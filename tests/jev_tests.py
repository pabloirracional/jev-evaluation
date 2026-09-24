"""
Jev test runner, using fictional data.

Each file in suites/*.json is one use case: questions + cases with the expected
answer. The runner sends each case to Jev and checks the answer.

Usage (credentials and URL in the root .env; see .env.example):
    python jev_tests.py list                          # show the suites
    python jev_tests.py run                           # run everything (resumes where it stopped)
    python jev_tests.py run --suite support_triage    # a single suite
    python jev_tests.py run --repeat 3                # repeat each case (consistency test)
    python jev_tests.py run --limit 5                 # quick test: only 5 calls
    python jev_tests.py report                        # accuracy report

Format of each case's "expect":
    choice -> "option" or ["option_a", "option_b"] (either counts)
    noul   -> true / false (0.5 cutoff)
    score  -> [min, max] (accepted range)
"""
import argparse
import hashlib
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import local_env  # noqa: E402

local_env.load()
sys.stdout.reconfigure(encoding="utf-8")   # avoids needing PYTHONIOENCODING in the Windows terminal

SUITES_DIR = HERE / "suites"
ANSWERS = HERE / "results" / "answers.jsonl"

API_KEY = os.environ.get("TYPESAFE_API_KEY")
URL = os.environ.get("JEV_URL", "https://ai-gateway.vercel.sh/typesafe/v1/systemone")
MODEL = os.environ.get("JEV_MODEL", "jev-latest")
RATE_PER_MIN = int(os.environ.get("JEV_RATE_PER_MIN", "28"))   # Vercel AI Gateway limit: 30/min
WORKERS = 8
PRICE_PER_M_INPUT = 0.042

write_lock = threading.Lock()
pace_lock = threading.Lock()
next_slot = [0.0]


# ---------- suites ----------
def load_suites(only=None):
    suites = []
    for path in sorted(SUITES_DIR.glob("*.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        if only and s["name"] != only:
            continue
        suites.append(s)
    if only and not suites:
        sys.exit(f"Suite '{only}' not found")
    return suites


def case_questions(suite, case):
    return case.get("questions", suite.get("questions"))


def fingerprint(state, questions):
    """Changes when the case or the questions change -> an old answer is not reused."""
    raw = json.dumps([state, questions], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


# ---------- calling Jev ----------
def wait_for_slot():
    interval = 60 / RATE_PER_MIN * 1.05
    with pace_lock:
        now = time.monotonic()
        slot = max(now, next_slot[0])
        next_slot[0] = slot + interval
    time.sleep(slot - now)


def ask_jev(state, questions):
    body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    for attempt in range(5):
        wait_for_slot()
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read()), time.perf_counter() - start
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"Error {e.code}: {e.read().decode(errors='replace')}")
            wait = min(float(e.headers.get("retry-after") or 2 ** attempt), 60)
            print(f"  HTTP {e.code}, retrying in {wait:.0f}s", flush=True)
        except (urllib.error.URLError, TimeoutError) as e:
            wait = 2 ** attempt
            print(f"  no response ({e}), retrying in {wait}s", flush=True)
        time.sleep(wait)
    raise RuntimeError("Jev did not respond after 5 attempts")


def cmd_run(args):
    if not API_KEY:
        sys.exit("Set TYPESAFE_API_KEY in .env (see .env.example)")
    ANSWERS.parent.mkdir(exist_ok=True)
    done = set()
    if ANSWERS.exists():
        for line in ANSWERS.open(encoding="utf-8"):
            r = json.loads(line)
            done.add((r["suite"], r["case"], r["fp"], r["rep"]))

    todo = []
    for s in load_suites(args.suite):
        for c in s["cases"]:
            q = case_questions(s, c)
            fp = fingerprint(c["state"], q)
            for rep in range(args.repeat):
                if (s["name"], c["id"], fp, rep) not in done:
                    todo.append((s["name"], c, q, fp, rep))
    todo = todo[: args.limit]
    print(f"{len(todo)} calls to make ({len(done)} already answered)", flush=True)

    count = [0]
    with ANSWERS.open("a", encoding="utf-8") as out:
        def work(item):
            suite, case, q, fp, rep = item
            resp, elapsed = ask_jev(case["state"], q)
            row = {"suite": suite, "case": case["id"], "fp": fp, "rep": rep, "model": resp.get("model"),
                   "latency_s": round(elapsed, 4), "usage": resp.get("usage"), "answers": resp["answers"]}
            with write_lock:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                count[0] += 1
                if count[0] % 20 == 0:
                    print(f"  {count[0]}/{len(todo)}", flush=True)
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(work, todo))
    print("Done. Run: python jev_tests.py report")


# ---------- checking ----------
def check(qtype, expected, answer):
    """Returns (correct, value_received, confidence)."""
    conf = answer.get("confidence")
    if qtype == "choice":
        ok_set = expected if isinstance(expected, list) else [expected]
        return answer["choice"] in ok_set, answer["choice"], conf
    if qtype == "noul":
        return (answer["noul"] >= 0.5) == expected, round(answer["noul"], 2), None
    lo, hi = expected
    return lo <= answer["score"] <= hi, round(answer["score"], 2), conf


def fmt_expected(qtype, e):
    if qtype == "noul":
        return "yes" if e else "no"
    if qtype == "score":
        return f"{e[0]}–{e[1]}"
    return e if isinstance(e, str) else " or ".join(e)


def cmd_report(args):
    if not ANSWERS.exists():
        sys.exit("No answers yet. Run: python jev_tests.py run")
    rows = defaultdict(list)
    for line in ANSWERS.open(encoding="utf-8"):
        r = json.loads(line)
        rows[(r["suite"], r["case"], r["fp"])].append(r)

    totals = {"ok": 0, "n": 0}
    conf_ok, conf_bad, lat, tokens = [], [], [], 0
    by_type = defaultdict(lambda: [0, 0])
    unstable = []
    print()
    for s in load_suites(args.suite):
        ok = n = 0
        fails = []
        for c in s["cases"]:
            q = case_questions(s, c)
            reps = rows.get((s["name"], c["id"], fingerprint(c["state"], q)))
            if not reps:
                continue
            for r in reps:
                lat.append(r["latency_s"])
                tokens += (r.get("usage") or {}).get("input_tokens", 0)
            a = reps[0]["answers"]
            for key, expected in c["expect"].items():
                qtype = q[key]["type"]
                hit, got, conf = check(qtype, expected, a[key])
                ok += hit
                n += 1
                by_type[qtype][0] += hit
                by_type[qtype][1] += 1
                if conf is not None:
                    (conf_ok if hit else conf_bad).append(conf)
                if not hit:
                    fails.append(f"      ✕ {c['id']}.{key}: expected {fmt_expected(qtype, expected)}, "
                                 f"got {got}" + (f" (confidence {conf:.2f})" if conf is not None else "")
                                 + (f"  — {c['note']}" if c.get("note") else ""))
                vals = {json.dumps(check(qtype, expected, r["answers"][key])[1]) for r in reps}
                if len(reps) > 1 and len(vals) > 1:
                    unstable.append(f"{s['name']}/{c['id']}.{key}: {sorted(vals)}")
        if n:
            totals["ok"] += ok
            totals["n"] += n
            print(f"  {s['title']:<52} {ok:>3}/{n:<3} correct ({100 * ok / n:5.1f}%)")
            if args.verbose or fails:
                print("\n".join(fails))
    if not totals["n"]:
        sys.exit("No answers match the current suites. Run: python jev_tests.py run")

    print(f"\n  TOTAL: {totals['ok']}/{totals['n']} ({100 * totals['ok'] / totals['n']:.1f}%)")
    print("  By question type: " + " | ".join(f"{t} {o}/{m} ({100 * o / m:.0f}%)" for t, (o, m) in by_type.items()))
    if conf_ok and conf_bad:
        print(f"  Average confidence: correct {statistics.mean(conf_ok):.2f} | wrong {statistics.mean(conf_bad):.2f}"
              "  (low confidence on errors = Jev knows when it doesn't know)")
    lat.sort()
    print(f"  Speed: median {1000 * lat[len(lat) // 2]:.0f} ms, p95 {1000 * lat[int(len(lat) * .95)]:.0f} ms"
          f" | {tokens:,} tokens = ${tokens * PRICE_PER_M_INPUT / 1e6:.4f}")
    if unstable:
        print("\n  Answers that changed between repetitions:\n    " + "\n    ".join(unstable))


def cmd_list(args):
    for s in load_suites():
        print(f"  {s['name']:<24} {len(s['cases']):>3} cases · {s['title']}\n      {s['what_it_tests']}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--suite")
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--limit", type=int, help="send at most N calls (quick test)")
    rp = sub.add_parser("report")
    rp.add_argument("--suite")
    rp.add_argument("--verbose", action="store_true")
    sub.add_parser("list")
    args = p.parse_args()
    {"run": cmd_run, "report": cmd_report, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    main()
