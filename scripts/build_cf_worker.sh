#!/usr/bin/env bash
set -e

echo "Building QA Benchmark Dashboard for Cloudflare..."

# We must run this from the dashboard directory
cd "$(dirname "$0")/../dashboard"

# Ensure we have the latest static export
uv run reflex export --frontend-only

# Create a basic wrangler.toml configuration
cat > wrangler.toml <<EOF
name = "qabench-dashboard"
compatibility_date = "2024-03-20"
pages_build_output_dir = ".web/_static"
EOF

echo "✅ Build complete."
echo "To test the Cloudflare worker LOCALLY without deploying, run:"
echo "  cd dashboard && npx wrangler pages dev .web/_static"
echo ""
echo "To deploy DIRECTLY to Cloudflare from your local machine (no GitHub required), run:"
echo "  cd dashboard && npx wrangler pages deploy .web/_static --project-name qabench-dashboard"
