#!/bin/bash
# Startup script for test MCP Server

set -e

# Change to script directory
cd "$(dirname "$0")"

# Check Python version
python3 --version >/dev/null 2>&1 || {
    echo "Error: Python 3 is required but not found"
    exit 1
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start server
echo "Starting Test MCP Server..."
python server.py "$@"
