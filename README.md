# Competitor Intelligence — Data Collection Engine

Periodically crawls competitor websites and stores structured data in PostgreSQL. Collects company info, services, pricing, blog content, and social profiles. Designed as the data collection layer for a larger competitive intelligence platform.

This system does not analyze data. It collects it.

## Key Features

| Feature | Description |
|---------|-------------|
| **Incremental Crawling** | ETag/Last-Modified conditional GET, 304 skip, content-hash deduplication |
| **Crawl Budget Engine** | Priority queue with URL scoring (source, depth, path patterns), max pages/depth limits |
| **Canonical URL Handling** | 50+ tracking params stripped, duplicate slashes removed, `<link rel="canonical">` extraction |
| **DOM Context Parser** | Proximity-based extraction: heading→paragraph→list→table→price, no CSS selectors |
| **Adaptive Strategy Ordering** | Learns strategy success rates, reorders by confidence×speed, persists to JSON |
| **HTTP Cache Layer** | ETag, Last-Modified, Cache-Control headers, conditional GET, TTL expiration |
| **Language Detection** | HTML `lang` tag → meta tags → text word frequency (9 languages) |
| **Intelligent Page Classification** | URL patterns + heading keywords + Schema.org + meta tags (12 page types) |
| **Observability** | Prometheus `/metrics` and `/metrics/summary` endpoints, counters/gauges/histograms |
| **Performance Utilities** | LRU cache, URL/Content deduplication, `@cached_parse` decorator |

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd utservio-competitor-intelligence
python scripts/setup.py

# 2. Edit .env with your PostgreSQL credentials
nano .env

# 3. Start the application
python scripts/run.py
```

The API starts at `http://localhost:8000`. Interactive docs at `/docs` when `CI_DEBUG=true`.

### Prerequisites

- Python 3.12+
- PostgreSQL 14+ (running locally)
- pip

### Native Installation (Step by Step)

#### 1. Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
Download and install from https://www.postgresql.org/download/windows/

#### 2. Create Database

```bash
# Create the database user and database
sudo -u postgres psql -c "CREATE USER utservio WITH PASSWORD 'changeme_in_production';"
sudo -u postgres psql -c "CREATE DATABASE utservio_ci OWNER utservio;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE utservio_ci TO utservio;"
```

#### 3. Setup Python Environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Install Playwright browsers (optional, for JS-heavy sites)
python -m playwright install chromium
```

#### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your PostgreSQL credentials:

```env
DATABASE_URL=postgresql+asyncpg://utservio:changeme_in_production@localhost:5432/utservio_ci
CI_DATABASE__URL=postgresql+asyncpg://utservio:changeme_in_production@localhost:5432/utservio_ci
```

#### 5. Run Migrations

```bash
alembic upgrade head
```

#### 6. Start the Application

```bash
# Production mode
python scripts/run.py

# Development mode (auto-reload)
python scripts/dev.py

# Or directly with uvicorn
uvicorn app.main:app --reload
```

---

## Helper Scripts

All scripts are in the `scripts/` directory:

| Script | Description |
|--------|-------------|
| `python scripts/setup.py` | Full setup: venv, deps, PostgreSQL, migrations |
| `python scripts/run.py` | Start in production mode |
| `python scripts/dev.py` | Start with auto-reload and debug logging |
| `python scripts/test.py` | Run pytest, ruff, black, mypy |
| `python scripts/collect.py --all` | Manual collection from all competitors |
| `python scripts/collect.py --competitor "Name"` | Collect from specific competitor |
| `python scripts/collect.py --id 1` | Collect from competitor by ID |

---

## Development Workflow

### Development Workflow

```bash
# Setup (first time only)
python scripts/setup.py

# Start development server
python scripts/dev.py

# In another terminal, run tests
python scripts/test.py

# Or run individual tools
pytest tests/unit/ -v
ruff check .
ruff format .
mypy app/
```

### Testing

```bash
# Run all tests and linting
python scripts/test.py

# Or run individually
pytest tests/unit/ -v           # Unit tests
ruff check .                    # Linting
ruff format --check .           # Format check
mypy app/                       # Type checking
```

### Manual Collection

```bash
# Collect from all enabled competitors
python scripts/collect.py --all

# Collect from a specific competitor
python scripts/collect.py --competitor "HomeServe"

# Collect by ID
python scripts/collect.py --id 1
```

---

## What Gets Collected

Each competitor website is crawled by independent collector modules. You choose which modules to run per competitor.

| Module | What It Extracts |
|--------|-----------------|
| discovery | Sitemap URLs, internal links, page classification |
| company | Company name, description, contact info, about pages |
| services | Service listings with descriptions, durations, pricing |
| pricing | Price points, subscription plans, promotional offers |
| content | Blog posts, articles, news with author/date detection |
| social | Social media profile URLs across major platforms |

All collected HTML is stored in `raw_storage` for audit and re-parsing.

---

## Configuration

### Adding Competitors

Edit `competitors.json` (path configurable via `CI_COMPETITORS_CONFIG_PATH`):

```json
{
  "competitors": [
    {
      "name": "Example Corp",
      "website_url": "https://example.com",
      "enabled": true,
      "collection_frequency": "daily",
      "modules": ["discovery", "company", "services", "pricing", "content", "social"],
      "tags": ["home-services"],
      "notes": "Optional notes"
    }
  ]
}
```

Competitors are synced to the database on startup. Existing competitors (matched by name) are skipped.

### Environment Variables

All settings use the `CI_` prefix. Nested settings use `__` as delimiter.

| Variable | Default | Description |
|----------|---------|-------------|
| `CI_DATABASE__URL` | `postgresql+asyncpg://...` | Database connection string |
| `CI_API_KEY` | `""` | API key for authentication (bypass if empty) |
| `CI_DEBUG` | `false` | Enable debug mode, OpenAPI docs |
| `CI_LOG_LEVEL` | `info` | Logging level |
| `CI_SCHEDULER__ENABLED` | `true` | Enable background scheduler |
| `CI_SCHEDULER__CHECK_INTERVAL_SECONDS` | `60` | How often the scheduler checks |
| `CI_COLLECTOR__RETRY_ATTEMPTS` | `3` | HTTP retry attempts per request |
| `CI_COLLECTOR__RETRY_DELAY` | `1.0` | Base delay between retries (exponential backoff) |

