"""Service for scraping all-in-one impact metrics from external sources.

Fetches player impact metrics from:
- EPM (Estimated Plus-Minus) from dunksandthrees.com
- DARKO DPM from darko.app (CSV export)
- LEBRON from bball-index.com
- RPM (Real Plus-Minus) from ESPN

Each scraper returns a list of dicts with player_name and metric values,
which are then fuzzy-matched to NBA player IDs for storage.
"""

import io
import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Common headers to mimic a browser
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Request timeout in seconds
REQUEST_TIMEOUT = 30


@dataclass
class AllInOnePlayerData:
    """Scraped all-in-one metric data for a single player."""

    player_name: str
    overall: Decimal | None = None
    offense: Decimal | None = None
    defense: Decimal | None = None


@dataclass
class ScraperResult:
    """Result from a single scraper."""

    source: str
    players: list[AllInOnePlayerData] = field(default_factory=list)
    success: bool = False
    error: str | None = None


def _safe_decimal(value) -> Decimal | None:
    """Safely convert a value to Decimal."""
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return None


def _normalize_name(name: str) -> str:
    """Normalize player name for matching.

    Strips suffixes like Jr., III, II, and normalizes whitespace.
    """
    name = name.strip()
    # Remove common suffixes for matching
    name = re.sub(r"\s+(Jr\.?|Sr\.?|III|II|IV)$", "", name, flags=re.IGNORECASE)
    # Normalize whitespace
    name = " ".join(name.split())
    return name


def _clean_header(text: str) -> str:
    """Clean a table header by removing sort arrows and special characters."""
    # Remove common sort indicator characters
    text = re.sub(r"[↕↑↓▲▼⬆⬇]", "", text)
    # Remove non-ASCII
    text = text.encode("ascii", errors="ignore").decode()
    return text.strip().upper()


