# Changelog

## 2026-03-17
- **added additional stat API endpoints** (`31392f5`)
  - `GET /stats/advanced` — all players advanced stats
  - `GET /stats/advanced/{player_id}` — player advanced stats
  - `GET /stats/shot-zones/{player_id}` — shot zone breakdown
  - `GET /stats/defense/leaderboard` — defensive leaderboard
  - `GET /stats/defense/{player_id}` — player defensive profile
  - `GET /stats/computed` — all players computed stats (PER, BPM, Win Shares, etc.)
  - `GET /stats/computed/{player_id}` — player computed stats
  - `GET /stats/career/{player_id}` — player career stats
  - `GET /stats/shooting` — all players shooting tracking
  - `GET /stats/shooting/{player_id}` — player shooting tracking
- **fix: add missing frontend data files blocked by overly broad gitignore** (`d16cbbb`)

## 2026-03-14
- **added player card page with mock data** (`fc902b4`)

## 2026-03-13
- **update branding to StatFloor** (`9c41187`)

## 2026-03-11
- **add recalculation job** (`5ee9abc`)
- **updated docker-compose** (`0dfa111`)
- **added celery scheduler** (`e8adae1`)
- **implemented alembic migrations** (`776136c`)

## 2026-03-10
- **added play types per game** (`b88b541`)
- **league leaders page with per-game stats table and tab navigation** (`09c39c0`)
- **Update README with Docker instructions for Impact Data** (`e25e7e4`)
- **added league leaders page with ppg, rpg, apg, mpg, updated the model** (`a8a517d`)
- **added ftm, fta, games_played, rebounds to the db** (`06a1b0d`)
- **added calls to more stats and v1 of context plus minus data** (`2635703`)

## 2026-03-08
- **added docker compose rebuild instructions** (`36adc67`)
- **updated readme with local database details** (`9d35c91`)
- **added unit tests** (`06e6a5f`)

## 2026-03-07
- **implemented redis caching** (`b1fa1ca`)
- **added optimizations to backend** (`7b9f93d`)
- **added http headers, config changes** (`9d6bf39`)
- **updated packages and config** (`67d90ce`)
- **updated ts config and pyrproject.toml** (`8464e0c`)
- **fixed missing package config** (`f21c6c9`)
- **updated ts config strictness, added hatch build config** (`d8c47bf`)

## 2026-03-06
- **initial framework** (`cbb81b3`)
