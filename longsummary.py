#!/usr/bin/env python3
"""Combine longbench results (repeat runs marked lane#N) into one summary.
Per turn: median across repeats of input tokens, seconds and model calls; failed turns are left out and counted.
Usage: longsummary.py out.json <results dirs or long.json / partial-*.json files>..."""
import glob, json, os, statistics as st, sys
rows = []
for p in sys.argv[2:]:
    files = glob.glob(os.path.join(p, "long.json")) or glob.glob(os.path.join(p, "partial-*.json")) if os.path.isdir(p) else [p]
    for f in files:
        d = json.load(open(f)); rows += d["rows"] if isinstance(d, dict) else d
med = lambda xs: st.median(xs) if xs else None
out = {"lanes": {}}
for lane in dict.fromkeys(r["lane"].split("#")[0] for r in rows):
    rs = [r for r in rows if r["lane"].split("#")[0] == lane]
    reps = sorted({r["lane"] for r in rs})
    good = [r for r in rs if not r.get("failed")]
    turns = sorted({r["turn"] for r in rs})
    series, cum = [], 0
    for t in turns:
        g = [r for r in good if r["turn"] == t]
        m = med([r["input_tokens"] for r in g]) or 0
        cum += m
        series.append({"turn": t, "input": m, "cumulative": cum, "secs": med([r["wall_s"] for r in g]),
                       "calls": med([r["calls"] for r in g]), "right": sum(r["ok"] for r in g), "runs": len(g),
                       "peak": med([max(r["context_per_call"] or [0]) for r in g])})
    out["lanes"][lane] = {"repeats": len(reps), "turns": len(turns), "graded": len(good), "right": sum(r["ok"] for r in good),
                          "failed": len(rs) - len(good), "input_per_turn": med([r["input_tokens"] for r in good]),
                          "secs_per_turn": med([r["wall_s"] for r in good]), "calls_per_turn": med([r["calls"] for r in good]),
                          "models": sorted({str(r.get("model")) for r in good if r.get("model")}), "series": series}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(f"{'lane':<18}{'reps':>5}{'turns':>6}{'right':>10}{'fail':>5}{'tokens/turn':>13}{'secs/turn':>10}{'calls':>6}")
for l, s in out["lanes"].items():
    print(f"{l:<18}{s['repeats']:>5}{s['turns']:>6}{str(s['right']) + '/' + str(s['graded']):>10}{s['failed']:>5}"
          f"{s['input_per_turn'] or 0:>13,.0f}{s['secs_per_turn'] or 0:>10.1f}{s['calls_per_turn'] or 0:>6g}")
