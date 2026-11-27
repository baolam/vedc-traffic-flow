"""Compile the test-seed benchmark rows (bench.py) into data/summary.json and markdown tables (stdout).
Usage: PYTHONPATH=. python compile.py > tables.md"""
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
from src.benchmark.scoring import qualification  # noqa: E402
from src.rl.selection import validation_score  # noqa: E402

OUT = Path(os.environ.get("BENCH_OUT", REPO / "artifacts/benchmarks/test-benchmark-20261126"))
DATA = Path(__file__).resolve().parents[1] / "data"
MAPS = ("cologne8_benchmark_v1", "grid4x4_benchmark_v1", "hcm_neighborhood_v3_benchmark_v1", "jakarta_menteng_v1",
        "hanoi_dong_da_v1", "four_intersection_rl_v1")
SHORT = dict(zip(MAPS, ("cologne8", "grid4x4", "HCM", "Jakarta", "Hanoi", "4-node")))
DET = ("fixed_time", "actuated", "max_queue", "max_pressure", "edgeflow", "flow_theory", "fair_cycle", "fair_cycle_native")
LEARNED = {"phase DQN baseline (it00b config)": ["it00b-17", "base-1604", "base-2026"],
           "round-3 config C": ["it32-17", "it37-29", "it44-41", "c-1604", "c-2026"]}
TAIL = ("delay_per_scheduled_s", "p95_wait_s", "worst_approach_wait_s", "max_approach_p95_wait_s")
CLASSES = ("motorcycle", "car", "taxi", "bus", "truck")
TEST = list(range(80001, 80021))  # contract test split 80001-80010 extended to 80020 for this benchmark only


def load(group, m):
    p = OUT / group / m / "rows.json"
    return json.loads(p.read_text()) if p.exists() else {}


def per_case(rows, cases):
    """Mean of every scalar metric over the test seeds, per case (complete valid seeds only)."""
    out = {}
    for c in cases:
        rs = [r for r in rows if r["scenario"] == c]
        f = lambda key: float(np.mean([r[key] for r in rs]))  # noqa: E731
        rec = [r["recovery_s"] for r in rs if r.get("recovery_s") is not None]
        out[c] = dict(
            **{k: f(k) for k in TAIL},
            completion_rate=float(np.mean([r["completed"] / max(r["scheduled"], 1) for r in rs])),
            throughput_veh_per_s=f("throughput_veh_per_s"), scheduled=f("scheduled"), completed=f("completed"),
            unfinished=f("unfinished"), uninserted=f("uninserted"),
            collisions=int(sum(r["collisions"] for r in rs)), teleports=int(sum(r["teleports"] for r in rs)),
            accounting_losses=int(sum(r["accounting_losses"] for r in rs)),
            invalid_runs=int(sum(not r["valid"] for r in rs)),
            recovery_s=float(np.mean(rec)) if rec else None,
            recovery_censored=int(sum(bool(r.get("recovery_censored")) for r in rs)),
            recovery_applicable=c in ("downstream_bottleneck", "directional_reversal"),
            max_service_gap_s=float(np.mean([max(r["maximum_demanded_service_gap_s"].values(), default=0) for r in rs])),
            clearance_node_s=f("total_signal_clearance_node_seconds"),
            peak_backlog_veh=float(np.mean([max((q for _, q in r["queue_backlog_trace"]), default=0) for r in rs])),
            class_delay_s={k: float(np.mean([r["vehicle_classes"][k]["delay_per_scheduled_s"] for r in rs
                                             if k in r["vehicle_classes"]])) for k in CLASSES
                           if any(k in r["vehicle_classes"] for r in rs)},
            wall_s=f("wall_seconds"), runs=len(rs))
    return out


