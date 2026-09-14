"""Append-only experiment ledger (plan/14 I1.6) -- the honest count of every backtest
variant ever tried, across sessions.

Why: `diagnostics.deflated_sharpe_ratio` discounts a result by the number of variants
searched (`n_trials`). Each caller (scan.py, xsect.py, run.py) only knows what IT searched
this run -- a variant tried yesterday, or in a different script, is invisible to it, so N
is under-reported and the deflated Sharpe looks better than it should. This is exactly the
multiple-testing trap the harness exists to catch.

`experiments.jsonl` is append-only, one JSON record per real experiment. `trial_count(family)`
returns the number of DISTINCT `config_key`s ever logged under that research question
("family") -- rerunning the identical config does not inflate N, a new variant does.

Off switches (synthetic / self-test runs must never pollute the ledger):
  - callers simply don't call `log_experiment` for synthetic data (see scan.py/xsect.py/
    run.py -- run.py only logs when given a real CSV)
  - `LEDGER_DISABLE=1` env var makes `log_experiment` a no-op, belt-and-suspenders.

Reads (`trial_count`) are NEVER disabled by `LEDGER_DISABLE` -- that var only stops writes,
so a session that turns off logging still sees the honest N left by earlier sessions.
"""
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

PATH = "experiments.jsonl"


def _disabled():
    return os.environ.get("LEDGER_DISABLE") == "1"


def _git_sha():
    """(sha, dirty) of the current worktree, or (None, None) if git isn't available."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL).decode().strip())
        return sha, dirty
    except Exception:
        return None, None


def _canonical(obj):
    """Stable JSON encoding used for hashing -- sorted keys so the same config always
    hashes the same way regardless of dict insertion order."""
    return json.dumps(obj, sort_keys=True, default=str)


def data_hash(paths):
    """sha256 over the sorted (filename, size, content-sha256) of `paths` -- identifies
    exactly which bytes a trial ran against. Missing/None paths are skipped; returns None
    if nothing resolved (e.g. a synthetic run with no backing file)."""
    entries = []
    for p in paths or []:
        if not p or not os.path.exists(p):
            continue
        with open(p, "rb") as f:
            content = f.read()
        entries.append([os.path.basename(p), len(content), hashlib.sha256(content).hexdigest()])
    if not entries:
        return None
    entries.sort()
    return hashlib.sha256(_canonical(entries).encode()).hexdigest()


def config_key(family, strategy, params, universe):
    """sha256 identifying one distinct (family, strategy, params, ticker/universe) variant.
    Two runs of the SAME config hash identically no matter when or how often they're run --
    that's what keeps `trial_count` immune to reruns."""
    payload = _canonical({"family": family, "strategy": strategy,
                          "params": params, "universe": universe})
    return hashlib.sha256(payload.encode()).hexdigest()


def log_experiment(family, strategy, params, universe, data_paths=None, result=None,
                   window=None, path=None):
    """Append one experiment record. No-op (returns None) if LEDGER_DISABLE=1."""
    path = path or PATH
    if _disabled():
        return None
    sha, dirty = _git_sha()
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha, "dirty": dirty,
        "entrypoint": {"script": os.path.basename(sys.argv[0]) if sys.argv else None,
                       "argv": list(sys.argv[1:]) if sys.argv else []},
        "family": family, "strategy": strategy, "params": params, "universe": universe,
        "window": window,
        "data_hash": data_hash(data_paths),
        "config_key": config_key(family, strategy, params, universe),
        "result": result or {},
    }
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return record


def load_experiments(path=None):
    path = path or PATH
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def trial_count(family, path=None):
    """Number of DISTINCT config_keys ever logged under `family` -- the honest N a caller
    cannot under-report. Rerunning an identical config doesn't grow it; a new variant does."""
    keys = {r["config_key"] for r in load_experiments(path) if r.get("family") == family}
    return len(keys)
