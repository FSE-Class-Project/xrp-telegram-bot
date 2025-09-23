#!/usr/bin/env python
"""XRP Telegram Bot - Debug & Setup Validation Script.

Cross-platform script to help users get up and running on Mac and Windows.
"""

import importlib.util
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


# ANSI color codes (work on both platforms)
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 60}")
    print(f"{text:^60}")
    print(f"{'=' * 60}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[ERROR] {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"{Colors.CYAN}[INFO] {text}{Colors.RESET}")


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    version = sys.version_info
    min_version = (3, 8)

    if version >= min_version:
        print_success(
            f"Python {version.major}.{version.minor}.{version.micro} (minimum 3.8 required)"
        )
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} - requires Python 3.8+")
        return False


def check_platform_info() -> dict[str, str]:
    """Get platform information."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_implementation": platform.python_implementation(),
    }

    print_info(f"Platform: {info['system']} {info['release']} ({info['machine']})")
    print_info(f"Python: {info['python_implementation']} {platform.python_version()}")

    return info


def check_required_files() -> bool:
    """Check if required files exist."""
    required_files = [
        ".env",
        "requirements.txt",
        "backend/config.py",
        "backend/main.py",
        "run.py",
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
            print_error(f"Missing required file: {file_path}")
        else:
            print_success(f"Found: {file_path}")

    if missing_files:
        print_error(f"Missing {len(missing_files)} required files")
        return False

    return True


def check_dependencies() -> tuple[bool, list[str]]:
    """Check if required Python packages are installed."""
    required_packages = [
        "fastapi",
        "telegram",
        "xrpl",
        "sqlalchemy",
        "cryptography",
        "httpx",
        "uvicorn",
        "pydantic",
        "dotenv",
        "slowapi",
    ]

    missing_packages = []
    installed_packages = []

    for package in required_packages:
        try:
            if package == "telegram":
                # Special case for python-telegram-bot
                import telegram

                installed_packages.append("python-telegram-bot (as telegram)")
                print_success(f"+ {package} (python-telegram-bot)")
            else:
                spec = importlib.util.find_spec(package)
                if spec is not None:
                    installed_packages.append(package)
                    print_success(f"+ {package}")
                else:
                    missing_packages.append(package)
                    print_error(f"- {package}")
        except ImportError:
            missing_packages.append(package)
            print_error(f"- {package}")

    return len(missing_packages) == 0, missing_packages


def check_env_file() -> tuple[bool, dict[str, Any]]:
    """Check .env file configuration."""
    env_path = Path(".env")
    if not env_path.exists():
        print_error(".env file not found")
        return False, {}

    # Load .env file manually to check contents
    env_vars = {}
    required_vars = ["TELEGRAM_BOT_TOKEN", "ENCRYPTION_KEY"]
    optional_vars = [
        "DATABASE_URL",
        "JWT_SECRET",
        "BOT_API_KEY",
        "ADMIN_API_KEY",
    ]

    try:
        with open(env_path, encoding="utf-8") as f:
            for _line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print_error(f"Error reading .env file: {e}")
        return False, {}

    # Check required variables
    all_good = True
    for var in required_vars:
        if var in env_vars and env_vars[var]:
            print_success(f"+ {var} is set")
        else:
            print_error(f"- {var} is missing or empty")
            all_good = False

    # Check optional variables
    for var in optional_vars:
        if var in env_vars and env_vars[var]:
            print_success(f"+ {var} is set")
        else:
            print_warning(f"? {var} is not set (will auto-generate in dev)")

    return all_good, env_vars


def test_config_loading() -> bool:
    """Test if configuration can be loaded successfully."""
    try:
        # Add current directory to Python path
        sys.path.insert(0, str(Path.cwd()))

        from backend.config import initialize_settings

        settings = initialize_settings()

        print_success("+ Configuration loaded successfully")
        print_info(f"Environment: {settings.ENVIRONMENT}")
        print_info(f"Database: {settings.DATABASE_URL}")
        print_info(f"Debug mode: {settings.DEBUG}")

        # Test critical settings
        critical_checks = [
            ("Telegram bot token", bool(settings.TELEGRAM_BOT_TOKEN)),
            ("Encryption key", bool(settings.ENCRYPTION_KEY)),
            ("Database URL", bool(settings.DATABASE_URL)),
        ]

        all_critical_ok = True
        for check_name, check_result in critical_checks:
            if check_result:
                print_success(f"+ {check_name} configured")
            else:
                print_error(f"- {check_name} missing")
                all_critical_ok = False

        return all_critical_ok

    except Exception as e:
        print_error(f"Configuration loading failed: {e}")
        return False


def test_database_connection() -> bool:
    """Test database connection."""
    try:
        sys.path.insert(0, str(Path.cwd()))

        from backend.config import initialize_settings
        from backend.database.connection import (
            check_database_health,
            initialize_database_engine,
        )

        settings = initialize_settings()
        initialize_database_engine(settings.DATABASE_URL, settings.DEBUG)

        if check_database_health():
            print_success("+ Database connection successful")
            return True
        else:
            print_error("- Database connection failed")
            return False

    except Exception as e:
        print_error(f"Database test failed: {e}")
        return False


def generate_install_commands(missing_packages: list[str], platform_info: dict[str, str]) -> None:
    """Generate platform-specific installation commands."""
    if not missing_packages:
        return

    print_header("INSTALLATION COMMANDS")

    # Determine pip command
    pip_cmd = "pip3" if platform_info["system"] in ["Darwin", "Linux"] else "pip"

    print_info(f"Install missing packages ({platform_info['system']}):")
    print(f"{Colors.YELLOW}{pip_cmd} install {' '.join(missing_packages)}{Colors.RESET}")

    if "telegram" in missing_packages:
        print_info("Note: 'telegram' package should be installed as 'python-telegram-bot':")
        print(f"{Colors.YELLOW}{pip_cmd} install python-telegram-bot{Colors.RESET}")

    print_info("\nOr install all requirements:")
    print(f"{Colors.YELLOW}{pip_cmd} install -r requirements.txt{Colors.RESET}")


def run_startup_test() -> bool:
    """Test if the application can start successfully."""
    try:
        print_info("Testing application startup (backend only)...")

        # Determine python command
        python_cmd = "python3" if platform.system() in ["Darwin", "Linux"] else "python"

        # Try to import and run a quick test
        result = subprocess.run(  # noqa: S603
            [
                python_cmd,
                "-c",
                'from backend.main import app; print("+ Backend app can be imported successfully")',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            print_success("+ Backend application imports successfully")
            return True
        else:
            print_error(f"- Backend import failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print_error("- Application startup test timed out")
        return False
    except Exception as e:
        print_error(f"- Startup test failed: {e}")
        return False


def main():
    """Run debug and setup validation."""
    print_header("XRP TELEGRAM BOT - SETUP VALIDATION")

    results = {}

    # 1. Check Python version
    print_header("PYTHON VERSION CHECK")
    results["python_version"] = check_python_version()

    # 2. Platform information
    print_header("PLATFORM INFORMATION")
    platform_info = check_platform_info()
    results["platform"] = True

    # 3. Check required files
    print_header("REQUIRED FILES CHECK")
    results["files"] = check_required_files()

    # 4. Check dependencies
    print_header("DEPENDENCY CHECK")
    deps_ok, missing_deps = check_dependencies()
    results["dependencies"] = deps_ok

    if not deps_ok:
        generate_install_commands(missing_deps, platform_info)

    # 5. Check .env file
    print_header("ENVIRONMENT CONFIGURATION")
    env_ok, env_vars = check_env_file()
    results["environment"] = env_ok

    # Only continue with advanced tests if basics are working
    if results["files"] and results["dependencies"]:
        # 6. Test configuration loading
        print_header("CONFIGURATION LOADING TEST")
        results["config"] = test_config_loading()

        # 7. Test database connection
        print_header("DATABASE CONNECTION TEST")
        results["database"] = test_database_connection()

        # 8. Test application startup
        print_header("APPLICATION STARTUP TEST")
        results["startup"] = run_startup_test()
    else:
        print_warning("Skipping advanced tests due to missing requirements")
        results["config"] = False
        results["database"] = False
        results["startup"] = False

    # Summary
    print_header("SETUP VALIDATION SUMMARY")

    total_checks = len(results)
    passed_checks = sum(results.values())

    for check_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        color = Colors.GREEN if passed else Colors.RED
        print(f"{color}{check_name.replace('_', ' ').title()}: {status}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Overall: {passed_checks}/{total_checks} checks passed{Colors.RESET}")

    if passed_checks == total_checks:
        print_success("All checks passed! Your setup is ready to go.")
        print_info("You can now run: python run.py")
    elif passed_checks >= total_checks - 2:
        print_warning("Most checks passed. Fix the remaining issues and you'll be ready!")
    else:
        print_error("Several issues found. Please address the failed checks above.")

    # Quick start commands
    print_header("QUICK START COMMANDS")
    python_cmd = "python3" if platform.system() in ["Darwin", "Linux"] else "python"

    print_info("To run the full application:")
    print(f"{Colors.YELLOW}{python_cmd} run.py{Colors.RESET}")

    print_info("To run only the backend:")
    print(f"{Colors.YELLOW}{python_cmd} run.py backend{Colors.RESET}")

    print_info("To run only the bot:")
    print(f"{Colors.YELLOW}{python_cmd} run.py bot{Colors.RESET}")

    return passed_checks == total_checks


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup validation interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
