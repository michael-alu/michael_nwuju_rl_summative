# ThinBook Pension game server for Render (or any Docker host).
#
# Serves the browser game and its API (environment/rendering.py) with the trained models already in the
# repo. Torch is the CPU-only build, so the image skips the ~2 GB of GPU libraries the default Linux build
# pulls in; the server needs about 200 MB of memory, which fits Render's free plan.
#
# Local test:
#   docker build -t thinbook .
#   docker run -p 8000:8000 thinbook        then open http://127.0.0.1:8000

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /app

# The same versions as pyproject.toml; torch comes from the CPU-only index.
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir \
    "numpy>=1.26,<2" \
    "gymnasium==0.29.1" \
    "torchrl==0.3.1" \
    "tensordict==0.3.2" \
    "pandas>=2.1,<2.3" \
    "matplotlib>=3.8,<3.10" \
    "pyyaml>=6.0" \
    "fastapi>=0.110,<0.116" \
    "uvicorn[standard]>=0.29,<0.33"

COPY . .

EXPOSE 8000

# Render sets PORT; locally it falls back to 8000.
CMD ["sh", "-c", "exec uvicorn environment.rendering:app --host 0.0.0.0 --port ${PORT:-8000}"]
