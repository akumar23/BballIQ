# CourtVision - Project Tickets

## Backend Tickets

### Data Pipeline
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 1 | Set up Python project with nba_api and pbpstats packages | P0 | 2h |
| 2 | Build data fetcher for player tracking stats (touches, time of possession) | P0 | 4h |
| 3 | Build data fetcher for offensive play type stats (ISO, PnR, spot-up, etc.) | P0 | 4h |
| 4 | Build data fetcher for defensive stats (deflections, contests, DFG%) | P0 | 4h |
| 5 | Build data fetcher for hustle stats (loose balls, charges drawn) | P1 | 3h |
| 6 | Implement local caching layer to avoid rate limits | P0 | 4h |
| 7 | Create scheduled job for daily data refresh (Celery + Redis) | P1 | 6h |
| 8 | Add garbage time filtering logic | P2 | 8h |

### Database
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 9 | Design PostgreSQL schema for players table | P0 | 2h |
| 10 | Design schema for game-level tracking stats | P0 | 4h |
| 11 | Design schema for season aggregates | P0 | 3h |
| 12 | Design schema for calculated metrics storage | P0 | 2h |
| 13 | Set up database migrations | P0 | 2h |
| 14 | Build historical data import script (2013-present) | P2 | 8h |

### Metric Calculation Engine
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 15 | Implement per-touch offensive metric formula | P0 | 6h |
| 16 | Implement per-touch defensive metric formula | P0 | 6h |
| 17 | Add volume scaling factor calculation | P1 | 3h |
| 18 | Add league average calculations for normalization | P0 | 4h |
| 19 | Implement regression to mean for low-sample players | P2 | 6h |
| 20 | Build metric recalculation job (runs after daily refresh) | P1 | 4h |

### API
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 21 | Set up FastAPI project structure | P0 | 2h |
| 22 | Create endpoint: GET /players (list all with current metrics) | P0 | 3h |
| 23 | Create endpoint: GET /players/{id} (single player detail) | P0 | 3h |
| 24 | Create endpoint: GET /players/{id}/games (game-by-game breakdown) | P1 | 4h |
| 25 | Create endpoint: GET /leaderboards (top offensive/defensive metrics) | P0 | 3h |
| 26 | Create endpoint: GET /compare?players=id1,id2 (player comparison) | P1 | 4h |
| 27 | Add Redis caching for API responses | P1 | 4h |
| 28 | Add rate limiting middleware | P2 | 2h |

### Backend Summary
| Priority | Tickets | Total Hours |
|----------|---------|-------------|
| P0 | 15 | 49h |
| P1 | 7 | 28h |
| P2 | 4 | 24h |
| **Total** | **28** | **101h** |

---

## Frontend Tickets

### Setup & Infrastructure
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 1 | Initialize React project with TypeScript | P0 | 2h |
| 2 | Set up TanStack Query for API data fetching | P0 | 2h |
| 3 | Configure routing (React Router) | P0 | 1h |
| 4 | Set up component library (shadcn/ui or similar) | P0 | 3h |
| 5 | Configure D3.js for custom visualizations | P1 | 2h |

### Core Pages
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 6 | Build player search/list page with filters | P0 | 8h |
| 7 | Build player detail page layout | P0 | 6h |
| 8 | Build leaderboard page (offensive + defensive rankings) | P0 | 6h |
| 9 | Build player comparison page | P1 | 8h |
| 10 | Build about/methodology page | P2 | 3h |

### Components
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 11 | Create player card component (photo, name, team, metrics) | P0 | 3h |
| 12 | Create offensive metric gauge/display component | P0 | 4h |
| 13 | Create defensive metric gauge/display component | P0 | 4h |
| 14 | Create stat breakdown table component | P1 | 4h |
| 15 | Create game log table with sorting/filtering | P1 | 6h |
| 16 | Create player comparison chart component | P1 | 6h |

### Visualizations (D3)
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 17 | Build metric distribution chart (where player ranks vs league) | P1 | 6h |
| 18 | Build offensive vs defensive scatter plot | P1 | 5h |
| 19 | Build game-by-game trend line chart | P2 | 5h |
| 20 | Build touch volume vs efficiency chart | P2 | 5h |

### Polish
| # | Ticket | Priority | Estimate |
|---|--------|----------|----------|
| 21 | Add loading states and skeletons | P1 | 3h |
| 22 | Add error handling and empty states | P1 | 3h |
| 23 | Implement mobile responsive layouts | P2 | 6h |
| 24 | Add dark mode support | P3 | 4h |
| 25 | SEO meta tags and OpenGraph | P2 | 2h |

### Frontend Summary
| Priority | Tickets | Total Hours |
|----------|---------|-------------|
| P0 | 10 | 39h |
| P1 | 10 | 45h |
| P2 | 4 | 21h |
| P3 | 1 | 4h |
| **Total** | **25** | **109h** |

---

## Overall Summary

| Category | P0 | P1 | P2 | P3 | Total |
|----------|----|----|----|----|-------|
| Backend | 49h | 28h | 24h | 0h | **101h** |
| Frontend | 39h | 45h | 21h | 4h | **109h** |
| **Combined** | **88h** | **73h** | **45h** | **4h** | **210h** |

### Priority Definitions
- **P0** - MVP required (functional site with core metrics)
- **P1** - Important for usability (should ship shortly after MVP)
- **P2** - Nice to have (improves quality/depth)
- **P3** - Polish (can defer indefinitely)

### MVP Scope (P0 only)
- **88 hours** (~2-3 weeks solo, ~1 week with 2 devs)
- Basic data pipeline + metric calculations
- Player list, detail page, leaderboards
- Core metric display components
