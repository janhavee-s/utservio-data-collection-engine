#!/usr/bin/env python3
"""
Full demo script: Start app → Scrape data → View results.

Usage:
    python scripts/demo.py
    python scripts/demo.py --competitor "Urban Company"
    python scripts/demo.py --id 1
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env() -> dict[str, str]:
    """Load .env file and return env vars."""
    env_file = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                env_vars[key] = value
                os.environ.setdefault(key, value)
    return env_vars


def header(msg: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 70}")
    print(f"  {msg}")
    print(f"{'=' * 70}")


def check_postgresql(env_vars: dict[str, str]) -> bool:
    """Check if PostgreSQL is running and database exists."""
    header("Step 1: Checking PostgreSQL")

    db_url = env_vars.get(
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
            host=host, port=port, user=user, dbname="postgres", password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cursor.fetchone()

        if not exists:
            print(f"  Database '{dbname}' not found. Creating...")
            cursor.execute(f'CREATE DATABASE "{dbname}"')
            print(f"  ✓ Database '{dbname}' created")
        else:
            print(f"  ✓ Database '{dbname}' exists")

        cursor.close()
        conn.close()
        return True

    except ImportError:
        print("  psycopg2 not available, skipping check")
        return True
    except Exception as e:
        print(f"  ✗ PostgreSQL connection failed: {e}")
        print(f"    Make sure PostgreSQL is running on {host}:{port}")
        return False


def run_migrations() -> bool:
    """Run Alembic migrations to create tables."""
    header("Step 2: Running migrations")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  ✓ Migrations applied successfully")
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    print(f"    {line}")
            return True
        else:
            print("  ⚠ Migrations may have issues (tables might already exist)")
            return True
    except Exception as e:
        print(f"  ⚠ Migration error: {e}")
        return True


def start_app_background() -> subprocess.Popen:
    """Start the FastAPI app in background."""
    header("Step 3: Starting application")

    # Set environment
    os.environ["CI_DEBUG"] = "true"
    os.environ["CI_LOG_LEVEL"] = "info"

    print("  Starting FastAPI server on http://127.0.0.1:8000...")
    print("  (This will run in background)")

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    print("  Waiting for server to start...")
    time.sleep(5)

    if process.poll() is not None:
        print("  ✗ Server failed to start")
        stderr = process.stderr.read().decode() if process.stderr else ""
        print(f"    Error: {stderr[:500]}")
        return None

    print("  ✓ Server started (PID: {})".format(process.pid))
    return process


def trigger_collection(competitor_id: int | None = None) -> tuple[bool, int, int]:
    """Trigger collection via API. Returns (success, log_id_before, count)."""
    header("Step 4: Triggering data collection")

    import httpx

    api_key = os.environ.get("CI_API_KEY", "utservio_data_engine")
    base_url = "http://127.0.0.1:8000"

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{base_url}/status", headers={"X-API-Key": api_key})
            if resp.status_code != 200:
                print(f"  ✗ Server not responding: {resp.status_code}")
                return False, 0, 0
            print("  ✓ Server is running")

            log_resp = client.get(
                f"{base_url}/logs",
                headers={"X-API-Key": api_key},
                params={"limit": 1},
            )
            log_before = log_resp.json()[0]["id"] if log_resp.status_code == 200 and log_resp.json() else 0

            if competitor_id:
                ids_to_collect = [competitor_id]
                print(f"  Triggering collection for competitor ID {competitor_id}...")
            else:
                comps_resp = client.get(f"{base_url}/competitors", headers={"X-API-Key": api_key})
                if comps_resp.status_code != 200:
                    print(f"  ✗ Failed to get competitors: {comps_resp.status_code}")
                    return False, 0, 0
                competitors = comps_resp.json()
                enabled = [c for c in competitors if c.get("enabled", True)]
                ids_to_collect = [c["id"] for c in enabled]
                print(f"  Found {len(enabled)} enabled competitor(s)")
                for comp in enabled:
                    print(f"    - [{comp['id']}] {comp['name']}")

            triggered = 0
            for cid in ids_to_collect:
                url = f"{base_url}/collection/collect/{cid}"
                resp = client.post(url, headers={"X-API-Key": api_key})
                if resp.status_code in (200, 202):
                    triggered += 1
                else:
                    print(f"    ✗ Failed for ID {cid}: {resp.status_code}")

            print(f"  ✓ Collection triggered for {triggered}/{len(ids_to_collect)} competitor(s)")
            return triggered > 0, log_before, len(ids_to_collect)

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, 0, 0


def wait_for_collection(log_before: int = 0, expected: int = 4, timeout: int = 300) -> bool:
    """Wait for collection to complete."""
    header("Step 5: Waiting for collection to complete")

    import httpx

    api_key = os.environ.get("CI_API_KEY", "utservio_data_engine")
    base_url = "http://127.0.0.1:8000"

    print(f"  Waiting up to {timeout}s for {expected} collection(s) to finish...")

    start = time.time()
    seen = set()

    while time.time() - start < timeout:
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{base_url}/logs",
                    headers={"X-API-Key": api_key},
                    params={"limit": 20},
                )
                if resp.status_code == 200:
                    logs = resp.json()
                    new_logs = [l for l in logs if l.get("id", 0) > log_before] if log_before else []
                    for log in new_logs:
                        lid = log.get("id")
                        if lid not in seen:
                            seen.add(lid)
                            status = "✓" if log.get("success") else "✗"
                            elapsed = log.get("duration_seconds", 0)
                            records = log.get("records_collected", 0)
                            print(f"  {status} Completed ({elapsed}s, {records} records)")
                    if len(seen) >= expected:
                        return True
        except Exception:
            pass

        time.sleep(2)

    print(f"  ⚠ Timeout after {timeout}s ({len(seen)}/{expected} completed)")
    return len(seen) > 0


def show_database_stats() -> None:
    """Show database statistics."""
    header("Step 6: Database Statistics")

    import httpx

    api_key = os.environ.get("CI_API_KEY", "utservio_data_engine")
    base_url = "http://127.0.0.1:8000"

    try:
        with httpx.Client(timeout=10) as client:
            # Get status
            resp = client.get(f"{base_url}/status", headers={"X-API-Key": api_key})
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Competitors:     {data.get('competitors', 0)}")
                print(f"  Collection Logs: {data.get('collection_logs', 0)}")

            # Get logs
            resp = client.get(
                f"{base_url}/logs",
                headers={"X-API-Key": api_key},
                params={"limit": 5},
            )
            if resp.status_code == 200:
                logs = resp.json()
                if logs:
                    print(f"\n  Recent Collections:")
                    for log in logs[:5]:
                        status = "✓" if log.get("success") else "✗"
                        records = log.get("records_collected", 0)
                        elapsed = log.get("duration_seconds", 0)
                        print(
                            f"    {status} ID={log.get('id')} | "
                            f"{records} records | {elapsed}s"
                        )

    except Exception as e:
        print(f"  Error: {e}")


def query_database_direct() -> None:
    """Query database directly via psql."""
    header("Step 7: Querying Database Directly")

    env_vars = load_env()
    db_url = env_vars.get(
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
            host=host, port=port, user=user, dbname=dbname, password=password
        )
        cursor = conn.cursor()

        # Competitors
        print("\n  ── Competitors ──")
        cursor.execute("SELECT id, name, website_url, enabled FROM competitors ORDER BY id")
        rows = cursor.fetchall()
        for row in rows:
            status = "✓" if row[3] else "✗"
            print(f"    {status} [{row[0]}] {row[1]} - {row[2]}")

        # Pricing
        print("\n  ── Pricing Data ──")
        cursor.execute("""
            SELECT c.name, p.service_name, p.base_price, p.currency, p.promotional_price
            FROM competitor_pricing p
            JOIN competitors c ON c.id = p.competitor_id
            ORDER BY c.name, p.base_price
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                price = f"{row[3]} {row[2]}" if row[2] else "N/A"
                promo = f" (promo: {row[3]} {row[4]})" if row[4] else ""
                print(f"    {row[0]}: {row[1]} - {price}{promo}")
        else:
            print("    No pricing data yet")

        # Services
        print("\n  ── Services ──")
        cursor.execute("""
            SELECT c.name, s.service_name, s.starting_price
            FROM competitor_services s
            JOIN competitors c ON c.id = s.competitor_id
            ORDER BY c.name
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                price = f"₹{row[2]}" if row[2] else "N/A"
                print(f"    {row[0]}: {row[1]} - {price}")
        else:
            print("    No services data yet")

        # Social profiles
        print("\n  ── Social Profiles ──")
        cursor.execute("""
            SELECT c.name, s.platform, s.profile_url
            FROM competitor_social s
            JOIN competitors c ON c.id = s.competitor_id
            ORDER BY c.name
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"    {row[0]}: {row[1]} - {row[2]}")
        else:
            print("    No social profiles yet")

        # Content
        print("\n  ── Content (Blogs/Articles) ──")
        cursor.execute("""
            SELECT c.name, co.title, co.url, co.publish_date
            FROM competitor_content co
            JOIN competitors c ON c.id = co.competitor_id
            ORDER BY co.publish_date DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                date = row[3] or "N/A"
                print(f"    {row[0]}: {row[1][:50]}... ({date})")
        else:
            print("    No content data yet")

        # Collection logs
        print("\n  ── Collection Logs ──")
        cursor.execute("""
            SELECT c.name, l.start_time, l.end_time, l.success,
                   l.duration_seconds, l.records_collected
            FROM collection_logs l
            JOIN competitors c ON c.id = l.competitor_id
            ORDER BY l.start_time DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                status = "✓" if row[3] else "✗"
                records = row[5] or 0
                elapsed = row[4] or 0
                print(
                    f"    {status} {row[0]} | {records} records | {elapsed}s | {row[1]}"
                )
        else:
            print("    No collection logs yet")

        cursor.close()
        conn.close()

    except ImportError:
        print("  psycopg2 not available, use API endpoint instead")
    except Exception as e:
        print(f"  Error: {e}")


def stop_app(process: subprocess.Popen) -> None:
    """Stop the FastAPI app."""
    header("Stopping application")
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        print("  ✓ Server stopped")
    else:
        print("  Server already stopped")


def main() -> int:
    parser = argparse.ArgumentParser(description="Full demo: Start → Scrape → View")
    parser.add_argument("--competitor", type=str, help="Collect from specific competitor by name")
    parser.add_argument("--id", type=int, help="Collect from specific competitor by ID")
    parser.add_argument("--skip-start", action="store_true", help="Skip starting app (if already running)")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip triggering collection")
    parser.add_argument("--query-only", action="store_true", help="Only query database")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  Utservio Competitor Intelligence - Full Demo")
    print("=" * 70)

    env_vars = load_env()

    if args.query_only:
        query_database_direct()
        return 0

    # Step 1: Check PostgreSQL
    if not check_postgresql(env_vars):
        return 1

    # Step 2: Run migrations
    run_migrations()

    process = None

    try:
        # Step 3: Start app (unless skipped)
        if not args.skip_start:
            process = start_app_background()
            if not process:
                return 1
        else:
            print("\n  Skipping app start (using existing server)")

        # Step 4: Trigger collection (unless skipped)
        if not args.skip_scrape:
            competitor_id = args.id
            if args.competitor:
                # Find competitor ID by name
                import httpx

                api_key = os.environ.get("CI_API_KEY", "utservio_data_engine")
                with httpx.Client(timeout=10) as client:
                    resp = client.get(
                        "http://127.0.0.1:8000/competitors",
                        headers={"X-API-Key": api_key},
                    )
                    if resp.status_code == 200:
                        for comp in resp.json():
                            if comp["name"].lower() == args.competitor.lower():
                                competitor_id = comp["id"]
                                break

            trigger_ok, log_before, num_triggered = trigger_collection(competitor_id)

            # Step 5: Wait for collection
            expected = num_triggered if not competitor_id else 1
            wait_for_collection(log_before=log_before, expected=expected, timeout=180)

        # Step 6: Show stats via API
        show_database_stats()

        # Step 7: Query database directly
        query_database_direct()

    except KeyboardInterrupt:
        print("\n\n  Interrupted by user")
    finally:
        # Stop app
        if process:
            stop_app(process)

    print("\n" + "=" * 70)
    print("  Demo complete!")
    print("=" * 70)
    print("\n  To query later:")
    print("    python scripts/demo.py --query-only")
    print("    psql -U utservio -d utservio_ci -h localhost")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
