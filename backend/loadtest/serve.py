"""Starts the API for a load run: python -m loadtest.serve <es|pg> <workers> <port>
pg = ELASTICSEARCH_URL emptied, so every search takes the original Postgres path (the baseline).
Search rate limit raised: k6 users are few tokens doing many searches. Other settings come from env / .env."""
import os
import sys

import uvicorn

if __name__ == "__main__":  # worker processes re-import this module; only the parent starts the server
    backend, workers, port = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    if backend == "pg":
        os.environ["ELASTICSEARCH_URL"] = ""
    os.environ["SEARCH_RATE_PER_MINUTE"] = "1000000"
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=workers, log_level="warning", access_log=False)
