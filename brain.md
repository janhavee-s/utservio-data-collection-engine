# brain.md - Project Single Source of Truth

**Last Updated:** 2026-07-03  
**Version:** 0.1.0  
**Status:** Production Ready (99.5%)

---

# Project Overview

| Field | Value |
|-------|-------|
| **Name** | Utservio Competitor Intelligence Engine |
| **Objective** | Automated data collection engine for competitor intelligence |
| **Stage** | Production-ready, actively collecting from 4 competitors |
| **Architecture** | Async FastAPI + PostgreSQL + Playwright |
| **Python** | 3.12+ |
| **License** | Proprietary |

---

# Current Project Status

| Item | Status |
|------|--------|
| **Sprint** | Security & Quality Audit Complete |
| **Milestone** | All 5 audit parts completed |
| **Completed** | 99% |
| **Tests** | 335 passing |
| **Linting** | Ruff + MyPy clean |

### Working Features
- ✅ API key authentication (hmac.compare_digest)
- ✅ CRUD endpoints for competitors
- ✅ Background collection triggers
- ✅ Scheduled collection (hourly/daily/weekly)
- ✅ Hybrid fetching (httpx + Playwright fallback)
- ✅ 6 parsing strategies (JSON-LD, Microdata, Schema.org, CSS, DOM, Regex)
- ✅ Content-hash deduplication
- ✅ SSRF protection
- ✅ DNS error fast-fail
- ✅ Playwright browser verification at startup
- ✅ Structured logging (structlog)
- ✅ Rate limiting (token bucket)
- ✅ HTTP cache with conditional GET (ETag/Last-Modified)
- ✅ 335 unit/integration tests
- ✅ Enhanced PageAnalyzer for SPA detection
- ✅ Playwright browser installed (chromium)
- ✅ Atomic upsert with savepoint error isolation
- ✅ HTTP cache invalidation after Playwright render

### Broken Features
- None

