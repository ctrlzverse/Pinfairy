#!/bin/bash

# Pinfairy Bot Setup Script
# This script sets up the development environment for Pinfairy Bot

set -e  # Exit on any error

echo "🚀 Setting up Pinfairy Bot development environment..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "📋 Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Install development dependencies (optional)
if [ "$1" = "--dev" ]; then
    echo "🛠️ Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

# Install Playwright browsers
echo "🎭 Installing Playwright browsers..."
playwright install

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env.template .env
    echo "⚠️ Please edit .env file with your credentials before running the bot"
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p downloads
mkdir -p logs
mkdir -p backups

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Telegram bot credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python3 bot_enhanced.py (recommended) or python3 bot.py"
echo ""
echo "For development:"
echo "- Run tests: pytest"
echo "- Format code: black ."
echo "- Check types: mypy ."