def evaluate(rows, ref, cases, baselines):
    """Guardrail per case on the seeds where the tuned Fixed-Time reference run is valid (a reference collision or
    teleport drops that pair for every controller alike); a candidate's own invalid run fails the guardrail."""
    if isinstance(rows, str):
        return dict(error=rows.strip().splitlines()[-1][:200])
    done = [r for r in rows if r is not None]
    if not done:  # e.g. legacy fair_cycle is two-phase only: "Requested controller did not execute"
        return dict(error="no valid run (controller does not apply to this map)")
    ref = [r for r in ref if r is not None]
    means, reasons, dropped = [], [], []
    for c in cases:
        seeds = [s for s in TEST if any(r["scenario"] == c and r["seed"] == s for r in ref)]
        dropped += [f"{c}/{s}" for s in TEST if s not in seeds]
        got = [r for r in done if r["scenario"] == c and r["seed"] in seeds]
        if len(got) == len(seeds):
            g = validation_score(got, [r for r in ref if r["scenario"] == c], [c], seeds)
            reasons += g["reasons"]
            means.append(g["score"])
        else:
            reasons.append(f"{c}: {len(seeds) - len(got)} invalid run(s) (collision/teleport)")
            means.append(float(np.mean([r["delay_per_scheduled_s"] for r in got])) if got else None)
    res = dict(score=float(np.mean(means)) if None not in means else None, feasible=not reasons, reasons=reasons,
               complete=f"{len(done)}/{len(rows)}", invalid_runs=len(rows) - len(done), reference_invalid_pairs_dropped=dropped, cases=per_case(done, cases))
    full = [s for s in TEST if all(any(r["scenario"] == c and r["seed"] == s for r in done) for c in cases)]
    if len(full) > 2:
        res["score_ci95_s"] = ci([np.mean([r["delay_per_scheduled_s"] for r in done if r["seed"] == s]) for s in full])
    if baselines is not None:  # the repo's qualification needs every pair, so it runs on seeds complete everywhere
        have = lambda rs, s: all(any(r["scenario"] == c and r["seed"] == s for r in rs) for c in cases)  # noqa: E731
        seeds = [s for s in full if all(have(b, s) for b in baselines.values())]
        pick = lambda rs: [r for r in rs if r["seed"] in seeds]  # noqa: E731
        q = qualification(pick(done), {k: pick(v) for k, v in baselines.items()}, cases, seeds)
        res["qualification"] = {k: q[k] for k in ("promoted", "reasons", "comparisons")} | dict(seeds=len(seeds))
    return res


def ci(values):
    """t-interval half-width of the mean over test seeds (equal-case delay per seed)."""
    from scipy.stats import t
    return float(t.ppf(0.975, len(values) - 1) * np.std(values, ddof=1) / np.sqrt(len(values)))


def build():
    summary = {}
    for m in MAPS:
        plain, boxed = load("det", m), load("det-maxred", m)
        ft = plain["fixed_time"]
        cases = list(dict.fromkeys(r["scenario"] for r in ft if r))
        base = {k: [r for r in plain.get(k, []) if r is not None] for k in ("fixed_time", "actuated", "max_pressure", "edgeflow")}
        res = {}
        for name, rows in plain.items():
            res[name] = evaluate(rows, ft, cases, None)
        for name, rows in boxed.items():
            res[name + " + max-red"] = evaluate(rows, ft, cases, None)
        for label, groups in LEARNED.items():
            for gname in groups:
                rows = load(gname, m).get("phase_dqn_unified")
                if rows is not None:
                    r = evaluate(rows, ft, cases, base)
                    r["policy"] = json.loads((OUT / gname / m / "policy.json").read_text())["policy"]
                    res[f"{label}::{gname}"] = r
        # paired context for the learned rows: vs the best guardrail-passing deterministic controller (± max-red)
        ok = [(v["score"], k) for k, v in res.items() if "::" not in k and v.get("feasible")]
        if ok:
            best = min(ok)[1]
            det_rows = (boxed if best.endswith(" + max-red") else plain)[best.replace(" + max-red", "")]
            for k, v in res.items():
                if "::" in k and "error" not in v:
                    g = k.split("::")[1]
                    v["vs_best_deterministic"] = dict(controller=best, **paired(load(g, m)["phase_dqn_unified"], det_rows, cases))
        summary[m] = dict(cases=cases, controllers=res)
    return summary


def paired(a, b, cases):
    """Learned minus deterministic equal-case delay per test seed (seeds valid in both); mean and t 95 % half-width."""
    def per_seed(rows):
        by = {(r["scenario"], r["seed"]): r["delay_per_scheduled_s"] for r in rows if r is not None}
        return {s: np.mean([by[(c, s)] for c in cases]) for s in TEST if all((c, s) in by for c in cases)}
    x, y = per_seed(a), per_seed(b)
    d = [x[s] - y[s] for s in x if s in y]
    return dict(diff_s=float(np.mean(d)), ci95_s=ci(d), seeds=len(d))


