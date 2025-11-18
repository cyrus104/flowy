"""
Unit Tests for File Validator Module

Comprehensive test suite for the file_validator module, covering:
- Duplicate detection in same directory
- Unique files validation
- Nested subdirectories
- Edge cases (hidden files, empty directories)
- Validation result reporting
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from file_validator import FileValidator, ValidationResult, DuplicateFileInfo


class TestFileValidator(unittest.TestCase):
    """Test suite for the FileValidator class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories for test templates and saves
        self.temp_base = tempfile.mkdtemp()
        self.templates_dir = os.path.join(self.temp_base, "templates")
        self.saves_dir = os.path.join(self.temp_base, "saves")
        os.makedirs(self.templates_dir)
        os.makedirs(self.saves_dir)

        self.validator = FileValidator(self.templates_dir, self.saves_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        shutil.rmtree(self.temp_base, ignore_errors=True)

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def create_temp_file(self, directory: str, filename: str, content: str = ""):
        """
        Create a file in the specified directory with optional content.

        Args:
            directory: Directory to create the file in
            filename: Name of the file to create
            content: Optional content to write to the file

        Returns:
            Full path to the created file
        """
        # Ensure parent directories exist
        os.makedirs(directory, exist_ok=True)

        file_path = os.path.join(directory, filename)
        with open(file_path, 'w') as f:
            f.write(content)

        return file_path

    def create_directory_structure(self, base_dir: str, structure: dict):
        """
        Create a directory structure from a dictionary.

        Args:
            base_dir: Base directory to create structure in
            structure: Dictionary where keys are subdirectory paths and values are lists of filenames

        Example:
            structure = {
                "reports": ["monthly.template", "monthly.txt"],
                "saves": ["client.save"]
            }
        """
        for subdir, files in structure.items():
            dir_path = os.path.join(base_dir, subdir)
            os.makedirs(dir_path, exist_ok=True)

            for filename in files:
                self.create_temp_file(dir_path, filename)

    # ========================================================================
    # Test Cases
    # ========================================================================

    def test_no_duplicates_in_empty_directories(self):
        """Test validation of empty directories."""
        result = self.validator.validate()

        self.assertFalse(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 0)
        self.assertEqual(result.templates_checked, 0)
        self.assertEqual(result.saves_checked, 0)

    def test_no_duplicates_with_unique_files(self):
        """Test validation with unique basenames."""
        # Create files with unique basenames in templates/
        self.create_temp_file(self.templates_dir, "report.template")
        self.create_temp_file(self.templates_dir, "invoice.template")
        self.create_temp_file(self.templates_dir, "letter.template")

        result = self.validator.validate()

        self.assertFalse(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 0)
        self.assertEqual(result.templates_checked, 3)

    def test_duplicate_in_same_directory(self):
        """Test detection of duplicate basenames in same directory."""
        # Create files with same basename but different extensions
        self.create_temp_file(self.templates_dir, "report.template")
        self.create_temp_file(self.templates_dir, "report.txt")
        self.create_temp_file(self.templates_dir, "report.md")

        result = self.validator.validate()

        self.assertTrue(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 1)
        self.assertEqual(result.get_duplicate_count(), 1)

        # Verify the duplicate info
        dup = result.duplicates[0]
        self.assertEqual(dup.basename, "report")
        self.assertEqual(set(dup.files), {"report.template", "report.txt", "report.md"})
        self.assertEqual(dup.directory, self.templates_dir)

    def test_duplicates_in_subdirectories_allowed(self):
        """Test that duplicates in different subdirectories are allowed."""
        # Create templates/reports/monthly.template
        reports_dir = os.path.join(self.templates_dir, "reports")
        self.create_temp_file(reports_dir, "monthly.template")

        # Create templates/letters/monthly.template
        letters_dir = os.path.join(self.templates_dir, "letters")
        self.create_temp_file(letters_dir, "monthly.template")

        result = self.validator.validate()

        # Should not report duplicates (different directories)
        self.assertFalse(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 0)
        self.assertEqual(result.templates_checked, 2)

    def test_multiple_duplicate_groups_in_same_directory(self):
        """Test detection of multiple duplicate groups in same directory."""
        # Create multiple duplicate groups
        self.create_temp_file(self.templates_dir, "report.template")
        self.create_temp_file(self.templates_dir, "report.txt")
        self.create_temp_file(self.templates_dir, "invoice.template")
        self.create_temp_file(self.templates_dir, "invoice.md")

        result = self.validator.validate()

        self.assertTrue(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 2)
        self.assertEqual(result.get_duplicate_count(), 2)

        # Verify both duplicate groups
        basenames = {dup.basename for dup in result.duplicates}
        self.assertEqual(basenames, {"report", "invoice"})

    def test_duplicates_in_both_templates_and_saves(self):
        """Test duplicates in both templates and saves directories."""
        # Create duplicates in templates
        self.create_temp_file(self.templates_dir, "report.template")
        self.create_temp_file(self.templates_dir, "report.txt")

        # Create duplicates in saves
        self.create_temp_file(self.saves_dir, "client.save")
        self.create_temp_file(self.saves_dir, "client.backup")

        result = self.validator.validate()

        self.assertTrue(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 2)
        self.assertEqual(result.templates_checked, 2)
        self.assertEqual(result.saves_checked, 2)

        # Verify duplicates from both directories
        directories = {dup.directory for dup in result.duplicates}
        self.assertEqual(directories, {self.templates_dir, self.saves_dir})

    def test_hidden_files_ignored(self):
        """Test that hidden files are ignored."""
        # Create hidden files
        self.create_temp_file(self.templates_dir, ".gitignore")
        self.create_temp_file(self.templates_dir, ".hidden.template")

        # Create regular file
        self.create_temp_file(self.templates_dir, "visible.template")

        result = self.validator.validate()

        # Only the visible file should be counted
        self.assertEqual(result.templates_checked, 1)
        self.assertFalse(result.has_duplicates)

    def test_nested_subdirectories(self):
        """Test validation in deeply nested subdirectory structure."""
        # Create deeply nested structure
        nested_dir = os.path.join(self.templates_dir, "reports", "2024", "Q1")

        # Create duplicates in the nested directory
        self.create_temp_file(nested_dir, "monthly.template")
        self.create_temp_file(nested_dir, "monthly.txt")

        result = self.validator.validate()

        self.assertTrue(result.has_duplicates)
        self.assertEqual(len(result.duplicates), 1)
        self.assertEqual(result.duplicates[0].basename, "monthly")

    def test_nonexistent_directories(self):
        """Test validator handles non-existent directories gracefully."""
        # Create validator with non-existent paths
        validator = FileValidator("/nonexistent/templates", "/nonexistent/saves")

        result = validator.validate()

        # Should not raise errors
        self.assertFalse(result.has_duplicates)
        self.assertEqual(result.templates_checked, 0)
        self.assertEqual(result.saves_checked, 0)

    def test_validation_result_summary(self):
        """Test ValidationResult summary methods."""
        # Create scenario with known duplicates
        self.create_temp_file(self.templates_dir, "report.template")
        self.create_temp_file(self.templates_dir, "report.txt")

        result = self.validator.validate()

        # Test get_duplicate_count
        self.assertEqual(result.get_duplicate_count(), 1)

        # Test get_summary
        summary = result.get_summary()
        self.assertIn("1 duplicate", summary)
        self.assertIn("2 files in templates directory", summary)

    def test_validation_result_summary_no_duplicates(self):
        """Test ValidationResult summary with no duplicates."""
        self.create_temp_file(self.templates_dir, "report.template")
        self.create_temp_file(self.templates_dir, "invoice.template")

        result = self.validator.validate()

        summary = result.get_summary()
        self.assertIn("No duplicates found", summary)
        self.assertIn("2 files in templates directory", summary)

    def test_basename_extraction_edge_cases(self):
        """Test basename extraction with edge cases."""
        # Test files with multiple dots
        self.create_temp_file(self.templates_dir, "file.tar.gz")
        self.create_temp_file(self.templates_dir, "file.tar.bz2")

        result = self.validator.validate()

        # Should detect "file.tar" as duplicate basename
        self.assertTrue(result.has_duplicates)
        self.assertEqual(result.duplicates[0].basename, "file.tar")

    def test_basename_extraction_no_extension(self):
        """Test files with no extension."""
        # Create files without extensions
        self.create_temp_file(self.templates_dir, "README")
        self.create_temp_file(self.templates_dir, "LICENSE")

        result = self.validator.validate()

        # Should not detect duplicates
        self.assertFalse(result.has_duplicates)

    def test_case_sensitivity(self):
        """Test case sensitivity handling."""
        # Create files with different cases
        self.create_temp_file(self.templates_dir, "Report.template")
        self.create_temp_file(self.templates_dir, "report.txt")

        result = self.validator.validate()

        # Behavior depends on filesystem case sensitivity
        # On case-sensitive systems, these are different files
        # On case-insensitive systems, these might be duplicates
        # We check that the validator runs without errors
        self.assertIsNotNone(result)

    def test_duplicate_file_info_repr(self):
        """Test DuplicateFileInfo __repr__ method."""
        dup_info = DuplicateFileInfo(
            directory="/path/to/templates",
            basename="report",
            files=["report.template", "report.txt"]
        )

        repr_str = repr(dup_info)

        self.assertIn("DuplicateFileInfo", repr_str)
        self.assertIn("/path/to/templates", repr_str)
        self.assertIn("report", repr_str)

    def test_hidden_directories_ignored(self):
        """Test that hidden directories are skipped."""
        # Create a hidden directory
        hidden_dir = os.path.join(self.templates_dir, ".hidden")
        os.makedirs(hidden_dir)

        # Create files in hidden directory
        self.create_temp_file(hidden_dir, "file.template")
        self.create_temp_file(hidden_dir, "file.txt")

        result = self.validator.validate()

        # Files in hidden directory should not be counted
        self.assertEqual(result.templates_checked, 0)
        self.assertFalse(result.has_duplicates)

    def test_complex_directory_structure(self):
        """Test validation with complex directory structure."""
        # Create complex structure with multiple levels and mixed files
        structure = {
            "reports": ["monthly.template", "weekly.template"],
            "reports/2024": ["annual.template", "annual.txt"],  # Duplicate in subdir
            "letters": ["formal.template"],
        }

        self.create_directory_structure(self.templates_dir, structure)

        result = self.validator.validate()

        # Should find 1 duplicate group (annual in reports/2024)
        self.assertTrue(result.has_duplicates)
        self.assertEqual(result.get_duplicate_count(), 1)
        self.assertEqual(result.templates_checked, 5)

        # Verify the duplicate is from the correct directory
        dup = result.duplicates[0]
        self.assertEqual(dup.basename, "annual")
        self.assertIn("2024", dup.directory)


if __name__ == '__main__':
    unittest.main()
