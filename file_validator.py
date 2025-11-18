"""
File validation module for detecting duplicate filenames in templates and saves directories.

This module provides functionality to validate that there are no duplicate filenames
(ignoring extensions) within the same directory. Duplicates across different
subdirectories are allowed.
"""

import os
from dataclasses import dataclass
from typing import List, Tuple
from collections import defaultdict


@dataclass
class DuplicateFileInfo:
    """
    Represents a group of files with the same basename in a directory.

    Attributes:
        directory: The directory path containing the duplicate files
        basename: The basename (without extension) that is duplicated
        files: List of full filenames with extensions
    """
    directory: str
    basename: str
    files: List[str]

    def __repr__(self) -> str:
        return f"DuplicateFileInfo(directory='{self.directory}', basename='{self.basename}', files={self.files})"


@dataclass
class ValidationResult:
    """
    Represents the complete validation result.

    Attributes:
        has_duplicates: Whether any duplicates were found
        duplicates: List of duplicate file groups
        templates_checked: Number of all non-hidden files under templates directory
        saves_checked: Number of all non-hidden files under saves directory
    """
    has_duplicates: bool
    duplicates: List[DuplicateFileInfo]
    templates_checked: int
    saves_checked: int

    def get_duplicate_count(self) -> int:
        """Return the total number of duplicate groups found."""
        return len(self.duplicates)

    def get_summary(self) -> str:
        """Return a formatted summary of the validation results."""
        if not self.has_duplicates:
            return f"No duplicates found. Checked {self.templates_checked} files in templates directory and {self.saves_checked} files in saves directory."
        else:
            return f"Found {self.get_duplicate_count()} duplicate(s) in {self.templates_checked} files in templates directory and {self.saves_checked} files in saves directory."


class FileValidator:
    """
    Validates templates and saves directories for duplicate filenames.

    This validator checks for files with the same basename (ignoring extensions)
    within the same directory. Files with the same basename in different
    subdirectories are considered valid and will not be reported as duplicates.
    """

    def __init__(self, templates_dir: str, saves_dir: str):
        """
        Initialize the FileValidator.

        Args:
            templates_dir: Path to the templates directory
            saves_dir: Path to the saves directory
        """
        self.templates_dir = templates_dir
        self.saves_dir = saves_dir

    def validate(self) -> ValidationResult:
        """
        Main validation method that orchestrates the validation process.

        Returns:
            ValidationResult containing all duplicate information and statistics
        """
        all_duplicates = []

        # Validate templates directory
        templates_duplicates, templates_count = self._validate_directory(self.templates_dir)
        all_duplicates.extend(templates_duplicates)

        # Validate saves directory
        saves_duplicates, saves_count = self._validate_directory(self.saves_dir)
        all_duplicates.extend(saves_duplicates)

        # Create and return the validation result
        has_duplicates = len(all_duplicates) > 0
        return ValidationResult(
            has_duplicates=has_duplicates,
            duplicates=all_duplicates,
            templates_checked=templates_count,
            saves_checked=saves_count
        )

    def _validate_directory(self, directory: str) -> Tuple[List[DuplicateFileInfo], int]:
        """
        Walk through the directory recursively and check for duplicates.

        Args:
            directory: The directory path to validate

        Returns:
            Tuple of (list of duplicates found, total file count)
        """
        duplicates = []
        file_count = 0

        # Handle non-existent directories gracefully
        if not os.path.exists(directory):
            return duplicates, file_count

        # Walk through the directory recursively
        for dirpath, dirnames, filenames in os.walk(directory):
            # Skip hidden directories
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]

            # Filter out hidden files
            visible_files = [f for f in filenames if not f.startswith('.')]
            file_count += len(visible_files)

            # Check this directory for duplicates
            dir_duplicates = self._check_directory_for_duplicates(dirpath, visible_files)
            duplicates.extend(dir_duplicates)

        return duplicates, file_count

    def _check_directory_for_duplicates(self, directory: str, files: List[str]) -> List[DuplicateFileInfo]:
        """
        Check a single directory for duplicate basenames.

        Args:
            directory: The directory path being checked
            files: List of filenames in the directory

        Returns:
            List of DuplicateFileInfo objects for each duplicate group found
        """
        # Group files by basename (without extension)
        basename_groups = defaultdict(list)

        for filename in files:
            basename = self._get_basename_without_extension(filename)
            basename_groups[basename].append(filename)

        # Identify groups with more than one file (duplicates)
        duplicates = []
        for basename, file_list in basename_groups.items():
            if len(file_list) > 1:
                duplicates.append(DuplicateFileInfo(
                    directory=directory,
                    basename=basename,
                    files=sorted(file_list)  # Sort for consistent output
                ))

        return duplicates

    def _get_basename_without_extension(self, filename: str) -> str:
        """
        Extract basename without extension from a filename.

        Handles edge cases like hidden files, multiple dots, and files without extensions.

        Args:
            filename: The filename to process

        Returns:
            The basename without extension
        """
        # Use os.path.splitext to remove extension
        basename, ext = os.path.splitext(filename)

        # Handle edge case of files with no extension
        if not ext:
            return filename

        return basename