def mark(r):
    """✓ passes; ✗* fails only because SUMO rejected some runs (collision/teleport); ✗ fails on tails/completion."""
    if r["feasible"]:
        return "✓"
    return "✗*" if all("invalid run" in x for x in r["reasons"]) else "✗"


def fmt(x, d=1):
    return "—" if x is None else f"{x:.{d}f}"


def tables(summary):
    out = []
    names = [n for n in DET] + [n + " + max-red" for n in DET]
    # 1. headline: score (feasible mark) per map
    out.append("### Score per map (equal-case mean delay ± 95 % CI over test seeds, s; ✓ = passes the guardrail vs tuned Fixed-Time; ✗* = fails only because SUMO rejected a run for a collision/teleport)\n")
    out.append("| Controller | " + " | ".join(SHORT[m] for m in MAPS) + " |")
    out.append("|---|" + "---|" * len(MAPS))

    def cell(r):
        if r is None:
            return "—"
        if "error" in r:
            return "n/a"
        if r["score"] is None:
            return f"incomplete ({r['complete']})"
        return f"{r['score']:.1f} ± {r.get('score_ci95_s', 0):.1f} {mark(r)}"
    for n in names:
        out.append(f"| {n} | " + " | ".join(cell(summary[m]["controllers"].get(n)) for m in MAPS) + " |")
    for label, groups in LEARNED.items():
        for g in groups:
            out.append(f"| {label.split(' (')[0]}, {g} | " + " | ".join(cell(summary[m]["controllers"].get(f"{label}::{g}")) for m in MAPS) + " |")
        if len(groups) > 1:
            row = []
            for m in MAPS:
                rs = [summary[m]["controllers"].get(f"{label}::{g}") for g in groups]
                s = [r["score"] for r in rs if r and r.get("score") is not None]
                row.append(f"**{np.mean(s):.1f}** (sd {np.std(s, ddof=1):.1f}; {sum(r['feasible'] for r in rs if r)}/{len(rs)} ✓)" if len(s) == len(rs) else "—")
            out.append(f"| {label.split(' (')[0]}, mean of {len(groups)} learner seeds | " + " | ".join(row) + " |")
    # 2. equal-map relative delay vs tuned Fixed-Time (mean over maps of mean over cases of delay ratio)
    out.append("\n### Equal-map relative delay vs tuned Fixed-Time (lower is better; per-case means over valid runs; only controllers that run on all six maps)\n")
    out.append("| Controller | relative delay | per map |")
    out.append("|---|---|---|")
    rel = {}
    for name in list(summary[MAPS[0]]["controllers"]):
        per = []
        for m in MAPS:
            r, ft = summary[m]["controllers"].get(name), summary[m]["controllers"]["fixed_time"]
            if not r or "error" in r or r["score"] is None:
                break
            per.append(np.mean([r["cases"][c]["delay_per_scheduled_s"] / ft["cases"][c]["delay_per_scheduled_s"]
                                for c in summary[m]["cases"]]))
        if len(per) == len(MAPS):
            rel[name] = (float(np.mean(per)), per)
    for name, (v, per) in sorted(rel.items(), key=lambda x: x[1][0]):
        out.append(f"| {name.replace('::', ', ')} | {v:.3f} | " + " · ".join(f"{SHORT[m]} {p:.2f}" for m, p in zip(MAPS, per)) + " |")
    # 3. qualification of learned controllers
    out.append("\n### Research qualification gate (learned controllers; paired over 20 test seeds)\n")
    out.append("Relative delay improvement vs each baseline (positive = learned better), with the paired bootstrap 95 % CI of the delay difference in s.\n")
    out.append("| Map | Policy | Seeds | Promoted | vs fixed_time | vs actuated | vs max_pressure | vs edgeflow | Blocking reasons |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for m in MAPS:
        for k, r in summary[m]["controllers"].items():
            if "::" in k and "qualification" in r:
                q = r["qualification"]
                cmp = [q["comparisons"].get(b) for b in ("fixed_time", "actuated", "max_pressure", "edgeflow")]
                cells = [f"{c['relative_delay_improvement'] * 100:+.1f} % [{c['paired_ci95_s'][0]:+.1f}, {c['paired_ci95_s'][1]:+.1f}]" if c else "—" for c in cmp]
                reasons = "; ".join(q["reasons"][:4]) + (f" (+{len(q['reasons']) - 4} more)" if len(q["reasons"]) > 4 else "")
                out.append(f"| {SHORT[m]} | {k.split('::')[1]} | {q['seeds']} | {'yes' if q['promoted'] else 'no'} | " + " | ".join(cells) + f" | {reasons} |")
    # 3b. paired context vs the best passing deterministic controller
    out.append("\n### Learned vs the best guardrail-passing deterministic controller (paired over test seeds valid in both)\n")
    out.append("Learned minus deterministic equal-case delay, s (negative = learned better), mean ± t 95 % half-width over seeds. The deterministic side is the lowest-scoring controller, plain or with max-red, that passes the guardrail on that map.\n")
    out.append("| Map | Best deterministic | " + " | ".join(g for gs in LEARNED.values() for g in gs) + " |")
    out.append("|---|---|" + "---|" * sum(len(gs) for gs in LEARNED.values()))
    for m in MAPS:
        c = summary[m]["controllers"]
        rows = [c.get(f"{label}::{g}", {}).get("vs_best_deterministic") for label, gs in LEARNED.items() for g in gs]
        best = next((r["controller"] for r in rows if r), "—")
        out.append(f"| {SHORT[m]} | {best} ({fmt(c[best]['score']) if best in c else '—'}) | "
                   + " | ".join(f"{r['diff_s']:+.1f} ± {r['ci95_s']:.1f}" if r else "—" for r in rows) + " |")
    # 4. per map: per-case delay/tails and secondary metrics
    for m in MAPS:
        s = summary[m]
        cases = s["cases"]
        rows = [(k, v) for k, v in s["controllers"].items() if "error" not in v and v["cases"]]
        out.append(f"\n### {SHORT[m]} (`{m}`)\n")
        out.append("Per case: mean delay / p95 wait / worst-approach wait / max approach-p95 wait (s), mean over 20 test seeds.\n")
        out.append("| Controller | Score | Pass | " + " | ".join(cases) + " |")
        out.append("|---|---|---|" + "---|" * len(cases))
        for k, v in rows:
            out.append(f"| {k.replace('::', ', ')} | {fmt(v['score'])} | {mark(v)} | "
                       + " | ".join(" / ".join(fmt(v['cases'][c][t]) for t in TAIL) if c in v["cases"] else "—" for c in cases) + " |")
        out.append("\nOther metrics, averaged over cases (recovery: bottleneck and reversal cases only, seeds that recovered; censored = runs that never recovered). Collisions / teleports / accounting losses are totals over valid runs; invalid = runs SUMO rejected for a collision or teleport (excluded from every mean).\n")
        out.append("| Controller | Completion % | Throughput veh/s | Unfinished | Uninserted | Peak backlog veh | Recovery s (censored) | Max service gap s | Clearance node-s | " + " | ".join(f"{c} delay" for c in CLASSES) + " | Coll / tele / acct / invalid | Wall s/run |")
        out.append("|---|" + "---|" * (10 + len(CLASSES)))
        for k, v in rows:
            cs = v["cases"].values()
            avg = lambda key: float(np.mean([c[key] for c in cs]))  # noqa: E731
            rec = [c["recovery_s"] for c in cs if c["recovery_applicable"] and c["recovery_s"] is not None]
            cens = sum(c["recovery_censored"] for c in cs if c["recovery_applicable"])
            cls = [fmt(np.mean([c["class_delay_s"][x] for c in cs if x in c["class_delay_s"]])) if any(x in c["class_delay_s"] for c in cs) else "—" for x in CLASSES]
            tot = lambda key: sum(c[key] for c in cs)  # noqa: E731
            out.append(f"| {k.replace('::', ', ')} | {avg('completion_rate') * 100:.2f} | {avg('throughput_veh_per_s'):.3f} | {avg('unfinished'):.1f} | "
                       f"{avg('uninserted'):.1f} | {avg('peak_backlog_veh'):.0f} | {fmt(np.mean(rec)) if rec else '—'} ({cens}) | "
                       f"{avg('max_service_gap_s'):.0f} | {avg('clearance_node_s'):.0f} | " + " | ".join(cls)
                       + f" | {tot('collisions')} / {tot('teleports')} / {tot('accounting_losses')} / {v['invalid_runs']} | {avg('wall_s'):.1f} |")
    return "\n".join(out)


if __name__ == "__main__":
    summary = build()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "summary.json").write_text(json.dumps(summary, indent=1))
    print(tables(summary))
