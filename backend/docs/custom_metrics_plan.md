Now I have a thorough understanding of all your data models, existing services, and available fields. Let me now provide the comprehensive computation plans.

---

# CORTEX Custom Metrics: Detailed Computation Plans

## 1. RAPM Self-Computation

### Methodology

RAPM (Regularized Adjusted Plus-Minus) is a ridge regression model that estimates each player's per-100-possession contribution to team point differential, controlling for all other players on the court simultaneously. It was pioneered by Joe Sill, Jeremias Engelmann, and others in the APM literature. The key insight versus raw plus-minus: raw +/- conflates the player's impact with their teammates/opponents. RAPM disentangles these by solving a regression across all stints in a season.

### Step 1: Extract Stint Data from pbpstats

Your `PBPStatsService.get_game_possessions()` already fetches possession-level data. You need to aggregate this into **stints** -- continuous periods where the same 10 players are on the floor.

```
For each game:
  possessions = pbp_service.get_game_possessions(game_id)
  
  For each possession:
    - Extract offense_team_id, defense_team_id
    - Extract the 5 offensive player IDs (possession.offense_players)
    - Extract the 5 defensive player IDs (possession.defense_players)
    - Extract points scored on this possession
    
  Group consecutive possessions with identical 10-player sets into stints.
  
  For each stint, record:
    - offense_player_ids: list[int]  (5 players)
    - defense_player_ids: list[int]  (5 players)
    - offensive_possessions: int
    - defensive_possessions: int (same stint from the other team's perspective)
    - points_scored_offense: int
    - points_scored_defense: int
```

From `pbpstats`, the `Game.possessions.items` list contains possession objects. Each possession object has attributes like `offense_team_id`, `player_game_stats` and lineup info. Specifically, use `possession.offense_lineup_ids` and `possession.defense_lineup_ids` to get the 5-player sets.

The stint aggregation produces rows of the form:

```
stint_i = {
    "off_players": [p1, p2, p3, p4, p5],
    "def_players": [p6, p7, p8, p9, p10],
    "possessions": N,
    "points_for": X,     # points scored by offense in this stint
    "points_against": Y  # points scored by defense in this stint
}
```

### Step 2: Build the Sparse Matrix

Let `P` = total unique players in the season (approximately 500-550). Let `S` = total stints (typically 30,000-60,000 for a full season).

Build matrix `X` of shape `(S, P)`:
- For stint `i`, for each of the 5 offensive players, set `X[i, player_index] = +1`
- For stint `i`, for each of the 5 defensive players, set `X[i, player_index] = -1`
- All other entries are 0

Build target vector `y` of shape `(S,)`:
- `y[i] = (points_for_i / possessions_i) * 100 - (points_against_i / possessions_i) * 100`
- This is the per-100-possession net rating for the stint

Build weight vector `w` of shape `(S,)`:
- `w[i] = possessions_i` (possessions in that stint)
- This ensures longer stints contribute more to the regression

Use `scipy.sparse.csr_matrix` for `X` since it is extremely sparse (only 10 non-zero entries per row out of ~500 columns).

### Step 3: Ridge Regression

```python
from sklearn.linear_model import Ridge

# Alpha selection: the regularization parameter
# Literature standard: alpha in range [2000, 5000] for full-season data
# Sill (2010) used ~2500; Engelmann used ~5000
# Higher alpha = more shrinkage toward zero = more stable but less responsive

# For a full 82-game season (~50,000 stints):
alpha = 2500

model = Ridge(alpha=alpha, fit_intercept=True)
model.fit(X, y, sample_weight=w)

# Each coefficient is the player's RAPM
player_rapm = dict(zip(player_ids, model.coef_))
intercept = model.intercept_  # Should be ~0 (league average)
```

**Cross-validation for alpha selection:**
```python
from sklearn.linear_model import RidgeCV

alphas = [1000, 1500, 2000, 2500, 3000, 4000, 5000]
model = RidgeCV(alphas=alphas, cv=5, scoring='neg_mean_squared_error')
model.fit(X, y, sample_weight=w)
best_alpha = model.alpha_
```

### Step 4: Splitting into O-RAPM and D-RAPM

Run two separate regressions:

**O-RAPM (Offensive RAPM):**
- Target: `y_off[i] = (points_for_i / possessions_i) * 100`
- Same X matrix, same weights
- This tells you each player's offensive contribution per 100 possessions

**D-RAPM (Defensive RAPM):**
- Target: `y_def[i] = -(points_against_i / possessions_i) * 100`
- Note the negation: lower points allowed = better defense = positive D-RAPM
- Same X matrix, same weights

```python
# Offensive RAPM
model_off = Ridge(alpha=alpha)
model_off.fit(X, y_off, sample_weight=w)
o_rapm = dict(zip(player_ids, model_off.coef_))

# Defensive RAPM
model_def = Ridge(alpha=alpha)
model_def.fit(X, y_def, sample_weight=w)
d_rapm = dict(zip(player_ids, model_def.coef_))

# Verify: RAPM ~= O-RAPM + D-RAPM (will be close but not exact due to separate intercepts)
```

### Step 5: Possession Minimum for Stability

- **Minimum threshold**: 500 possessions (~6 games as a starter). Below this, RAPM is dominated by regularization and essentially returns ~0.
- **Moderate confidence**: 1,500+ possessions (roughly 20+ games as a starter).
- **High confidence**: 3,000+ possessions (roughly 40+ games as a starter, ~half season).
- **Full confidence**: 5,000+ possessions (full season starter).

Store a `rapm_confidence` field alongside the value. Compute it as:
```python
confidence = min(1.0, possessions / 5000)
```

Players below 500 possessions should have their RAPM flagged as unreliable or excluded.

### Step 6: Runtime and Performance Considerations

- **Data volume**: A full NBA season has ~1,230 games. At ~200 possessions per game, that is ~246,000 possessions, which aggregate into ~30,000-60,000 stints.
- **Matrix size**: ~50,000 rows x 500 columns, sparse. The ridge regression solves `(X'WX + alpha*I)^-1 X'Wy`, which for a 500x500 system is trivial (< 1 second).
- **Bottleneck**: Data fetching. Fetching 1,230 games from pbpstats is the slow part. At 1 request/second with caching, initial fetch takes ~20-25 minutes. Once cached in Redis, recomputation is fast.
- **Memory**: The sparse matrix at 50K x 500 with 10 non-zeros per row uses ~4MB. Negligible.
- **Recommendation**: Run RAPM computation as a Celery task (`app/tasks/metrics.py`). Pre-cache all game possessions, then build and solve the regression in a single batch.

### Data Fields Used

| Source Table/Service | Fields |
|---|---|
| `PBPStatsService.get_game_possessions()` | offense_lineup_ids, defense_lineup_ids, points scored per possession |
| `PBPStatsService.get_season_totals()` | game_ids for the season |
| `PlayerAllInOneMetrics` | `rapm`, `rapm_offense`, `rapm_defense` (output destination) |

---

## 2. Contextualized Net Rating (Enhanced)

Your existing `ImpactCalculator` has teammate adjustment, a rough opponent quality estimate, and a reliability factor. Here is the full 5-adjustment pipeline.

### Adjustment 1: Teammate Quality Adjustment (Enhanced)

**Problem with current approach**: Your current implementation uses on-court net rating of teammates, which is circular -- a great player inflates their teammates' on-court ratings.

**Proper approach**: Use an **independent** measure of teammate quality that does not include the player being evaluated.

```python
def calculate_teammate_quality(player_id: int, lineup_data: list[LineupData], 
                                player_impact: dict[int, float]) -> float:
    """
    Args:
        player_id: Player being evaluated
        lineup_data: All 5-man lineup data
        player_impact: Independent impact metric for all players (use EPM or BPM)
                       from PlayerAllInOneMetrics or PlayerComputedAdvanced
    
    Returns:
        Minutes-weighted average teammate impact, excluding the target player
    """
    total_weighted_impact = 0.0
    total_minutes = 0.0
    
    for lineup in lineup_data:
        if player_id not in lineup.player_ids:
            continue
        
        teammates = [pid for pid in lineup.player_ids if pid != player_id]
        lineup_teammate_impact = sum(
            player_impact.get(tid, 0.0) for tid in teammates
        ) / 4.0  # Average of 4 teammates
        
        total_weighted_impact += lineup_teammate_impact * float(lineup.minutes)
        total_minutes += float(lineup.minutes)
    
    if total_minutes == 0:
        return 0.0
    
    return total_weighted_impact / total_minutes
```

**Formula:**
```
teammate_adj = avg_teammate_independent_impact - league_avg_independent_impact
adjusted_net = raw_net_rating_diff - (teammate_adj * TEAMMATE_BLEED_FACTOR)
```

Where `TEAMMATE_BLEED_FACTOR = 0.5` (research by Thinking Basketball and others suggests teammates account for roughly 50% of on/off noise).

**Data fields**: `LineupData.player_ids`, `LineupData.minutes`, `PlayerAllInOneMetrics.epm` (or `.bpm` from `PlayerComputedAdvanced`), `PlayerOnOffStats.net_rating_diff`

### Adjustment 2: Opponent Starter Adjustment

Now that you have `PlayerMatchups` data, replace the rough estimation with actual matchup-based opponent quality measurement.

```python
def calculate_opponent_quality(player_id: int, season: str, 
                                matchups: list[PlayerMatchups],
                                opponent_impact: dict[int, float]) -> tuple[float, float]:
    """
    Returns:
        (weighted_avg_opponent_impact, opponent_quality_factor)
    """
    total_weighted = 0.0
    total_poss = 0.0
    
    for matchup in matchups:
        if matchup.player_id != player_id or matchup.season != season:
            continue
        
        opp_impact = opponent_impact.get(matchup.off_player_nba_id, 0.0)
        poss = float(matchup.partial_poss or 0)
        
        total_weighted += opp_impact * poss
        total_poss += poss
    
    if total_poss == 0:
        return 0.0, 1.0
    
    avg_opponent = total_weighted / total_poss
    
    # Scale: if avg opponent is above average (positive EPM), quality factor > 1
    # If below average, quality factor < 1
    # Center at 1.0, scale by +/- 0.1 per point of opponent EPM
    opponent_quality_factor = 1.0 + (avg_opponent * 0.1)
    opponent_quality_factor = max(0.7, min(1.3, opponent_quality_factor))
    
    return avg_opponent, opponent_quality_factor
```

