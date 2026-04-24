"""Seed ONE synthetic player with realistic data across every table the
new advanced-signal helpers read from. Lets us verify the card endpoint
populates all 14 new fields end-to-end without waiting for an NBA API
seed run.

Run: docker exec nba-stats-backend-dev python -m scripts.seed_synthetic_verify
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    LineupStats,
    Player,
    PlayerAdvancedStats,
    PlayerCareerStats,
    PlayerDefenderDistanceShooting,
    PlayerDefensiveStats,
    PlayerOnOffStats,
    PlayerPassingStats,
    PlayerShootingTracking,
    PlayerShotZones,
    PlayerSpeedDistance,
    PlayerTouchesBreakdown,
    SeasonPlayTypeStats,
    SeasonStats,
)
from app.models.game_stats import GameStats

SEASON = "2024-25"
NBA_ID = 999_999_01
PLAYER_ID = 999_999  # will be overwritten by autoincrement — we look up by nba_id


def wipe(db: Session) -> None:
    """Remove prior synthetic rows so the script is idempotent."""
    player = db.query(Player).filter(Player.nba_id == NBA_ID).first()
    if not player:
        return
    pid = player.id
    models_with_pid = [
        GameStats,
        LineupStats,
        PlayerAdvancedStats,
        PlayerCareerStats,
        PlayerDefenderDistanceShooting,
        PlayerDefensiveStats,
        PlayerOnOffStats,
        PlayerPassingStats,
        PlayerShootingTracking,
        PlayerShotZones,
        PlayerSpeedDistance,
        PlayerTouchesBreakdown,
        SeasonPlayTypeStats,
        SeasonStats,
    ]
    for m in models_with_pid:
        db.query(m).filter(m.player_id == pid).delete(synchronize_session=False)
    # Lineup rows reference the player across multiple slots — the loop
    # above only covered player1_id. Clean up the other slots as well.
    db.query(LineupStats).filter(
        (LineupStats.player1_id == pid)
        | (LineupStats.player2_id == pid)
        | (LineupStats.player3_id == pid)
        | (LineupStats.player4_id == pid)
        | (LineupStats.player5_id == pid)
    ).delete(synchronize_session=False)
    db.delete(player)
    db.flush()


def seed(db: Session) -> Player:
    wipe(db)

    player = Player(
        nba_id=NBA_ID,
        name="Synthetic Star",
        team_abbreviation="SYN",
        position="SG",
        height="6-6",
        weight=210,
        jersey_number="1",
        birth_date="28",
        country="USA",
        draft_year=2018,
        draft_round=1,
        draft_number=1,
    )
    db.add(player)
    db.flush()
    pid = player.id

    # --- Season totals (for Dwell, Contest-to-Miss, Gravity) ---
    db.add(
        SeasonStats(
            player_id=pid,
            season=SEASON,
            games_played=70,
            total_minutes=2450,
            total_points=2100,
            total_assists=450,
            total_rebounds=380,
            total_steals=95,
            total_blocks=30,
            total_turnovers=180,
            total_fg3m=220,
            total_fg3a=570,
            total_touches=5200,
            total_front_court_touches=3600,
            total_paint_touches=620,
            total_post_touches=210,
            total_elbow_touches=310,
            total_time_of_possession=Decimal("4320.50"),
            total_contested_shots=520,
            total_contested_shots_2pt=330,
            total_contested_shots_3pt=190,
            total_deflections=120,
        )
    )

    db.add(
        PlayerCareerStats(
            player_id=pid,
            season=SEASON,
            games_played=70,
            ppg=Decimal("30.0"),
            rpg=Decimal("5.4"),
            apg=Decimal("6.4"),
            spg=Decimal("1.4"),
            bpg=Decimal("0.4"),
            fg_pct=Decimal("0.505"),
            fg3_pct=Decimal("0.386"),
            ft_pct=Decimal("0.910"),
            minutes=Decimal("35.0"),
        )
    )

    db.add(
        PlayerAdvancedStats(
            player_id=pid,
            season=SEASON,
            ts_pct=Decimal("0.620"),
            usg_pct=Decimal("0.295"),
            off_rating=Decimal("120.0"),
            def_rating=Decimal("110.5"),
            pace=Decimal("99.5"),
        )
    )

    # --- Defender distance shooting (Friction + Gravity tight-rate) ---
    db.add(
        PlayerDefenderDistanceShooting(
            player_id=pid,
            season=SEASON,
            very_tight_fga_freq=Decimal("0.120"),
            very_tight_fg_pct=Decimal("0.410"),
            very_tight_efg_pct=Decimal("0.450"),
            very_tight_fg3_pct=Decimal("0.320"),
            tight_fga_freq=Decimal("0.360"),
            tight_fg_pct=Decimal("0.470"),
            tight_efg_pct=Decimal("0.510"),
            tight_fg3_pct=Decimal("0.360"),
            open_fga_freq=Decimal("0.350"),
            open_fg_pct=Decimal("0.520"),
            open_efg_pct=Decimal("0.580"),
            open_fg3_pct=Decimal("0.400"),
            wide_open_fga_freq=Decimal("0.170"),
            wide_open_fg_pct=Decimal("0.570"),
            wide_open_efg_pct=Decimal("0.650"),
            wide_open_fg3_pct=Decimal("0.450"),
        )
    )

    # --- On/off (Gravity) ---
    db.add(
        PlayerOnOffStats(
            player_id=pid,
            season=SEASON,
            on_court_minutes=Decimal("2450"),
            on_court_off_rating=Decimal("119.5"),
            on_court_def_rating=Decimal("112.0"),
            on_court_net_rating=Decimal("7.5"),
            off_court_minutes=Decimal("1480"),
            off_court_off_rating=Decimal("111.0"),
            off_court_def_rating=Decimal("114.5"),
            off_court_net_rating=Decimal("-3.5"),
            plus_minus_diff=Decimal("10.0"),
            off_rating_diff=Decimal("8.5"),
            def_rating_diff=Decimal("-2.5"),
            net_rating_diff=Decimal("11.0"),
        )
    )

    # --- Play types (Shot Diet + Scheme Robustness) ---
    db.add(
        SeasonPlayTypeStats(
            player_id=pid,
            season=SEASON,
            total_poss=1800,
            isolation_poss=330,
            isolation_pts=380,
            isolation_ppp=Decimal("1.150"),
            isolation_fg_pct=Decimal("0.485"),
            isolation_freq=Decimal("0.183"),
            isolation_ppp_percentile=82,
            pnr_ball_handler_poss=540,
            pnr_ball_handler_pts=600,
            pnr_ball_handler_ppp=Decimal("1.110"),
            pnr_ball_handler_fg_pct=Decimal("0.470"),
            pnr_ball_handler_freq=Decimal("0.300"),
            pnr_ball_handler_ppp_percentile=78,
            spot_up_poss=280,
            spot_up_pts=340,
            spot_up_ppp=Decimal("1.210"),
            spot_up_fg_pct=Decimal("0.500"),
            spot_up_freq=Decimal("0.156"),
            spot_up_ppp_percentile=85,
            transition_poss=240,
            transition_pts=330,
            transition_ppp=Decimal("1.375"),
            transition_fg_pct=Decimal("0.580"),
            transition_freq=Decimal("0.133"),
            transition_ppp_percentile=90,
            post_up_poss=110,
            post_up_pts=115,
            post_up_ppp=Decimal("1.045"),
            post_up_fg_pct=Decimal("0.460"),
            post_up_freq=Decimal("0.061"),
            post_up_ppp_percentile=70,
            cut_poss=90,
            cut_pts=130,
            cut_ppp=Decimal("1.444"),
            cut_fg_pct=Decimal("0.680"),
            cut_freq=Decimal("0.050"),
            cut_ppp_percentile=88,
            off_screen_poss=60,
            off_screen_pts=55,
            off_screen_ppp=Decimal("0.917"),
            off_screen_fg_pct=Decimal("0.410"),
            off_screen_freq=Decimal("0.033"),
            off_screen_ppp_percentile=55,
            handoff_poss=80,
            handoff_pts=88,
            handoff_ppp=Decimal("1.100"),
            handoff_fg_pct=Decimal("0.475"),
            handoff_freq=Decimal("0.044"),
            handoff_ppp_percentile=72,
            pnr_roll_man_poss=30,
            pnr_roll_man_pts=34,
            pnr_roll_man_ppp=Decimal("1.133"),
            pnr_roll_man_fg_pct=Decimal("0.560"),
            pnr_roll_man_freq=Decimal("0.017"),
            pnr_roll_man_ppp_percentile=70,
        )
    )

    # --- Touches breakdown (Rim Gravity) ---
    db.add(
        PlayerTouchesBreakdown(
            player_id=pid,
            season=SEASON,
            paint_touches=Decimal("8.2"),
            paint_touch_fga=Decimal("4.5"),
            paint_touch_fg_pct=Decimal("0.625"),
            paint_touch_pts=Decimal("6.8"),
            paint_touch_passes=Decimal("3.1"),
            paint_touch_ast=Decimal("1.0"),
            paint_touch_tov=Decimal("0.7"),
            paint_touch_fouls=Decimal("1.9"),
            paint_touch_pts_per_touch=Decimal("0.830"),
            post_touches=Decimal("3.0"),
            post_touch_fga=Decimal("1.5"),
            post_touch_fg_pct=Decimal("0.460"),
            post_touch_pts=Decimal("1.6"),
            post_touch_pts_per_touch=Decimal("0.533"),
            elbow_touches=Decimal("4.4"),
            elbow_touch_fga=Decimal("2.0"),
            elbow_touch_fg_pct=Decimal("0.495"),
            elbow_touch_pts=Decimal("2.2"),
            elbow_touch_pts_per_touch=Decimal("0.500"),
        )
    )

    # --- Shooting tracking (Rim Gravity drives + catch/shoot context) ---
    db.add(
        PlayerShootingTracking(
            player_id=pid,
            season=SEASON,
            catch_shoot_fga=Decimal("4.2"),
            catch_shoot_fg_pct=Decimal("0.410"),
            catch_shoot_fg3a=Decimal("3.5"),
            catch_shoot_fg3_pct=Decimal("0.395"),
            catch_shoot_pts=Decimal("5.2"),
            catch_shoot_efg_pct=Decimal("0.580"),
            pullup_fga=Decimal("7.8"),
            pullup_fg_pct=Decimal("0.420"),
            pullup_fg3a=Decimal("3.0"),
            pullup_fg3_pct=Decimal("0.360"),
            pullup_pts=Decimal("8.1"),
            pullup_efg_pct=Decimal("0.490"),
            drives=Decimal("14.5"),
            drive_fga=Decimal("6.0"),
            drive_fg_pct=Decimal("0.520"),
            drive_pts=Decimal("9.1"),
            drive_passes=Decimal("5.0"),
            drive_ast=Decimal("2.0"),
            drive_tov=Decimal("0.9"),
        )
    )

    # --- Shot zones (Rim Gravity RimFG%) ---
    db.add(
        PlayerShotZones(
            player_id=pid,
            season=SEASON,
            zone="Restricted Area",
            fgm=Decimal("6.8"),
            fga=Decimal("10.0"),
            fg_pct=Decimal("0.680"),
            freq=Decimal("0.320"),
            league_avg=Decimal("0.640"),
        )
    )
    db.add(
        PlayerShotZones(
            player_id=pid,
            season=SEASON,
            zone="Above the Break 3",
            fgm=Decimal("2.5"),
            fga=Decimal("6.2"),
            fg_pct=Decimal("0.403"),
            freq=Decimal("0.230"),
            league_avg=Decimal("0.365"),
        )
    )

    # --- Passing (Pass Funnel) ---
    db.add(
        PlayerPassingStats(
            player_id=pid,
            season=SEASON,
            passes_made=Decimal("55.2"),
            passes_received=Decimal("62.5"),
            secondary_ast=Decimal("1.8"),
            potential_ast=Decimal("12.3"),
            ast_points_created=Decimal("16.2"),
            ast_adj=Decimal("7.0"),
            ast_to_pass_pct=Decimal("0.1156"),
            ast_to_pass_pct_adj=Decimal("0.1260"),
        )
    )

    # --- Defense (Terrain + Contest-to-Miss) ---
    db.add(
        PlayerDefensiveStats(
            player_id=pid,
            season=SEASON,
            games_played=70,
            age=28,
            overall_d_fga=Decimal("680"),
            overall_d_fgm=Decimal("290"),
            overall_d_fg_pct=Decimal("0.426"),
            overall_normal_fg_pct=Decimal("0.465"),
            overall_pct_plusminus=Decimal("-0.039"),
            overall_freq=Decimal("1.000"),
            rim_d_fga=Decimal("210"),
            rim_d_fgm=Decimal("115"),
            rim_d_fg_pct=Decimal("0.548"),
            rim_normal_fg_pct=Decimal("0.640"),
            rim_pct_plusminus=Decimal("-0.092"),
            rim_freq=Decimal("0.310"),
            three_pt_d_fga=Decimal("280"),
            three_pt_d_fgm=Decimal("96"),
            three_pt_d_fg_pct=Decimal("0.343"),
            three_pt_normal_fg_pct=Decimal("0.370"),
            three_pt_pct_plusminus=Decimal("-0.027"),
            three_pt_freq=Decimal("0.410"),
            iso_poss=55,
            iso_pts=48,
            iso_fgm=19,
            iso_fga=50,
            iso_ppp=Decimal("0.873"),
            iso_fg_pct=Decimal("0.380"),
            iso_percentile=Decimal("72"),
        )
    )

    # --- Speed/Distance (Mile-Adjusted) ---
    db.add(
        PlayerSpeedDistance(
            player_id=pid,
            season=SEASON,
            dist_miles=Decimal("2.55"),
            dist_miles_off=Decimal("1.35"),
            dist_miles_def=Decimal("1.20"),
            avg_speed=Decimal("4.10"),
            avg_speed_off=Decimal("4.25"),
            avg_speed_def=Decimal("3.95"),
            dist_feet=Decimal("13464.00"),
        )
    )

    # --- Game Stats: 30 games (enough for the 10/10 late-season window) ---
    # Vary plus_minus so we have both leverage (|pm|<=15) and blowouts.
    start = date(2024, 10, 22)
    base_pts = 30
    for i in range(30):
        gdate = (start + timedelta(days=i * 2)).isoformat()
        # Alternate between close games and blowouts; ramp game_score up
        # late in the sample so Late-Season Trend shows a positive delta.
        pm = 7 if i % 3 != 0 else 22
        pm = -pm if i % 2 == 0 else pm
        pts = base_pts + (i % 5) + (i >= 20) * 3
        fga = 19 + (i % 3)
        fta = 6 + (i % 2)
        db.add(
            GameStats(
                player_id=pid,
                season=SEASON,
                game_id=f"SYN{i:04d}",
                game_date=gdate,
                matchup=f"SYN vs OPP{i % 5}",
                wl="W" if pm > 0 else "L",
                minutes=Decimal("34.50"),
                points=pts,
                assists=6,
                rebounds=5,
                steals=1,
                blocks=0,
                turnovers=3,
                fga=fga,
                fta=fta,
                plus_minus=pm,
                game_score=Decimal(str(round(20.0 + (i * 0.15), 2))),
                fg_pct=Decimal("0.500"),
                fg3_pct=Decimal("0.380"),
                touches=72,
                front_court_touches=48,
                paint_touches=10,
                post_touches=4,
                elbow_touches=5,
                time_of_possession=Decimal("6.2"),
                avg_seconds_per_touch=Decimal("2.80"),
            )
        )

    # --- Lineups (Buoyancy) ---
    # Eight lineups with varied net ratings + minutes so the tercile
    # split produces a meaningful floor/ceiling read.
    teammate_ids: list[int] = []
    for i, other_name in enumerate(
        ["Bob", "Carl", "Dan", "Eli", "Finn", "Gus", "Hal", "Ian"], start=1
    ):
        other = Player(
            nba_id=NBA_ID + i,
            name=f"Teammate {other_name}",
            team_abbreviation="SYN",
            position="SF",
        )
        db.add(other)
        db.flush()
        teammate_ids.append(other.id)

    # (minutes, net_rating) pairs spanning the worst/middle/best terciles.
    lineup_perf = [
        (95, Decimal("-9.5")),
        (80, Decimal("-5.0")),
        (140, Decimal("-1.0")),
        (210, Decimal("1.5")),
        (260, Decimal("3.0")),
        (180, Decimal("5.8")),
        (130, Decimal("9.2")),
        (60, Decimal("14.0")),
    ]
    for idx, (minutes, net) in enumerate(lineup_perf):
        mates = [teammate_ids[(idx + j) % len(teammate_ids)] for j in range(4)]
        db.add(
            LineupStats(
                season=SEASON,
                team_id=1,
                team_abbreviation="SYN",
                lineup_id=f"syn-{idx}",
                group_name=f"Synthetic Unit {idx}",
                player1_id=pid,
                player2_id=mates[0],
                player3_id=mates[1],
                player4_id=mates[2],
                player5_id=mates[3],
                games_played=max(8, idx * 4),
                minutes=Decimal(str(minutes)),
                plus_minus=Decimal(str(int(float(net) * minutes / 100))),
                off_rating=Decimal("115") + net,
                def_rating=Decimal("115") - net,
                net_rating=net,
            )
        )

    db.commit()
    return player


def main() -> None:
    with SessionLocal() as db:
        player = seed(db)
        print(f"Seeded synthetic player id={player.id} nba_id={player.nba_id}")


if __name__ == "__main__":
    main()
