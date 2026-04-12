# StatFloor

Per-touch offensive and defensive metrics for every NBA player.

## What This Project Does

This site creates two single-number ratings for every NBA player:
- **Offensive Metric**: Combines points per touch, assist rate, turnover rate, and free throw drawing — scaled by volume
- **Defensive Metric**: Combines deflections, contested shots, charges drawn, and loose balls — scaled by possessions

Both metrics are normalized so you can compare a high-usage star to a role player fairly.

---

## Quick Start with Docker (Recommended)

This is the easiest way to run the project. You only need Docker installed.

### 1. Install Docker

**macOS:**
Download Docker Desktop from https://www.docker.com/products/docker-desktop/ and run the installer.

**Windows:**
Download Docker Desktop from https://www.docker.com/products/docker-desktop/ and run the installer.
You may need to enable WSL 2 — Docker will prompt you.

**Linux:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

**Verify it works:**
```bash
docker --version
docker-compose --version
```

### 2. Start Everything

```bash
# From the project root folder
docker-compose up --build
```

First run takes 2-3 minutes to build. You'll see logs from all services.

### 3. Populate the Database

The easiest way to load all data is the **seed** service, which runs migrations and all 7 fetch phases automatically:

```bash
docker compose --profile seed run --rm seed
```

This fetches everything from the NBA API and external sources (~15-20 minutes total due to rate limits). It runs the following phases in order:

1. Traditional + tracking stats (touch, hustle, defensive)
2. Computed advanced stats (PER, BPM, WS)
3. Advanced stats + shot zones + clutch + defense
4. Play type stats (isolation, PnR, spot-up, etc.)
5. Impact + on/off + lineups
6. Player matchups
7. All-in-one metrics (EPM, DARKO, LEBRON, RPM)

**Options:**

```bash
# Seed a specific season
docker compose --profile seed run --rm seed python -m scripts.seed_all --season 2023-24

# Run only specific phases
docker compose --profile seed run --rm seed python -m scripts.seed_all --only phase1 advanced play_types

# Skip migrations (if already applied)
docker compose --profile seed run --rm seed python -m scripts.seed_all --skip-migrations
```

**Alternatively**, you can run individual fetch scripts against the running backend:

```bash
docker-compose exec backend python -m scripts.fetch_data --create-tables --season 2024-25
```

### 4. Open the App

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Stopping

Press `Ctrl+C` in the terminal running docker-compose, or:

```bash
docker-compose down
```

### Development Mode (with hot reload)

For active development with live code reloading:

```bash
docker-compose -f docker-compose.dev.yml up
```

- Frontend (Vite dev server): http://localhost:5173
- Backend (with reload): http://localhost:8000

Changes to your code will automatically reload.

### Rebuilding After Code Changes

**Development mode** (`docker-compose.dev.yml`) auto-reloads on code changes — no rebuild needed.

**Production mode** (`docker-compose.yml`) requires a rebuild when you change code:

```bash
# Rebuild and restart all services
docker-compose up --build

# Rebuild a specific service only
docker-compose up --build backend
docker-compose up --build frontend

# Force full rebuild (no cache)
docker-compose build --no-cache
docker-compose up
```

**When to rebuild:**
- Changed Python dependencies (`pyproject.toml`)
- Changed Node dependencies (`package.json`)
- Modified Dockerfile
- Any code changes when using production compose file

**When rebuild is NOT needed:**
- Using `docker-compose.dev.yml` (hot reload handles it)
- Only changed database data
- Only changed environment variables (just restart: `docker-compose up -d`)

---

## Manual Setup (without Docker)

If you prefer to run things directly on your machine, follow the steps below.

### Prerequisites

You need to install these tools first. If you've never done this before, follow each step carefully.

### 1. Install Homebrew (macOS only)

Homebrew is a package manager that makes installing everything else easier.

Open **Terminal** (press `Cmd + Space`, type "Terminal", hit Enter) and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts. When done, **close and reopen Terminal**.

### 2. Install Python 3.11+

**macOS:**
```bash
brew install python@3.11
```

**Windows:**
Download from https://www.python.org/downloads/ and run the installer.
**Important:** Check the box that says "Add Python to PATH" during installation.

**Verify it works:**
```bash
python3 --version
```
You should see something like `Python 3.11.x` or higher.

### 3. Install Node.js 18+

**macOS:**
```bash
brew install node
```

**Windows:**
Download from https://nodejs.org/ (choose the LTS version) and run the installer.

**Verify it works:**
```bash
node --version
npm --version
```

### 4. Install PostgreSQL

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:**
Download from https://www.postgresql.org/download/windows/ and run the installer.
Remember the password you set for the `postgres` user.

**Verify it works:**
```bash
psql --version
```

### 5. Create the Database

**macOS:**
```bash
createdb nba_stats
```

