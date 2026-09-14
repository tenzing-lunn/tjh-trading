"""Verdict auto-logger (plan/10 Part A) -- the harness writes results, humans write judgment.

Every real walk-forward run appends one JSON line to `verdicts.jsonl`. The logger
NEVER recomputes anything: it records what metrics.py / diagnostics.py already produced.
Synthetic runs are tagged `synthetic=true` so they can't pollute the real track record.

Render the machine log as a markdown table (newest first):

    python3 verdict_log.py                 # print the table
    python3 verdict_log.py --write-md plan/02-verdict-log.md
                                           # refresh the AUTO section of the verdict log
                                           # (everything above the marker is human-owned;
                                           #  Henry's judgment stays a human column)
"""
import json
import os
import sys
from datetime import datetime, timezone

PATH = "verdicts.jsonl"
MARKER = "<!-- AUTO-VERDICTS BELOW: rendered by verdict_log.py, do not hand-edit -->"


def _jsonable(v):
    if hasattr(v, "item"):                 # numpy scalar -> python scalar
        return v.item()
    raise TypeError(f"not JSON serializable: {type(v)}")


def append_verdict(record, path=PATH):
    """Append one result record as a JSON line. Adds a UTC timestamp if missing."""
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with open(path, "a") as f:
        f.write(json.dumps(record, default=_jsonable) + "\n")
    return record


def load_verdicts(path=PATH):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def scan_row_to_record(row, cost_regime="3/1 bps (liquid ETF)"):
    """Map one scan.py result row (see scan.scan_universe) onto the verdict schema.
    The logger stays a pure recorder: every field here already came out of metrics.py /
    diagnostics.py inside the scan -- nothing is recomputed."""
    m = row["metrics"]
    return {
        "ticker": row["ticker"], "strategy": row["strategy"],
        "cost_regime": cost_regime, "run": "wide_scan",
        "oos_total_return": m["total_return"], "oos_sharpe": m["sharpe"],
        "oos_max_dd": m["max_drawdown"], "num_trades": m["num_trades"],
        "buy_hold_return": row["bh_return"], "spy_return": row["spy_return"],
        "beats_bh": bool(row["beats_bh"]),
        # What actually gated the verdict: significance of the ACTIVE return (strategy net
        # minus benchmark net) against both benchmarks, the scan-wide best-of-N discount, and
        # the percentile against holding-period-matched random schedules.
        "active_return_vs_bh": row["active_return_vs_bh"],
        "dsr_vs_bh": row["dsr_vs_bh"], "dsr_vs_spy": row["dsr_vs_spy"],
        "dsr_scan": row["dsr_scan"], "rand_pct": row["rand_pct"],
        # Legacy field, kept so old records stay comparable: the binding (weakest) of the
        # three active DSR legs above. NOT the old raw vs-zero number, which pure beta passed.
        "deflated_sharpe": row["dsr"], "trades_per_fold": row["trades_per_fold"],
        "red_flags": row["red_flags"], "clean": bool(row["clean"]),
        "synthetic": False,
    }


def _pct(v):
    return f"{v * 100:+.1f}%" if isinstance(v, (int, float)) and v == v else "--"


def render_markdown(records):
    """Markdown table of real (non-synthetic) records, newest first. Judgment is
    deliberately blank: that column belongs to Henry, never the machine."""
    rows = [r for r in records if not r.get("synthetic")]
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    # Keep only the newest verdict per (ticker, strategy, run, cost_regime) so re-running
    # a scan refreshes the record instead of stacking duplicate rows.
    seen, deduped = set(), []
    for r in rows:
        key = (r.get("ticker"), r.get("strategy"), r.get("run", "single"), r.get("cost_regime"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    rows = deduped
    out = ["| Date | Strategy | Data | Cost regime | OOS net | OOS Sharpe | vs B&H | vs SPY | Flags | Judgment (Henry) |",
           "|------|----------|------|-------------|---------|-----------|--------|--------|-------|------------------|"]
    for r in rows:
        flags = r.get("red_flags") or []
        out.append("| {d} | {s} | {t} | {c} | {oos} | {sh} | {bh} | {spy} | {fl} | |".format(
            d=str(r.get("timestamp", ""))[:10], s=r.get("strategy", "?"),
            t=r.get("ticker", "?"), c=r.get("cost_regime", "?"),
            oos=_pct(r.get("oos_total_return")),
            sh=f"{r['oos_sharpe']:.2f}" if r.get("oos_sharpe") == r.get("oos_sharpe") else "--",
            bh="BEAT" if r.get("beats_bh") else "lost",
            spy=_pct(r.get("spy_return")),
            fl=f"{len(flags)} flag(s)" if flags else "none"))
    return "\n".join(out)


def write_md(md_path, records):
    """Replace everything below MARKER in md_path (append the section if absent)."""
    table = render_markdown(records)
    text = open(md_path).read() if os.path.exists(md_path) else ""
    head = text.split(MARKER)[0].rstrip()
    open(md_path, "w").write(f"{head}\n\n{MARKER}\n\n{table}\n")


if __name__ == "__main__":
    recs = load_verdicts()
    if not recs:
        sys.exit("no verdicts.jsonl yet -- run `python3 run.py <ticker.csv>` first")
    if len(sys.argv) > 2 and sys.argv[1] == "--write-md":
        write_md(sys.argv[2], recs)
        print(f"refreshed AUTO section of {sys.argv[2]} ({len(recs)} records)")
    else:
        print(render_markdown(recs))
