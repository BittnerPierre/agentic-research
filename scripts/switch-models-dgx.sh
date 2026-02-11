#!/usr/bin/env bash
# Switch model setup without restarting Docker
set -euo pipefail

SETUP_NAME=${1:-}

if [ -z "$SETUP_NAME" ]; then
  echo "Usage: $0 <setup_name>"
  echo ""
  echo "Available setups:"
  echo "  - ministral"
  echo "  - mistralai"
  echo "  - glm"
  echo "  - qwen"
  echo "  - openai"
  exit 1
fi

MODELS_ENV="models.${SETUP_NAME}.env"

if [ ! -f "$MODELS_ENV" ]; then
  echo "Error: $MODELS_ENV not found"
  exit 1
fi

echo "🔗 Switching to $MODELS_ENV..."
ln -sf "$MODELS_ENV" models.env

# Show current setup
echo ""
echo "Current setup:"
ls -l models.env

echo ""
echo "✅ Model setup switched to: $SETUP_NAME"
echo "⚠️  Note: Docker services NOT restarted."
echo "   Run ./scripts/start-docker-dgx.sh to apply changes."
