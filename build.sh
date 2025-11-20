#!/bin/bash

################################################################################
# build.sh - Automated Wheel Building Script for flowy
#
# This script automates the process of building a Python wheel package for
# the flowy CLI application. It cleans old build artifacts,
# verifies dependencies, and creates distributable wheel files.
#
# Usage: ./build.sh
#
# Note: This script is designed for Unix-like systems (Linux, macOS, WSL).
#       Windows users should run the equivalent commands manually or use
#       PowerShell with appropriate syntax adjustments.
################################################################################

# Exit immediately if any command fails
set -e

echo "=========================================="
echo "  Flowy Wheel Build Script"
echo "=========================================="
echo ""

# Step 1: Clean old build artifacts
echo "[1/3] Cleaning old build artifacts..."
rm -rf dist/
rm -rf build/
rm -rf *.egg-info
echo "      ✓ Cleaned dist/, build/, and *.egg-info directories"
echo ""

# Step 2: Verify build package is installed
echo "[2/3] Verifying build dependencies..."
if ! python -m build --version &> /dev/null; then
    echo "      ✗ ERROR: 'build' package is not installed"
    echo ""
    echo "Please install the build package by running:"
    echo "  pip install build"
    echo ""
    exit 1
fi
echo "      ✓ Build package is available"
echo ""

# Step 3: Build the wheel
echo "[3/3] Building wheel package..."
python -m build
echo ""

# Success message
echo "=========================================="
echo "  ✓ Build completed successfully!"
echo "=========================================="
echo ""
echo "Generated files in dist/:"
ls dist/
echo ""
echo "Quick install:"
echo "  pip install dist/flowy-<version>-py3-none-any.whl"
echo ""
echo "For detailed installation instructions, see INSTALL.md"
echo ""
