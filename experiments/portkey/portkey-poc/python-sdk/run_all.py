"""
run_all.py
----------
Run all 8 Portkey Cloud Python SDK demos in sequence and print a pass/fail summary.

Usage:
    python run_all.py              # run all 8 demos
    python run_all.py --only 1 4   # run demos 1 and 4 only
    python run_all.py --skip 7 8   # skip guardrails and semantic cache
"""

import sys
import os
import time
import argparse
import traceback

sys.path.insert(0, os.path.dirname(__file__))

DEMOS = [
    (1, "Basic Completion",       "01_basic_completion"),
    (2, "Chat Completion",        "02_chat_completion"),
    (3, "Streaming Response",     "03_streaming"),
    (4, "Fallback Routing",       "04_fallback"),
    (5, "Load Balancing",         "05_load_balance"),
    (6, "Retry & Timeout",        "06_retry_timeout"),
    (7, "Guardrails",             "07_guardrails"),
    (8, "Semantic Cache",         "08_semantic_cache"),
]


def parse_args():
    p = argparse.ArgumentParser(description="Run Portkey Cloud POC demos")
    p.add_argument("--only", nargs="+", type=int, help="Run only these demo numbers")
    p.add_argument("--skip", nargs="+", type=int, help="Skip these demo numbers")
    return p.parse_args()


def run():
    args = parse_args()

    print("\n" + "█" * 64)
    print("  Portkey Cloud POC — Python SDK Demos")
    print("  Gateway : api.portkey.ai  (Portkey Cloud)")
    print("█" * 64)

    results = []

    for num, label, module_name in DEMOS:
        if args.only and num not in args.only:
            continue
        if args.skip and num in args.skip:
            results.append((num, label, "SKIP", 0))
            continue

        print(f"\n{'━' * 64}")
        print(f"  Demo {num:02d} of {len(DEMOS):02d}  —  {label}")
        print(f"{'━' * 64}")

        start = time.perf_counter()
        try:
            import importlib
            mod = importlib.import_module(module_name)
            mod.run()
            elapsed = (time.perf_counter() - start) * 1000
            results.append((num, label, "PASS", elapsed))
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            traceback.print_exc()
            results.append((num, label, "FAIL", elapsed))

        time.sleep(0.5)  # brief pause between demos

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n{'═' * 64}")
    print("  SUMMARY")
    print(f"{'═' * 64}")
    print(f"  {'#':<4} {'Demo':<28} {'Status':<8} {'Time':>8}")
    print(f"  {'─' * 54}")
    for num, label, status, ms in results:
        icon = "✅" if status == "PASS" else ("⏭️ " if status == "SKIP" else "❌")
        time_str = f"{ms:.0f}ms" if status != "SKIP" else "—"
        print(f"  {icon} {num:<3} {label:<28} {status:<8} {time_str:>8}")

    passed  = sum(1 for _, _, s, _ in results if s == "PASS")
    failed  = sum(1 for _, _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, _, s, _ in results if s == "SKIP")
    print(f"\n  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")
    print(f"{'═' * 64}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run()
