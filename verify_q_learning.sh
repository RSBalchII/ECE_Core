#!/bin/bash
# Script to verify that all QLearningGraphAgent components work correctly

echo "Verifying QLearningGraphAgent implementation..."

# Check that all required files exist
echo "Checking required files..."
REQUIRED_FILES=(
    "src/external_context_engine/memory_management/models/memory_path.py"
    "src/external_context_engine/memory_management/q_learning/q_learning_agent.py"
    "src/external_context_engine/memory_management/q_learning/__init__.py"
    "src/external_context_engine/memory_management/models/__init__.py"
    "tests/unit/q_learning/test_imports.py"
    "tests/unit/q_learning/test_q_learning_agent.py"
    "tests/integration/q_learning/test_q_learning_api.py"
    "docs/q_learning_agent.md"
    "examples/q_learning_example.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "ERROR: Required file $file not found"
        exit 1
    fi
done

echo "All required files found."

# Run import tests
echo "Running import tests..."
python3 -m pytest tests/unit/q_learning/test_imports.py -v
if [ $? -ne 0 ]; then
    echo "ERROR: Import tests failed"
    exit 1
fi

# Run unit tests
echo "Running unit tests..."
python3 -m pytest tests/unit/q_learning/test_q_learning_agent.py -v
if [ $? -ne 0 ]; then
    echo "ERROR: Unit tests failed"
    exit 1
fi

# Run integration tests
echo "Running integration tests..."
python3 -m pytest tests/integration/q_learning/test_q_learning_api.py::TestQLearningAPI::test_get_convergence_metrics_endpoint -v
if [ $? -ne 0 ]; then
    echo "ERROR: Integration tests failed"
    exit 1
fi

# Check that the application can be imported
echo "Checking application import..."
python3 -c "from src.external_context_engine.main import app; print('Application imported successfully')"
if [ $? -ne 0 ]; then
    echo "ERROR: Application import failed"
    exit 1
fi

echo "All checks passed! QLearningGraphAgent implementation is working correctly."