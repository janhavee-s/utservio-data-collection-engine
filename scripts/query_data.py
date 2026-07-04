#!/usr/bin/env python3
"""
Query and display all parsed data from the database.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env() -> dict[str, str]:
    """Load .env file."""
    env_file = PROJECT_ROOT / ".env"
    env_vars = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
                os.environ.setdefault(key.strip(), value.strip())
    return env_vars


def query_all_data() -> None:
    """Query all parsed data from database."""
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
        import psycopg2.extras

        conn = psycopg2.connect(
            host=host, port=port, user=user, dbname=dbname, password=password
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        print("\n" + "=" * 70)
        print("  PARSED DATA FROM DATABASE")
        print("=" * 70)

        # ── Competitors ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  COMPETITORS                                              │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("SELECT id, name, website_url, enabled FROM competitors ORDER BY id")
        for row in cursor.fetchall():
            status = "✓" if row["enabled"] else "✗"
            print(f"  {status} [{row['id']}] {row['name']}")
            print(f"     URL: {row['website_url']}")

        # ── Discovered URLs (Sources) ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  DISCOVERED URLS (Sources)                                 │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, s.url, s.page_type, s.discovered_at
            FROM competitor_sources s
            JOIN competitors c ON c.id = s.competitor_id
            ORDER BY c.name, s.url
            LIMIT 30
        """)
        rows = cursor.fetchall()
        if rows:
            current_competitor = None
            for row in rows:
                if row["name"] != current_competitor:
                    current_competitor = row["name"]
                    print(f"\n  {current_competitor}:")
                page_type = row["page_type"] or "general"
                print(f"    [{page_type}] {row['url'][:80]}")
        else:
            print("  No URLs discovered yet")

        # ── Pricing Data ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  PRICING DATA                                              │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, p.service_name, p.category, p.base_price,
                   p.promotional_price, p.currency, p.discount
            FROM competitor_pricing p
            JOIN competitors c ON c.id = p.competitor_id
            ORDER BY c.name, p.base_price
            LIMIT 30
        """)
        rows = cursor.fetchall()
        if rows:
            current_competitor = None
            for row in rows:
                if row["name"] != current_competitor:
                    current_competitor = row["name"]
                    print(f"\n  {current_competitor}:")
                price = f"{row['currency']} {row['base_price']}" if row["base_price"] else "N/A"
                promo = f" → {row['currency']} {row['promotional_price']}" if row["promotional_price"] else ""
                discount = f" ({row['discount']}% off)" if row["discount"] else ""
                category = f" [{row['category']}]" if row["category"] else ""
                print(f"    • {row['service_name']}{category}: {price}{promo}{discount}")
        else:
            print("  No pricing data parsed yet")

        # ── Services ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  SERVICES                                                  │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, s.service_name, s.service_category, s.description,
                   s.starting_price, s.currency
            FROM competitor_services s
            JOIN competitors c ON c.id = s.competitor_id
            ORDER BY c.name, s.service_name
            LIMIT 30
        """)
        rows = cursor.fetchall()
        if rows:
            current_competitor = None
            for row in rows:
                if row["name"] != current_competitor:
                    current_competitor = row["name"]
                    print(f"\n  {current_competitor}:")
                price = f"{row['currency']} {row['starting_price']}" if row["starting_price"] else "N/A"
                desc = (row["description"] or "")[:60]
                category = f" [{row['service_category']}]" if row["service_category"] else ""
                print(f"    • {row['service_name']}{category}: {price}")
                if desc:
                    print(f"      {desc}...")
        else:
            print("  No services data parsed yet")

        # ── Content (Blogs/Articles) ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  CONTENT (Blogs/Articles)                                  │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, co.title, co.url, co.publish_date, co.content_type
            FROM competitor_content co
            JOIN competitors c ON c.id = co.competitor_id
            ORDER BY co.publish_date DESC NULLS LAST
            LIMIT 20
        """)
        rows = cursor.fetchall()
        if rows:
            current_competitor = None
            for row in rows:
                if row["name"] != current_competitor:
                    current_competitor = row["name"]
                    print(f"\n  {current_competitor}:")
                date = row["publish_date"] or "N/A"
                content_type = row["content_type"] or "article"
                print(f"    • [{content_type}] {row['title'][:70]}")
                print(f"      URL: {row['url'][:80]}")
                print(f"      Date: {date}")
        else:
            print("  No content data parsed yet")

        # ── Social Profiles ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  SOCIAL PROFILES                                           │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, s.platform, s.profile_url, s.username
            FROM competitor_social s
            JOIN competitors c ON c.id = s.competitor_id
            ORDER BY c.name, s.platform
            LIMIT 20
        """)
        rows = cursor.fetchall()
        if rows:
            current_competitor = None
            for row in rows:
                if row["name"] != current_competitor:
                    current_competitor = row["name"]
                    print(f"\n  {current_competitor}:")
                username = f" (@{row['username']})" if row["username"] else ""
                print(f"    • {row['platform']}{username}: {row['profile_url']}")
        else:
            print("  No social profiles parsed yet")

        # ── Raw Storage (HTML Snapshots) ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  RAW STORAGE (HTML Snapshots)                              │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, r.source_url, r.content_hash,
                   LENGTH(r.raw_html) as html_size, r.collection_status
            FROM raw_storage r
            JOIN competitors c ON c.id = r.competitor_id
            ORDER BY c.name, r.source_url
            LIMIT 20
        """)
        rows = cursor.fetchall()
        if rows:
            current_competitor = None
            for row in rows:
                if row["name"] != current_competitor:
                    current_competitor = row["name"]
                    print(f"\n  {current_competitor}:")
                size_kb = (row["html_size"] or 0) / 1024
                status = row["collection_status"] or "unknown"
                print(f"    • {row['source_url'][:70]}")
                print(f"      Size: {size_kb:.1f} KB | Status: {status}")
                print(f"      Hash: {row['content_hash'][:32]}...")
        else:
            print("  No raw storage yet")

        # ── Collection Logs ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  COLLECTION LOGS                                           │")
        print("└─────────────────────────────────────────────────────────────┘")
        cursor.execute("""
            SELECT c.name, l.start_time, l.end_time, l.success,
                   l.duration_seconds, l.records_collected, l.errors
            FROM collection_logs l
            JOIN competitors c ON c.id = l.competitor_id
            ORDER BY l.start_time DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                status = "✓" if row["success"] else "✗"
                records = row["records_collected"] or 0
                elapsed = row["duration_seconds"] or 0
                errors = row["errors"] or []
                print(f"\n  {status} {row['name']}")
                print(f"    Time: {row['start_time']}")
                print(f"    Duration: {elapsed}s | Records: {records}")
                if errors:
                    print(f"    Errors: {errors}")
        else:
            print("  No collection logs yet")

        # ── Summary Statistics ──
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│  SUMMARY STATISTICS                                        │")
        print("└─────────────────────────────────────────────────────────────┘")

        cursor.execute("SELECT COUNT(*) as count FROM competitors")
        print(f"  Competitors:         {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM competitor_sources")
        print(f"  Discovered URLs:     {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM competitor_pricing")
        print(f"  Pricing Records:     {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM competitor_services")
        print(f"  Service Records:     {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM competitor_content")
        print(f"  Content Records:     {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM competitor_social")
        print(f"  Social Profiles:     {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM raw_storage")
        print(f"  Raw HTML Snapshots:  {cursor.fetchone()['count']}")

        cursor.execute("SELECT COUNT(*) as count FROM collection_logs")
        print(f"  Collection Runs:     {cursor.fetchone()['count']}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 70)
        print("  Done!")
        print("=" * 70 + "\n")

    except ImportError:
        print("\n  psycopg2 not available. Install it with:")
        print("    pip install psycopg2-binary")
        print("\n  Or use the API endpoints:")
        print("    curl http://localhost:8000/competitors -H 'X-API-Key: utservio_data_engine'")
        print("    curl http://localhost:8000/logs -H 'X-API-Key: utservio_data_engine'")
    except Exception as e:
        print(f"\n  Error: {e}")


if __name__ == "__main__":
    query_all_data()
