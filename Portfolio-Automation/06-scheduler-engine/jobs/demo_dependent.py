import datetime
import sys

now = datetime.datetime.now(datetime.UTC).isoformat()
print(f"[{now}] Dependent task running after prerequisite succeeded!")
sys.exit(0)
