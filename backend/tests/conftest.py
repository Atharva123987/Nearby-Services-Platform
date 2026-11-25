import os

# Most tests build the app without Redis; rate-limit tests opt back in explicitly.
os.environ["RATE_LIMIT_ENABLED"] = "false"
