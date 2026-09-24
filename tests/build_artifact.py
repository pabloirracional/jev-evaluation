"""
Builds the visual catalog of the suites (results/jev-scoreboard.html).

Combines the questions, the cases and, when available, Jev's answer for each case
(results/answers.jsonl), and injects everything into artifact_template.html.

Usage:
    python build_artifact.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from jev_tests import ANSWERS, PRICE_PER_M_INPUT, case_questions, check, fingerprint, load_suites

HERE = Path(__file__).parent
TEMPLATE = HERE / "artifact_template.html"
OUT = HERE / "results" / "jev-scoreboard.html"
GENERATED = {"extraction_check", "same_product", "known_weaknesses", "smart_home"}


def score_band(e):
    mid = (e[0] + e[1]) / 2
    return f"level {round(mid)}"


def main():
    answers = {}
    if ANSWERS.exists():
        for line in ANSWERS.open(encoding="utf-8"):
            r = json.loads(line)
            answers.setdefault((r["suite"], r["case"], r["fp"]), r)
    rows = list(answers.values())
    lat = sorted(r["latency_s"] for r in rows)
    tokens = sum((r.get("usage") or {}).get("input_tokens", 0) for r in rows)
    run_info = {
        "model": rows[0].get("model") if rows else None,
        "latency_median_ms": round(1000 * lat[len(lat) // 2]) if lat else None,
        "latency_p95_ms": round(1000 * lat[int(len(lat) * .95)]) if lat else None,
        "tokens": tokens,
        "cost_usd": round(tokens * PRICE_PER_M_INPUT / 1e6, 4),
    }

    suites_out, totals = [], Counter()
    for s in load_suites():
        dist = defaultdict(Counter)
        cases = []
        ran = hits = checks = 0
        for c in s["cases"]:
            q = case_questions(s, c)
            row = answers.get((s["name"], c["id"], fingerprint(c["state"], q)))
            res = {}
            for key, e in c["expect"].items():
                t = q[key]["type"]
                label = ("yes" if e else "no") if t == "noul" else score_band(e) if t == "score" else \
                        (e if isinstance(e, str) else " or ".join(e))
                dist[key][label] += 1
                checks += 1
                if row:
                    ok, got, conf = check(t, e, row["answers"][key])
                    res[key] = {"ok": ok, "got": got, "conf": None if conf is None else round(conf, 2)}
                    hits += ok
            if row:
                ran += 1
            cases.append({"id": c["id"], "state": c["state"], "note": c.get("note"), "expect": c["expect"],
                          "types": {k: q[k]["type"] for k in c["expect"]}, "res": res or None,
                          "questions": c.get("questions")})
        suites_out.append({
            "name": s["name"], "title": s["title"], "what": s["what_it_tests"],
            "source": "generator" if s["name"] in GENERATED else "hand",
            "questions": s.get("questions"), "cases": cases, "checks": checks, "ran": ran,
            "hits": hits, "ran_checks": sum(len(c["res"] or {}) for c in cases),
            "dist": {k: dict(v.most_common()) for k, v in dist.items()},
        })
        totals["cases"] += len(cases)
        totals["checks"] += checks
        totals["ran"] += ran
        totals["hits"] += hits
        totals["ran_checks"] += suites_out[-1]["ran_checks"]

    data = {"suites": suites_out, "totals": dict(totals), "run": run_info}
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT} ({OUT.stat().st_size / 1024:.0f} KB) — {totals['cases']} cases, {totals['ran']} already run")


if __name__ == "__main__":
    main()
