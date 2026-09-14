"""Tests for ledger.py (plan/14 I1.6) -- plain python3, no test framework.

    python3 test_ledger.py

Uses a temp ledger path throughout so it never touches the real experiments.jsonl.
"""
import os
import subprocess
import sys
import tempfile

import ledger

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main():
    print("=== ledger.py tests ===\n")

    # 1. Identical configs don't grow N; a new param variant grows N by 1.
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "experiments.jsonl")
        ledger.log_experiment("fam", "meanrev", {"lookback": 20}, "spy", path=path)
        ledger.log_experiment("fam", "meanrev", {"lookback": 20}, "spy", path=path)
        n1 = ledger.trial_count("fam", path=path)
        check("identical config logged twice does not grow N", n1 == 1, f"N={n1} (want 1)")

        ledger.log_experiment("fam", "meanrev", {"lookback": 40}, "spy", path=path)
        n2 = ledger.trial_count("fam", path=path)
        check("a new param variant grows N by 1", n2 == 2, f"N={n2} (want 2)")

        ledger.log_experiment("fam", "meanrev", {"lookback": 40}, "qqq", path=path)
        n3 = ledger.trial_count("fam", path=path)
        check("a new ticker (universe) is a new variant", n3 == 3, f"N={n3} (want 3)")

        # a different family is a separate count entirely
        ledger.log_experiment("other-fam", "meanrev", {"lookback": 20}, "spy", path=path)
        check("a different family doesn't leak into this family's count",
              ledger.trial_count("fam", path=path) == 3, "fam count unaffected")
        check("the other family has its own count of 1",
              ledger.trial_count("other-fam", path=path) == 1)

    # 2. A caller passing n_trials=1 against a ledger with 12 distinct configs gets N=12.
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "experiments.jsonl")
        for i in range(12):
            ledger.log_experiment("fam12", "s", {"i": i}, "t", path=path)
        n_used = ledger.trial_count("fam12", path=path)
        check("ledger has 12 distinct configs", n_used == 12, f"N={n_used}")

        import diagnostics
        eff = diagnostics.effective_n_trials(1, family=None)  # family=None: unaffected
        check("family=None leaves n_trials untouched", eff == 1, f"eff={eff} (want 1)")

        # effective_n_trials reads the MODULE-LEVEL ledger.PATH, so point it at our temp
        # ledger for the duration of this check, then restore it.
        old_path = ledger.PATH
        ledger.PATH = path
        try:
            eff12 = diagnostics.effective_n_trials(1, family="fam12")
            check("a caller under-reporting n_trials=1 gets the ledger's N=12",
                  eff12 == 12, f"eff={eff12} (want 12)")
            eff_over = diagnostics.effective_n_trials(20, family="fam12")
            check("a caller's own (larger) n_trials is never reduced by the ledger",
                  eff_over == 20, f"eff={eff_over} (want 20)")
        finally:
            ledger.PATH = old_path

    # 3. LEDGER_DISABLE=1 writes nothing.
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "experiments.jsonl")
        os.environ["LEDGER_DISABLE"] = "1"
        try:
            rec = ledger.log_experiment("fam", "s", {}, "t", path=path)
            check("log_experiment returns None when LEDGER_DISABLE=1", rec is None)
            check("LEDGER_DISABLE=1 writes no file at all", not os.path.exists(path))
        finally:
            del os.environ["LEDGER_DISABLE"]
        # sanity: without the flag, the same call DOES write
        ledger.log_experiment("fam", "s", {}, "t", path=path)
        check("without the flag, the same call writes normally", os.path.exists(path))

    # 4. sanity_check.py leaves the ledger file byte-identical (it must never touch it --
    #    it calls diagnostics functions with no `family`, and never imports ledger).
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "experiments.jsonl")
        ledger.log_experiment("fam", "s", {"x": 1}, "t", path=path)
        before = open(path, "rb").read()
        env = dict(os.environ)
        env["LEDGER_DISABLE"] = "1"          # belt-and-suspenders; sanity_check shouldn't need it
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run([sys.executable, "sanity_check.py"], cwd=repo_dir, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        after = open(path, "rb").read()
        check("sanity_check.py leaves an unrelated ledger file byte-identical",
              before == after)
        # and it must not have touched the REAL experiments.jsonl either
        real = os.path.join(repo_dir, "experiments.jsonl")
        real_before = open(real, "rb").read() if os.path.exists(real) else None
        subprocess.run([sys.executable, "sanity_check.py"], cwd=repo_dir,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        real_after = open(real, "rb").read() if os.path.exists(real) else None
        check("sanity_check.py leaves the real experiments.jsonl untouched",
              real_before == real_after)

    n_fail = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{'='*48}\n{len(results)-n_fail}/{len(results)} checks passed.")
    if n_fail:
        print("FAILED.")
        return 1
    print("All green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
