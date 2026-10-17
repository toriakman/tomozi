"""Production server: one process shares the persistent SQLite database."""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = 1
threads = 4
timeout = 30
# URLs contain private host/participant tokens; omit them from access logs.
accesslog = None
errorlog = "-"
