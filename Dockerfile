# F-1 Copilot API. Builds the search index at image build time, so the server starts ready.
# Works on Render, Fly.io, Hugging Face Spaces (Docker) or any container host.
# Needs about 1.5 GB of RAM at runtime (PyTorch + the multilingual embedding model).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface PORT=7860

WORKDIR /app

# CPU-only PyTorch first: about 5x smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY config.yaml ./
COPY rules ./rules

# Crawl the allowlisted official sources and embed them. This also downloads and caches the
# embedding model, so nothing is fetched at startup. Rebuild the image to refresh the corpus.
RUN copilot ingest && copilot stats

# Run as a non-root user (required by Hugging Face Spaces, good practice everywhere).
RUN useradd -m -u 1000 app && chown -R app /app
USER app

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health')"
CMD ["sh", "-c", "copilot serve --host 0.0.0.0 --port ${PORT}"]