**Windows (open Command Prompt as Administrator):**
```bash
psql -U postgres -c "CREATE DATABASE nba_stats;"
```

---

## Project Setup

### Step 1: Clone or Download the Project

If you have the project as a folder, open Terminal and navigate to it:

```bash
cd /path/to/nba-advanced-stats
```

### Step 2: Set Up the Backend

```bash
# Go to the backend folder
cd backend

# Create a virtual environment (keeps dependencies isolated)
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Your terminal prompt should now start with (.venv)

# Install all Python dependencies
pip install -e ".[dev]"
```

### Step 3: Configure the Backend

```bash
# Copy the example environment file
cp .env.example .env
```

Now edit the `.env` file with your database settings. Open it in any text editor:

```bash
# On macOS, you can use:
open -e .env

# Or use nano in terminal:
nano .env
```

Update the `DATABASE_URL` line. For most local setups:

```
DATABASE_URL=postgresql://localhost:5432/nba_stats
```

If you're on Windows or set a password for PostgreSQL:
```
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/nba_stats
```

Save and close the file.

### Step 4: Create Database Tables & Fetch Data

```bash
# Make sure you're in the backend folder with venv activated

# Run migrations to create all database tables
alembic upgrade head

# Seed all data at once (~15-20 minutes total)
python -m scripts.seed_all --skip-migrations --season 2024-25
```

This runs all 7 fetch phases in order (traditional stats, computed advanced, shot zones, play types, impact, matchups, and all-in-one metrics).

**To run individual phases instead:**

```bash
# Phase 1: Traditional + tracking stats
python -m scripts.fetch_data --season 2024-25

# Phase 2: Computed advanced stats (PER, BPM, WS)
python -m scripts.fetch_phase2_data --season 2024-25

# Phase 3: Advanced stats, shot zones, clutch, defense
python -m scripts.fetch_advanced_data --season 2024-25

# Phase 4: Play type stats
python -m scripts.fetch_play_type_data --season 2024-25

# Phase 5: Impact + on/off + lineups
python -m scripts.fetch_impact_data --season 2024-25

# Phase 6: Player matchups
python -m scripts.fetch_matchup_data --season 2024-25

# Phase 7: All-in-one metrics (EPM, DARKO, LEBRON, RPM)
python -m scripts.fetch_all_in_one_data --season 2024-25
```

> Note: Phase 1 must be run first as other phases depend on players existing in the database.

### Step 5: Start the Backend Server

```bash
# Still in the backend folder with venv activated
uvicorn app.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started reloader process
```

**Leave this terminal window open.** The backend is now running.

### Step 6: Set Up the Frontend

Open a **new terminal window** (keep the backend running in the first one).

```bash
# Go to the frontend folder
cd /path/to/nba-advanced-stats/frontend

# Install all JavaScript dependencies
npm install
```

This will take a minute or two the first time.

### Step 7: Start the Frontend

```bash
npm run dev
```

You should see:
```
  VITE v6.0.5  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Step 8: Open the App

Open your web browser and go to:

**http://localhost:5173**

You should see the StatFloor leaderboard!

---

## Database Safety (Docker)

Your PostgreSQL data is stored in a Docker volume (`postgres_data`) and **persists between restarts** — but certain commands will delete it.

### Safe Commands (data preserved)

```bash
# Stop containers, keep data
docker-compose stop

# Stop and remove containers, keep data
docker-compose down

# Restart everything
docker-compose up -d
```

### Dangerous Commands (data lost)

```bash
# DON'T use -v flag — this removes volumes!
docker-compose down -v

# DON'T prune volumes
docker system prune --volumes
docker volume rm postgres_data
```

### Backup & Restore

**Create a backup:**
```bash
docker exec nba-stats-db pg_dump -U postgres nba_stats > backup.sql
```

**Restore from backup:**
```bash
docker exec -i nba-stats-db psql -U postgres nba_stats < backup.sql
```

**Quick data refresh (if you lose data):**
```bash
docker compose --profile seed run --rm seed
```

### Optional: Local Directory Storage

To store database files directly in your project (easier to see/backup), update `docker-compose.yml`:

```yaml
services:
  db:
    volumes:
      - ./data/postgres:/var/lib/postgresql/data  # Instead of named volume
```

Then add `data/` to your `.gitignore`.

---

## Common Issues

### "command not found: python3"

Try `python` instead of `python3`. On Windows, Python is often just `python`.

### "pip: command not found"

Try `pip3` instead of `pip`, or `python3 -m pip` / `python -m pip`.

### "connection refused" or database errors

1. Make sure PostgreSQL is running:
   - macOS: `brew services start postgresql@15`
   - Windows: Check Services app for "postgresql" service

2. Make sure the database exists:
   - macOS: `createdb nba_stats`
   - Windows: `psql -U postgres -c "CREATE DATABASE nba_stats;"`

3. Check your `.env` file has the correct `DATABASE_URL`

### "ModuleNotFoundError"

Make sure your virtual environment is activated. Your terminal prompt should show `(.venv)` at the beginning.

To activate it again:
```bash
cd backend
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### API rate limiting / blocked requests

