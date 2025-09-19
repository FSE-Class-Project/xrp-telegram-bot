#!/usr/bin/env python
"""Cross-platform code formatting script using your project's tools
Works with your existing pyproject.toml configuration.
"""

import subprocess
import sys
from pathlib import Path

# ANSI color codes (work on all platforms)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def run_command(cmd, check=True):
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)  # noqa: S602
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def check_tool(tool_name):
    """Check if a tool is installed."""
    cmd = f"{sys.executable} -m pip show {tool_name}"
    success, _, _ = run_command(cmd, check=False)
    return success


def install_tools():
    """Install formatting tools if missing."""
    tools = {
        "black": "black>=24.1.1",
        "ruff": "ruff>=0.1.9",  # Using ruff instead of flake8/isort
    }

    missing = []
    for tool, package in tools.items():
        if not check_tool(tool):
            missing.append(package)

    if missing:
        print(f"{YELLOW}Installing missing tools: {', '.join(missing)}{RESET}")
        cmd = f"{sys.executable} -m pip install {' '.join(missing)}"
        success, _, _ = run_command(cmd)
        if not success:
            print(f"{RED}Failed to install tools{RESET}")
            return False

    return True


def format_code():
    """Format Python code with Black and Ruff (using your pyproject.toml settings)."""
    directories = ["backend", "bot", "tests"]
    existing_dirs = [d for d in directories if Path(d).exists()]

    if not existing_dirs:
        print(f"{RED}No Python directories found. Are you in the project root?{RESET}")
        return False

    print(f"{BLUE}=== Code Formatting Tool ==={RESET}")
    print("Using configuration from pyproject.toml")
    print("  • Black line-length: 100")
    print("  • Ruff for linting and import sorting")
    print(f"Directories to format: {', '.join(existing_dirs)}\n")

    # Check and install tools if needed
    if not install_tools():
        return False

    # Run Black with your config (line-length=100 from pyproject.toml)
    print(f"{YELLOW}Running Black formatter...{RESET}")
    black_cmd = f"{sys.executable} -m black {' '.join(existing_dirs)}"
    success, stdout, stderr = run_command(black_cmd, check=False)

    if success or "reformatted" in stdout:
        print(f"{GREEN}✓ Black formatting complete{RESET}")
        if "reformatted" in stdout:
            # Show which files were reformatted
            for line in stdout.split("\n"):
                if "reformatted" in line:
                    print(f"  {line}")
    else:
        if "No Python files are present to be formatted" in stderr:
            print(f"{YELLOW}! No Python files found to format{RESET}")
        else:
            print(f"{RED}✗ Black formatting failed{RESET}")
            print(stderr)

    # Run Ruff for linting and import sorting (replaces flake8 + isort)
    print(f"\n{YELLOW}Running Ruff (linting + import sorting)...{RESET}")

    # First, fix what can be auto-fixed
    ruff_fix_cmd = f"{sys.executable} -m ruff check {' '.join(existing_dirs)} --fix"
    success, stdout, stderr = run_command(ruff_fix_cmd, check=False)

    if success:
        print(f"{GREEN}✓ Ruff auto-fixes applied{RESET}")
    else:
        print(f"{YELLOW}! Ruff found issues{RESET}")
        if stdout:
            print(stdout[:1000])  # Show first 1000 chars

    # Sort imports using Ruff's isort functionality
    ruff_sort_cmd = f"{sys.executable} -m ruff check {' '.join(existing_dirs)} --select I --fix"
    success, _, _ = run_command(ruff_sort_cmd, check=False)

    if success:
        print(f"{GREEN}✓ Imports sorted{RESET}")

    # Now check what issues remain
    print(f"\n{YELLOW}Checking for remaining issues...{RESET}")
    ruff_check_cmd = f"{sys.executable} -m ruff check {' '.join(existing_dirs)}"
    success, stdout, stderr = run_command(ruff_check_cmd, check=False)

    if success:
        print(f"{GREEN}✓ No linting issues found{RESET}")
    else:
        print(f"{YELLOW}! Some issues remain (may need manual fixes):{RESET}")
        if stdout:
            # Parse and show issues nicely
            lines = stdout.split("\n")[:10]  # Show first 10 issues
            for line in lines:
                if line.strip():
                    print(f"  {line}")
            if len(stdout.split("\n")) > 10:
                newline_count = len(stdout.split("\n"))
                print(f"  ... and {newline_count - 10} more issues")

    # Show git status
    print(f"\n{BLUE}=== Git Status ==={RESET}")
    success, stdout, _ = run_command("git status --short", check=False)
    if stdout:
        print(stdout)
    else:
        print("No changes detected")

    return True


def check_ci_compliance():
    """Check if code will pass CI checks."""
    print(f"\n{BLUE}=== CI Compliance Check ==={RESET}")

    directories = ["backend", "bot", "tests"]
    existing_dirs = [d for d in directories if Path(d).exists()]

    all_pass = True

    # Check Black formatting
    print(f"\n{YELLOW}Checking Black formatting...{RESET}")
    black_check = f"{sys.executable} -m black --check {' '.join(existing_dirs)}"
    success, stdout, _ = run_command(black_check, check=False)

    if success:
        print(f"{GREEN}✓ Black formatting OK{RESET}")
    else:
        print(f"{RED}✗ Black formatting issues found{RESET}")
        print(f"  Run: black {' '.join(existing_dirs)}")
        all_pass = False

    # Check Ruff
    print(f"\n{YELLOW}Checking Ruff linting...{RESET}")
    ruff_check = f"{sys.executable} -m ruff check {' '.join(existing_dirs)}"
    success, stdout, _ = run_command(ruff_check, check=False)

    if success:
        print(f"{GREEN}✓ Ruff linting OK{RESET}")
    else:
        print(f"{YELLOW}! Ruff found issues (may not fail CI){RESET}")

    return all_pass


def main():
    """Execute the main entry point."""
    # Check if we're in the right directory
    if not Path("requirements.txt").exists() or not Path("pyproject.toml").exists():
        print(f"{RED}Error: Not in project root directory!{RESET}")
        print("Please run from the xrp-telegram-bot directory")
        sys.exit(1)

    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            # Just check, don't format
            if check_ci_compliance():
                print(f"\n{GREEN}✓ Code is CI compliant!{RESET}")
                sys.exit(0)
            else:
                print(f"\n{RED}✗ Code needs formatting{RESET}")
                sys.exit(1)

    # Format the code
    if format_code():
        print(f"\n{GREEN}=== Formatting Complete ==={RESET}")

        # Check CI compliance
        if check_ci_compliance():
            print(f"\n{GREEN}✓ Code is ready for CI!{RESET}")
        else:
            print(f"\n{YELLOW}! Code may still need fixes for CI{RESET}")

        print("\nNext steps:")
        print("1. Review changes: git diff")
        print("2. Stage changes: git add .")
        print("3. Commit: git commit -m 'fix: Apply Black formatting (line-length=100)'")
        print("4. Push: git push origin dev/ces")
    else:
        print(f"\n{RED}Formatting encountered issues{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
