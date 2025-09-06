#!/bin/bash
# Comprehensive verification script for QLearningGraphAgent

echo "=============================================="
echo "QLearningGraphAgent Comprehensive Verification"
echo "=============================================="

# Exit on any error
set -e

# Function to print section headers
print_section() {
    echo
    echo "----------------------------------------------"
    echo "$1"
    echo "----------------------------------------------"
}

# Function to print success message
print_success() {
    echo "✓ $1"
}

# Function to print failure message
print_failure() {
    echo "✗ $1"
}

# Check that all required files exist
print_section "Checking Required Files"
REQUIRED_FILES=(
    "src/external_context_engine/memory_management/models/memory_path.py"
    "src/external_context_engine/memory_management/models/__init__.py"
    "src/external_context_engine/memory_management/q_learning/q_learning_agent.py"
    "src/external_context_engine/memory_management/q_learning/__init__.py"
    "tests/unit/q_learning/test_imports.py"
    "tests/unit/q_learning/test_q_learning_agent.py"
    "tests/unit/q_learning/__init__.py"
    "tests/integration/q_learning/test_q_learning_api.py"
    "tests/integration/q_learning/__init__.py"
    "docs/q_learning_agent.md"
    "examples/q_learning_example.py"
    "verify_q_learning.sh"
)

missing_files=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_failure "Required file $file not found"
        missing_files=1
    else
        print_success "Found $file"
    fi
done

if [ $missing_files -ne 0 ]; then
    echo "ERROR: Some required files are missing"
    exit 1
fi

# Run import tests
print_section "Running Import Tests"
if python3 -m pytest tests/unit/q_learning/test_imports.py -v --tb=short; then
    print_success "Import tests passed"
else
    print_failure "Import tests failed"
    exit 1
fi

# Run unit tests
print_section "Running Unit Tests"
if python3 -m pytest tests/unit/q_learning/test_q_learning_agent.py -v --tb=short; then
    print_success "Unit tests passed"
else
    print_failure "Unit tests failed"
    exit 1
fi

# Run integration tests
print_section "Running Integration Tests"
if python3 -m pytest tests/integration/q_learning/test_q_learning_api.py -v --tb=short; then
    print_success "Integration tests passed"
else
    print_failure "Integration tests failed"
    exit 1
fi

# Check that the application can be imported
print_section "Checking Application Import"
if python3 -c "from src.external_context_engine.main import app; print('Application imported successfully')"; then
    print_success "Application import successful"
else
    print_failure "Application import failed"
    exit 1
fi

# Verify configuration
print_section "Verifying Configuration"
if grep -q "QLearningGraphAgent" config.yaml; then
    print_success "QLearningGraphAgent configuration found in config.yaml"
else
    print_failure "QLearningGraphAgent configuration not found in config.yaml"
    exit 1
fi

if grep -q "find_path" config.yaml; then
    print_success "find_path intent found in config.yaml"
else
    print_failure "find_path intent not found in config.yaml"
    exit 1
fi

# Verify documentation
print_section "Verifying Documentation"
if grep -q "QLearningGraphAgent" README.md; then
    print_success "QLearningGraphAgent documentation found in README.md"
else
    print_failure "QLearningGraphAgent documentation not found in README.md"
    exit 1
fi

if [ -f "docs/q_learning_agent.md" ]; then
    print_success "Detailed documentation found at docs/q_learning_agent.md"
else
    print_failure "Detailed documentation not found at docs/q_learning_agent.md"
    exit 1
fi

# Verify examples
print_section "Verifying Examples"
if [ -f "examples/q_learning_example.py" ]; then
    print_success "Example code found at examples/q_learning_example.py"
else
    print_failure "Example code not found at examples/q_learning_example.py"
    exit 1
fi

# Final summary
echo
echo "=============================================="
echo "ALL VERIFICATIONS PASSED!"
echo "=============================================="
echo
echo "The QLearningGraphAgent implementation is complete and working correctly."
echo
echo "Summary of what was verified:"
echo "  ✓ All required files exist"
echo "  ✓ Import tests pass"
echo "  ✓ Unit tests pass"
echo "  ✓ Integration tests pass"
echo "  ✓ Application can be imported"
echo "  ✓ Configuration is correct"
echo "  ✓ Documentation is in place"
echo "  ✓ Example code is available"
echo
echo "The QLearningGraphAgent is ready for use in the External Context Engine."