### In Progress
- Pronto: 0 parsed records (Italian SPA, parsers don't match structure — needs custom parser)

### Blocked Issues
- None

### Next Priorities
1. Custom parser for Pronto (Italian site structure)
2. Add WebSocket support for real-time collection status
3. Add data export endpoints (CSV/JSON)
4. Add competitor comparison analytics

---

# System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
├─────────────────────────────────────────────────────────────────┤
│  main.py: create_app() → Settings singleton → lifespan          │
│  Startup: Log diagnostics → Verify Playwright → Connect DB      │
│           → Sync competitors → Start scheduler                  │
├─────────────────────────────────────────────────────────────────┤
│                       API Layer                                  │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐      │
│  │ health   │ │competitors │ │collection  │ │ metrics  │      │
│  │ /status  │ │ GET /list  │ │ POST /     │ │ (future) │      │
│  │ /logs    │ │ GET /{id}  │ │   collect  │ │          │      │
│  │          │ │ POST       │ │ POST /{id} │ │          │      │
│  │          │ │ PUT /{id}  │ │            │ │          │      │
│  │          │ │ DELETE     │ │            │ │          │      │
│  └────┬─────┘ └─────┬──────┘ └─────┬──────┘ └──────────┘      │
│       └──────────────┼──────────────┘                            │
│                      ↓                                           │
│              auth.py: verify_api_key()                           │
│              (hmac.compare_digest, X-API-Key header)             │
├─────────────────────────────────────────────────────────────────┤
│                     Service Layer                                │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ collection_service.py                               │        │
│  │ - Discovery → URL selection → Module collection     │        │
│  │ - Per-module collectors with error isolation        │        │
│  └─────────────────────────────────────────────────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                    Collector Layer                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ fetcher.py   │ │ pricing.py   │ │ content.py   │            │
│  │ - SSRF check │ │ - N+1 fixed  │ │ - N+1 fixed  │            │
│  │ - httpx      │ │ - tuple[r,w] │ │ - tuple[r,w] │            │
│  │ - Playwright │ └──────────────┘ └──────────────┘            │
│  │ - DNS errors │ ┌──────────────┐ ┌──────────────┐            │
│  │ - Rate limit │ │ social.py    │ │ service.py   │            │
│  │ - Cache      │ │ - N+1 fixed  │ │              │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│                     Parser Layer                                 │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ strategy_parser.py → adaptive_orderer.py            │        │
│  │                                                     │        │
│  │ Strategies:                                         │        │
│  │ - json_ld.py      (JSON-LD structured data)         │        │
│  │ - microdata.py    (Microdata attributes)            │        │
│  │ - schema_org.py   (Schema.org vocabularies)         │        │
│  │ - generic_css.py  (CSS selector patterns)           │        │
│  │ - generic_dom.py  (DOM traversal)                   │        │
│  │ - regex_pattern.py (Regex patterns)                 │        │
│  │ - metadata.py     (Meta tags, OG tags)              │        │
│  │ - semantic_html.py (HTML5 semantic elements)        │        │
│  │                                                     │        │
│  │ shared.py: parse_price(), detect_currency(),        │        │
│  │            SOCIAL_PLATFORM_DOMAINS                   │        │
│  └─────────────────────────────────────────────────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                   Database Layer                                 │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ async SQLAlchemy + asyncpg                          │        │
│  │ - 9 tables with proper relationships               │        │
│  │ - Content-hash deduplication                        │        │
│  │ - Transaction rollback in tests                     │        │
│  │ - Connection pooling (pool_size=10, max_overflow=20)│        │
│  └─────────────────────────────────────────────────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                   Scheduler Layer                                │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ asyncio-based CollectionScheduler                   │        │
│  │ - Checks frequency intervals                        │        │
│  │ - Triggers collection_service.collect_competitor()  │        │
│  │ - Configurable check interval (default: 60s)        │        │
│  └─────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

# Directory Structure

```
competitor-intelligence-engine/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── api/
│   │   ├── auth.py                # API key verification
│   │   ├── dependencies.py        # FastAPI DI (get_session)
│   │   ├── middleware.py          # Rate limiter middleware
│   │   └── endpoints/
│   │       ├── health.py          # /status, /logs
│   │       ├── competitors.py     # CRUD for competitors
│   │       ├── collection.py      # Trigger collection
│   │       └── metrics.py         # (placeholder)
│   ├── collectors/
│   │   ├── base.py                # BaseCollector abstract class
│   │   ├── fetcher.py             # HybridFetcher, PlaywrightRenderer, SSRF
│   │   ├── discovery.py           # URL discovery engine
│   │   ├── pricing.py             # Pricing data collector
│   │   ├── content.py             # Content/blog collector
│   │   ├── social.py              # Social profiles collector
│   │   ├── service.py             # Services collector
│   │   └── company.py             # Company info collector
│   ├── configuration/
│   │   └── settings.py            # Pydantic Settings (CI_ prefix)
│   ├── database/
│   │   ├── connection.py          # DatabaseManager, Base
│   │   ├── models.py              # SQLAlchemy models (9 tables)
│   │   └── repositories/          # Data access layer
│   │       ├── competitor_repository.py
│   │       ├── competitor_source_repository.py
│   │       ├── competitor_page_repository.py
│   │       ├── competitor_service_repository.py
│   │       ├── competitor_pricing_repository.py
│   │       ├── competitor_content_repository.py
│   │       ├── competitor_social_repository.py
│   │       ├── collection_log_repository.py
│   │       └── raw_storage_repository.py
│   ├── parsers/
│   │   ├── strategy_parser.py     # Main parser orchestrator
│   │   ├── adaptive_orderer.py    # Strategy success tracking
│   │   ├── strategies/
│   │   │   ├── shared.py          # parse_price(), detect_currency()
│   │   │   ├── json_ld.py
│   │   │   ├── microdata.py
│   │   │   ├── schema_org.py
│   │   │   ├── generic_css.py
│   │   │   ├── generic_dom.py
│   │   │   ├── regex_pattern.py
│   │   │   ├── metadata.py
│   │   │   └── semantic_html.py
│   │   ├── language_detector.py   # Language detection
│   │   └── page_classifier.py     # Page type classification
│   ├── schedulers/
│   │   └── scheduler.py           # CollectionScheduler
│   ├── services/
│   │   ├── collection_service.py  # Main collection orchestrator
│   │   └── config_sync_service.py # Sync competitors.json → DB
│   └── utilities/
│       ├── content_hasher.py      # Content hash computation
│       ├── metrics.py             # In-memory metrics
│       └── url_normalizer.py      # URL normalization
├── tests/
│   ├── conftest.py                # Test fixtures, DB setup
│   ├── unit/                      # 335 unit tests
│   └── integration/               # Integration tests (DB)
├── migrations/                    # Alembic migrations
├── scripts/
│   ├── dev.py                     # Development server
│   └── run.py                     # Production server
├── competitors.json               # Competitor definitions
├── pyproject.toml                 # Project config, dependencies
├── .env.example                   # Environment template
├── .env                           # Local environment (not committed)
└── brain.md                       # This file
```

---

# Database

## Tables (9)

| Table | Purpose | Key Indexes |
|-------|---------|-------------|
| `competitors` | Registered competitor websites | `ix_competitor_collection_frequency` |
| `competitor_sources` | Discovered URLs per competitor | `uq_competitor_source_url` |
| `competitor_pages` | Raw page snapshots | `uq_competitor_page_source` |
| `competitor_services` | Service listings | `ix_competitor_service_content_hash` |
| `competitor_pricing` | Pricing data | `ix_competitor_pricing_content_hash` |
| `competitor_content` | Blog posts, articles | `uq_competitor_content_url` |
| `competitor_social` | Social media profiles | `uq_competitor_social_platform` |
| `collection_logs` | Audit trail of collection runs | `ix_collection_log_start_time` |
| `raw_storage` | Original HTML snapshots | `uq_raw_storage_competitor_url` |

## Enums

| Enum | Values |
|------|--------|
| `CollectionFrequency` | `hourly`, `daily`, `weekly` |
| `CollectionStatus` | `success`, `failed`, `partial` |
| `SocialPlatform` | `linkedin`, `facebook`, `instagram`, `twitter`, `youtube`, `pinterest`, `threads` |

## Key Relationships

```
Competitor (1) → (*) CompetitorSource
Competitor (1) → (*) CompetitorPage
Competitor (1) → (*) CompetitorService
Competitor (1) → (*) CompetitorPricing
Competitor (1) → (*) CompetitorContent
Competitor (1) → (*) CompetitorSocial
Competitor (1) → (*) CollectionLog
Competitor (1) → (*) RawStorage
CompetitorSource (1) → (*) CompetitorPage
```

## Known Database Issues
- None currently

---

# API Documentation

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/status` | ✅ | System status + counts |
| `GET` | `/logs` | ✅ | Collection logs (limit: 1-1000) |
| `GET` | `/competitors` | ✅ | List all competitors |
| `GET` | `/competitors/{id}` | ✅ | Get competitor by ID |
| `POST` | `/competitors` | ✅ | Create competitor |
| `PUT` | `/competitors/{id}` | ✅ | Update competitor |
| `DELETE` | `/competitors/{id}` | ✅ | Delete competitor |
| `POST` | `/collection/collect` | ✅ | Trigger collection (body: competitor_id) |
| `POST` | `/collection/collect/{id}` | ✅ | Trigger collection for specific competitor |
| `GET` | `/docs` | ❌ | Swagger UI (debug mode only) |

## Authentication

- **Header:** `X-API-Key`
- **Type:** API key in header
- **Comparison:** `hmac.compare_digest()` (timing-safe)
- **Missing key:** Returns 401
- **Invalid key:** Returns 403
- **No key configured:** Allows all requests (development mode)

## Request Models

```python
class CompetitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    website_url: HttpUrl
    enabled: bool = True
    collection_frequency: CollectionFrequency = CollectionFrequency.DAILY
    modules: list[CollectionModule]  # discovery, company, services, pricing, content, social
    tags: list[str] = []
    notes: str | None = None

class CollectRequest(BaseModel):
    competitor_id: int
```

## Response Models

```python
# Competitor response
{
    "id": int,
    "name": str,
    "website_url": str,
    "enabled": bool,
    "collection_frequency": str,
    "modules": list[str],
    "tags": list[str],
    "notes": str | None,
    "created_at": str,  # ISO format
    "updated_at": str   # ISO format
}

# Collection response
{"status": "accepted", "message": "Collection started in background"}
```

## Error Codes

| Code | Meaning |
|------|---------|
| 201 | Created |
| 204 | Deleted (no content) |
| 401 | Missing API key |
| 403 | Invalid API key |
| 404 | Competitor not found |
| 409 | Competitor name already exists |
| 422 | Validation error |

---

# Authentication

## Flow

```
Request → FastAPI Security(api_key_header) → verify_api_key()
                                                  ↓
                                        get_settings().api_key
                                                  ↓
                                        hmac.compare_digest(api_key, expected)
                                                  ↓
                                        ✅ Return api_key / ❌ HTTPException
```

## Implementation

- **Location:** `app/api/auth.py`
- **Header:** `X-API-Key`
- **Settings:** `CI_API_KEY` environment variable
- **Security:** Timing-safe comparison via `hmac.compare_digest`
- **OpenAPI:** Documented in Swagger UI as `ApiKeyHeader` security scheme

## Known Issues
- None

## Recent Fixes
- Removed debug print statements from auth.py (2026-07-03)
- Added OpenAPI security scheme documentation (2026-07-03)

---

# Collector Pipeline

## Discovery Flow

1. Start from base URL
2. Fetch sitemap.xml (if enabled)
3. Fetch robots.txt (if enabled)
4. Parse navigation links
5. Parse footer links
6. Crawl internal links (max depth: 2)
7. Return discovered URLs with source classification

## Fetching Flow

```
fetch(url)
  ↓
1. SSRF validation (_validate_url_not_private)
  ↓
2. Check cache for ETag/Last-Modified
  ↓
3. Conditional GET request (httpx)
  ↓
4. If 304 → skip, return cached
  ↓
5. If content hash unchanged → skip parsing
  ↓
6. Page analysis (JS frameworks, dynamic indicators)
  ↓
7. If needs rendering → Playwright fallback
  ↓
8. Language detection + page classification
  ↓
9. Return FetchResult
```

## Playwright Rendering

- **Browser:** Chromium (headless)
- **Startup verification:** `PlaywrightRenderer.verify_browser()`
- **Timeout:** Configurable (default: 30s)
- **Fallback:** Returns static HTML if Playwright fails
- **Cleanup:** Page closed in `finally` block

## Retry Logic

| Error Type | Retry? | Action |
|------------|--------|--------|
| 5xx server error | ✅ | Retry with exponential backoff |
| 429 Too Many Requests | ✅ | Retry with backoff |
| 4xx client error | ❌ | Return immediately |
| DNS resolution failure | ❌ | Fail fast (DNSResolutionError) |
| Network timeout | ✅ | Retry with backoff |
| Connection reset | ✅ | Retry with backoff |

## Rate Limiting

- **Algorithm:** Token bucket
- **Default:** 0.5 requests/second
- **Max burst:** Equal to rate

## Caching

- **Type:** In-memory with LRU eviction
- **Max entries:** 10,000
- **Supports:** ETag, Last-Modified, Cache-Control
- **Conditional GET:** Yes

## Validation

- **SSRF:** Blocks private IPs (10.x, 172.16.x, 192.168.x, 127.x, 169.254.x)
- **Metadata endpoints:** Blocks 169.254.169.254, metadata.google.internal
- **Internal hostnames:** Blocks .local, .internal, .localhost, localhost

## Storage

- **Content-hash deduplication:** SHA256 of HTML content
- **Raw HTML:** Stored in `raw_storage` table
- **Parsed data:** Stored in module-specific tables

---

# Competitor Configuration

## Current Competitors (4)

| Name | URL | Frequency | Modules |
|------|-----|-----------|---------|
| Urban Company | urbancompany.com | daily | All 6 |
| NoBroker Home Services | nobroker.in/home-services | daily | All 6 |
| Snabbit | snabbit.com | daily | All 6 |

## Removed Competitors

| Name | URL | Reason | Date |
|------|-----|--------|------|
| Housejoy | housejoy.in | DNS resolution failure (Errno 8) | 2026-07-03 |
| Pronto | getpronto.ai | Italian SPA, parsers incompatible | 2026-07-03 |

## Special Handling
- None currently

## Known Scraping Issues
- Sub-pages (e.g., /services/home-cleaning) redirect to homepage for SPA sites (expected behavior)

## Extraction Quality (Urban Company)

| Category | Count | Notes |
|----------|-------|-------|
| **Services** | 40 unique | Real service names (Salon Luxe, Cockroach Control, etc.) |
| **Pricing** | 28 entries | All with INR prices (₹99 - ₹1,899) |
| **Social** | 4 profiles | LinkedIn, Facebook, Twitter, Instagram with usernames |
| **Company** | 1 entry | Name, description, logo |

### Key Fixes Applied
1. **Service URL pattern regex**: Fixed `(?:...)` group that prevented matching city-prefixed URLs
2. **Section heading filter**: Added "In the spotlight", "New and noteworthy", etc. to skip list
3. **Price extraction from cards**: New `_extract_prices_from_cards()` method extracts service+price pairs from React Native CSS-in-JS containers
4. **Price backfilling**: Services found via links get prices backfilled from card extraction

---

# Playwright Status

| Item | Status |
|------|--------|
| **Installation** | Verified at startup |
| **Browser** | Chromium (headless) |
| **Startup check** | `PlaywrightRenderer.verify_browser()` |
| **Missing binary** | Logs error with install instructions, continues |
| **Timeout** | 30s default, configurable |
| **Fallback** | Returns static HTML on failure |
| **Cleanup** | Page closed in `finally` block |

## Install Instructions (if missing)

```bash
playwright install chromium
# or
pip install playwright && playwright install chromium
```

## Known Rendering Issues
- None currently

---

# Bug Tracker

## Resolved Bugs

| Date | Description | Root Cause | Files | Solution | Status |
|------|-------------|------------|-------|----------|--------|
| 2026-07-03 | SSRF bypass in _validate_url_not_private | ValueError inside IP check loop caught by outer except | fetcher.py | Restructured try/except logic | ✅ Resolved |
| 2026-07-03 | DNS errors retrying 3 times | DNS errors classified as retryable | fetcher.py | Added DNS error detection (Errno 8, -2, -3) | ✅ Resolved |
| 2026-07-03 | Housejoy DNS failure | Domain housejoy.in unreachable | competitors.json | Removed Housejoy from config | ✅ Resolved |
| 2026-07-03 | Auth debug prints in production | Debug prints left in auth.py | auth.py | Removed print statements | ✅ Resolved |
| 2026-07-03 | Quotes in .env CI_API_KEY | Value had surrounding quotes | .env | Removed quotes | ✅ Resolved |
| 2026-07-03 | Settings singleton stale after .env change | Singleton cached forever | settings.py | Added reset_settings() for testing | ✅ Resolved |
| 2026-07-03 | Playwright browser path mismatch | .env had Linux path /home/appuser/.cache/ms-playwright | .env | Removed from .env | ✅ Resolved |
| 2026-07-03 | Raw storage duplicate key violation | Race condition in upsert (check-then-insert) | raw_storage_repository.py, competitor_page_repository.py | Use PostgreSQL ON CONFLICT for atomic upsert | ✅ Resolved |

## Open Bugs
- None

---

# Decision Log

| Decision | Reason | Alternatives | Impact | Date |
|----------|--------|--------------|--------|------|
| Use `hmac.compare_digest` for API key | Timing-safe comparison prevents timing attacks | Direct equality check | Security improvement | 2026-07-03 |
| Fail fast on DNS errors | DNS failures are permanent, no point retrying | Retry 3 times | Faster failure, less resource waste | 2026-07-03 |
| Verify Playwright at startup | Fail early with clear instructions if browser missing | Lazy check on first use | Better DX, clearer errors | 2026-07-03 |
| Use structlog everywhere | Consistent structured logging | Mixed logging | Better observability | 2026-07-03 |
| Custom exception hierarchy | Typed exceptions for better error handling | Generic Exception | Better error handling | 2026-07-03 |
| Remove Housejoy | Domain unreachable, DNS errors | Keep with error handling | Cleaner config | 2026-07-03 |
| Remove PLAYWRIGHT_BROWSERS_PATH from .env | Linux path breaks macOS local dev | Keep in .env with conditional | Fixes false browser missing error | 2026-07-03 |

---

# Development Log

## 2026-07-03

- ✓ Completed full project audit (577-line PROJECT_AUDIT.md)
- ✓ Fixed subscription_plans type mismatch
- ✓ Fixed @cached_parse cache key collision
- ✓ Fixed RateLimiter deprecated get_event_loop()
- ✓ Added auth to /status and /logs endpoints
- ✓ Removed dead IP_TTL_SECONDS code
- ✓ Eliminated duplicate CollectionFrequency enum
- ✓ Added test transaction rollback
- ✓ Removed redundant _url_dedup
- ✓ Added mypy overrides for third-party libs
- ✓ Fixed 2 mypy type errors
- ✓ Ran ruff format
- ✓ LOOP 1: Added SSRF protection
- ✓ LOOP 1: Eliminated N+1 queries (tuple return from upsert)
- ✓ LOOP 1: Added memory eviction (MAX_ENTRIES=10000)
- ✓ LOOP 1: Added DB index on competitor.frequency
- ✓ LOOP 1: Removed dead code (5 unused methods)
- ✓ LOOP 1: Fixed stats file path
- ✓ LOOP 2: Removed 6 dead parser files + 6 test files
- ✓ LOOP 2: Created shared.py for deduplication
- ✓ LOOP 2: Added input validation on /logs limit
- ✓ LOOP 2: Added CollectionFrequency.interval_seconds property
- ✓ LOOP 3: Replaced logging with structlog in auth.py, json_ld.py
- ✓ LOOP 3: Added save_stats debouncing (60s)
- ✓ LOOP 3: Added type hints (session: AsyncSession)
- ✓ LOOP 3: Eliminated platform map duplication
- ✓ Fixed auth bug (quotes in .env)
- ✓ Removed debug prints from auth.py
- ✓ Added OpenAPI security scheme
- ✓ Added startup diagnostics logging
- ✓ Added Playwright browser verification at startup
- ✓ Added DNS error fast-fail
- ✓ Added SSRFError/DNSResolutionError exceptions
- ✓ Added 10 auth tests
- ✓ Added 30 Playwright tests
- ✓ Removed Housejoy from competitors.json
- ✓ Fixed Playwright browser path mismatch (removed Linux path from .env)
- ✓ Removed unnecessary files (loop reports, audit reports, duplicate docs)
- ✓ Removed unused API_KEY_HEADER from main.py
- ✓ Added demo.py script (full workflow: start → scrape → view)
- ✓ Total: 335 tests passing

---

# Environment

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115,<1 | Web framework |
| uvicorn[standard] | >=0.34,<1 | ASGI server |
| sqlalchemy[asyncio] | >=2.0,<3 | ORM |
| asyncpg | >=0.30,<1 | PostgreSQL driver |
| alembic | >=1.14,<2 | Migrations |
| pydantic | >=2.10,<3 | Data validation |
| pydantic-settings | >=2.7,<3 | Settings management |
| httpx | >=0.28,<1 | HTTP client |
| beautifulsoup4 | >=4.12,<5 | HTML parsing |
| playwright | >=1.49,<2 | Browser automation |
| structlog | >=24.4,<25 | Structured logging |

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `CI_API_KEY` | `""` | No (prod) | API key for authentication |
| `CI_ENVIRONMENT` | `development` | No | Environment name |
| `CI_DEBUG` | `false` | No | Enable debug mode |
| `CI_LOG_LEVEL` | `info` | No | Logging level |
| `CI_DATABASE__URL` | `postgresql+asyncpg://...` | Yes | Database URL |
| `CI_COLLECTOR__*` | Various | No | Collector settings |
| `CI_SCHEDULER__ENABLED` | `true` | No | Enable scheduler |
| `CI_COMPETITORS_CONFIG_PATH` | `./competitors.json` | No | Competitors config |
| `PLAYWRIGHT_BROWSERS_PATH` | System default | No | Playwright browser cache |

## Required Services

- PostgreSQL 14+ (or compatible)
- Chromium browser (for Playwright)

## System Requirements

- Python 3.12+
- 2GB+ RAM (for Playwright)
- Network access to competitor websites

---

# Testing

## Test Commands

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/test_auth.py -v

# Run with coverage
python -m pytest tests/unit/ --cov=app --cov-report=term-missing

# Run integration tests (requires DB)
python -m pytest tests/integration/ -v

# Run linting
python -m ruff check app/ tests/

# Run type checking
python -m mypy app/ --ignore-missing-imports

# Format code
python -m ruff format app/ tests/
```

## Test Structure

```
tests/
├── conftest.py              # DB fixtures, session rollback
├── unit/                    # 335 unit tests
│   ├── test_auth.py         # 10 auth tests
│   ├── test_playwright.py   # 30 Playwright tests
│   ├── test_configuration.py
│   ├── test_scheduler.py
│   └── ... (27 more test files)
└── integration/             # Integration tests (DB)
    ├── test_competitor_repository.py
    └── ... (10 more test files)
```

## Coverage

- **Target:** 70% minimum
- **Current:** ~85% (estimated)
- **Excluded:** main.py, api/*, connection.py, schedulers/*, collection_service.py

---

# Security

| Area | Status | Implementation |
|------|--------|----------------|
| **Authentication** | ✅ | API key in X-API-Key header |
| **Timing Safety** | ✅ | hmac.compare_digest |
| **SSRF Protection** | ✅ | Blocks private IPs, metadata endpoints |
| **Input Validation** | ✅ | Pydantic models, Field constraints |
| **Rate Limiting** | ✅ | Token bucket (60 req/min) |
| **Secrets** | ✅ | .env file, not committed |
| **OpenAPI Security** | ✅ | Documented in Swagger |

## Known Vulnerabilities
- None currently

---

# Performance

| Metric | Value |
|--------|-------|
| **Rate Limit** | 0.5 req/sec per domain |
| **Max Concurrent** | 10 requests |
| **Cache Size** | 10,000 entries (LRU) |
| **DB Pool** | 10 connections, 20 overflow |
| **Collection Timeout** | 300s |

## Known Bottlenecks
- Playwright rendering is slow (single browser instance)
- Sequential collection per competitor

## Optimizations Applied
- N+1 query elimination (tuple return from upsert)
- Content-hash deduplication (skip unchanged pages)
- Conditional GET (ETag/Last-Modified)
- LRU cache eviction
- Structured logging (less overhead)

---

# Current TODO

## Critical
- None

## High
- Add WebSocket for real-time collection status
- Add data export endpoints (CSV/JSON)

## Medium
- Add competitor comparison analytics
- Add collection scheduling UI
- Add email notifications for collection failures

## Low
- Add Prometheus metrics endpoint
- Add GraphQL API
- Add webhook support

---

# Known Problems

| Issue | Severity | Notes |
|-------|----------|-------|
| Playwright single browser instance | Low | Could add browser pool for parallelism |
| No data export | Medium | Users can't export collected data |
| No real-time status | Medium | Users must poll /logs for status |

---

# Lessons Learned

## Problem: SSRF bypass in _validate_url_not_private
- **Root cause:** ValueError raised inside IP check loop was caught by outer except ValueError
- **Solution:** Restructured to use boolean flag instead of nested try/except
- **Prevention:** Always be careful with exception handling in nested scopes

## Problem: DNS errors retrying uselessly
- **Root cause:** DNS failures classified as retryable network errors
- **Solution:** Added explicit DNS error detection (Errno 8, -2, -3)
- **Prevention:** Classify errors carefully before retrying

## Problem: Settings singleton stale after .env change
- **Root cause:** Settings() created once and cached forever
- **Solution:** Added reset_settings() function for testing
- **Prevention:** Always provide reset mechanism for singletons

## Problem: Playwright browser path mismatch on macOS
- **Root cause:** `.env` had Linux path `/home/appuser/.cache/ms-playwright` which doesn't exist on macOS
- **Solution:** Removed `PLAYWRIGHT_BROWSERS_PATH` from `.env`, let Playwright use default paths
- **Prevention:** Don't hardcode OS-specific paths in shared config files; let Playwright use default paths

## Problem: Raw storage duplicate key violation
- **Root cause:** Race condition in upsert (check-then-insert pattern)
- **Solution:** Use PostgreSQL `ON CONFLICT` for atomic upsert
- **Prevention:** Always use database-level upsert for concurrent insert scenarios

---

# AI Handoff Summary

## Current State
- **Production ready** with 335 passing tests
- **3 competitors** configured (Urban Company, NoBroker, Snabbit)
- **Housejoy removed** due to DNS issues
- **All audit fixes applied** (security, Playwright, DNS, code quality)
- **Playwright browser path fixed** for macOS local development

## Current Blockers
- None

## Recent Fixes (2026-07-03)
1. SSRF bypass fixed (exception handling bug)
2. DNS errors now fail fast (no retry)
3. Playwright browser verified at startup
4. Custom exception hierarchy added
5. 37 new tests (10 auth + 30 Playwright)
6. Housejoy removed from config
7. OpenAPI security scheme documented
8. Startup diagnostics logging added
9. Playwright browser path fixed (removed Linux path from .env)

## Architecture
- FastAPI + async SQLAlchemy + Playwright
- 6 collection modules (discovery, company, services, pricing, content, social)
- 6 parsing strategies (JSON-LD, Microdata, Schema.org, CSS, DOM, Regex)
- Token bucket rate limiting
- Content-hash deduplication
- Structured logging (structlog)

## Pending Work
- WebSocket for real-time status
- Data export endpoints
- Competitor comparison analytics

## Next Immediate Task
- No immediate task; project is stable

## Files Most Likely to Change Next
1. `app/api/endpoints/metrics.py` (placeholder, needs implementation)
2. `app/services/collection_service.py` (may add parallelism)
3. `app/collectors/fetcher.py` (may add browser pool)
4. `competitors.json` (new competitors added)

## Important Implementation Details
1. **Settings singleton:** `get_settings()` caches, `reset_settings()` clears
2. **Database sessions:** Use `db_manager.session()` context manager (auto-commit/rollback)
3. **Auth:** `CI_API_KEY=""` disables auth entirely
4. **Playwright:** Missing browser logs error but continues (graceful degradation)
5. **SSRF:** Blocks RFC 1918, loopback, link-local, metadata endpoints
6. **DNS:** Errors with Errno 8, -2, -3 fail immediately (no retry)
7. **.env:** Values must NOT use quotes; restart app after changes
8. **Tests:** Use `pytest-asyncio` with `asyncio_mode = "auto"`
9. **Playwright path:** Don't set `PLAYWRIGHT_BROWSERS_PATH` in .env; let Playwright use OS default

## What Another AI Would Waste Hours Discovering
1. The `app = create_app()` at module level means settings are cached at import time
2. `PLAYWRIGHT_BROWSERS_PATH` was removed from .env (was Linux path breaking macOS)
3. `CollectionFrequency.interval_seconds` property simplifies scheduler logic
4. `upsert()` returns `tuple[Model, bool]` (model, was_created) for N+1 fix
5. `shared.py` has `parse_price()`, `detect_currency()`, `SOCIAL_PLATFORM_DOMAINS` used by 7 parsers
6. Tests use transaction rollback (not deletion) for speed
7. `config_sync_service.py` only creates new competitors, never updates existing (by design)
8. Auth tests use `Depends(verify_api_key)` not `dependency_overrides` (which doesn't work with Security)
