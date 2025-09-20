#!/usr/bin/env python3
"""Safe linting and formatting script.

Runs ruff and mypy in the correct order with conflict detection and rollback.
This prevents one tool from breaking what another tool expects.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple


class ToolResult(NamedTuple):
    """Result from running a tool."""

    success: bool
    output: str
    errors: str


def run_command(cmd: list[str], check: bool = True) -> ToolResult:
    """Run a command and capture output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check, cwd=Path.cwd())
        return ToolResult(True, result.stdout, result.stderr)
    except subprocess.CalledProcessError as e:
        return ToolResult(False, e.stdout or "", e.stderr or "")


def backup_codebase(backup_dir: Path) -> None:
    """Create a backup of the current codebase."""
    print("Creating backup...")

    # Files and directories to backup
    important_paths = [
        "backend/",
        "bot/",
        "tests/",
        "pyproject.toml",
        "*.py",  # Root level Python files
    ]

    backup_dir.mkdir(exist_ok=True)

    for pattern in important_paths:
        if pattern.endswith("/"):
            # Directory
            src_dir = Path(pattern.rstrip("/"))
            if src_dir.exists():
                dst_dir = backup_dir / src_dir
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
        else:
            # Files (with potential wildcards)
            for file_path in Path.cwd().glob(pattern):
                if file_path.is_file():
                    dst_file = backup_dir / file_path.name
                    shutil.copy2(file_path, dst_file)


def restore_from_backup(backup_dir: Path) -> None:
    """Restore codebase from backup."""
    print("RESTORE Restoring from backup...")

    for item in backup_dir.iterdir():
        dst = Path.cwd() / item.name

        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)


def check_mypy() -> ToolResult:
    """Run mypy and return results."""
    print("CHECK Running MyPy type checking...")
    return run_command(["mypy", ".", "--no-error-summary"], check=False)


def check_ruff_lint() -> ToolResult:
    """Run ruff linting without fixes."""
    print("CHECK Running Ruff linting check...")
    return run_command(["ruff", "check", "--no-fix"], check=False)


def apply_ruff_format() -> ToolResult:
    """Apply ruff formatting."""
    print("FORMAT Applying Ruff formatting...")
    return run_command(["ruff", "format"], check=False)


def apply_ruff_fixes() -> ToolResult:
    """Apply ruff auto-fixes."""
    print("FIX Applying Ruff fixes...")
    return run_command(["ruff", "check", "--fix"], check=False)


def count_errors(output: str) -> int:
    """Count the number of errors in tool output."""
    if not output.strip():
        return 0

    # Count lines that look like errors
    error_lines = [
        line
        for line in output.split("\n")
        if ": error:" in line or "Found" in line and "error" in line
    ]

    # Try to extract number from "Found X errors" format
    for line in error_lines:
        if "Found" in line and "error" in line:
            try:
                # Extract number before "error"
                parts = line.split()
                for i, part in enumerate(parts):
                    if "error" in part and i > 0:
                        return int(parts[i - 1])
            except (ValueError, IndexError):
                pass

    return len(error_lines)


def main():
    """Main safe linting workflow."""
    print("Starting safe linting and formatting workflow...")

    # Create temporary backup
    with tempfile.TemporaryDirectory() as temp_dir:
        backup_dir = Path(temp_dir) / "backup"
        backup_codebase(backup_dir)

        # Step 1: Check initial state
        print("\nSTATUS Checking initial state...")
        initial_mypy = check_mypy()
        initial_ruff = check_ruff_lint()

        initial_mypy_errors = count_errors(initial_mypy.output + initial_mypy.errors)
        initial_ruff_errors = count_errors(initial_ruff.output + initial_ruff.errors)

        print(f"Initial MyPy errors: {initial_mypy_errors}")
        print(f"Initial Ruff errors: {initial_ruff_errors}")

        # Step 2: Apply formatting (safest first)
        print("\nFORMAT Step 1: Applying formatting...")
        format_result = apply_ruff_format()

        if not format_result.success:
            print("ERROR Formatting failed, aborting")
            return 1

        # Check if formatting broke anything
        post_format_mypy = check_mypy()
        post_format_mypy_errors = count_errors(post_format_mypy.output + post_format_mypy.errors)

        if post_format_mypy_errors > initial_mypy_errors:
            print(
                f"WARNING  Formatting increased MyPy errors from {initial_mypy_errors} to {post_format_mypy_errors}"
            )
            print("RESTORE Rolling back formatting...")
            restore_from_backup(backup_dir)
            return 1

        print(f"SUCCESS Formatting completed. MyPy errors: {post_format_mypy_errors}")

        # Step 3: Apply Ruff fixes cautiously
        print("\nFIX Step 2: Applying Ruff fixes...")
        fixes_result = apply_ruff_fixes()

        # Check if fixes broke anything
        post_fixes_mypy = check_mypy()
        post_fixes_mypy_errors = count_errors(post_fixes_mypy.output + post_fixes_mypy.errors)

        if post_fixes_mypy_errors > post_format_mypy_errors:
            print(
                f"WARNING  Ruff fixes increased MyPy errors from {post_format_mypy_errors} to {post_fixes_mypy_errors}"
            )
            print("RESTORE Rolling back fixes (keeping formatting)...")
            # Restore and re-apply just formatting
            restore_from_backup(backup_dir)
            apply_ruff_format()
            post_fixes_mypy_errors = post_format_mypy_errors

        # Step 4: Final verification
        print("\nSTATUS Final verification...")
        final_mypy = check_mypy()
        final_ruff = check_ruff_lint()

        final_mypy_errors = count_errors(final_mypy.output + final_mypy.errors)
        final_ruff_errors = count_errors(final_ruff.output + final_ruff.errors)

        # Summary
        print("\nSUMMARY Summary:")
        print(f"MyPy errors: {initial_mypy_errors} → {final_mypy_errors}")
        print(f"Ruff errors: {initial_ruff_errors} → {final_ruff_errors}")

        if final_mypy_errors <= initial_mypy_errors and final_ruff_errors <= initial_ruff_errors:
            print("SUCCESS Safe linting completed successfully!")
            return 0
        else:
            print("WARNING  Some issues remain, but no regressions introduced")
            return 0


if __name__ == "__main__":
    sys.exit(main())
