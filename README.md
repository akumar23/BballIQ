# NBA Advanced Stats

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

### 3. Fetch NBA Data

Open a **new terminal** and run:

```bash
docker-compose exec backend python -m scripts.fetch_data --create-tables --season 2024-25
```

This fetches data from the NBA API (takes 2-3 minutes due to rate limits).

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

# Create the database tables
python -m scripts.fetch_data --create-tables

# Fetch NBA data (this takes 2-3 minutes due to API rate limits)
python -m scripts.fetch_data --season 2024-25
```

You should see output like:
```
Creating database tables...
Done.
Fetching tracking data for season 2024-25...
  - Fetching traditional stats...
  - Fetching touch stats...
  - Fetching hustle stats...
  - Fetching defensive stats...
  - Combined data for 450 players
Processing 450 players...
Data committed to database.
Calculating percentiles...
Percentiles calculated.
Done!
```

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

You should see the NBA Advanced Stats leaderboard!

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
│       └── fetch_data.py        ← Data loading script
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

To refresh with the latest NBA stats:

**With Docker:**
```bash
docker-compose exec backend python -m scripts.fetch_data --season 2024-25
```

**Without Docker:**
```bash
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
python -m scripts.fetch_data --season 2024-25
```

---

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, TanStack Query
- **Data Sources**: NBA Stats API (via nba_api), PBP Stats (via pbpstats)

---

## License

MIT