class AllInOneMetricsScraper:
    """Scrapes all-in-one impact metrics from multiple external sources."""

    def __init__(self, delay_between_sources: float = 2.0):
        """Initialize the scraper.

        Args:
            delay_between_sources: Seconds to wait between scraping different sites
        """
        self.delay = delay_between_sources
        self._client = httpx.Client(
            headers=BROWSER_HEADERS,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def fetch_all(self) -> dict[str, ScraperResult]:
        """Fetch all available all-in-one metrics.

        Returns:
            Dict mapping source name to ScraperResult
        """
        results = {}

        scrapers = [
            ("EPM", self.fetch_epm),
            ("DARKO", self.fetch_darko),
            ("LEBRON", self.fetch_lebron),
            ("RPM", self.fetch_rpm),
        ]

        for source_name, scraper_fn in scrapers:
            logger.info("Fetching %s data...", source_name)
            try:
                result = scraper_fn()
                results[source_name] = result
                if result.success:
                    logger.info(
                        "Successfully fetched %s for %d players",
                        source_name,
                        len(result.players),
                    )
                else:
                    logger.warning(
                        "Failed to fetch %s: %s", source_name, result.error
                    )
            except Exception as e:
                logger.error("Unexpected error fetching %s: %s", source_name, e)
                results[source_name] = ScraperResult(
                    source=source_name, success=False, error=str(e)
                )

            # Be polite between sources
            time.sleep(self.delay)

        return results

    def fetch_epm(self) -> ScraperResult:
        """Fetch EPM data from dunksandthrees.com.

        EPM page renders a sortable table with columns including
        player name, O-EPM, D-EPM, and EPM (total).
        """
        result = ScraperResult(source="EPM")

        try:
            response = self._client.get("https://dunksandthrees.com/epm")
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Look for the data table — try multiple approaches
            table = soup.find("table")
            if not table:
                # EPM may be JS-rendered. Try to find JSON data in script tags.
                import json as _json
                for script in soup.find_all("script"):
                    text = script.get_text()
                    # Look for player data arrays
                    for pattern in [
                        r'"players"\s*:\s*(\[.*?\])',
                        r'"data"\s*:\s*(\[.*?\])',
                        r'__NEXT_DATA__.*?"players"\s*:\s*(\[.*?\])',
                    ]:
                        match = re.search(pattern, text, re.DOTALL)
                        if match:
                            try:
                                data = _json.loads(match.group(1))
                                for item in data:
                                    name = item.get("name") or item.get("player", "")
                                    if not name:
                                        continue
                                    player = AllInOnePlayerData(
                                        player_name=_normalize_name(name),
                                        overall=_safe_decimal(item.get("epm") or item.get("EPM")),
                                        offense=_safe_decimal(item.get("o_epm") or item.get("O-EPM")),
                                        defense=_safe_decimal(item.get("d_epm") or item.get("D-EPM")),
                                    )
                                    result.players.append(player)
                            except _json.JSONDecodeError:
                                pass
                if result.players:
                    result.success = True
                    return result
                result.error = "No table found on EPM page (site may require JavaScript)"
                return result

            # Parse headers
            headers = []
            thead = table.find("thead")
            if thead:
                for th in thead.find_all("th"):
                    headers.append(_clean_header(th.get_text(strip=True)))

            # Find column indices
            name_idx = None
            epm_idx = None
            oepm_idx = None
            depm_idx = None

            for i, h in enumerate(headers):
                if h in ("PLAYER", "NAME"):
                    name_idx = i
                elif h == "EPM":
                    epm_idx = i
                elif h in ("O-EPM", "OEPM", "OFF. EPM", "OFF"):
                    oepm_idx = i
                elif h in ("D-EPM", "DEPM", "DEF. EPM", "DEF"):
                    depm_idx = i

            if name_idx is None or epm_idx is None:
                # Try alternate parsing: look for all th/td in rows
                result.error = f"Could not identify columns. Headers: {headers}"
                return result

            # Parse rows
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(
                    filter(None, [name_idx, epm_idx, oepm_idx, depm_idx])
                ):
                    continue

                name = cells[name_idx].get_text(strip=True)
                if not name:
                    continue

                player = AllInOnePlayerData(
                    player_name=_normalize_name(name),
                    overall=_safe_decimal(cells[epm_idx].get_text(strip=True)),
                    offense=(
                        _safe_decimal(cells[oepm_idx].get_text(strip=True))
                        if oepm_idx is not None
                        else None
                    ),
                    defense=(
                        _safe_decimal(cells[depm_idx].get_text(strip=True))
                        if depm_idx is not None
                        else None
                    ),
                )
                result.players.append(player)

            result.success = len(result.players) > 0
            if not result.success:
                result.error = "No player rows parsed from EPM table"

        except httpx.HTTPError as e:
            result.error = f"HTTP error: {e}"
        except Exception as e:
            result.error = f"Parse error: {e}"

        return result

    def fetch_darko(self) -> ScraperResult:
        """Fetch DARKO DPM data from darko.app.

        The leaderboard page has a CSV download button. We try to find
        the CSV export URL or parse the page directly.
        """
        result = ScraperResult(source="DARKO")

        try:
            # First try the main page to find data
            response = self._client.get("https://darko.app/")
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Look for a table with DPM data
            table = soup.find("table")
            if table:
                return self._parse_darko_table(table, result)

            # If no table, try to find embedded JSON or CSV link
            # Look for CSV download links
            csv_links = soup.find_all("a", href=re.compile(r"\.csv", re.IGNORECASE))
            if csv_links:
                csv_url = csv_links[0].get("href")
                if csv_url and not csv_url.startswith("http"):
                    csv_url = f"https://darko.app{csv_url}"

                csv_response = self._client.get(csv_url)
                csv_response.raise_for_status()

                df = pd.read_csv(io.StringIO(csv_response.text))
                return self._parse_darko_csv(df, result)

            # Try finding data in script tags (React/Next.js apps often embed data)
            scripts = soup.find_all("script")
            for script in scripts:
                text = script.get_text()
                if "DPM" in text and "player" in text.lower():
                    # Try to extract JSON data
                    json_match = re.search(
                        r'\[{.*?"(?:name|player)".*?}.*?\]', text, re.DOTALL
                    )
                    if json_match:
                        import json

                        try:
                            data = json.loads(json_match.group())
                            for item in data:
                                name = item.get("name") or item.get("player", "")
                                if not name:
                                    continue
                                player = AllInOnePlayerData(
                                    player_name=_normalize_name(name),
                                    overall=_safe_decimal(
                                        item.get("dpm") or item.get("DPM")
                                    ),
                                    offense=_safe_decimal(
                                        item.get("o_dpm") or item.get("O-DPM")
                                    ),
                                    defense=_safe_decimal(
                                        item.get("d_dpm") or item.get("D-DPM")
                                    ),
                                )
                                result.players.append(player)
                        except json.JSONDecodeError:
                            pass

            if not result.players:
                result.error = "Could not find DARKO data on page"
            else:
                result.success = True

        except httpx.HTTPError as e:
            result.error = f"HTTP error: {e}"
        except Exception as e:
            result.error = f"Error: {e}"

        return result

    def _parse_darko_table(
        self, table: BeautifulSoup, result: ScraperResult
    ) -> ScraperResult:
        """Parse a DARKO HTML table."""
        headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.find_all("th"):
                headers.append(_clean_header(th.get_text(strip=True)))

        name_idx = None
        dpm_idx = None
        odpm_idx = None
        ddpm_idx = None

        for i, h in enumerate(headers):
            if h in ("PLAYER", "NAME"):
                name_idx = i
            elif h in ("DPM", "TOTAL DPM", "TOTAL"):
                dpm_idx = i
            elif h in ("O-DPM", "ODPM", "OFF DPM", "OFF"):
                odpm_idx = i
            elif h in ("D-DPM", "DDPM", "DEF DPM", "DEF"):
                ddpm_idx = i

        if name_idx is None or dpm_idx is None:
            result.error = f"Could not identify DARKO columns. Headers: {headers}"
            return result

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) <= max(
                filter(None, [name_idx, dpm_idx, odpm_idx, ddpm_idx])
            ):
                continue

            name = cells[name_idx].get_text(strip=True)
            if not name:
                continue

            player = AllInOnePlayerData(
                player_name=_normalize_name(name),
                overall=_safe_decimal(cells[dpm_idx].get_text(strip=True)),
                offense=(
                    _safe_decimal(cells[odpm_idx].get_text(strip=True))
                    if odpm_idx is not None
                    else None
                ),
                defense=(
                    _safe_decimal(cells[ddpm_idx].get_text(strip=True))
                    if ddpm_idx is not None
                    else None
                ),
            )
            result.players.append(player)

        result.success = len(result.players) > 0
        return result

    def _parse_darko_csv(
        self, df: pd.DataFrame, result: ScraperResult
    ) -> ScraperResult:
        """Parse a DARKO CSV DataFrame."""
        # Normalize column names
        col_map = {c.upper().strip(): c for c in df.columns}

        name_col = col_map.get("PLAYER") or col_map.get("NAME")
        dpm_col = col_map.get("DPM") or col_map.get("TOTAL DPM")
        odpm_col = col_map.get("O-DPM") or col_map.get("ODPM")
        ddpm_col = col_map.get("D-DPM") or col_map.get("DDPM")

        if not name_col or not dpm_col:
            result.error = f"Could not identify DARKO CSV columns: {list(df.columns)}"
            return result

        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            if not name or name == "nan":
                continue

            player = AllInOnePlayerData(
                player_name=_normalize_name(name),
                overall=_safe_decimal(row.get(dpm_col)),
                offense=_safe_decimal(row.get(odpm_col)) if odpm_col else None,
                defense=_safe_decimal(row.get(ddpm_col)) if ddpm_col else None,
            )
            result.players.append(player)

        result.success = len(result.players) > 0
        return result

    def fetch_lebron(self) -> ScraperResult:
        """Fetch LEBRON data from bball-index.com.

        The LEBRON database page shows a table/dashboard with player
        LEBRON values including offensive and defensive components.
        """
        result = ScraperResult(source="LEBRON")

        try:
            response = self._client.get(
                "https://www.bball-index.com/lebron-database/"
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Look for tables
            table = soup.find("table")
            if table:
                headers = []
                thead = table.find("thead")
                if thead:
                    for th in thead.find_all("th"):
                        headers.append(th.get_text(strip=True).upper())

                name_idx = None
                lebron_idx = None
                olebron_idx = None
                dlebron_idx = None

                for i, h in enumerate(headers):
                    if h in ("PLAYER", "NAME"):
                        name_idx = i
                    elif h in ("LEBRON", "TOTAL"):
                        lebron_idx = i
                    elif h in ("O-LEBRON", "OFFENSE", "OFF"):
                        olebron_idx = i
                    elif h in ("D-LEBRON", "DEFENSE", "DEF"):
                        dlebron_idx = i

                if name_idx is not None and lebron_idx is not None:
                    tbody = table.find("tbody")
                    rows = (
                        tbody.find_all("tr") if tbody else table.find_all("tr")[1:]
                    )

                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) <= max(
                            filter(
                                None,
                                [name_idx, lebron_idx, olebron_idx, dlebron_idx],
                            )
                        ):
                            continue

                        name = cells[name_idx].get_text(strip=True)
                        if not name:
                            continue

                        player = AllInOnePlayerData(
                            player_name=_normalize_name(name),
                            overall=_safe_decimal(
                                cells[lebron_idx].get_text(strip=True)
                            ),
                            offense=(
                                _safe_decimal(
                                    cells[olebron_idx].get_text(strip=True)
                                )
                                if olebron_idx is not None
                                else None
                            ),
                            defense=(
                                _safe_decimal(
                                    cells[dlebron_idx].get_text(strip=True)
                                )
                                if dlebron_idx is not None
                                else None
                            ),
                        )
                        result.players.append(player)

            # If no table found, check for Tableau embeds or iframes
            if not result.players:
                iframes = soup.find_all("iframe")
                if iframes:
                    result.error = (
                        "LEBRON data is in an embedded dashboard (iframe/Tableau). "
                        "Manual scraping not supported. Consider using the BBall Index API."
                    )
                else:
                    result.error = "No LEBRON data table found on page"
                return result

            result.success = len(result.players) > 0

        except httpx.HTTPError as e:
            result.error = f"HTTP error: {e}"
        except Exception as e:
            result.error = f"Error: {e}"

        return result

    def fetch_rpm(self) -> ScraperResult:
        """Fetch RPM data from ESPN.

        ESPN's RPM page renders server-side with paginated player data.
        We iterate through pages to collect all players.
        """
        result = ScraperResult(source="RPM")

        try:
            page = 1
            max_pages = 15  # ~450 players / 50 per page

            while page <= max_pages:
                url = f"https://www.espn.com/nba/statistics/rpm/_/page/{page}"
                response = self._client.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                # Find the stats table
                table = soup.find("table")
                if not table:
                    break

                # Parse headers on first page
                if page == 1:
                    headers = []
                    thead = table.find("thead")
                    if thead:
                        for th in thead.find_all("th"):
                            headers.append(th.get_text(strip=True).upper())

                tbody = table.find("tbody")
                rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

                if not rows:
                    break

                rows_found = 0
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) < 4:
                        continue

                    # ESPN typically: Rank, Name, Team, GP, MPG, ORPM, DRPM, RPM, WINS
                    # Find name — usually the cell with an anchor tag
                    name = None
                    for cell in cells:
                        link = cell.find("a")
                        if link:
                            name = link.get_text(strip=True)
                            break

                    if not name:
                        # Try second cell as name
                        name = cells[1].get_text(strip=True) if len(cells) > 1 else None

                    if not name:
                        continue

                    # Try to find RPM values by looking for numeric cells
                    numeric_vals = []
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        try:
                            numeric_vals.append(float(text))
                        except ValueError:
                            numeric_vals.append(None)

                    # RPM columns are typically: ORPM, DRPM, RPM
                    # They are the last few numeric columns
                    rpm_vals = [v for v in numeric_vals if v is not None]

                    if len(rpm_vals) >= 3:
                        # Last 3 numeric values are typically ORPM, DRPM, RPM
                        # or RPM, ORPM, DRPM — check the header order
                        orpm = _safe_decimal(rpm_vals[-3])
                        drpm = _safe_decimal(rpm_vals[-2])
                        rpm_total = _safe_decimal(rpm_vals[-1])

                        # Sometimes the order is RPM, ORPM, DRPM
                        # Verify: O + D should roughly equal total
                        if orpm is not None and drpm is not None and rpm_total is not None:
                            if abs(float(orpm) + float(drpm) - float(rpm_total)) > 1.0:
                                # Try swapping — total might be first
                                rpm_total, orpm, drpm = orpm, drpm, rpm_total

                        player = AllInOnePlayerData(
                            player_name=_normalize_name(name),
                            overall=rpm_total,
                            offense=orpm,
                            defense=drpm,
                        )
                        result.players.append(player)
                        rows_found += 1

                if rows_found == 0:
                    break

                page += 1
                time.sleep(1.0)  # Be polite to ESPN

            result.success = len(result.players) > 0
            if not result.success:
                result.error = "No RPM data parsed from ESPN"

        except httpx.HTTPError as e:
            result.error = f"HTTP error: {e}"
            # Partial success is still useful
            if result.players:
                result.success = True
        except Exception as e:
            result.error = f"Error: {e}"
            if result.players:
                result.success = True

        return result


