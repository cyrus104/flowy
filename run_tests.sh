#!/bin/bash

################################################################################
# Test Runner Script for Workflow Project
#
# This script automates the execution of the complete test suite using Python's
# unittest framework. It provides colored output, progress reporting, and proper
# exit codes for CI/CD integration.
#
# Usage:
#   ./run_tests.sh                    # Run all tests
#   ./run_tests.sh 2>&1 | tee test_results.log  # Save output to log
################################################################################

# Exit on error
set -e

# Color codes for output formatting
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

# Display banner
echo -e "${BLUE}================================${RESET}"
echo -e "${BLUE}  Workflow Test Suite Runner${RESET}"
echo -e "${BLUE}================================${RESET}"
echo ""

# Pre-flight checks
echo -e "${BLUE}[INFO]${RESET} Checking Python availability..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo -e "${GREEN}✓${RESET} Found Python 3: $(python3 --version)"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    echo -e "${GREEN}✓${RESET} Found Python: $(python --version)"
else
    echo -e "${RED}✗ Error: Python is not installed or not in PATH${RESET}"
    exit 1
fi

echo -e "${BLUE}[INFO]${RESET} Checking tests/ directory..."
if [ ! -d "tests" ]; then
    echo -e "${RED}✗ Error: tests/ directory not found${RESET}"
    echo -e "${YELLOW}Please run this script from the project root directory${RESET}"
    exit 1
fi
echo -e "${GREEN}✓${RESET} Found tests/ directory"
echo ""

# Test execution
echo -e "${BLUE}[INFO]${RESET} Running all tests in tests/ directory..."
echo -e "${BLUE}════════════════════════════════════════════════${RESET}"
echo ""

# Run tests and capture exit code
set +e  # Temporarily disable exit on error to capture test results
$PYTHON_CMD -m unittest discover -s tests -p 'test_*.py' -v
TEST_EXIT_CODE=$?
set -e  # Re-enable exit on error

echo ""
echo -e "${BLUE}════════════════════════════════════════════════${RESET}"

# Results summary
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${RESET}"
    echo -e "${GREEN}Test suite completed successfully.${RESET}"
else
    echo -e "${RED}✗ Some tests failed!${RESET}"
    echo -e "${YELLOW}Review the output above for details.${RESET}"
    echo -e "${YELLOW}Run specific test files with: $PYTHON_CMD -m unittest tests.test_<module>${RESET}"
fi

# Exit with test result code
exit $TEST_EXIT_CODE
