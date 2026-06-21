# Sandbox image for executing model-generated Python tests.
# Build: docker build -f docker/python-runner.Dockerfile -t qabench-python:latest .
FROM python:3.11-slim

RUN pip install --no-cache-dir pytest==8.* pytest-json-report==1.5.* coverage==7.*

# Unprivileged user; root filesystem is mounted read-only at run time.
RUN useradd -m runner
USER runner

WORKDIR /work