See `.env.example` for the full list.

---

## API

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/status` | Yes | Competitor and log counts |
| GET | `/logs` | Yes | Collection logs (paginated) |
| GET | `/competitors` | Yes | List all competitors |
| GET | `/competitors/{id}` | Yes | Get competitor by ID |
| POST | `/competitors` | Yes | Create competitor |
| PUT | `/competitors/{id}` | Yes | Update competitor |
| DELETE | `/competitors/{id}` | Yes | Delete competitor |
| GET | `/competitors/{id}/overview` | Yes | Data overview for competitor |
| GET | `/competitors/{id}/services` | Yes | Services (paginated) |
| GET | `/competitors/{id}/pricing` | Yes | Pricing (paginated) |
| GET | `/competitors/{id}/social` | Yes | Social profiles |
| GET | `/competitors/{id}/company` | Yes | Company info |
| GET | `/competitors/{id}/content` | Yes | Content/articles (paginated) |
| POST | `/collection/collect` | Yes | Trigger collection by request body |
| POST | `/collection/collect/{id}` | Yes | Trigger collection for one competitor |
| GET | `/metrics` | Yes | Prometheus metrics exposition |
| GET | `/metrics/summary` | Yes | JSON summary of all metrics |

### Authentication

All endpoints require an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: utservio_data_engine" http://localhost:8000/competitors
```

If no API key is configured, authentication is bypassed.

---

## Architecture

```
API (FastAPI)
  -> CollectionService (orchestration)
    -> Collectors (one per module)
      -> Parsers (HTML -> structured data)
      -> Repositories (structured data -> PostgreSQL)
    -> RawStorage (HTML snapshots)
```

Key design decisions:

- **Collector-based**: Each data type has its own collector. Adding a new data type means adding a new collector, not modifying existing code.
- **Configuration-driven**: Competitors are defined in `competitors.json`, not in code.
- **Transactional writes**: Each collector writes within a single database transaction. Partial failures roll back cleanly.
- **Content-hash deduplication**: Services, pricing, and content use SHA-256 content hashes to detect identical data across collection runs. No duplicate records.

See [documentation/architecture.md](documentation/architecture.md) for the full schema and design rationale.

---

## Features Implemented (v0.9 — Release Candidate)

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Incremental Crawling** | ETag/Last-Modified conditional GET, 304 skip, content-hash deduplication |
| 2 | **Crawl Budget Engine** | Priority queue with URL scoring (source, depth, path patterns), max pages/depth limits |
| 3 | **Canonical URL Handling** | 50+ tracking params stripped, duplicate slashes removed, `<link rel="canonical">` extraction |
| 4 | **DOM Context Parser** | Proximity-based extraction: heading→paragraph→list→table→price (no CSS selectors) |
| 5 | **Adaptive Strategy Ordering** | Historical success/confidence/speed scoring, JSON persistence, auto-reorder strategies |
| 6 | **HTTP Cache Layer** | ETag, Last-Modified, Cache-Control headers, conditional GET, TTL expiration |
| 7 | **Language Detection** | HTML lang → meta tags → word frequency (9 languages) |
| 8 | **Intelligent Page Classification** | URL patterns + headings + Schema.org + meta tags → 12 page types |
| 9 | **Observability** | Prometheus `/metrics` + `/metrics/summary`, counters/gauges/histograms |
| 10 | **Performance Utilities** | LRU cache, URL/content deduplication, `@cached_parse` decorator |

---

## Duplicate Prevention

All data types use content hashing and canonical URL normalization to prevent duplicates across collection runs:

- **URL Normalization**: Protocol lowercasing, `www.` stripping, trailing slash removal, query parameter sorting, tracking parameter stripping.
- **Content Hashing**: SHA-256 hashes from canonical field values (case-insensitive, whitespace-insensitive).
- **Services/Pricing**: Unique constraint on `(competitor_id, content_hash)` with upsert. Identical data updates its timestamp; changed data creates new records.
- **Content**: Dual-key dedup — primary check by normalized URL, secondary by content hash.
- **Raw Storage**: Upsert by URL — re-crawled pages update in-place.

---

## Project Structure

```
app/
  api/             FastAPI routes, auth, middleware
  collectors/      Data collection modules (one per data type)
  configuration/   Settings, config models, JSON loader
  database/        SQLAlchemy models and repositories
  parsers/         HTML parsing logic (strategy-based)
  schedulers/      Background scheduler for periodic collection
  services/        Orchestration and config sync
  utilities/       URL normalization and content hashing
  main.py          Application factory
documentation/     Architecture, deployment, limitations
migrations/        Alembic migration scripts
scripts/           Helper scripts for native development
sample-data/       Example competitor configuration
tests/
  unit/            Isolated tests with mocks
  integration/     Tests against real PostgreSQL
```

---

## Development

```bash
ruff check .        # Lint
ruff format .       # Format
mypy app/           # Type check
pytest              # Run tests
```

---

## License

Proprietary
