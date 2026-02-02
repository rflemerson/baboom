
import subprocess
import sys
import os

item_ids = [1, 2, 3, 4, 5, 6, 7, 8]

for item_id in item_ids:
    print(f"\n=== PROCESSING ITEM {item_id} ===")
    cmd = [sys.executable, "agents/flows/main_flow.py", "--item-id", str(item_id)]
    # Set the environment variable for the subprocess
    env = os.environ.copy()
    env["AGENTS_API_KEY"] = "dev-key"
    try:
        subprocess.run(cmd, check=True, env=env)
        print(f"DONE: ITEM {item_id}")
    except subprocess.CalledProcessError as e:
        print(f"FAILED: ITEM {item_id}: {e}")

print("\n--- ALL TASKS FINISHED ---")
