#!/bin/bash

# Nifty Paper Trading System - Unix Startup Script

echo "========================================"
echo " Nifty Paper Trading System"
echo "========================================"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update requirements
echo "Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

# Run the app
echo ""
echo "========================================"
echo " Starting Flask Backend..."
echo "========================================"
echo ""
echo "Open browser: http://localhost:5000"
echo ""

python app.py
