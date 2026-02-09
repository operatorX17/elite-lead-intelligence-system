#!/bin/bash

# ZRAI Lead OS - Quick Start Script
# This script helps you get started quickly

set -e

echo "=========================================="
echo "ZRAI Lead OS - Quick Start"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.11+ required. Current: $python_version"
    exit 1
fi
echo "✅ Python $python_version"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "✅ .env created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env with your API keys before continuing!"
    echo ""
    read -p "Press Enter after you've edited .env..."
else
    echo "✅ .env exists"
fi
echo ""

# Install dependencies
echo "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt > /dev/null 2>&1
    echo "✅ Dependencies installed"
else
    echo "❌ requirements.txt not found"
    exit 1
fi
echo ""

# Run setup verification
echo "Running setup verification..."
python setup.py
echo ""

# Check if setup passed
if [ $? -eq 0 ]; then
    echo "=========================================="
    echo "✅ Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Check system status:"
    echo "   python -m src.cli status"
    echo ""
    echo "2. Try a dry run:"
    echo "   python -m src.cli dry_run --limit 5"
    echo ""
    echo "3. Run the pipeline:"
    echo "   python -m src.cli run_daily --limit 10"
    echo ""
    echo "4. View help:"
    echo "   python -m src.cli --help"
    echo ""
    echo "For more information, see README.md"
    echo "=========================================="
else
    echo "=========================================="
    echo "❌ Setup failed"
    echo "=========================================="
    echo ""
    echo "Please fix the issues above and try again."
    echo ""
    echo "Common issues:"
    echo "- Missing API keys in .env"
    echo "- Supabase migrations not run"
    echo "- Pinecone index not created"
    echo ""
    echo "See README.md for detailed setup instructions."
    exit 1
fi
