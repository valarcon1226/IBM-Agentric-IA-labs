import datetime
import sys

args = sys.argv[1:]
now = datetime.datetime.now(datetime.UTC).isoformat()
print(f"[{now}] Demo task running with args: {args}")
print("Demo task finished successfully.")
sys.exit(0)