The NBA API sometimes blocks requests. If you get errors while fetching data:
1. Wait a few minutes and try again
2. Make sure you're not on a VPN
3. Try from a different network

### Frontend shows "Error loading leaderboard"

Make sure the backend is running in another terminal window:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

---

## Project Structure

```
nba-advanced-stats/
├── README.md                ← You are here
├── timeline.md              ← Development tickets and estimates
├── docker-compose.yml       ← Production Docker setup
├── docker-compose.dev.yml   ← Development Docker setup (hot reload)
│
├── backend/                 ← Python/FastAPI server
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py              ← API entry point
│   │   ├── models/              ← Database models
│   │   ├── api/routes/          ← API endpoints
│   │   └── services/            ← Data fetching & metrics
│   └── scripts/
│       ├── seed_all.py              ← Master seed script (runs all phases)
│       ├── fetch_data.py            ← Phase 1: Traditional + tracking stats
│       ├── fetch_phase2_data.py     ← Phase 2: PER, BPM, WS
│       ├── fetch_advanced_data.py   ← Phase 3: Advanced, shot zones, clutch, defense
│       ├── fetch_play_type_data.py  ← Phase 4: Play type stats
│       ├── fetch_impact_data.py     ← Phase 5: Impact + on/off + lineups
│       ├── fetch_matchup_data.py    ← Phase 6: Player matchups
│       └── fetch_all_in_one_data.py ← Phase 7: All-in-one metrics
│
└── frontend/                ← React/TypeScript UI
    ├── Dockerfile
    ├── nginx.conf           ← Production web server config
    ├── package.json
    └── src/
        ├── pages/               ← Page components
        ├── components/          ← Reusable UI components
        └── hooks/               ← Data fetching hooks
```

---

## Updating Data

To refresh all data with the latest NBA stats:

**With Docker (recommended):**
```bash
# Re-run the full seed (all 7 phases)
docker compose --profile seed run --rm seed

# Or refresh specific phases only
docker compose --profile seed run --rm seed python -m scripts.seed_all --only phase1 advanced --skip-migrations
```

**Without Docker:**
```bash
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
python -m scripts.seed_all --skip-migrations --season 2024-25
```

**Refresh individual data types:**
```bash
# With Docker (use docker-compose exec backend ... or docker exec -it nba-stats-backend ...)
docker-compose exec backend python -m scripts.fetch_data --season 2024-25           # Traditional + tracking
docker-compose exec backend python -m scripts.fetch_phase2_data --season 2024-25    # PER, BPM, WS
docker-compose exec backend python -m scripts.fetch_advanced_data --season 2024-25  # Advanced, shot zones, clutch
docker-compose exec backend python -m scripts.fetch_play_type_data --season 2024-25 # Play types
docker-compose exec backend python -m scripts.fetch_impact_data --season 2024-25    # Impact + on/off
docker-compose exec backend python -m scripts.fetch_matchup_data --season 2024-25   # Matchups
docker-compose exec backend python -m scripts.fetch_all_in_one_data --season 2024-25 # EPM, DARKO, LEBRON, RPM
```

### Fetching Historical Seasons

Several scripts support `--from-season` and `--seasons` flags for backfilling:

```bash
# Fetch all seasons from 2020-21 to current
python -m scripts.fetch_data --from-season 2020-21

# Specify a custom end season
python -m scripts.fetch_data --from-season 2018-19 --season 2022-23

# Fetch an explicit list of seasons
python -m scripts.fetch_data --seasons 2022-23 2023-24 2024-25

# Same flags work for advanced data
python -m scripts.fetch_advanced_data --from-season 2020-21
```

> Note: NBA tracking stats (touch, hustle, defensive) are available from 2013-14 onward.
> Each season takes ~2-3 minutes to fetch per script due to API rate limits.

---

## Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.

### Running Migrations

**With Docker:**
```bash
docker-compose exec backend alembic upgrade head
```

**Without Docker:**
```bash
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
alembic upgrade head
```

### Creating New Migrations

After modifying SQLAlchemy models, generate a new migration:

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
```

Review the generated migration in `alembic/versions/` before applying.

### Common Migration Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current revision
alembic current

# Generate migration without applying
alembic revision --autogenerate -m "Your message"
```

### Migration Workflow

1. Modify models in `app/models/`
2. Run `alembic revision --autogenerate -m "Description"`
3. Review generated migration file
4. Apply with `alembic upgrade head`
5. Commit migration file to version control

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Alembic
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, TanStack Query
- **Data Sources**: NBA Stats API (via nba_api), PBP Stats (via pbpstats)

---

## License

MIT
