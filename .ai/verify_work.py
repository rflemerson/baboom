import os
import sys
import time
from contextlib import suppress

import django
from celery.result import AsyncResult

# Setup Django setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

from baboom.celery import app as celery_app  # noqa: E402
from scrapers.tasks import (  # noqa: E402
    scrape_blackskull_monitor,
    scrape_darklab_monitor,
    scrape_dux_monitor,
    scrape_growth_monitor,
    scrape_integral_monitor,
    scrape_maxtitanium_monitor,
    scrape_probiotica_monitor,
)

TASKS = {
    "Growth (API)": scrape_growth_monitor,
    "Black Skull (API)": scrape_blackskull_monitor,
    "Integral Medica (VTEX)": scrape_integral_monitor,
    "Max Titanium (VTEX)": scrape_maxtitanium_monitor,
    "Probiotica (VTEX)": scrape_probiotica_monitor,
    "Dux Nutrition (VTEX)": scrape_dux_monitor,
    "Dark Lab (Shopify)": scrape_darklab_monitor,
}


def verify_all():
    print("🚀 Starting Verification of All Scrapers...")
    print(f"Target: {len(TASKS)} Brands")
    print("-" * 60)

    results = {}

    # 1. Trigger All Tasks
    for name, task_func in TASKS.items():
        print(f"Triggering: {name}...")
        try:
            # Call .delay() to send to Celery
            async_result = task_func.delay()
            results[name] = {
                "id": async_result.id,
                "status": "PENDING",
                "result": None,
                "start_time": time.time(),
            }
        except Exception as e:
            print(f"❌ Failed to trigger {name}: {e}")
            results[name] = {"status": "ERROR", "error": str(e)}

    # 2. Poll for Completion
    print("\n⏳ Waiting for tasks to complete...")

    pending_count = len(TASKS)
    while pending_count > 0:
        pending_count = 0
        for _, info in results.items():
            if info["status"] in ["PENDING", "STARTED"]:
                res = AsyncResult(info["id"], app=celery_app)
                state = res.state

                if state in ["SUCCESS", "FAILURE", "REVOKED"]:
                    info["status"] = state
                    info["end_time"] = time.time()
                    if state == "SUCCESS":
                        info["result"] = res.result
                    else:
                        info["error"] = str(res.info)
                else:
                    pending_count += 1

        sys.stdout.write(f"\r  Pending Tasks: {pending_count}   ")
        sys.stdout.flush()
        if pending_count > 0:
            time.sleep(1)

    # 3. Report
    print("\n\n" + "=" * 60)
    print("📊 FINAL REPORT")
    print("=" * 60)
    print(f"{'BRAND':<25} | {'STATUS':<10} | {'DURATION':<8} | {'RESULT'}")
    print("-" * 60)

    total_items = 0

    for name, info in results.items():
        status = info["status"]
        duration = 0
        if "end_time" in info:
            duration = round(info["end_time"] - info["start_time"], 2)

        result_str = str(info.get("result", ""))
        if "monitor" in result_str.lower():
            # Extract number from string if possible "Saved/Updated X items"
            with suppress(Exception):
                import re

                match = re.search(r"(\d+)", result_str)
                if match:
                    total_items += int(match.group(1))

        if status == "FAILURE":
            result_str = f"ERR: {info.get('error')}"[:50]

        print(f"{name:<25} | {status:<10} | {duration}s    | {result_str}")

    print("=" * 60)
    print(f"✅ Total Items Processed: {total_items}")
    print("=" * 60)


if __name__ == "__main__":
    verify_all()
