#!/usr/bin/env python3
"""
Setup script for native local development.

Creates virtual environment, installs dependencies, verifies PostgreSQL,
runs migrations, and prepares the development environment.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
LOGS_DIR = PROJECT_ROOT / "logs"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


def run(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=check, capture_output=False)


def header(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def check_python_version() -> bool:
    header("Checking Python version")
    major, minor = sys.version_info[:2]
    print(f"  Python {major}.{minor}.{sys.version_info[2]} detected")
    if major < 3 or (major == 3 and minor < 12):
        print("  ERROR: Python 3.12 or higher is required")
        return False
    print("  OK: Python version is compatible")
    return True


def create_virtual_environment() -> bool:
    header("Creating virtual environment")
    if VENV_DIR.exists():
        print("  Virtual environment already exists, skipping creation")
        return True
    try:
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
        print(f"  Created virtual environment at {VENV_DIR}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: Failed to create virtual environment: {e}")
        return False


def get_python_binary() -> str:
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def get_pip_binary() -> str:
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "pip.exe")
    return str(VENV_DIR / "bin" / "pip")


def install_dependencies() -> bool:
    header("Installing dependencies")
    pip_bin = get_pip_binary()

    if not Path(pip_bin).exists():
        print("  ERROR: pip not found in virtual environment")
        return False

    print("  Upgrading pip...")
    run([pip_bin, "install", "--upgrade", "pip"], check=False)

    print("  Installing project in editable mode with dev dependencies...")
    try:
        run([pip_bin, "install", "-e", ".[dev]"], cwd=PROJECT_ROOT)
        print("  Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: Failed to install dependencies: {e}")
        return False


def install_playwright() -> bool:
    header("Installing Playwright browsers")
    python_bin = get_python_binary()
    try:
        run([python_bin, "-m", "playwright", "install", "chromium"], check=False)
        print("  Playwright chromium installed")
        return True
    except subprocess.CalledProcessError:
        print("  WARNING: Playwright install failed (optional, needed for JS-heavy sites)")
        return True


def setup_environment_file() -> bool:
    header("Setting up environment file")
    if ENV_FILE.exists():
        print("  .env file already exists, skipping creation")
        return True
    if ENV_EXAMPLE.exists():
        import shutil

        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        print("  Created .env from .env.example")
        print("  IMPORTANT: Edit .env to set your PostgreSQL credentials")
        return True
    print("  WARNING: .env.example not found, please create .env manually")
    return True


def create_logs_directory() -> bool:
    header("Creating logs directory")
    LOGS_DIR.mkdir(exist_ok=True)
    print(f"  Logs directory ready at {LOGS_DIR}")
    return True


def check_postgresql_connection() -> bool:
    header("Checking PostgreSQL connection")
    try:
        import asyncio
        from urllib.parse import urlparse

        env_content = {}
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_content[key.strip()] = value.strip()

        db_url = env_content.get(
            "DATABASE_URL",
            "postgresql+asyncpg://utservio:changeme_in_production@localhost:5432/utservio_ci",
        )
        parsed = urlparse(db_url.replace("+asyncpg", ""))
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        user = parsed.username or "utservio"
        dbname = parsed.path.lstrip("/") or "utservio_ci"

        try:
            import psycopg2

            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                dbname=dbname,
                password=parsed.password or "",
            )
            conn.close()
            print(f"  Connected to PostgreSQL at {host}:{port}")
            print(f"  Database '{dbname}' is accessible")
            return True
        except ImportError:
            print("  psycopg2 not available, attempting connection via asyncpg...")
            import asyncpg

            async def test_connection() -> bool:
                conn = await asyncpg.connect(
                    host=host,
                    port=port,
                    user=user,
                    database=dbname,
                    password=parsed.password or "",
                )
                await conn.close()
                return True

            asyncio.run(test_connection())
            print(f"  Connected to PostgreSQL at {host}:{port}")
            return True
        except Exception as e:
            print(f"  WARNING: Could not connect to PostgreSQL: {e}")
            print("  Make sure PostgreSQL is running and credentials are correct in .env")
            print("  You can still use the project, but database operations will fail")
            return True

    except Exception as e:
        print(f"  WARNING: PostgreSQL connection check failed: {e}")
        print("  Make sure PostgreSQL is running and .env is configured")
        return True


def create_database_if_needed() -> bool:
    header("Creating database if needed")
    try:
        from urllib.parse import urlparse

        env_content = {}
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_content[key.strip()] = value.strip()

        db_url = env_content.get(
            "DATABASE_URL",
            "postgresql+asyncpg://utservio:changeme_in_production@localhost:5432/utservio_ci",
        )
        parsed = urlparse(db_url.replace("+asyncpg", ""))
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        user = parsed.username or "utservio"
        dbname = parsed.path.lstrip("/") or "utservio_ci"
        password = parsed.password or ""

        try:
            import psycopg2

            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                dbname="postgres",
                password=password,
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = cursor.fetchone()
            if not exists:
                cursor.execute(f'CREATE DATABASE "{dbname}"')
                print(f"  Created database '{dbname}'")
            else:
                print(f"  Database '{dbname}' already exists")
            cursor.close()
            conn.close()
            return True
        except ImportError:
            print("  psycopg2 not available, skipping database creation")
            print("  If database does not exist, create it manually:")
            print(f"    createdb {dbname}")
            return True
        except Exception as e:
            print(f"  WARNING: Could not create database: {e}")
            return True

    except Exception as e:
        print(f"  WARNING: Database creation check failed: {e}")
        return True


def run_migrations() -> bool:
    header("Running Alembic migrations")
    python_bin = get_python_binary()
    try:
        result = subprocess.run(
            [python_bin, "-m", "alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  Migrations applied successfully")
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    print(f"    {line}")
            return True
        else:
            print("  WARNING: Migrations may have failed:")
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n"):
                    print(f"    {line}")
            print("  You can run migrations manually later: alembic upgrade head")
            return True
    except Exception as e:
        print(f"  WARNING: Migration execution failed: {e}")
        return True


def print_summary() -> None:
    header("Setup Complete")
    print(
        """
  Next steps:

  1. Edit .env file with your PostgreSQL credentials:
     nano .env

  2. Start the application:
     python scripts/run.py

  3. Or start in development mode:
     python scripts/dev.py

  4. Run the test suite:
     python scripts/test.py

  5. Run a manual collection:
     python scripts/collect.py --all

  6. Access the API:
     http://localhost:8000

  7. Access API docs (when CI_DEBUG=true):
     http://localhost:8000/docs
"""
    )


def main() -> int:
    print("\n" + "=" * 60)
    print("  Utservio Competitor Intelligence - Setup")
    print("=" * 60)

    steps = [
        ("Python version", check_python_version),
        ("Virtual environment", create_virtual_environment),
        ("Dependencies", install_dependencies),
        ("Playwright browsers", install_playwright),
        ("Environment file", setup_environment_file),
        ("Logs directory", create_logs_directory),
        ("PostgreSQL connection", check_postgresql_connection),
        ("Database creation", create_database_if_needed),
        ("Alembic migrations", run_migrations),
    ]

    results = {}
    for name, step in steps:
        try:
            results[name] = step()
        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            results[name] = False

    print_summary()

    failed = [name for name, ok in results.items() if not ok]
    if failed:
        print(f"\n  WARNING: The following steps had issues: {', '.join(failed)}")
        print("  The project may still work, but please check the warnings above.")
    else:
        print("\n  All setup steps completed successfully!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
