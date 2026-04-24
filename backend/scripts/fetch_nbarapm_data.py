#!/usr/bin/env python3
"""Script to fetch data from nbarapm.com API endpoints.

Fetches and stores:
- /load/current_comp: Multi-metric comparison (RAPM windows, LEBRON, LAKER, DARKO)
- /load/player_stats_export: Big Board (148 fields of per-player analytics)
- /load/SCALEDOUTPUT_SMALLER: Six Factor RAPM decomposition
- /api/peakleaderboard: Peak RAPM across 2Y-5Y windows
- /load/raptor: RAPTOR history (back to 1977)
- /load/mamba: MAMBA history
- /load/rFTOV: Forced turnovers

Usage:
    python -m scripts.fetch_nbarapm_data
    python -m scripts.fetch_nbarapm_data --season 2024-25
    python -m scripts.fetch_nbarapm_data --only current_comp big_board six_factor peak raptor mamba ftov
    python -m scripts.fetch_nbarapm_data --verbose
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player, PlayerAllInOneMetrics
from app.models.big_board import PlayerBigBoard
from app.models.darko_history import DarkoHistory
from app.models.forced_turnovers import ForcedTurnovers
from app.models.mamba_history import MambaHistory
from app.models.peak_rapm import PeakRapm
from app.models.rapm_windows import PlayerRapmWindows
from app.models.raptor_history import RaptorHistory
from app.models.six_factor_rapm import SixFactorRapm
from scripts.shared import build_nba_id_lookup, safe_decimal, safe_int, setup_logging

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nbarapm.com"
REQUEST_TIMEOUT = 60


def fetch_json(client: httpx.Client, endpoint: str) -> list[dict]:
    url = f"{BASE_URL}{endpoint}"
    logger.info("Fetching %s ...", url)
    response = client.get(url)
    response.raise_for_status()
    data = response.json()
    logger.info("Fetched %d records from %s", len(data), endpoint)
    return data



# ---------------------------------------------------------------------------
# Phase 1: current_comp -> PlayerRapmWindows + update PlayerAllInOneMetrics
# ---------------------------------------------------------------------------

def store_current_comp(
    db: Session,
    data: list[dict],
    season: str,
    nba_id_lookup: dict[int, int],
    verbose: bool = False,
) -> dict[str, int]:
    """Store current_comp data into rapm_windows and update all_in_one_metrics."""
    rapm_stored = 0
    lebron_updated = 0
    laker_updated = 0
    rapm_filled = 0
    positions_updated = 0
    skipped = 0

    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            skipped += 1
            continue

        player_id = nba_id_lookup.get(int(nba_id))
        if not player_id:
            skipped += 1
            continue

        # Fill player position if missing
        pos = row.get("Pos2")
        if pos:
            player = db.query(Player).filter(Player.id == player_id).first()
            if player and not player.position:
                player.position = pos
                positions_updated += 1

        # Upsert RAPM windows
        existing_rapm = (
            db.query(PlayerRapmWindows)
            .filter(
                PlayerRapmWindows.player_id == player_id,
                PlayerRapmWindows.season == season,
            )
            .first()
        )
        if not existing_rapm:
            existing_rapm = PlayerRapmWindows(player_id=player_id, season=season)
            db.add(existing_rapm)

        # Timedecay
        existing_rapm.timedecay_orapm = safe_decimal(row.get("orapm_timedecay"))
        existing_rapm.timedecay_drapm = safe_decimal(row.get("drapm_timedecay"))
        existing_rapm.timedecay_rapm = safe_decimal(row.get("rapm_timedecay"))
        existing_rapm.timedecay_orapm_rank = safe_int(row.get("orapm_rank_timedecay"))
        existing_rapm.timedecay_drapm_rank = safe_int(row.get("drapm_rank_timedecay"))
        existing_rapm.timedecay_rapm_rank = safe_int(row.get("rapm_rank_timedecay"))
        # 2-year
        existing_rapm.two_year_orapm = safe_decimal(row.get("two_year_orapm"))
        existing_rapm.two_year_drapm = safe_decimal(row.get("two_year_drapm"))
        existing_rapm.two_year_rapm = safe_decimal(row.get("two_year_rapm"))
        existing_rapm.two_year_orapm_rank = safe_int(row.get("two_year_orapm_rank"))
        existing_rapm.two_year_drapm_rank = safe_int(row.get("two_year_drapm_rank"))
        existing_rapm.two_year_rapm_rank = safe_int(row.get("two_year_rapm_rank"))
        # 3-year
        existing_rapm.three_year_orapm = safe_decimal(row.get("three_year_orapm"))
        existing_rapm.three_year_drapm = safe_decimal(row.get("three_year_drapm"))
        existing_rapm.three_year_rapm = safe_decimal(row.get("three_year_rapm"))
        existing_rapm.three_year_orapm_rank = safe_int(row.get("three_year_orapm_rank"))
        existing_rapm.three_year_drapm_rank = safe_int(row.get("three_year_drapm_rank"))
        existing_rapm.three_year_rapm_rank = safe_int(row.get("three_year_rapm_rank"))
        # 4-year
        existing_rapm.four_year_orapm = safe_decimal(row.get("four_year_orapm"))
        existing_rapm.four_year_drapm = safe_decimal(row.get("four_year_drapm"))
        existing_rapm.four_year_rapm = safe_decimal(row.get("four_year_rapm"))
        existing_rapm.four_year_orapm_rank = safe_int(row.get("four_year_orapm_rank"))
        existing_rapm.four_year_drapm_rank = safe_int(row.get("four_year_drapm_rank"))
        existing_rapm.four_year_rapm_rank = safe_int(row.get("four_year_rapm_rank"))
        # 5-year
        existing_rapm.five_year_orapm = safe_decimal(row.get("five_year_orapm"))
        existing_rapm.five_year_drapm = safe_decimal(row.get("five_year_drapm"))
        existing_rapm.five_year_rapm = safe_decimal(row.get("five_year_rapm"))
        existing_rapm.five_year_orapm_rank = safe_int(row.get("five_year_orapm_rank"))
        existing_rapm.five_year_drapm_rank = safe_int(row.get("five_year_drapm_rank"))
        existing_rapm.five_year_rapm_rank = safe_int(row.get("five_year_rapm_rank"))
        rapm_stored += 1

        # Update all_in_one_metrics with LEBRON and LAKER from this source
        metrics = (
            db.query(PlayerAllInOneMetrics)
            .filter(
                PlayerAllInOneMetrics.player_id == player_id,
                PlayerAllInOneMetrics.season == season,
            )
            .first()
        )
        if not metrics:
            metrics = PlayerAllInOneMetrics(player_id=player_id, season=season)
            db.add(metrics)

        # Fill LEBRON if missing (we couldn't scrape bball-index.com)
        lebron_val = safe_decimal(row.get("rapm_lebron"))
        if lebron_val is not None and metrics.lebron is None:
            metrics.lebron = lebron_val
            metrics.lebron_offense = safe_decimal(row.get("orapm_lebron"))
            metrics.lebron_defense = safe_decimal(row.get("drapm_lebron"))
            lebron_updated += 1

        # Always set LAKER (new metric)
        laker_val = safe_decimal(row.get("rapm_laker"))
        if laker_val is not None:
            metrics.laker = laker_val
            metrics.laker_offense = safe_decimal(row.get("orapm_laker"))
            metrics.laker_defense = safe_decimal(row.get("drapm_laker"))
            laker_updated += 1

        # Fill RAPM from timedecay (best single-number RAPM estimate)
        rapm_val = safe_decimal(row.get("rapm_timedecay"))
        if rapm_val is not None:
            metrics.rapm = rapm_val
            metrics.rapm_offense = safe_decimal(row.get("orapm_timedecay"))
            metrics.rapm_defense = safe_decimal(row.get("drapm_timedecay"))
            rapm_filled += 1

        # Update data_sources
        existing_sources = (metrics.data_sources or "").split(",")
        all_sources = sorted(
            set(s.strip() for s in existing_sources + ["NBARAPM"] if s.strip())
        )
        metrics.data_sources = ",".join(all_sources)

    return {
        "rapm_windows": rapm_stored,
        "lebron_filled": lebron_updated,
        "laker_updated": laker_updated,
        "rapm_filled": rapm_filled,
        "positions_updated": positions_updated,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Phase 2: player_stats_export -> PlayerBigBoard
# ---------------------------------------------------------------------------

def store_big_board(
    db: Session,
    data: list[dict],
    season: str,
    nba_id_lookup: dict[int, int],
    verbose: bool = False,
) -> dict[str, int]:
    """Store Big Board data."""
    stored = 0
    skipped = 0

    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            skipped += 1
            continue

        player_id = nba_id_lookup.get(int(nba_id))
        if not player_id:
            skipped += 1
            continue

        existing = (
            db.query(PlayerBigBoard)
            .filter(
                PlayerBigBoard.player_id == player_id,
                PlayerBigBoard.season == season,
            )
            .first()
        )
        if not existing:
            existing = PlayerBigBoard(player_id=player_id, season=season)
            db.add(existing)

        # Bio
        existing.position = row.get("Pos2") or row.get("Pos")
        existing.offensive_archetype = row.get("Offensive Archetype")
        existing.age = safe_decimal(row.get("Age2"))
        existing.games_played = safe_int(row.get("GamesPlayed"))
        existing.minutes = safe_decimal(row.get("Minutes"))
        existing.mpg = safe_decimal(row.get("MPG"))
        existing.salary = safe_decimal(row.get("salary"))

        # Scoring efficiency
        existing.pts_per_75 = safe_decimal(row.get("Pts75"))
        existing.ts_pct = safe_decimal(row.get("TS_percent"))
        existing.ts_pct_percentile = safe_decimal(row.get("TS_percent_percentile"))
        existing.relative_ts = safe_decimal(row.get("rTSPct"))
        existing.relative_ts_percentile = safe_decimal(row.get("rTSPct_percentile"))
        existing.mod_ts = safe_decimal(row.get("mod_ts"))
        existing.ts_added_per_100 = safe_decimal(row.get("TS_added_100"))
        existing.ts_added_per_100_percentile = safe_decimal(row.get("TS_added_100_percentile"))
        existing.tsa_per_100 = safe_decimal(row.get("TSA100"))
        existing.tsa_per_100_percentile = safe_decimal(row.get("TSA100_percentile"))

        # Shooting splits
        existing.fg2_pct = safe_decimal(row.get("2P_PERC"))
        existing.fg2_pct_percentile = safe_decimal(row.get("2P_PERC_percentile"))
        existing.fg2a_per_100 = safe_decimal(row.get("2PA_100"))
        existing.fg3_pct = safe_decimal(row.get("3P_PERC"))
        existing.fg3_pct_percentile = safe_decimal(row.get("3P_PERC_percentile"))
        existing.fg3a_per_100 = safe_decimal(row.get("FG3A100") or row.get("3PA_100"))
        existing.three_point_rate = safe_decimal(row.get("3PR"))
        existing.ft_pct = safe_decimal(row.get("FT_PERC"))
        existing.ft_pct_percentile = safe_decimal(row.get("FT_PERC_percentile"))
        existing.fta_per_100 = safe_decimal(row.get("FTA_100"))
        existing.ftr = safe_decimal(row.get("FTR"))
        existing.ftr_percentile = safe_decimal(row.get("FTR_percentile"))

        # Catch-and-shoot / pull-up
        existing.cs_3pa = safe_decimal(row.get("cs_3pa"))
        existing.cs_3pct = safe_decimal(row.get("cs_3pct"))
        existing.pu_3pa = safe_decimal(row.get("pu_3pa"))
        existing.pu_3pct = safe_decimal(row.get("pu_3pct"))

        # Passing
        existing.assists_per_100 = safe_decimal(row.get("PASSING_Assists/100"))
        existing.assists_per_100_percentile = safe_decimal(row.get("PASSING_Assists/100_percentile"))
        existing.potential_assists_per_100 = safe_decimal(row.get("PASSING_Potential Assists/100"))
        existing.at_rim_assists_per_100 = safe_decimal(row.get("PASSING_AtRimAssists/100"))
        existing.mid_assists_per_100 = safe_decimal(row.get("PASSING_MidAssists/100"))
        existing.three_pt_assists_per_100 = safe_decimal(row.get("PASSING_ThreePtAssists/100"))
        existing.assist_efg = safe_decimal(row.get("PASSING_AssistEFG"))
        existing.assist_efg_percentile = safe_decimal(row.get("PASSING_AssistEFG_percentile"))
        existing.on_ball_time_pct = safe_decimal(row.get("PASSING_on-ball-time%"))
        existing.on_ball_time_pct_percentile = safe_decimal(row.get("PASSING_on-ball-time%_percentile"))
        existing.bad_pass_pct = safe_decimal(row.get("PASSING_BP%"))
        existing.bad_pass_tov_per_100 = safe_decimal(row.get("final_bp_tov_100"))

        # Turnovers
        existing.scoring_tov_pct = safe_decimal(row.get("Scoring_TOV%"))
        existing.scoring_tov_pct_percentile = safe_decimal(row.get("Scoring_TOV%_percentile"))
        existing.scoring_tovs_per_100 = safe_decimal(row.get("scoring_tovs_100"))

        # Defense
        existing.dfga_per_100 = safe_decimal(row.get("dfga/100"))
        existing.dfga_per_100_percentile = safe_decimal(row.get("dfga/100_percentile"))
        existing.dif_pct = safe_decimal(row.get("dif%"))
        existing.dif_pct_percentile = safe_decimal(row.get("dif%_percentile"))
        existing.stops_per_100 = safe_decimal(row.get("STOPS_100"))
        existing.stops_per_100_percentile = safe_decimal(row.get("STOPS_100_percentile"))
        existing.relative_stops_per_100 = safe_decimal(row.get("rSTOPS_100"))
        existing.blocks_per_100 = safe_decimal(row.get("Blocks_100"))
        existing.steals_per_100 = safe_decimal(row.get("Steals_100"))
        existing.offd_per_100 = safe_decimal(row.get("OFFD_100"))
        existing.points_saved_per_100 = safe_decimal(row.get("points_saved_100"))
        existing.points_saved_per_100_percentile = safe_decimal(row.get("points_saved_100_percentile"))
        existing.forced_tov_per_100 = safe_decimal(row.get("rFTOV_100"))
        existing.forced_tov_per_100_percentile = safe_decimal(row.get("rFTOV_100_percentile"))

        # Rim defense
        existing.rim_dfga_per_100 = safe_decimal(row.get("rimdfga/100"))
        existing.rim_dif_pct = safe_decimal(row.get("rim_dif%"))
        existing.rim_dif_pct_percentile = safe_decimal(row.get("rim_dif%_percentile"))
        existing.rim_points_saved_per_100 = safe_decimal(row.get("rim_points_saved_100"))
        existing.rim_freq_on = safe_decimal(row.get("rim_freq_on"))
        existing.rim_freq_onoff = safe_decimal(row.get("rim_freq_onoff"))
        existing.rim_acc_on = safe_decimal(row.get("rim_acc_on"))
        existing.rim_acc_onoff = safe_decimal(row.get("rim_acc_onoff"))

        # Rebounding
        existing.prob_off_rebounded = safe_decimal(row.get("ProbabilityOffRebounded"))
        existing.self_oreb_pct = safe_decimal(row.get("SelfORebPct"))
        existing.teammate_miss_oreb_pct = safe_decimal(row.get("TeammateMissORebPerc"))

        # Play type impact
        existing.playtype_rppp = safe_decimal(row.get("playtype_rPPP"))
        existing.playtype_rppp_percentile = safe_decimal(row.get("playtype_rPPP_percentile"))
        existing.playtype_ts_rppp = safe_decimal(row.get("playtype_TS_rPPP"))
        existing.playtype_tov_rppp = safe_decimal(row.get("playtype_TOV_rPPP"))
        existing.playtype_diff = safe_decimal(row.get("playtype_diff"))
        existing.playtype_diff_percentile = safe_decimal(row.get("playtype_diff_percentile"))
        existing.playtype_adj_rppp = safe_decimal(row.get("playtype_adj_rPPP"))
        existing.pt_adj_rts = safe_decimal(row.get("pt_adj_rTS"))

        # Shooting context
        existing.first_chance_pct = safe_decimal(row.get("firstchanceperc"))
        existing.second_fg_created_per_100 = safe_decimal(row.get("SFC_100"))

        stored += 1

    return {"stored": stored, "skipped": skipped}


# ---------------------------------------------------------------------------
# Phase 3: SCALEDOUTPUT_SMALLER -> SixFactorRapm
# ---------------------------------------------------------------------------

def store_six_factor(
    db: Session,
    data: list[dict],
    verbose: bool = False,
) -> dict[str, int]:
    """Store Six Factor RAPM data (bulk replace)."""
    # Clear existing data and bulk insert
    db.query(SixFactorRapm).delete()

    stored = 0
    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            continue

        record = SixFactorRapm(
            nba_id=int(nba_id),
            player_name=row.get("player_name", ""),
            year_interval=row.get("Year_Interval", ""),
            latest_year=safe_int(row.get("Latest_Year")) or 0,
            off_poss=safe_int(row.get("Off_Poss")),
            off_rapm=safe_decimal(row.get("Off_RAPM")),
            def_rapm=safe_decimal(row.get("Def_RAPM")),
            ovr_rapm=safe_decimal(row.get("OVR_RAPM")),
            off_rapm_rank=safe_int(row.get("Off_RAPM_rank")),
            def_rapm_rank=safe_int(row.get("Def_RAPM_rank")),
            ovr_rapm_rank=safe_int(row.get("OVR_RAPM_rank")),
            sc_off_ts=safe_decimal(row.get("sc_OFF_TS")),
            sc_off_ts_rank=safe_int(row.get("sc_OFF_TS_rank")),
            sc_off_tov=safe_decimal(row.get("sc_OFF_TOV")),
            sc_off_tov_rank=safe_int(row.get("sc_OFF_TOV_rank")),
            sc_off_reb=safe_decimal(row.get("sc_OFF_REB")),
            sc_off_reb_rank=safe_int(row.get("sc_OFF_REB_rank")),
            sc_def_ts=safe_decimal(row.get("sc_DEF_TS")),
            sc_def_ts_rank=safe_int(row.get("sc_DEF_TS_rank")),
            sc_def_tov=safe_decimal(row.get("sc_DEF_TOV")),
            sc_def_tov_rank=safe_int(row.get("sc_DEF_TOV_rank")),
            sc_def_reb=safe_decimal(row.get("sc_DEF_REB")),
            sc_def_reb_rank=safe_int(row.get("sc_DEF_REB_rank")),
            sc_poss=safe_decimal(row.get("sc_POSS")),
            sc_poss_rank=safe_int(row.get("sc_POSS_rank")),
            off_diff=safe_decimal(row.get("off_diff")),
            def_diff=safe_decimal(row.get("def_diff")),
        )
        db.add(record)
        stored += 1

        if stored % 5000 == 0:
            db.flush()
            if verbose:
                print(f"    Flushed {stored} records...")

    return {"stored": stored}


# ---------------------------------------------------------------------------
# Phase 4: peakleaderboard -> PeakRapm
# ---------------------------------------------------------------------------

def store_peak_rapm(db: Session, data: list[dict], verbose: bool = False) -> dict[str, int]:
    """Store Peak RAPM leaderboard data (bulk replace)."""
    db.query(PeakRapm).delete()
    stored = 0
    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            continue
        record = PeakRapm(
            nba_id=int(nba_id),
            player_name=row.get("player_name", ""),
            dataset=row.get("dataset", ""),
            orapm=safe_decimal(row.get("orapm")),
            drapm=safe_decimal(row.get("drapm")),
            rapm=safe_decimal(row.get("rapm")),
            orapm_rank=safe_int(row.get("orapm_rank")),
            drapm_rank=safe_int(row.get("drapm_rank")),
            rapm_rank=safe_int(row.get("rapm_rank")),
            current=safe_int(row.get("current")),
            team_id=safe_int(row.get("team_id")),
        )
        db.add(record)
        stored += 1
        if stored % 5000 == 0:
            db.flush()
    return {"stored": stored}


# ---------------------------------------------------------------------------
# Phase 5: raptor -> RaptorHistory
# ---------------------------------------------------------------------------

def store_raptor(db: Session, data: list[dict], verbose: bool = False) -> dict[str, int]:
    """Store RAPTOR history data (bulk replace)."""
    db.query(RaptorHistory).delete()
    stored = 0
    for row in data:
        record = RaptorHistory(
            player_name=row.get("player_name", ""),
            nba_id=str(row.get("nba_id", "")),
            season=safe_int(row.get("season")) or 0,
            minutes=safe_int(row.get("mp")),
            possessions=safe_int(row.get("poss")),
            raptor_offense=safe_decimal(row.get("raptor_offense")),
            raptor_defense=safe_decimal(row.get("raptor_defense")),
            raptor_total=safe_decimal(row.get("raptor_total")),
            war_total=safe_decimal(row.get("war_total")),
            o_raptor_rank=safe_int(row.get("o_raptor_rank")),
            d_raptor_rank=safe_int(row.get("d_raptor_rank")),
            raptor_rank=safe_int(row.get("raptor_rank")),
        )
        db.add(record)
        stored += 1
        if stored % 5000 == 0:
            db.flush()
    return {"stored": stored}


# ---------------------------------------------------------------------------
# Phase 6: mamba -> MambaHistory
# ---------------------------------------------------------------------------

def store_mamba(db: Session, data: list[dict], verbose: bool = False) -> dict[str, int]:
    """Store MAMBA history data (bulk replace)."""
    db.query(MambaHistory).delete()
    stored = 0
    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            continue
        record = MambaHistory(
            nba_id=int(nba_id),
            player_name=row.get("player_name", ""),
            year=safe_int(row.get("year")) or 0,
            minutes=safe_decimal(row.get("Minutes")),
            o_mamba=safe_decimal(row.get("O-MAMBA")),
            d_mamba=safe_decimal(row.get("D-MAMBA")),
            mamba=safe_decimal(row.get("MAMBA")),
            o_mamba_rank=safe_int(row.get("O-MAMBA_rank")),
            d_mamba_rank=safe_int(row.get("D-MAMBA_rank")),
            mamba_rank=safe_int(row.get("MAMBA_rank")),
        )
        db.add(record)
        stored += 1
        if stored % 2000 == 0:
            db.flush()
    return {"stored": stored}


# ---------------------------------------------------------------------------
# Phase 7: rFTOV -> ForcedTurnovers
# ---------------------------------------------------------------------------

def store_darko_history(db: Session, data: list[dict], verbose: bool = False) -> dict[str, int]:
    """Store DARKO DPM history data (bulk replace)."""
    db.query(DarkoHistory).delete()
    stored = 0
    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            continue
        record = DarkoHistory(
            nba_id=int(nba_id),
            player_name=row.get("player_name", ""),
            season=safe_int(row.get("season")) or 0,
            team_name=row.get("team_name"),
            age=safe_decimal(row.get("age")),
            dpm=safe_decimal(row.get("dpm")),
            o_dpm=safe_decimal(row.get("o_dpm")),
            d_dpm=safe_decimal(row.get("d_dpm")),
            dpm_rank=safe_int(row.get("dpm_rank")),
            o_dpm_rank=safe_int(row.get("o_dpm_rank")),
            d_dpm_rank=safe_int(row.get("d_dpm_rank")),
            box_odpm=safe_decimal(row.get("box_odpm")),
            box_ddpm=safe_decimal(row.get("box_ddpm")),
            on_off_odpm=safe_decimal(row.get("on_off_odpm")),
            on_off_ddpm=safe_decimal(row.get("on_off_ddpm")),
        )
        db.add(record)
        stored += 1
        if stored % 5000 == 0:
            db.flush()
    return {"stored": stored}


# ---------------------------------------------------------------------------
# Phase 8: rFTOV -> ForcedTurnovers
# ---------------------------------------------------------------------------

def store_ftov(db: Session, data: list[dict], verbose: bool = False) -> dict[str, int]:
    """Store Forced Turnovers data (bulk replace)."""
    db.query(ForcedTurnovers).delete()
    stored = 0
    for row in data:
        nba_id = row.get("nba_id")
        if not nba_id:
            continue
        record = ForcedTurnovers(
            nba_id=int(nba_id),
            player_name=row.get("player_name", ""),
            dtov=safe_decimal(row.get("DTOV")),
            diff=safe_decimal(row.get("Diff")),
            total_def_poss=safe_int(row.get("Total_DefPoss")),
            weighted_avg_rftov=safe_decimal(row.get("Weighted_Avg_rFTOV")),
        )
        db.add(record)
        stored += 1
    return {"stored": stored}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch data from nbarapm.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--season", default="2025-26", help="NBA season (default: 2025-26)")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["current_comp", "big_board", "six_factor", "peak", "raptor", "mamba", "darko_history", "ftov"],
        help="Run only specific phases",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--create-tables", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    phases = args.only or ["current_comp", "big_board", "six_factor", "peak", "raptor", "mamba", "darko_history", "ftov"]

    print("\n" + "=" * 60)
    print("  StatFloor — nbarapm.com Data Fetcher")
    print("=" * 60)
    print(f"\n  Season: {args.season}")
    print(f"  Phases: {', '.join(phases)}")

    if args.create_tables:
        import subprocess
        print("\n  Running Alembic migrations...")
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=Path(__file__).parent.parent,
            check=True,
        )

    db = SessionLocal()
    client = httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True)

    try:
        nba_id_lookup = build_nba_id_lookup(db)
        print(f"  Player lookup: {len(nba_id_lookup)} players\n")

        # Phase 1: current_comp
        if "current_comp" in phases:
            print("-" * 60)
            print("Phase 1: Current Multi-Metric Comparison")
            print("-" * 60)
            data = fetch_json(client, "/load/current_comp")
            print(f"  Fetched {len(data)} players")

            result = store_current_comp(db, data, args.season, nba_id_lookup, args.verbose)
            db.commit()

            print(f"  RAPM windows stored: {result['rapm_windows']}")
            print(f"  Positions filled: {result['positions_updated']}")
            print(f"  RAPM (timedecay) filled: {result['rapm_filled']}")
            print(f"  LEBRON filled: {result['lebron_filled']}")
            print(f"  LAKER updated: {result['laker_updated']}")
            print(f"  Skipped (not in DB): {result['skipped']}")

            time.sleep(1)

        # Phase 2: Big Board
        if "big_board" in phases:
            print("\n" + "-" * 60)
            print("Phase 2: Big Board (Player Stats Export)")
            print("-" * 60)
            data = fetch_json(client, "/load/player_stats_export")
            print(f"  Fetched {len(data)} players ({len(data[0]) if data else 0} fields)")

            result = store_big_board(db, data, args.season, nba_id_lookup, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")
            print(f"  Skipped: {result['skipped']}")

            time.sleep(1)

        # Phase 3: Six Factor RAPM
        if "six_factor" in phases:
            print("\n" + "-" * 60)
            print("Phase 3: Six Factor RAPM Decomposition")
            print("-" * 60)
            data = fetch_json(client, "/load/SCALEDOUTPUT_SMALLER")
            print(f"  Fetched {len(data)} records ({len(data[0]) if data else 0} fields)")

            result = store_six_factor(db, data, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")

        # Phase 4: Peak RAPM
        if "peak" in phases:
            print("\n" + "-" * 60)
            print("Phase 4: Peak RAPM Leaderboard")
            print("-" * 60)
            data = fetch_json(client, "/api/peakleaderboard")
            print(f"  Fetched {len(data)} records")

            result = store_peak_rapm(db, data, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")
            time.sleep(1)

        # Phase 5: RAPTOR history
        if "raptor" in phases:
            print("\n" + "-" * 60)
            print("Phase 5: RAPTOR History (1977-present)")
            print("-" * 60)
            data = fetch_json(client, "/load/raptor")
            print(f"  Fetched {len(data)} records")

            result = store_raptor(db, data, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")
            time.sleep(1)

        # Phase 6: MAMBA history
        if "mamba" in phases:
            print("\n" + "-" * 60)
            print("Phase 6: MAMBA History")
            print("-" * 60)
            data = fetch_json(client, "/load/mamba")
            print(f"  Fetched {len(data)} records")

            result = store_mamba(db, data, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")

            # Backfill player_all_in_one_metrics.mamba from current season
            season_year = int(args.season.split("-")[0]) + 1  # "2024-25" -> 2025
            mamba_current = [r for r in data if r.get("year") == season_year]
            mamba_filled = 0
            for row in mamba_current:
                nba_id = row.get("nba_id")
                if not nba_id:
                    continue
                player_id = nba_id_lookup.get(int(nba_id))
                if not player_id:
                    continue
                metrics = (
                    db.query(PlayerAllInOneMetrics)
                    .filter(
                        PlayerAllInOneMetrics.player_id == player_id,
                        PlayerAllInOneMetrics.season == args.season,
                    )
                    .first()
                )
                if metrics:
                    metrics.mamba = safe_decimal(row.get("MAMBA"))
                    metrics.mamba_offense = safe_decimal(row.get("O-MAMBA"))
                    metrics.mamba_defense = safe_decimal(row.get("D-MAMBA"))
                    mamba_filled += 1
            db.commit()
            print(f"  MAMBA backfilled to all_in_one_metrics: {mamba_filled}")

            time.sleep(1)

        # Phase 7: DARKO history
        if "darko_history" in phases:
            print("\n" + "-" * 60)
            print("Phase 7: DARKO DPM History (1997-present)")
            print("-" * 60)
            data = fetch_json(client, "/load/DARKO")
            print(f"  Fetched {len(data)} records")

            result = store_darko_history(db, data, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")
            time.sleep(1)

        # Phase 8: Forced Turnovers
        if "ftov" in phases:
            print("\n" + "-" * 60)
            print("Phase 7: Forced Turnovers (rFTOV)")
            print("-" * 60)
            data = fetch_json(client, "/load/rFTOV")
            print(f"  Fetched {len(data)} records")

            result = store_ftov(db, data, args.verbose)
            db.commit()

            print(f"  Stored: {result['stored']}")

        print("\n" + "=" * 60)
        print("  nbarapm.com data fetch completed successfully!")
        print("=" * 60 + "\n")
        return 0

    except httpx.HTTPError as e:
        logger.error("HTTP error: %s", e)
        print(f"\n  [ERROR] HTTP error: {e}")
        return 1
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"\n  [ERROR] {e}")
        return 1
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    sys.exit(main())
