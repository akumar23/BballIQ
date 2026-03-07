#!/usr/bin/env python3
"""
Script to fetch all NBA tracking data and populate the database.

Usage:
    python -m scripts.fetch_data --season 2024-25
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.session import engine, SessionLocal
from app.models.base import Base
from app.models import Player, SeasonStats
from app.services.nba_data import nba_data_service, PlayerTrackingData
from app.services.metrics import MetricsCalculator


def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


def fetch_and_store_data(season: str, db: Session):
    """Fetch all tracking data and store in database."""

    # Fetch combined tracking data
    tracking_data = nba_data_service.fetch_all_tracking_data(season)

    if not tracking_data:
        print("No tracking data fetched!")
        return

    # Calculate league averages for normalization
    total_touches = sum(p.touches for p in tracking_data.values())
    league_avg_touches = Decimal(total_touches) / Decimal(len(tracking_data))
    print(f"League average touches: {league_avg_touches:.1f}")

    # Initialize metrics calculator
    calculator = MetricsCalculator(league_avg_touches)

    # Process each player
    print(f"Processing {len(tracking_data)} players...")

    for player_id, data in tracking_data.items():
        # Upsert player
        player = db.query(Player).filter(Player.nba_id == player_id).first()
        if not player:
            player = Player(
                nba_id=player_id,
                name=data.player_name,
                team_abbreviation=data.team_abbreviation,
                active=True,
            )
            db.add(player)
            db.flush()

        # Calculate rates for metrics
        if data.touches > 0:
            assist_rate = Decimal(data.assists) / Decimal(data.touches)
            turnover_rate = Decimal(data.turnovers) / Decimal(data.touches)
            ft_rate = Decimal(data.fta) / Decimal(data.touches)
        else:
            assist_rate = Decimal(0)
            turnover_rate = Decimal(0)
            ft_rate = Decimal(0)

        # Calculate offensive metric
        offensive_metric = calculator.calculate_offensive_metric(
            points_per_touch=data.points_per_touch,
            assist_rate=assist_rate,
            turnover_rate=turnover_rate,
            ft_rate=ft_rate,
            total_touches=data.touches,
        )

        # Estimate defensive possessions (minutes * ~2 possessions per minute)
        est_def_possessions = int(data.minutes * 2)

        # Calculate per-100 defensive rates
        if est_def_possessions > 0:
            deflections_per_100 = Decimal(data.deflections * 100) / Decimal(est_def_possessions)
            total_contests = data.contested_shots_2pt + data.contested_shots_3pt
            contests_per_100 = Decimal(total_contests * 100) / Decimal(est_def_possessions)
            # Steals not in tracking data, estimate from traditional
            steals_per_100 = Decimal(0)  # Would need to add steals to tracking data
            charges_per_100 = Decimal(data.charges_drawn * 100) / Decimal(est_def_possessions)
            loose_balls_per_100 = Decimal(data.loose_balls_recovered * 100) / Decimal(est_def_possessions)
        else:
            deflections_per_100 = Decimal(0)
            contests_per_100 = Decimal(0)
            steals_per_100 = Decimal(0)
            charges_per_100 = Decimal(0)
            loose_balls_per_100 = Decimal(0)

        # Calculate defensive metric
        defensive_metric = calculator.calculate_defensive_metric(
            deflections_per_100=deflections_per_100,
            contests_per_100=contests_per_100,
            steals_per_100=steals_per_100,
            charges_per_100=charges_per_100,
            loose_balls_per_100=loose_balls_per_100,
            total_possessions=est_def_possessions,
        )

        # Overall metric (weighted average)
        if offensive_metric > 0 or defensive_metric > 0:
            overall_metric = (offensive_metric * Decimal("0.6") + defensive_metric * Decimal("0.4"))
        else:
            overall_metric = Decimal(0)

        # Upsert season stats
        season_stats = (
            db.query(SeasonStats)
            .filter(SeasonStats.player_id == player.id, SeasonStats.season == season)
            .first()
        )

        if not season_stats:
            season_stats = SeasonStats(
                player_id=player.id,
                season=season,
            )
            db.add(season_stats)

        # Update stats
        season_stats.total_touches = data.touches
        season_stats.total_front_court_touches = data.front_court_touches
        season_stats.total_time_of_possession = data.time_of_possession
        season_stats.avg_points_per_touch = data.points_per_touch
        season_stats.total_deflections = data.deflections
        season_stats.total_contested_shots = data.contested_shots_2pt + data.contested_shots_3pt
        season_stats.total_charges_drawn = data.charges_drawn
        season_stats.total_loose_balls_recovered = data.loose_balls_recovered
        season_stats.total_minutes = data.minutes
        season_stats.total_points = data.points
        season_stats.total_assists = data.assists
        season_stats.offensive_metric = offensive_metric
        season_stats.defensive_metric = defensive_metric
        season_stats.overall_metric = overall_metric

    db.commit()
    print("Data committed to database.")

    # Calculate percentiles
    print("Calculating percentiles...")
    calculate_percentiles(season, db)


def calculate_percentiles(season: str, db: Session):
    """Calculate league percentiles for all players."""
    stats = (
        db.query(SeasonStats)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.offensive_metric > 0)
        .all()
    )

    # Sort by offensive metric
    off_sorted = sorted(stats, key=lambda x: x.offensive_metric or 0)
    for i, stat in enumerate(off_sorted):
        stat.offensive_percentile = int((i / len(off_sorted)) * 100)

    # Sort by defensive metric
    def_sorted = sorted(stats, key=lambda x: x.defensive_metric or 0)
    for i, stat in enumerate(def_sorted):
        stat.defensive_percentile = int((i / len(def_sorted)) * 100)

    db.commit()
    print("Percentiles calculated.")


def main():
    parser = argparse.ArgumentParser(description="Fetch NBA tracking data")
    parser.add_argument("--season", default="2024-25", help="NBA season (e.g., 2024-25)")
    parser.add_argument("--create-tables", action="store_true", help="Create database tables")
    args = parser.parse_args()

    if args.create_tables:
        create_tables()

    db = SessionLocal()
    try:
        fetch_and_store_data(args.season, db)
    finally:
        db.close()

    print("Done!")


if __name__ == "__main__":
    main()
