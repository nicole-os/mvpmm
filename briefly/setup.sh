#!/bin/bash
# briefly — one-time setup script
# Run this once after cloning: bash setup.sh

set -e

echo ""
echo "▸ Installing Python dependencies..."
python3 -m pip install -r requirements.txt

echo ""
echo "▸ Installing Playwright browser (Chromium)..."
echo "  This downloads the browser binary — takes 1-2 minutes."
python3 -m playwright install chromium

echo ""
echo "▸ Checking for .env file..."
if [ ! -f .env ]; then
    echo "  Creating .env — add your OpenAI API key inside."
    echo "OPENAI_API_KEY=sk-your-key-here" > .env
    echo "  ⚠️  Open .env and replace sk-your-key-here with your real key."
else
    echo "  .env already exists — skipping."
fi

echo ""
echo "✓ Setup complete. Run the app with: python3 run.py"
echo "  Then open http://localhost:8003"
echo ""