**Data fields**: `PlayerMatchups.off_player_nba_id`, `PlayerMatchups.partial_poss`, `PlayerAllInOneMetrics.epm` for each opponent

### Adjustment 3: Garbage Time Filter

**Definition of garbage time** (based on NBA analytics consensus and what Cleaning the Glass uses):

| Time Remaining | Score Margin for Garbage Time |
|---|---|
| Q4, 0:00-2:00 | >= 15 points |
| Q4, 2:00-5:00 | >= 20 points |
| Q4, 5:00-8:00 | >= 25 points |
| Q4, 8:00-12:00 | >= 30 points |
| Q3, any | >= 35 points |
| OT, any | Never garbage time |

**Implementation**: This requires play-by-play data. You cannot compute this from your current aggregated tables alone. You need to process `pbpstats` possession data.

```python
def is_garbage_time(period: int, time_remaining_seconds: float, 
                    score_margin: int) -> bool:
    abs_margin = abs(score_margin)
    
    if period >= 5:  # Overtime
        return False
    
    if period <= 2:  # First half
        return abs_margin >= 40  # Extremely rare but possible
    
    if period == 3:
        return abs_margin >= 35
    
    # period == 4
    minutes_remaining = time_remaining_seconds / 60
    if minutes_remaining <= 2:
        return abs_margin >= 15
    elif minutes_remaining <= 5:
        return abs_margin >= 20
    elif minutes_remaining <= 8:
        return abs_margin >= 25
    else:
        return abs_margin >= 30

def compute_non_garbage_time_net_rating(player_id: int, 
                                         possession_data: dict) -> float:
    """
    Filter possessions to non-garbage time, then compute:
    net_rating = (pts_scored / off_poss * 100) - (pts_allowed / def_poss * 100)
    """
    player_off_poss = 0
    player_off_pts = 0
    player_def_poss = 0
    player_def_pts = 0
    
    for game_id, possessions in possession_data.items():
        for poss in possessions:
            if is_garbage_time(poss.period, poss.time_remaining, poss.score_margin):
                continue
            
            if player_id in poss.offense_lineup_ids:
                player_off_poss += 1
                player_off_pts += poss.points_scored
            
            if player_id in poss.defense_lineup_ids:
                player_def_poss += 1
                player_def_pts += poss.points_scored
    
    if player_off_poss == 0 or player_def_poss == 0:
        return 0.0
    
    ortg = (player_off_pts / player_off_poss) * 100
    drtg = (player_def_pts / player_def_poss) * 100
    return ortg - drtg
```

**Data fields**: `PBPStatsService.get_game_possessions()` -- possession-level period, time remaining, score margin, lineup IDs, points scored

**Shortcut if no PBP**: You can approximate the garbage time adjustment. NBA teams play roughly 5-8% of their minutes in garbage time. Star players play almost none. A simple proxy:

```python
# If player's minutes per game is within 5 of team leader, 
# garbage_time_fraction ~= 0.02
# If minutes per game is bottom 3 on team, 
# garbage_time_fraction ~= 0.08-0.15

garbage_time_adjustment = raw_net_rating * garbage_time_fraction * DIRECTION
# DIRECTION: +1 if team is winning in garbage time (inflated stats), 
#            -1 if losing
```

### Adjustment 4: Score Leverage Adjustment

This weights possessions by how much they "matter" -- close games matter more than blowouts, late-game possessions matter more than early ones.

