#!/bin/bash
set -e

echo "🚀 Setting up Universal Swagger → MCP Server development environment..."

# Check if Python 3.11+ is installed
python_version=$(python3 --version 2>&1 | sed 's/.* \([0-9]\).\([0-9]\).\([0-9]\).*/\1\2\3/')
if [ "$python_version" -lt "311" ]; then
    echo "❌ Error: Python 3.11 or higher is required"
    echo "Current version: $(python3 --version)"
    exit 1
fi

echo "✅ Python $(python3 --version) detected"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
    echo "✅ Poetry installed"
else
    echo "✅ Poetry already installed"
fi

# Install project dependencies
echo "📦 Installing project dependencies..."
poetry install --with dev

# Setup pre-commit hooks
echo "🔗 Installing pre-commit hooks..."
poetry run pre-commit install

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/samples
mkdir -p data/fixtures

# Run initial tests to verify setup
echo "🧪 Running tests to verify setup..."
poetry run pytest src/tests/unit/test_sample.py -v

# Run linting to verify setup
echo "🔍 Running linting to verify setup..."
poetry run black --check src/ || poetry run black src/
poetry run isort --check-only src/ || poetry run isort src/
poetry run flake8 src/

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "To activate the virtual environment:"
echo "  poetry shell"
echo ""
echo "To run tests:"
echo "  pytest"
echo "  pytest --cov=swagger_mcp_server  # with coverage"
echo ""
echo "To run linting:"
echo "  black src/        # format code"
echo "  isort src/        # sort imports"
echo "  flake8 src/       # check linting"
echo "  mypy src/swagger_mcp_server/  # type checking"
echo ""
echo "Happy coding! 🎯"