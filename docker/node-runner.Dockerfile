# Sandbox image for executing model-generated JS/TS unit tests (vitest).
# Build: docker build -f docker/node-runner.Dockerfile -t qabench-node:latest .
FROM node:22-slim

RUN npm install -g vitest@2 c8@10 typescript@5

RUN useradd -m runner
USER runner

WORKDIR /work
