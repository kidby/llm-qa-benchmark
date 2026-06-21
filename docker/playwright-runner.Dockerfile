# Sandbox image for executing model-generated Playwright E2E tests.
# Build: docker build -f docker/playwright-runner.Dockerfile -t qabench-playwright:latest .
#
# @playwright/test and @axe-core/playwright are installed in /pw (not /work) so the
# runtime bind-mount of the test files onto /work does not hide them; NODE_PATH lets
# the test's bare `import ... from '@playwright/test'` (and '@axe-core/playwright')
# resolve from /pw.
#
# @playwright/test is pinned to the base image's Playwright version so the test
# runner matches the browsers baked into the image. @axe-core/playwright powers the
# accessibility-audit scenario.
#
# The E2E track needs network access to reach the app under test, so the runner
# relaxes --network none for this image only (see qabench/scoring/e2e.py).
FROM mcr.microsoft.com/playwright:v1.60.0-noble

WORKDIR /pw
RUN npm init -y >/dev/null 2>&1 \
    && npm install -D @playwright/test@1.60.0 @axe-core/playwright@4
ENV NODE_PATH=/pw/node_modules

WORKDIR /work
