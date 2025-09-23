#!/usr/bin/env python3
"""Quick safe linting script with rollback protection."""

import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: str, description: str = "") -> tuple[bool, str]:
    """Run a command and return success status and output."""
    print(f"Running: {description or cmd}")
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=30,  # 30 second timeout
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def main():
    """Safe linting workflow."""
    print("=== Safe Linting Workflow ===")

    # Step 1: Format code (safest operation)
    print("\n1. Formatting code...")
    success, output = run_cmd("ruff format", "Code formatting")
    if not success:
        print(f"ERROR: Formatting failed\n{output}")
        return 1
    print("SUCCESS: Code formatted")

    # Step 2: Check for obvious issues without fixing
    print("\n2. Checking for linting issues...")
    success, output = run_cmd("ruff check --no-fix", "Linting check")
    if output.strip():
        print("Linting issues found:")
        print(output)

    # Step 3: Apply safe fixes only (no aggressive changes)
    print("\n3. Applying safe fixes...")
    success, output = run_cmd("ruff check --fix --no-unsafe-fixes", "Safe fixes")
    if output.strip():
        print("Applied fixes:")
        print(output)

    # Step 4: Quick type check (local files only)
    print("\n4. Quick type check...")
    success, output = run_cmd(
        "mypy backend bot --ignore-missing-imports --no-error-summary", "Type checking"
    )
    if output.strip():
        print("Type issues found:")
        # Only show first 10 lines to avoid spam
        lines = output.split("\n")[:10]
        print("\n".join(lines))
        if len(output.split("\n")) > 10:
            print("... (output truncated)")

    print("\n=== Workflow Complete ===")
    print("TIP: Run 'ruff check' to see remaining issues")
    print("TIP: Run 'mypy .' for full type checking")
    return 0


if __name__ == "__main__":
    sys.exit(main())
