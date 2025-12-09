#!/bin/bash
# run_tests.sh - Run test suite for ECE_Core

echo "========================================="
echo "  ECE_Core Test Suite"
echo "========================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing dependencies..."
    pip install -r requirements.txt
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo "Running tests..."
echo ""

# Run tests with coverage
pytest tests/ \
    --verbose \
    --cov=. \
    --cov-report=term-missing \
    --cov-report=html:coverage_html \
    --tb=short

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    echo ""
    echo "Coverage report: coverage_html/index.html"
else
    echo ""
    echo "❌ Some tests failed"
    exit 1
fi
