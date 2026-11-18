# API image (docs/search.md, "Production"). From backend/:  docker build -t samaj-api .
# Settings come from the environment (docker run --env-file / -e); .env is not copied in.
# The same image runs the search worker:  docker run ... samaj-api python -m search.worker
FROM python:3.14-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN useradd --uid 1000 --create-home app && mkdir -p media private && chown app media private
USER app
EXPOSE 8000
# --workers: about one per CPU core (docs/search-loadtest.md). --proxy-headers: the proxy passes the client IP.
# --no-access-log: access lines carry the full query string, i.e. the names people search for. Log at the proxy,
# without query strings, if you need request logs.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--no-access-log"]