def build_name_lookup(
    players: list[tuple[int, str]],
) -> dict[str, int]:
    """Build a normalized name -> player_id lookup.

    Args:
        players: List of (player_db_id, player_name) tuples

    Returns:
        Dict mapping normalized names to player DB IDs
    """
    lookup = {}
    for player_id, name in players:
        normalized = _normalize_name(name).lower()
        lookup[normalized] = player_id

        # Also add last name only for common lookups
        parts = normalized.split()
        if len(parts) >= 2:
            # "first last" -> also index by "last"
            lookup[parts[-1]] = player_id

    return lookup


def match_player(
    scraped_name: str,
    lookup: dict[str, int],
) -> int | None:
    """Match a scraped player name to a DB player ID.

    Tries exact match first, then progressively fuzzier matches.

    Args:
        scraped_name: Player name from scraped source
        lookup: Normalized name -> player_id dict

    Returns:
        Player DB ID if matched, None otherwise
    """
    normalized = _normalize_name(scraped_name).lower()

    # Exact match
    if normalized in lookup:
        return lookup[normalized]

    # Try without periods (e.g., "P.J." -> "PJ")
    no_periods = normalized.replace(".", "")
    if no_periods in lookup:
        return lookup[no_periods]

    # Try matching just "First Last" (drop middle names)
    parts = normalized.split()
    if len(parts) > 2:
        first_last = f"{parts[0]} {parts[-1]}"
        if first_last in lookup:
            return lookup[first_last]

    return None