**Leverage formula** (adapted from baseball's Leverage Index concept):

```python
def possession_leverage(period: int, time_remaining_seconds: float, 
                        score_margin: int) -> float:
    """
    Returns a leverage multiplier between 0.3 (low leverage) and 2.5 (high leverage).
    Average across a season should be ~1.0.
    """
    abs_margin = abs(score_margin)
    total_seconds_remaining = time_remaining_seconds + max(0, (4 - period)) * 720
    
    # Time factor: later in game = higher leverage
    # Max 2880 seconds in regulation
    time_factor = 1.0 + (1.0 - total_seconds_remaining / 2880) * 0.5
    # Ranges from 1.0 (start of game) to 1.5 (end of game)
    
    # Score margin factor: closer game = higher leverage
    if abs_margin <= 3:
        margin_factor = 2.0
    elif abs_margin <= 6:
        margin_factor = 1.5
    elif abs_margin <= 10:
        margin_factor = 1.2
    elif abs_margin <= 15:
        margin_factor = 0.9
    elif abs_margin <= 20:
        margin_factor = 0.6
    else:
        margin_factor = 0.3
    
    # Overtime gets a boost
    if period >= 5:
        margin_factor *= 1.3
    
    leverage = time_factor * margin_factor
    return max(0.3, min(2.5, leverage))
```

**Application**: When computing per-possession net rating, weight each possession by its leverage:

```python
leverage_weighted_net_rating = sum(poss_net * leverage(poss)) / sum(leverage(poss))
# vs unweighted: sum(poss_net) / count(poss)
```

**Data fields**: Same PBP data as garbage time -- period, time remaining, score margin per possession.

### Adjustment 5: Pace and Possession Adjustment

Normalize all ratings to league-average pace so that players on fast-paced teams are not unfairly penalized/boosted.

```python
def pace_adjust(player_net_rating: float, player_pace: float, 
                league_avg_pace: float) -> float:
    """
    Normalize net rating to league average pace.
    
    A player on a team with pace=105 (vs league avg 100) has their 
    per-possession impact spread across more possessions, making their 
    per-possession value slightly lower than raw net rating suggests.
    """
    pace_factor = league_avg_pace / player_pace
    return player_net_rating * pace_factor
```

**Data fields**: `PlayerAdvancedStats.pace`, league average pace (compute from all players' pace values or from team stats)

### Final Composite Formula

```python
def contextualized_net_rating(
    raw_net_diff: float,           # PlayerOnOffStats.net_rating_diff
    teammate_adj: float,           # from Adjustment 1
    opponent_quality_factor: float, # from Adjustment 2
    garbage_time_adj: float,       # from Adjustment 3 (additive correction)
    leverage_ratio: float,         # from Adjustment 4 (leverage-weighted / unweighted)
    pace_factor: float,            # from Adjustment 5
    reliability: float,            # sqrt(min/1000) capped at 1.0
) -> float:
    
    # Step 1: Remove teammate inflation
    teammate_corrected = raw_net_diff - (teammate_adj * 0.5)
    
    # Step 2: Apply opponent quality scaling
    opponent_adjusted = teammate_corrected * opponent_quality_factor
    
    # Step 3: Remove garbage time inflation
    quality_adjusted = opponent_adjusted + garbage_time_adj
    
    # Step 4: Apply leverage weighting ratio
    # leverage_ratio = leverage_weighted_net / unweighted_net
    # If > 1, player performed better in high-leverage situations
    leverage_adjusted = quality_adjusted * leverage_ratio
    
    # Step 5: Pace normalize
    pace_normalized = leverage_adjusted * pace_factor
    
    # Step 6: Reliability dampen
    final = pace_normalized * reliability
    
    return round(final, 2)
```

**Scoring scale**: The output is on the same scale as net rating (points per 100 possessions). Typical range: -8 to +8 for most players, with elite players reaching +6 to +10 and negative players at -4 to -8. Store in `ContextualizedImpact` table.

---

## 3. Portability Index (0-100 Composite)

### 3a. Self-Creation Score (0-100)

**What it measures**: How well a player can generate offense independently -- without needing designed plays, specific teammates, or favorable scheme.

**Sub-components:**

**i. Unassisted FG Rate (25% of Self-Creation Score)**

This comes from the efficiency tracking data (assisted vs unassisted FG breakdown). You need a `pct_unassisted` field. If you do not have this directly, compute from shooting tracking:

```python
# Proxy: Pull-up shooting is unassisted by definition
# Drives that end in FGA are largely unassisted
# Isolation FGA is unassisted
# PnR Ball Handler is partially self-created

unassisted_fga = (
    float(shooting_tracking.pullup_fga or 0) * games_played +  # per game -> total
    float(play_types.isolation_fga or 0) +                      # season total
    float(shooting_tracking.drive_fga or 0) * games_played      # per game -> total
)

total_fga = float(season_stats.total_fga or 0)

pct_unassisted = unassisted_fga / total_fga if total_fga > 0 else 0

# Score mapping (percentile-based):
# League average pct_unassisted ~= 0.35
# Elite self-creators (Luka, SGA): 0.55-0.65
# Pure catch-and-shoot: 0.10-0.20

unassisted_score = percentile_rank(pct_unassisted, all_players_pct_unassisted) 
# Result: 0-100
```

**ii. Self-Created PPP (25% of Self-Creation Score)**

```python
self_created_poss = (
    (play_types.isolation_poss or 0) + 
    (play_types.pnr_ball_handler_poss or 0)
)
self_created_pts = (
    (play_types.isolation_pts or 0) + 
    (play_types.pnr_ball_handler_pts or 0)
)

self_created_ppp = self_created_pts / self_created_poss if self_created_poss > 0 else 0

# Minimum 50 self-created possessions for reliability
# League average self-created PPP ~= 0.85-0.90
# Elite: 1.00+
# Poor: < 0.75

self_created_ppp_score = percentile_rank(self_created_ppp, all_players_self_ppp)
# Apply minimum volume filter: if self_created_poss < 50, cap score at 40
```

**iii. Gravity Proxy (25% of Self-Creation Score)**

Gravity measures how much defensive attention a player draws. Without optical tracking data, approximate it:

```python
def compute_gravity_proxy(player, team_stats, on_off, play_types, shooting):
    """
    Gravity proxy based on:
    1. Team 3PT% when player is ON vs OFF court
    2. Teammate open 3PT rate (from play type data)
    3. Shot creation for teammates (AST rate + screen assists)
    4. Pull-up 3PT volume (draws closeouts)
    """
    
    # Component 1: Team shooting lift when ON court
    # Use on/off offensive rating differential as proxy
    off_rating_lift = float(on_off.off_rating_diff or 0)
    # Normalize: league avg diff ~= 0, range typically -5 to +5
    lift_score = normalize_to_0_100(off_rating_lift, min_val=-5, max_val=5)
    
    # Component 2: Shot creation volume
    # AST_PCT from advanced stats + screen_assists from hustle
    ast_pct = float(player.advanced_stats.ast_pct or 0)
    screen_ast_per_75 = float(player.per_75.screen_assists_per_75 or 0)
    creation_score = (
        percentile_rank(ast_pct, all_ast_pcts) * 0.6 + 
        percentile_rank(screen_ast_per_75, all_screen_ast) * 0.4
    )
    
    # Component 3: Pull-up 3PT volume (threat draws defense out)
    pullup_3pa = float(shooting.pullup_fg3a or 0)  # per game
    pullup_3_score = percentile_rank(pullup_3pa, all_pullup_3pa)
    
    # Component 4: Touch-to-points efficiency (drawing defensive focus)
    ppt = float(player.season_stats.avg_points_per_touch or 0)
    ppt_score = percentile_rank(ppt, all_ppt)
    
    gravity = (
        lift_score * 0.30 +
        creation_score * 0.30 +
        pullup_3_score * 0.20 +
        ppt_score * 0.20
    )
    
    return gravity
```

**iv. Self-Creation Volume (25% of Self-Creation Score)**

```python
# What fraction of total possessions are self-created?
self_creation_freq = (
    float(play_types.isolation_freq or 0) + 
    float(play_types.pnr_ball_handler_freq or 0)
)

# League average ~= 0.25-0.30
# Elite ball-dominant guards: 0.45-0.55
# Off-ball players: 0.05-0.15

volume_score = percentile_rank(self_creation_freq, all_players_creation_freq)
```

**Final Self-Creation Score:**
```python
self_creation_score = (
    unassisted_score * 0.25 +
    self_created_ppp_score * 0.25 +
    gravity_proxy * 0.25 +
    volume_score * 0.25
)
# Result: 0-100
```

**Data fields**: `PlayerShootingTracking` (pullup_fga, pullup_fg3a, drive_fga), `SeasonPlayTypeStats` (isolation_*, pnr_ball_handler_*), `SeasonStats` (total_fga), `PlayerAdvancedStats` (ast_pct), `PlayerOnOffStats` (off_rating_diff), `Per75Stats` (screen_assists_per_75), `SeasonStats` (avg_points_per_touch)

### 3b. Scheme Flexibility Score (0-100)

For each of 5 offensive archetypes, score how well the player fits (0-100), then compute the **average of the top 3 fits** as the flexibility score. A truly portable player fits multiple schemes.

**Archetype 1: Motion/Read Offense** (e.g., Warriors, Spurs 2014)
Requires: cutting, off-ball movement, passing, spot-up shooting, low usage.

```python
motion_fit = (
    0.25 * percentile(cut_ppp_percentile) +
    0.20 * percentile(off_screen_ppp_percentile) +
    0.20 * percentile(spot_up_ppp_percentile) +
    0.15 * percentile(ast_ratio) +
    0.10 * percentile(screen_assists_per_75) +
    0.10 * low_usage_bonus
)

# low_usage_bonus: 100 if USG% < 20%, scale down to 0 at USG% > 30%
low_usage_bonus = max(0, min(100, (30 - usg_pct) / 10 * 100))
```

**Archetype 2: PnR Heavy Offense** (e.g., Mavericks, Hawks)
Requires: PnR ball handling OR roll man efficiency, drives, FT drawing.

```python
# For ball handlers:
pnr_handler_fit = (
    0.35 * percentile(pnr_ball_handler_ppp_percentile) +
    0.20 * percentile(drive_pts_per_game) +
    0.15 * percentile(ast_pct) +
    0.15 * percentile(fta_per_75) +
    0.15 * percentile(pullup_efg_pct)
)

# For roll men/bigs:
pnr_roller_fit = (
    0.35 * percentile(pnr_roll_man_ppp_percentile) +
    0.25 * percentile(cut_ppp_percentile) +
    0.20 * percentile(rim_fg_pct) +  # from shot zones, Restricted Area
    0.20 * percentile(screen_assists_per_75)
)

# Use the higher of handler or roller fit
pnr_fit = max(pnr_handler_fit, pnr_roller_fit)
```

**Archetype 3: Iso-Heavy Offense** (e.g., Nets 2021, Thunder)
Requires: isolation efficiency, self-creation, high-volume scoring.

```python
iso_fit = (
    0.30 * percentile(isolation_ppp_percentile) +
    0.25 * percentile(pullup_efg_pct) +
    0.20 * percentile(usg_pct) +
    0.15 * percentile(ts_pct) +
    0.10 * percentile(drives_per_game)
)
```

**Archetype 4: Egalitarian/Balanced** (e.g., Nuggets, Celtics)
Requires: versatility across play types, high efficiency, good passing.

```python
# Count play types where player has >= 50th percentile PPP
versatility_count = sum(1 for pt in [
    isolation_ppp_percentile, pnr_ball_handler_ppp_percentile,
    spot_up_ppp_percentile, transition_ppp_percentile,
    cut_ppp_percentile, off_screen_ppp_percentile
] if pt >= 50)

versatility_bonus = (versatility_count / 6) * 100

egalitarian_fit = (
    0.30 * versatility_bonus +
    0.20 * percentile(ts_pct) +
    0.20 * percentile(ast_to_ratio) +
    0.15 * percentile(spot_up_ppp_percentile) +
    0.15 * low_tov_bonus
)

# low_tov_bonus: 100 if TOV% < 10%, 0 if > 20%
low_tov_bonus = max(0, min(100, (20 - tov_pct) / 10 * 100))
```

**Archetype 5: Post-Up / Inside-Out Offense** (e.g., Embiid Sixers, Jokic Nuggets)
Requires: post-up efficiency, mid-range, passing out of the post.

```python
post_fit = (
    0.35 * percentile(post_up_ppp_percentile) +
    0.20 * percentile(paint_touch_scoring) +  # proxy: restricted area FG%
    0.20 * percentile(ast_ratio) +  # passing out of post
    0.15 * percentile(oreb_pct) +
    0.10 * percentile(ft_rate)  # FTA/FGA
)
```

**Final Scheme Flexibility Score:**
```python
fits = sorted([motion_fit, pnr_fit, iso_fit, egalitarian_fit, post_fit], reverse=True)
scheme_flexibility = sum(fits[:3]) / 3  # Average of top 3
# Result: 0-100
```

**Rationale**: A player who scores 90 in one scheme but 20 in the other four is scheme-dependent (not portable). A player who scores 70-80 in three or more schemes is genuinely flexible.

**Data fields**: All `SeasonPlayTypeStats` fields (PPP percentiles, frequencies), `PlayerAdvancedStats` (ast_pct, ast_to, usg_pct, ts_pct, oreb_pct), `PlayerShootingTracking` (pullup_efg_pct, drives), `Per75Stats` (screen_assists_per_75, fta_per_75), `PlayerShotZones` (Restricted Area fg_pct)

### 3c. Defensive Switchability Score (0-100)

**Methodology**: Use `PlayerMatchups` data to determine which positions a player guards and how effectively.

```python
def compute_switchability(player_id: int, matchups: list[PlayerMatchups],
                          all_players: dict[int, Player]) -> float:
    """
    Steps:
    1. Group matchups by opponent position
    2. For each position, compute the player's matchup FG% vs league-avg FG%
    3. Score each position as effective/neutral/liability
    4. Composite: how many positions can they guard effectively?
    """
    
    position_groups = {
        'G': [],   # Guards (PG, SG)
        'W': [],   # Wings (SF, SG/SF)
        'F': [],   # Forwards (PF, SF/PF)
        'C': [],   # Centers (C)
    }
    
    for matchup in matchups:
        if matchup.player_id != player_id:
            continue
        if (matchup.partial_poss or 0) < 10:  # Minimum 10 possessions
            continue
        
        opp_position = get_player_position(matchup.off_player_nba_id, all_players)
        position_bucket = map_position_to_bucket(opp_position)
        position_groups[position_bucket].append(matchup)
    
    position_scores = {}
    
    for pos, pos_matchups in position_groups.items():
        if not pos_matchups:
            position_scores[pos] = None  # No data
            continue
        
        total_fga = sum(float(m.matchup_fga or 0) for m in pos_matchups)
        total_fgm = sum(float(m.matchup_fgm or 0) for m in pos_matchups)
        
        if total_fga < 20:  # Need minimum sample
            position_scores[pos] = None
            continue
        
        matchup_fg_pct = total_fgm / total_fga
        
        # Compare to league average FG% for that position
        # League avg FG% by position bucket:
        #   G: ~0.445, W: ~0.460, F: ~0.480, C: ~0.530
        league_avg = POSITION_LEAGUE_AVG_FG[pos]
        
        # Differential: negative is good (holding opponents below average)
        diff = matchup_fg_pct - league_avg
        
        # Score: center at 50, +/- based on differential
        # Each 1% below league avg = +5 points, each 1% above = -5 points
        pos_score = max(0, min(100, 50 - (diff * 500)))
        position_scores[pos] = pos_score
    
    # Switchability = how many positions they can guard at 50+ score
    valid_scores = [v for v in position_scores.values() if v is not None]
    
    if not valid_scores:
        return 50.0  # Default to average
    
    # Weight: average of all position scores, with bonus for breadth
    avg_score = sum(valid_scores) / len(valid_scores)
    
    positions_above_50 = sum(1 for s in valid_scores if s >= 50)
    breadth_bonus = (positions_above_50 / 4) * 20  # Max 20 point bonus for guarding all 4
    
    switchability = min(100, avg_score + breadth_bonus)
    return switchability
```

**Thresholds:**
- Matchup DFG% at or below league average for that position = "Effective" (score 50-100)
- Matchup DFG% 1-3% above league average = "Neutral" (score 35-50)
- Matchup DFG% 3%+ above league average = "Liability" (score 0-35)

**Data fields**: `PlayerMatchups` (matchup_fga, matchup_fgm, matchup_fg_pct, off_player_nba_id, partial_poss), `Player.position` for opponent position classification

### 3d. Low Dependency Score (0-100)

**What it measures**: How much does a player's performance depend on specific teammate types (spacing, rim protection)?

**i. Spacing Independence (50% of Low Dependency)**

```python
def spacing_independence(player_id: int, lineup_data: list[LineupData],
                          player_3pt_rates: dict[int, float]) -> float:
    """
    Compare player's lineup net rating when surrounded by good 3PT shooters
    vs poor 3PT shooters.
    
    player_3pt_rates: each player's 3PT attempt rate (3PA/FGA) as spacing proxy
    """
    good_spacing_lineups = []
    poor_spacing_lineups = []
    
    GOOD_SPACING_THRESHOLD = 0.35  # Teammates avg 3PA rate >= 35%
    POOR_SPACING_THRESHOLD = 0.25  # Teammates avg 3PA rate < 25%
    
    for lineup in lineup_data:
        if player_id not in lineup.player_ids:
            continue
        if float(lineup.minutes) < 20:  # Min 20 minutes per lineup
            continue
        
        teammates = [pid for pid in lineup.player_ids if pid != player_id]
        teammate_3pt_rates = [player_3pt_rates.get(t, 0.30) for t in teammates]
        avg_teammate_3pt_rate = sum(teammate_3pt_rates) / len(teammate_3pt_rates)
        
        if avg_teammate_3pt_rate >= GOOD_SPACING_THRESHOLD:
            good_spacing_lineups.append(lineup)
        elif avg_teammate_3pt_rate < POOR_SPACING_THRESHOLD:
            poor_spacing_lineups.append(lineup)
    
    if not good_spacing_lineups or not poor_spacing_lineups:
        return 50.0  # Insufficient data, assume average
    
    good_minutes = sum(float(l.minutes) for l in good_spacing_lineups)
    good_net = sum(float(l.net_rating) * float(l.minutes) for l in good_spacing_lineups) / good_minutes
    
    poor_minutes = sum(float(l.minutes) for l in poor_spacing_lineups)
    poor_net = sum(float(l.net_rating) * float(l.minutes) for l in poor_spacing_lineups) / poor_minutes
    
    # Performance drop from good to poor spacing
    drop = good_net - poor_net
    
    # Lower drop = more spacing independent = higher score
    # Average drop is ~3-5 points of net rating
    # Scale: 0 drop = 100, 10+ drop = 0
    independence_score = max(0, min(100, 100 - (drop * 10)))
    
    return independence_score
```

**ii. Rim Protection Independence (50% of Low Dependency)**

```python
def rim_protection_independence(player_id: int, lineup_data: list[LineupData],
                                 player_rim_prot: dict[int, float]) -> float:
    """
    Compare lineup performance with vs without a rim protector.
    
    player_rim_prot: each player's rim DFG% plus-minus (from PlayerDefensiveStats)
                     More negative = better rim protector
    """
    RIM_PROTECTOR_THRESHOLD = -0.03  # rim_pct_plusminus <= -3%
    
    with_protector = []
    without_protector = []
    
    for lineup in lineup_data:
        if player_id not in lineup.player_ids:
            continue
        if float(lineup.minutes) < 20:
            continue
        
        teammates = [pid for pid in lineup.player_ids if pid != player_id]
        has_protector = any(
            player_rim_prot.get(t, 0) <= RIM_PROTECTOR_THRESHOLD 
            for t in teammates
        )
        
        if has_protector:
            with_protector.append(lineup)
        else:
            without_protector.append(lineup)
    
    if not with_protector or not without_protector:
        return 50.0
    
    with_min = sum(float(l.minutes) for l in with_protector)
    with_net = sum(float(l.net_rating) * float(l.minutes) for l in with_protector) / with_min
    
    without_min = sum(float(l.minutes) for l in without_protector)
    without_net = sum(float(l.net_rating) * float(l.minutes) for l in without_protector) / without_min
    
    drop = with_net - without_net
    
    # Lower drop = more independent
    independence_score = max(0, min(100, 100 - (drop * 10)))
    return independence_score
```

**Final Low Dependency Score:**
```python
low_dependency = spacing_independence * 0.50 + rim_prot_independence * 0.50
```

**Data fields**: `LineupData` (player_ids, minutes, net_rating), `SeasonStats` (total_fg3a, total_fga for 3PT rate), `PlayerDefensiveStats` (rim_pct_plusminus)

### Final Portability Index

```python
portability_index = (
    self_creation_score * 0.30 +
    scheme_flexibility * 0.25 +
    defensive_switchability * 0.25 +
    low_dependency * 0.20
)
# Result: 0-100
```

**Interpretation:**
- 80-100: Elite portability (e.g., Kawhi Leonard, Jimmy Butler -- can thrive anywhere)
- 65-79: High portability (e.g., Jaylen Brown, Jalen Brunson)
- 50-64: Average portability (e.g., most solid starters)
- 35-49: Scheme-dependent (e.g., Rudy Gobert -- elite in certain contexts)
- 0-34: Highly dependent on specific teammates/scheme

---

## 4. Championship Index (0-100 Composite)

### 4a. Playoff Scoring Projection (25% weight, 0-100)

**Methodology**: In the playoffs, defenses tighten, pace slows, and star players see increased usage while role players often decline. Historical data shows consistent patterns.

**Historical regular-season-to-playoff adjustments** (based on research from Cleaning the Glass, Ben Taylor, and Seth Partnow):

```python
def project_playoff_performance(player, advanced, play_types, season_stats):
    """
    Key historical findings:
    - League-wide TS% drops ~1.5-2.0% in playoffs
    - Star players (USG% > 28%) see TS% drop ~1.0%
    - Role players (USG% < 22%) see TS% drop ~2.5-3.0%
    - 3PT% drops ~1.0% league-wide
    - Self-creators maintain efficiency better than catch-and-shoot players
    - FT rate increases ~5-10% for star players
    """
    
    usg = float(advanced.usg_pct or 0.20)
    ts = float(advanced.ts_pct or 0.55)
    
    # TS% adjustment: higher usage players drop less
    if usg >= 0.28:
        ts_drop = 0.010  # 1.0% TS drop
    elif usg >= 0.22:
        ts_drop = 0.018  # 1.8% TS drop
    else:
        ts_drop = 0.028  # 2.8% TS drop
    
    projected_ts = ts - ts_drop
    
    # Self-creation bonus: self-creators maintain better
    self_creation_freq = float(play_types.isolation_freq or 0) + float(play_types.pnr_ball_handler_freq or 0)
    if self_creation_freq > 0.40:
        projected_ts += 0.005  # Recovers 0.5% for elite self-creators
    
    # Volume projection: stars see usage increase ~2-3%
    projected_usg = usg
    if usg >= 0.25:
        projected_usg += 0.02
    
    # Projected PPG (rough): current PPG * (projected_usg / current_usg) * (projected_ts / current_ts)
    ppg = float(season_stats.total_points or 0) / max(1, season_stats.games_played or 1)
    projected_ppg = ppg * (projected_usg / usg) * (projected_ts / ts)
    
    # Score components:
    # 1. Projected TS% vs league playoff average (~0.555)
    ts_score = normalize_to_0_100(projected_ts, min_val=0.50, max_val=0.65)
    
    # 2. Projected PPG relative to playoff standards
    ppg_score = normalize_to_0_100(projected_ppg, min_val=8, max_val=32)
    
    # 3. Resilience: how much does their game depend on things that shrink in playoffs?
    # High catch-and-shoot dependency = worse; high FT rate = better
    catch_shoot_dependency = float(play_types.spot_up_freq or 0)
    ft_rate = float(season_stats.total_fta or 0) / max(1, float(season_stats.total_fga or 1))
    resilience_score = (
        (1 - catch_shoot_dependency) * 50 +  # Lower C&S dependency = better
        min(50, ft_rate * 200)                # Higher FT rate = better (max 50)
    )
    
    playoff_scoring = ts_score * 0.35 + ppg_score * 0.40 + resilience_score * 0.25
    return playoff_scoring
```

**Data fields**: `PlayerAdvancedStats` (ts_pct, usg_pct), `SeasonPlayTypeStats` (isolation_freq, pnr_ball_handler_freq, spot_up_freq), `SeasonStats` (total_points, total_fta, total_fga, games_played)

### 4b. Two-Way Impact (20% weight, 0-100)

```python
def two_way_impact(all_in_one: PlayerAllInOneMetrics) -> float:
    """
    Combine offensive and defensive all-in-one metrics.
    Use the average of available metrics, weighted by reliability.
    """
    
    # Collect available offensive metrics
    off_metrics = [
        float(m) for m in [
            all_in_one.epm_offense, all_in_one.rpm_offense,
            all_in_one.lebron_offense, all_in_one.rapm_offense,
            all_in_one.darko_offense
        ] if m is not None
    ]
    
    # Collect available defensive metrics
    def_metrics = [
        float(m) for m in [
            all_in_one.epm_defense, all_in_one.rpm_defense,
            all_in_one.lebron_defense, all_in_one.rapm_defense,
            all_in_one.darko_defense
        ] if m is not None
    ]
    
    avg_off = sum(off_metrics) / len(off_metrics) if off_metrics else 0
    avg_def = sum(def_metrics) / len(def_metrics) if def_metrics else 0
    
    # Two-way composite: total impact = off + def
    total_impact = avg_off + avg_def
    
    # Scale: all-in-one metrics are on ~per-100-possessions scale
    # Elite two-way: +8 to +12 (e.g., Jokic, Giannis)
    # Good two-way: +3 to +8
    # Average: -1 to +3
    # Below average: -5 to -1
    # Poor: < -5
    
    # Require both sides to be positive for elite scores
    # Penalty for one-dimensional players
    if avg_off > 0 and avg_def > 0:
        two_way_bonus = min(10, min(avg_off, avg_def) * 3)  # Bonus for being good on both ends
    else:
        two_way_bonus = 0
    
    adjusted_impact = total_impact + two_way_bonus
    
    score = normalize_to_0_100(adjusted_impact, min_val=-8, max_val=18)
    return score
```

**Data fields**: `PlayerAllInOneMetrics` (all offensive/defensive splits)

### 4c. Clutch & Pressure Performance (15% weight, 0-100)

```python
def clutch_performance(clutch: PlayerClutchStats, season_stats: SeasonStats,
                       advanced: PlayerAdvancedStats) -> float:
    """
    Score clutch performance from clutch stats.
    """
    if not clutch or (clutch.games_played or 0) < 10:
        return 50.0  # Insufficient data, assume average
    
    # 1. Clutch TS% (35% of clutch score)
    clutch_fga = float(clutch.fga or 0) * (clutch.games_played or 0)
    clutch_pts = float(clutch.pts or 0) * (clutch.games_played or 0)
    clutch_fta = float(clutch.fta or 0) * (clutch.games_played or 0)
    
    if clutch_fga + clutch_fta > 0:
        clutch_ts = clutch_pts / (2 * (clutch_fga + 0.44 * clutch_fta))
    else:
        clutch_ts = 0.55
    
    # Compare to league average clutch TS% (~0.530)
    clutch_ts_score = normalize_to_0_100(clutch_ts, min_val=0.40, max_val=0.65)
    
    # 2. Clutch net rating (25% of clutch score)
    clutch_net = float(clutch.net_rating or 0)
    clutch_net_score = normalize_to_0_100(clutch_net, min_val=-15, max_val=15)
    
    # 3. Clutch volume -- PPG in clutch (20% of clutch score)
    clutch_ppg = float(clutch.pts or 0)
    volume_score = normalize_to_0_100(clutch_ppg, min_val=0, max_val=6)
    
    # 4. Clutch AST/TOV (10% of clutch score)
    clutch_ast = float(clutch.ast or 0)
    clutch_tov = float(clutch.tov or 0)
    clutch_ast_tov = clutch_ast / max(0.1, clutch_tov)
    ast_tov_score = normalize_to_0_100(clutch_ast_tov, min_val=0, max_val=4)
    
    # 5. Clutch vs regular-season drop (10% of clutch score)
    regular_ts = float(advanced.ts_pct or 0.55)
    ts_diff = clutch_ts - regular_ts
    # Positive diff = player improves in clutch
    consistency_score = normalize_to_0_100(ts_diff, min_val=-0.08, max_val=0.08)
    
    final = (
        clutch_ts_score * 0.35 +
        clutch_net_score * 0.25 +
        volume_score * 0.20 +
        ast_tov_score * 0.10 +
        consistency_score * 0.10
    )
    return final
```

**Data fields**: `PlayerClutchStats` (pts, fga, fta, fg_pct, net_rating, ast, tov, games_played), `PlayerAdvancedStats` (ts_pct)

### 4d. Portability / Roster Flexibility (15% weight)

This is simply the Portability Index from section 3:
```python
portability_score = portability_index  # 0-100 from section 3
```

### 4e. Durability & Availability (10% weight, 0-100)

```python
def durability_score(season_stats: SeasonStats, career: list[PlayerCareerStats]) -> float:
    """
    Score based on games played, minutes load, and historical availability.
    """
    
    gp = season_stats.games_played or 0
    total_min = float(season_stats.total_minutes or 0)
    mpg = total_min / max(1, gp)
    
    # Maximum games available in current season (82 or however many have been played)
    # Use 82 as standard
    MAX_GAMES = 82
    
    # 1. Games played ratio (40% of durability)
    gp_ratio = gp / MAX_GAMES
    gp_score = normalize_to_0_100(gp_ratio, min_val=0.40, max_val=0.95)
    
    # 2. Minutes load sustainability (20% of durability)
    # Sweet spot: 30-36 mpg is sustainable. >38 = injury risk, <25 = limited role
    if mpg >= 30 and mpg <= 36:
        minutes_score = 90 + (mpg - 30) / 6 * 10  # 90-100 for ideal range
    elif mpg > 36:
        minutes_score = max(50, 100 - (mpg - 36) * 10)
    else:
        minutes_score = max(30, mpg / 30 * 90)
    
    # 3. Career availability trend (40% of durability)
    if len(career) >= 2:
        recent_seasons = sorted(career, key=lambda c: c.season, reverse=True)[:3]
        career_gp_ratios = [
            (c.games_played or 0) / MAX_GAMES for c in recent_seasons
        ]
        avg_career_availability = sum(career_gp_ratios) / len(career_gp_ratios)
        career_score = normalize_to_0_100(avg_career_availability, min_val=0.40, max_val=0.95)
    else:
        career_score = gp_score  # Default to current season
    
    durability = gp_score * 0.40 + minutes_score * 0.20 + career_score * 0.40
    return durability
```

**Data fields**: `SeasonStats` (games_played, total_minutes), `PlayerCareerStats` (games_played per season)

### 4f. Playoff Experience & Growth Arc (10% weight, 0-100)

```python
def experience_and_growth(career: list[PlayerCareerStats], 
                           player: Player) -> float:
    """
    Score based on career trajectory and experience.
    """
    if len(career) < 2:
        return 40.0  # Rookie or first-year, below average
    
    sorted_career = sorted(career, key=lambda c: c.season)
    
    # 1. Growth trajectory (50% of this pillar)
    # Compare last 2 seasons vs 2 seasons before that
    recent_2 = sorted_career[-2:]
    prior_2 = sorted_career[-4:-2] if len(sorted_career) >= 4 else sorted_career[:2]
    
    recent_ppg = sum(float(c.ppg or 0) for c in recent_2) / len(recent_2)
    prior_ppg = sum(float(c.ppg or 0) for c in prior_2) / len(prior_2)
    
    ppg_growth = recent_ppg - prior_ppg
    # Positive = improving, negative = declining
    # Scale: -5 ppg = 0, 0 = 50, +5 ppg = 100
    growth_score = normalize_to_0_100(ppg_growth, min_val=-5, max_val=5)
    
    # 2. Years of experience (25% of this pillar)
    years = len(career)
    # Sweet spot: 4-10 years (proven but not declining)
    if 4 <= years <= 10:
        experience_score = 80 + (min(years, 10) - 4) / 6 * 20
    elif years < 4:
        experience_score = years / 4 * 80
    else:
        experience_score = max(50, 100 - (years - 10) * 5)
    
    # 3. Peak proximity (25% of this pillar)
    # Is the player near their peak (best season)?
    peak_ppg = max(float(c.ppg or 0) for c in career)
    current_ppg = float(sorted_career[-1].ppg or 0) if sorted_career else 0
    
    if peak_ppg > 0:
        peak_ratio = current_ppg / peak_ppg
        peak_score = normalize_to_0_100(peak_ratio, min_val=0.60, max_val=1.0)
    else:
        peak_score = 50
    
    final = growth_score * 0.50 + experience_score * 0.25 + peak_score * 0.25
    return final
```

**Data fields**: `PlayerCareerStats` (ppg, games_played, season for each historical season), `Player.position`

### 4g. Supporting Cast Threshold (5% weight, 0-100)

```python
def supporting_cast_score(player_id: int, lineup_data: list[LineupData],
                           all_in_one: dict[int, PlayerAllInOneMetrics]) -> float:
    """
    Evaluate quality of current teammates using impact metrics.
    Better teammates = higher championship probability.
    """
    
    # Find the player's most common teammates (by shared minutes)
    teammate_minutes = {}
    for lineup in lineup_data:
        if player_id not in lineup.player_ids:
            continue
        for tid in lineup.player_ids:
            if tid != player_id:
                teammate_minutes[tid] = teammate_minutes.get(tid, 0) + float(lineup.minutes)
    
    # Get top 8 teammates by minutes (approximate rotation)
    top_teammates = sorted(teammate_minutes.items(), key=lambda x: x[1], reverse=True)[:8]
    
    if not top_teammates:
        return 50.0
    
    # Get impact metrics for each teammate
    teammate_impacts = []
    for tid, minutes in top_teammates:
        metrics = all_in_one.get(tid)
        if metrics:
            # Average available all-in-one metrics
            available = [float(m) for m in [metrics.epm, metrics.rpm, metrics.lebron, 
                                             metrics.darko] if m is not None]
            if available:
                teammate_impacts.append((sum(available) / len(available), minutes))
    
    if not teammate_impacts:
        return 50.0
    
    # Minutes-weighted average teammate impact
    total_weighted = sum(impact * min_val for impact, min_val in teammate_impacts)
    total_min = sum(min_val for _, min_val in teammate_impacts)
    avg_teammate_impact = total_weighted / total_min
    
    # Count teammates with positive impact (contributes to championship)
    positive_teammates = sum(1 for impact, _ in teammate_impacts if impact > 0)
    
    # Championship teams typically have 3-4 positive-impact players
    # Score based on both quality and quantity
    quality_score = normalize_to_0_100(avg_teammate_impact, min_val=-2, max_val=4)
    quantity_score = normalize_to_0_100(positive_teammates, min_val=1, max_val=5)
    
    final = quality_score * 0.60 + quantity_score * 0.40
    return final
```

**Data fields**: `LineupData` (player_ids, minutes), `PlayerAllInOneMetrics` (epm, rpm, lebron, darko for each teammate)

### Final Championship Index

```python
championship_index = (
    playoff_scoring * 0.25 +
    two_way_impact * 0.20 +
    clutch_performance * 0.15 +
    portability_score * 0.15 +
    durability * 0.10 +
    experience_growth * 0.10 +
    supporting_cast * 0.05
)
# Result: 0-100
```

**Interpretation:**
- 85-100: Legitimate MVP / championship cornerstone (Jokic, Giannis, Luka tier)
- 70-84: All-NBA caliber, can be the best player on a contender
- 55-69: All-Star caliber, strong #2 option
- 40-54: Quality starter, solid #3-4 option
- 25-39: Rotation player
- 0-24: Fringe / development player

---

## 5. Luck-Adjusted Metrics

### 5a. Expected Wins (xWins)

**Pythagorean Expectation** (Daryl Morey, Dean Oliver, John Hollinger):

```python
def pythagorean_expected_wins(points_for: float, points_against: float, 
                               games: int, exponent: float = 14.23) -> float:
    """
    Morey's NBA-specific exponent is 13.91.
    Hollinger uses 16.5.
    Oliver found ~14.
    Basketball-Reference uses 14.
    
    Best empirical fit for modern NBA: 14.23 (from Kubatko et al.)
    
    Formula: Win% = PF^exp / (PF^exp + PA^exp)
    """
    if points_for <= 0 or points_against <= 0:
        return games / 2  # Assume .500
    
    win_pct = points_for ** exponent / (points_for ** exponent + points_against ** exponent)
    return win_pct * games
```

**Player-Level xWins using On/Off Data:**

```python
def player_expected_wins(on_off: PlayerOnOffStats, season_stats: SeasonStats,
                          team_stats: dict, league_pace: float) -> float:
    """
    Isolate the player's contribution to team wins.
    
    Method: Compare team's expected win rate WITH player vs WITHOUT,
    then attribute the difference to the player proportional to minutes played.
    """
    
    # Team's overall record / point differential
    team_pts_for = team_stats['pts_for']
    team_pts_against = team_stats['pts_against']
    team_games = team_stats['games']
    team_xwins = pythagorean_expected_wins(team_pts_for, team_pts_against, team_games)
    
    # Player's on-court offensive/defensive ratings -> point differential per game
    on_ortg = float(on_off.on_court_off_rating or 0)
    on_drtg = float(on_off.on_court_def_rating or 0)
    on_court_min = float(on_off.on_court_minutes or 0)
    
    # Off-court ratings
    off_ortg = float(on_off.off_court_off_rating or 0)
    off_drtg = float(on_off.off_court_def_rating or 0)
    off_court_min = float(on_off.off_court_minutes or 0)
    
    total_team_min = on_court_min + off_court_min
    if total_team_min == 0:
        return 0
    
    pct_on = on_court_min / total_team_min
    
    # Points per game with player on vs off (at league avg pace)
    # Possessions per 48 min ~= pace
    poss_per_game = league_pace  # ~100
    
    on_pts_for_per_game = on_ortg / 100 * poss_per_game
    on_pts_against_per_game = on_drtg / 100 * poss_per_game
    
    off_pts_for_per_game = off_ortg / 100 * poss_per_game
    off_pts_against_per_game = off_drtg / 100 * poss_per_game
    
    # Team if player played 100% of minutes
    full_xwins = pythagorean_expected_wins(
        on_pts_for_per_game, on_pts_against_per_game, team_games
    )
    
    # Team if player played 0% of minutes
    zero_xwins = pythagorean_expected_wins(
        off_pts_for_per_game, off_pts_against_per_game, team_games
    )
    
    # Player's marginal contribution, scaled by actual minutes
    marginal_wins = (full_xwins - zero_xwins) * pct_on
    
    return round(marginal_wins, 1)
```

**Data fields**: `PlayerOnOffStats` (on/off court offensive/defensive ratings, minutes), `PlayerAdvancedStats` (pace), team-level stats (total points for/against, games)

### 5b. Clutch EPA (Expected Points Added)

```python
def clutch_epa(clutch: PlayerClutchStats, league_avg_clutch: dict) -> float:
    """
    EPA = Actual clutch points - Expected clutch points (at league average efficiency).
    
    league_avg_clutch contains:
        - avg_clutch_ts: league average TS% in clutch (~0.530)
        - avg_clutch_ppg: league average clutch PPG (~1.5)
    """
    if not clutch or (clutch.games_played or 0) < 10:
        return 0.0
    
    gp = clutch.games_played
    
    # Actual clutch production (total, not per game)
    actual_pts = float(clutch.pts or 0) * gp
    actual_fga = float(clutch.fga or 0) * gp
    actual_fta = float(clutch.fta or 0) * gp
    
    # True shooting attempts
    actual_tsa = actual_fga + 0.44 * actual_fta
    
    if actual_tsa == 0:
        return 0.0
    
    # Expected points: if this player shot at league average clutch TS%
    # Expected PTS = TSA * 2 * league_avg_clutch_TS
    expected_pts = actual_tsa * 2 * league_avg_clutch['avg_clutch_ts']
    
    # EPA = Actual - Expected
    epa_total = actual_pts - expected_pts
    
    # Per game normalization
    epa_per_game = epa_total / gp
    
    return round(epa_per_game, 2)
```

**League average clutch TS%**: Compute from all `PlayerClutchStats` rows:
```python
all_clutch_pts = sum(c.pts * c.games_played for c in all_clutch_stats)
all_clutch_fga = sum(c.fga * c.games_played for c in all_clutch_stats)
all_clutch_fta = sum(c.fta * c.games_played for c in all_clutch_stats)
league_avg_clutch_ts = all_clutch_pts / (2 * (all_clutch_fga + 0.44 * all_clutch_fta))
```

**Data fields**: `PlayerClutchStats` (pts, fga, fta, games_played)

### 5c. Garbage Time Points per Game

```python
def garbage_time_points_estimate(player, season_stats, on_off) -> float:
    """
    Without play-by-play tagging of individual possessions, estimate 
    garbage time production using available data.
    
    Approach: Players who play heavy minutes rarely accumulate garbage time stats.
    Players with fewer minutes may have a significant garbage time component.
    """
    
    gp = season_stats.games_played or 1
    mpg = float(season_stats.total_minutes or 0) / gp
    ppg = float(season_stats.total_points or 0) / gp
    
    # Estimate fraction of minutes in garbage time
    # Based on team's blowout tendency and player's role
    # Starters (mpg >= 30): ~2-3% garbage time minutes
    # Rotation (20-30 mpg): ~5-8% garbage time minutes
    # Bench (< 20 mpg): ~10-20% garbage time minutes
    
    if mpg >= 32:
        gt_fraction = 0.02
    elif mpg >= 28:
        gt_fraction = 0.04
    elif mpg >= 24:
        gt_fraction = 0.06
    elif mpg >= 20:
        gt_fraction = 0.10
    else:
        gt_fraction = 0.15
    
    # Garbage time scoring rate is typically higher (weaker opponents)
    # Assume 1.2x normal scoring rate in garbage time
    gt_ppg = ppg * gt_fraction * 1.2
    
    return round(gt_ppg, 2)
```

**Better approach with PBP**: If you process pbpstats data, you can tag each possession as garbage time using the `is_garbage_time()` function from section 2, sum points scored in garbage time possessions where the player is on offense, and divide by games played. This is exact rather than estimated.

**Data fields**: `SeasonStats` (total_minutes, total_points, games_played), or `PBPStatsService` for exact computation

---

## 6. Performance by Opponent Tier

### Tier Definitions

**Ranking metric**: Use the average of available all-in-one metrics (EPM preferred, fallback to BPM) as the ranking criterion. This is preferable to minutes because it measures quality rather than role.

```python
def assign_player_tiers(all_in_one: dict[int, PlayerAllInOneMetrics],
                         computed: dict[int, PlayerComputedAdvanced],
                         season_stats: dict[int, SeasonStats]) -> dict[int, str]:
    """
    Tier assignment:
    - Elite (top ~30 players, roughly rank 1-30): Best player on a playoff team
    - Quality (rank 31-100): Solid starters and 6th men
    - Role (rank 101-200): Rotation players
    - Bench (rank 201+): End of bench, two-way, etc.
    
    Minimum: 500 minutes played to be ranked
    """
    
    player_scores = []
    
    for pid, metrics in all_in_one.items():
        ss = season_stats.get(pid)
        if not ss or float(ss.total_minutes or 0) < 500:
            continue
        
        # Average available all-in-one metrics
        available = [float(m) for m in [
            metrics.epm, metrics.rpm, metrics.lebron, metrics.darko
        ] if m is not None]
        
        if not available:
            # Fallback to BPM
            comp = computed.get(pid)
            if comp and comp.bpm is not None:
                available = [float(comp.bpm)]
        
        if available:
            score = sum(available) / len(available)
            player_scores.append((pid, score))
    
    # Sort by score descending
    player_scores.sort(key=lambda x: x[1], reverse=True)
    
    tiers = {}
    for rank, (pid, score) in enumerate(player_scores, 1):
        if rank <= 30:
            tiers[pid] = 'Elite'
        elif rank <= 100:
            tiers[pid] = 'Quality'
        elif rank <= 200:
            tiers[pid] = 'Role'
        else:
            tiers[pid] = 'Bench'
    
    return tiers
```

### Computing Performance by Tier

```python
def performance_by_tier(player_id: int, matchups: list[PlayerMatchups],
                         opponent_tiers: dict[int, str]) -> dict:
    """
    Bucket the player's defensive matchup data by opponent tier,
    then compute net efficiency against each tier.
    """
    
    tier_stats = {
        'Elite': {'poss': 0, 'pts_allowed': 0, 'fgm': 0, 'fga': 0},
        'Quality': {'poss': 0, 'pts_allowed': 0, 'fgm': 0, 'fga': 0},
        'Role': {'poss': 0, 'pts_allowed': 0, 'fgm': 0, 'fga': 0},
        'Bench': {'poss': 0, 'pts_allowed': 0, 'fgm': 0, 'fga': 0},
    }
    
    for matchup in matchups:
        if matchup.player_id != player_id:
            continue
        
        opp_tier = opponent_tiers.get(matchup.off_player_nba_id, 'Bench')
        poss = float(matchup.partial_poss or 0)
        
        if poss < 5:
            continue
        
        stats = tier_stats[opp_tier]
        stats['poss'] += poss
        stats['fgm'] += float(matchup.matchup_fgm or 0)
        stats['fga'] += float(matchup.matchup_fga or 0)
        # Approximate points allowed: FGM*2 + FG3M*1 (3s get extra point) + FTM
        pts = (float(matchup.matchup_fgm or 0) * 2 + 
               float(matchup.matchup_fg3m or 0) * 1 +  # extra point for 3s
               float(matchup.matchup_ftm or 0))
        stats['pts_allowed'] += pts
    
    # Compute per-possession metrics and scores
    results = {}
    for tier, stats in tier_stats.items():
        if stats['poss'] < 20:  # Minimum possessions
            results[tier] = None
            continue
        
        dfg_pct = stats['fgm'] / stats['fga'] if stats['fga'] > 0 else 0
        ppp_allowed = stats['pts_allowed'] / stats['poss']
        
        results[tier] = {
            'possessions': stats['poss'],
            'dfg_pct': round(dfg_pct, 3),
            'ppp_allowed': round(ppp_allowed, 3),
            'poss_count': int(stats['poss']),
        }
    
    return results
```

**Weight multipliers for composite scoring:**
```python
TIER_WEIGHTS = {
    'Elite': 1.0,    # Full weight -- this is what matters most
    'Quality': 0.8,  # Strong weight
    'Role': 0.6,     # Moderate weight
    'Bench': 0.4,    # Low weight -- beating up on bad players matters less
}

def weighted_opponent_score(tier_performance: dict) -> float:
    """
    Compute a weighted composite defensive score across tiers.
    """
    total_weighted = 0
    total_weight = 0
    
    for tier, perf in tier_performance.items():
        if perf is None:
            continue
        
        weight = TIER_WEIGHTS[tier]
        # Lower PPP allowed = better
        # Invert so higher score = better defense
        # League avg PPP ~= 1.05
        tier_score = normalize_to_0_100(1.05 - perf['ppp_allowed'], 
                                         min_val=-0.20, max_val=0.20)
        
        total_weighted += tier_score * weight * perf['poss_count']
        total_weight += weight * perf['poss_count']
    
    if total_weight == 0:
        return 50.0
    
    return total_weighted / total_weight
```

**Data fields**: `PlayerMatchups` (all fields), `PlayerAllInOneMetrics` (for tier ranking), `PlayerComputedAdvanced` (bpm as fallback), `SeasonStats` (total_minutes for minimum filter)

---

## 7. Scheme Compatibility Detailed Scoring

### Archetype 1: Motion/Read Offense (0-100)

**Philosophy**: Ball movement, player movement, reads off the defense. Warriors "Motion Offense", Spurs 2014 "Beautiful Game". Values cutting, off-ball screens, spot-up shooting, passing, low ego/usage.

```python
def motion_read_fit(play_types: SeasonPlayTypeStats, advanced: PlayerAdvancedStats,
                    per75: Per75Stats, shooting: PlayerShootingTracking) -> float:
    
    # Cut efficiency -- core motion action
    cut_score = float(play_types.cut_ppp_percentile or 50)  # 0-100
    
    # Off-screen efficiency -- coming off pin-downs, flare screens
    off_screen_score = float(play_types.off_screen_ppp_percentile or 50)
    
    # Spot-up efficiency -- end product of ball movement
    spot_up_score = float(play_types.spot_up_ppp_percentile or 50)
    
    # Passing/playmaking -- making reads
    ast_ratio = float(advanced.ast_ratio or 0)
    # League avg ast_ratio ~= 12. Elite passers: 25+. Scale:
    passing_score = normalize_to_0_100(ast_ratio, min_val=5, max_val=30)
    
    # Screen assists -- physical enabler of motion
    screen_ast = float(per75.screen_assists_per_75 or 0)
    # League avg ~= 1.5. Elite screeners: 4+
    screen_score = normalize_to_0_100(screen_ast, min_val=0, max_val=5)
    
    # Low usage bonus -- motion offense distributes usage
    usg = float(advanced.usg_pct or 0.20) * 100  # Convert to percentage
    low_usage = max(0, min(100, (30 - usg) / 12 * 100))
    
    # Catch-and-shoot efficiency -- motion creates open looks
    cs_efg = float(shooting.catch_shoot_efg_pct or 0.50)
    cs_score = normalize_to_0_100(cs_efg, min_val=0.42, max_val=0.62)
    
    motion_fit = (
        cut_score * 0.20 +
        off_screen_score * 0.15 +
        spot_up_score * 0.15 +
        passing_score * 0.15 +
        screen_score * 0.10 +
        low_usage * 0.10 +
        cs_score * 0.15
    )
    
    return round(motion_fit, 1)
```

### Archetype 2: PnR Heavy Offense (0-100)

**Philosophy**: Pick-and-roll as the primary action. Mavericks (Luka), Hawks (Trae), Cavaliers (Garland). Either as the ball handler or the roll man.

```python
def pnr_heavy_fit(play_types: SeasonPlayTypeStats, advanced: PlayerAdvancedStats,
                  per75: Per75Stats, shooting: PlayerShootingTracking,
                  shot_zones: list[PlayerShotZones]) -> float:
    
    # PnR Ball Handler efficiency
    pnr_bh_score = float(play_types.pnr_ball_handler_ppp_percentile or 50)
    pnr_bh_freq = float(play_types.pnr_ball_handler_freq or 0) * 100  # as percentage
    
    # PnR Roll Man efficiency
    pnr_rm_score = float(play_types.pnr_roll_man_ppp_percentile or 50)
    pnr_rm_freq = float(play_types.pnr_roll_man_freq or 0) * 100
    
    # Determine primary role: handler or roller
    is_handler = pnr_bh_freq > pnr_rm_freq
    
    if is_handler:
        # Handler-focused scoring
        drive_score = normalize_to_0_100(
            float(shooting.drive_pts or 0), min_val=2, max_val=12
        )
        pullup_score = normalize_to_0_100(
            float(shooting.pullup_efg_pct or 0.40), min_val=0.35, max_val=0.55
        )
        ast_pct = float(advanced.ast_pct or 0) * 100
        playmaking_score = normalize_to_0_100(ast_pct, min_val=10, max_val=40)
        
        # FT drawing (PnR drives draw fouls)
        fta_per_75 = float(per75.fta_per_75 or 0)
        ft_draw_score = normalize_to_0_100(fta_per_75, min_val=1, max_val=8)
        
        pnr_fit = (
            pnr_bh_score * 0.30 +
            drive_score * 0.20 +
            pullup_score * 0.15 +
            playmaking_score * 0.20 +
            ft_draw_score * 0.15
        )
    else:
        # Roller-focused scoring
        # Restricted area FG%
        restricted_fg = 0.60  # default
        for sz in shot_zones:
            if 'restricted' in sz.zone.lower():
                restricted_fg = float(sz.fg_pct or 0.60)
                break
        rim_score = normalize_to_0_100(restricted_fg, min_val=0.55, max_val=0.75)
        
        screen_ast = float(per75.screen_assists_per_75 or 0)
        screen_score = normalize_to_0_100(screen_ast, min_val=0, max_val=5)
        
        # Catch ability (lob threat, short roll passing)
        cut_score = float(play_types.cut_ppp_percentile or 50)
        
        pnr_fit = (
            pnr_rm_score * 0.30 +
            rim_score * 0.25 +
            screen_score * 0.20 +
            cut_score * 0.25
        )
    
    return round(pnr_fit, 1)
```

### Archetype 3: Iso-Heavy Offense (0-100)

**Philosophy**: Star-driven isolation scoring. Thunder (SGA), historical KD Nets, Harden Rockets. Values self-creation, high volume, efficiency under pressure.

```python
def iso_heavy_fit(play_types: SeasonPlayTypeStats, advanced: PlayerAdvancedStats,
                  shooting: PlayerShootingTracking, season_stats: SeasonStats) -> float:
    
    # Isolation PPP -- the core metric
    iso_score = float(play_types.isolation_ppp_percentile or 50)
    
    # Isolation volume (frequency)
    iso_freq = float(play_types.isolation_freq or 0) * 100
    iso_volume = normalize_to_0_100(iso_freq, min_val=2, max_val=15)
    
    # Pull-up shooting efficiency
    pullup_efg = float(shooting.pullup_efg_pct or 0.40)
    pullup_score = normalize_to_0_100(pullup_efg, min_val=0.35, max_val=0.55)
    
    # Usage rate -- iso-heavy needs high usage tolerance
    usg = float(advanced.usg_pct or 0.20) * 100
    usage_score = normalize_to_0_100(usg, min_val=18, max_val=35)
    
    # True Shooting -- must be efficient at volume
    ts = float(advanced.ts_pct or 0.55) * 100
    ts_score = normalize_to_0_100(ts, min_val=50, max_val=65)
    
    # Drives per game -- iso players attack the rim
    drives = float(shooting.drives or 0)
    drive_score = normalize_to_0_100(drives, min_val=3, max_val=18)
    
    iso_fit = (
        iso_score * 0.25 +
        iso_volume * 0.15 +
        pullup_score * 0.20 +
        usage_score * 0.10 +
        ts_score * 0.15 +
        drive_score * 0.15
    )
    
    return round(iso_fit, 1)
```

### Archetype 4: Egalitarian/Balanced Offense (0-100)

**Philosophy**: No single dominant action. Nuggets (Jokic system), Celtics (multiple actions, read-and-react). Values versatility, decision-making, low turnovers.

```python
def egalitarian_fit(play_types: SeasonPlayTypeStats, advanced: PlayerAdvancedStats,
                    season_stats: SeasonStats) -> float:
    
    # Versatility: how many play types does the player rank well in?
    percentiles = [
        float(play_types.isolation_ppp_percentile or 0),
        float(play_types.pnr_ball_handler_ppp_percentile or 0),
        float(play_types.spot_up_ppp_percentile or 0),
        float(play_types.transition_ppp_percentile or 0),
        float(play_types.cut_ppp_percentile or 0),
        float(play_types.off_screen_ppp_percentile or 0),
    ]
    
    # Count play types above 50th percentile (with minimum volume)
    above_50 = sum(1 for p in percentiles if p >= 50)
    above_40 = sum(1 for p in percentiles if p >= 40)
    
    versatility_score = (above_50 / 6) * 70 + (above_40 / 6) * 30
    
    # Average PPP percentile across all play types
    avg_percentile = sum(percentiles) / len(percentiles) if percentiles else 50
    
    # TS% -- must be efficient
    ts = float(advanced.ts_pct or 0.55) * 100
    ts_score = normalize_to_0_100(ts, min_val=50, max_val=65)
    
    # AST/TOV ratio -- decision making
    ast_to = float(advanced.ast_to or 1.5)
    ast_to_score = normalize_to_0_100(ast_to, min_val=0.8, max_val=3.5)
    
    # Low turnover rate
    gp = max(1, season_stats.games_played or 1)
    tov_pg = float(season_stats.total_turnovers or 0) / gp
    usg = float(advanced.usg_pct or 0.20) * 100
    # Turnover rate relative to usage
    tov_per_usage = tov_pg / max(1, usg)
    low_tov_score = normalize_to_0_100(0.15 - tov_per_usage, min_val=-0.05, max_val=0.10)
    
    # Moderate usage -- egalitarian doesn't need ball dominance
    moderate_usage_score = 100 - abs(usg - 22) * 5  # Peak at 22% usage
    moderate_usage_score = max(0, min(100, moderate_usage_score))
    
    egalitarian_fit = (
        versatility_score * 0.25 +
        avg_percentile * 0.20 +
        ts_score * 0.20 +
        ast_to_score * 0.15 +
        low_tov_score * 0.10 +
        moderate_usage_score * 0.10
    )
    
    return round(egalitarian_fit, 1)
```

### Archetype 5: Post-Up / Inside-Out Offense (0-100)

**Philosophy**: Offense initiated from the post. Jokic Nuggets, Embiid Sixers, historical Lakers. Values post scoring, passing from the post, offensive rebounding, mid-range.

```python
def post_up_fit(play_types: SeasonPlayTypeStats, advanced: PlayerAdvancedStats,
                per75: Per75Stats, shot_zones: list[PlayerShotZones],
                season_stats: SeasonStats) -> float:
    
    # Post-up PPP -- the core metric
    post_score = float(play_types.post_up_ppp_percentile or 50)
    
    # Post-up volume
    post_freq = float(play_types.post_up_freq or 0) * 100
    post_volume = normalize_to_0_100(post_freq, min_val=2, max_val=15)
    
    # Paint scoring (Restricted Area + In The Paint)
    paint_fg = 0.50
    paint_fga = 0
    for sz in shot_zones:
        zone_lower = sz.zone.lower()
        if 'restricted' in zone_lower or 'paint' in zone_lower:
            fga = float(sz.fga or 0)
            fgm = float(sz.fgm or 0)
            paint_fga += fga
            if fga > 0:
                paint_fg = fgm / paint_fga if paint_fga > 0 else 0.50
    paint_score = normalize_to_0_100(paint_fg, min_val=0.45, max_val=0.70)
    
    # Passing out of the post (AST ratio)
    ast_ratio = float(advanced.ast_ratio or 0)
    passing_score = normalize_to_0_100(ast_ratio, min_val=5, max_val=30)
    
    # Offensive rebounding
    oreb_pct = float(advanced.oreb_pct or 0) * 100
    oreb_score = normalize_to_0_100(oreb_pct, min_val=2, max_val=12)
    
    # Free throw drawing
    gp = max(1, season_stats.games_played or 1)
    fta_per_game = float(season_stats.total_fta or 0) / gp
    fga_per_game = float(season_stats.total_fga or 0) / gp
    ft_rate = fta_per_game / max(1, fga_per_game)
    ft_score = normalize_to_0_100(ft_rate, min_val=0.15, max_val=0.50)
    
    post_fit = (
        post_score * 0.30 +
        post_volume * 0.10 +
        paint_score * 0.20 +
        passing_score * 0.15 +
        oreb_score * 0.10 +
        ft_score * 0.15
    )
    
    return round(post_fit, 1)
```

### All Data Fields for Scheme Scoring

| Archetype | Primary Data Sources |
|---|---|
| Motion/Read | `SeasonPlayTypeStats` (cut, off_screen, spot_up PPP percentiles, freqs), `PlayerAdvancedStats` (ast_ratio, usg_pct), `Per75Stats` (screen_assists_per_75), `PlayerShootingTracking` (catch_shoot_efg_pct) |
| PnR Heavy | `SeasonPlayTypeStats` (pnr_ball_handler, pnr_roll_man PPP percentiles, freqs), `PlayerAdvancedStats` (ast_pct), `Per75Stats` (fta_per_75, screen_assists_per_75), `PlayerShootingTracking` (drives, drive_pts, pullup_efg_pct), `PlayerShotZones` (Restricted Area) |
| Iso-Heavy | `SeasonPlayTypeStats` (isolation PPP percentile, freq), `PlayerAdvancedStats` (usg_pct, ts_pct), `PlayerShootingTracking` (pullup_efg_pct, drives) |
| Egalitarian | `SeasonPlayTypeStats` (all PPP percentiles), `PlayerAdvancedStats` (ts_pct, ast_to, usg_pct), `SeasonStats` (total_turnovers, games_played) |
| Post-Up | `SeasonPlayTypeStats` (post_up PPP percentile, freq), `PlayerAdvancedStats` (ast_ratio, oreb_pct), `PlayerShotZones` (Restricted Area, In The Paint), `SeasonStats` (total_fta, total_fga, games_played) |

---

## Utility Function: `normalize_to_0_100`

All scoring above relies on this normalization helper:

```python
def normalize_to_0_100(value: float, min_val: float, max_val: float) -> float:
    """
    Linearly map a value from [min_val, max_val] to [0, 100].
    Values outside the range are clamped.
    """
    if max_val == min_val:
        return 50.0
    score = (value - min_val) / (max_val - min_val) * 100
    return max(0.0, min(100.0, score))


def percentile_rank(value: float, all_values: list[float]) -> float:
    """
    Compute the percentile rank of a value within a distribution.
    Returns 0-100.
    """
    if not all_values:
        return 50.0
    below = sum(1 for v in all_values if v < value)
    return (below / len(all_values)) * 100
```

---

## Edge Cases and Gotchas Summary

**Across all metrics:**

1. **Minimum sample sizes**: Always enforce minimums. Suggested thresholds:
   - RAPM: 500 possessions
   - Clutch stats: 10 games with clutch minutes
   - Matchup data: 20 FGA per position bucket, 10 possessions per individual matchup
   - Lineup data: 20 minutes per lineup for dependency analysis
   - Play type data: 30 possessions per play type for percentile to be meaningful

2. **Division by zero**: Every division must guard against zero denominators. Use `max(1, denominator)` or return a default (usually 50 for scores, 0.0 for raw metrics).

3. **Missing data**: All your model fields are `Mapped[... | None]`. Every computation must handle `None` gracefully. Convert to `float(x or default)` before arithmetic.

4. **Decimal vs float**: Your models use `Decimal` but computations are easier in `float`. Convert at input boundaries, convert back to `Decimal` for storage.

5. **Mid-season instability**: Early in the season (games < 20), most metrics will be noisy. Consider adding a `confidence` field (0.0-1.0) alongside each composite score, computed as `min(1.0, games_played / 40)`.

6. **Traded players**: Players traded mid-season have stats with different teams. For lineup-based metrics, filter by team. For aggregate metrics, combine across teams but weight by games/minutes with each team.

7. **Rookies**: Career trajectory metrics will be incomplete. Default the experience/growth pillar to 40 (slightly below average) for first-year players.

8. **Position mapping**: Your `Player.position` field uses NBA API format ("G", "F", "C", "G-F", "F-C", etc.). Create a mapping function:
   ```python
   def map_position_to_bucket(pos: str) -> str:
       if not pos:
           return 'W'  # Default to wing
       pos = pos.upper()
       if pos in ('PG', 'SG', 'G'):
           return 'G'
       elif pos in ('SF', 'G-F', 'F-G'):
           return 'W'
       elif pos in ('PF', 'F'):
           return 'F'
       elif pos in ('C', 'F-C', 'C-F'):
           return 'C'
       return 'W'
   ```

9. **Percentile computation ordering**: When computing league-wide percentiles (for `percentile_rank()`), always compute them in a single batch pass across all qualifying players for the season, then store the results. Do not recompute percentiles per-player.

10. **RAPM intercept**: The ridge regression intercept represents the league-average per-100-possession net rating. It should be close to 0 but will not be exactly 0. The player coefficients should be interpreted relative to this intercept, not relative to 0.