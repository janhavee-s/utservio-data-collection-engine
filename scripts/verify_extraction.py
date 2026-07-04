#!/usr/bin/env python3
"""Quick verification: fetch Urban Company actual pages and test extraction."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from app.collectors.fetcher import HybridFetcher
    from app.parsers.strategy_parser import StrategyParser

    fetcher = HybridFetcher()
    parser = StrategyParser()

    urls = [
        ("Homepage", "https://www.urbancompany.com"),
        ("Cleaning", "https://www.urbancompany.com/services/home-cleaning"),
        ("Salon", "https://www.urbancompany.com/services/salon-for-women"),
        ("AC Repair", "https://www.urbancompany.com/services/ac-repair"),
    ]

    for label, url in urls:
        print(f"\n{'='*60}")
        print(f"  {label}: {url}")
        print(f"{'='*60}")

        try:
            result = await fetcher.fetch(url)
            html = result.html
            print(f"  Fetched: {len(html)} chars, method={result.method}")

            if not html:
                print("  EMPTY HTML - skipping")
                continue

            parsed = parser.parse(html, url)

            print(f"\n  Company: {parsed.company_name}")
            print(f"  Description: {(parsed.description or '')[:120]}")
            print(f"  Logo: {bool(parsed.logo)}")
            print(f"  Email: {parsed.contact_email}")
            print(f"  Phone: {parsed.contact_phone}")
            print(f"  Social: {list(parsed.social_links.keys())}")

            print(f"\n  Services ({len(parsed.services)}):")
            for s in parsed.services[:15]:
                cat = f" [{s['category']}]" if s.get('category') else ""
                price = f" - {s.get('starting_price')} {s.get('currency', '')}" if s.get('starting_price') else ""
                dur = f" ({s['estimated_duration']})" if s.get('estimated_duration') else ""
                print(f"    - {s['name']}{cat}{price}{dur}")

            print(f"\n  Pricing ({len(parsed.pricing)}):")
            for p in parsed.pricing[:15]:
                base = p.get('base_price', 'N/A')
                promo = f" (promo: {p['promotional_price']})" if p.get('promotional_price') else ""
                print(f"    - {p['service_name']}: {base} {p.get('currency', 'USD')}{promo}")

            print(f"\n  Content ({len(parsed.content)}):")
            for c in parsed.content[:10]:
                print(f"    - {c.get('title', 'N/A')[:80]}")

            print(f"\n  Social Profiles ({len(parsed.social_profiles)}):")
            for sp in parsed.social_profiles[:10]:
                print(f"    - {sp['platform']}: {sp.get('username', 'N/A')}")

        except Exception as e:
            print(f"  ERROR: {e}")

    await fetcher.close()


if __name__ == "__main__":
    asyncio.run(main())
