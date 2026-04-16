"""Service for scraping all-in-one impact metrics from external sources.

Fetches player impact metrics from:
- EPM (Estimated Plus-Minus) from dunksandthrees.com via SvelteKit __data.json
- DARKO DPM from darko.app via SvelteKit __data.json
- LEBRON from bball-index.com (JS-rendered; currently unavailable without browser)
- RPM/xRAPM from xrapm.com (original RPM metric by Jeremias Engelmann)

Each scraper returns a list of dicts with player_name and metric values,
which are then fuzzy-matched to NBA player IDs for storage.
"""

import json
import logging
import re
import time
import unicodedata
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


def _to_ascii(name: str) -> str:
    """Transliterate Unicode characters to ASCII equivalents.

    Converts diacritical characters like ć, č, ņ, ģ to their base letters.
    E.g., 'Jokić' -> 'Jokic', 'Porziņģis' -> 'Porzingis'
    """
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _clean_header(text: str) -> str:
    """Clean a table header by removing sort arrows and special characters."""
    # Remove common sort indicator characters
    text = re.sub(r"[↕↑↓▲▼⬆⬇]", "", text)
    # Remove non-ASCII
    text = text.encode("ascii", errors="ignore").decode()
    return text.strip().upper()


def _parse_sveltekit_ndjson(response_text: str) -> list[dict]:
    """Parse a SvelteKit newline-delimited JSON response.

    SvelteKit __data.json endpoints return NDJSON (newline-delimited JSON)
    where the first line is the main data and subsequent lines are deferred
    chunks that resolve Promise placeholders in the main data.

    Args:
        response_text: Raw response body text

    Returns:
        List of parsed JSON objects (one per line)
    """
    results = []
    for line in response_text.strip().split("\n"):
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return results


def _extract_sveltekit_players(
    data_array: list,
    pointer_array: list[int],
    name_field: str,
    overall_field: str,
    offense_field: str,
    defense_field: str,
) -> list[AllInOnePlayerData]:
    """Extract player records from a SvelteKit __data.json flat data array.

    SvelteKit serializes data using a flat array with per-record field maps.
    Each entry in the pointer_array points to a dict in data_array that maps
    field names to absolute indices within data_array where the values live.

    This deduplication strategy means shared values (like season=2026) appear
    once in the array and multiple records reference the same index.

    Example structure:
        data_array[pointer[0]] = {"player_name": 6, "tot": 16, ...}
        data_array[6] = "Victor Wembanyama"
        data_array[16] = 8.79

        data_array[pointer[1]] = {"player_name": 89, "tot": 98, ...}
        data_array[89] = "Shai Gilgeous-Alexander"
        data_array[98] = 8.36

    Args:
        data_array: The flat data list from a SvelteKit node
        pointer_array: List of indices pointing to per-record field maps
        name_field: Key name for player name in the field maps
        overall_field: Key name for overall metric value
        offense_field: Key name for offensive metric value
        defense_field: Key name for defensive metric value

    Returns:
        List of AllInOnePlayerData instances
    """
    players = []

    for ptr in pointer_array:
        try:
            if ptr >= len(data_array):
                continue

            record_map = data_array[ptr]
            if not isinstance(record_map, dict):
                continue

            # Get the absolute index for each field from the per-record map
            name_idx = record_map.get(name_field)
            if name_idx is None or name_idx >= len(data_array):
                continue

            name_val = data_array[name_idx]
            if not isinstance(name_val, str) or not name_val:
                continue

            # Extract metric values
            overall_val = None
            overall_idx = record_map.get(overall_field)
            if overall_idx is not None and overall_idx < len(data_array):
                overall_val = data_array[overall_idx]

            offense_val = None
            offense_idx = record_map.get(offense_field)
            if offense_idx is not None and offense_idx < len(data_array):
                offense_val = data_array[offense_idx]

            defense_val = None
            defense_idx = record_map.get(defense_field)
            if defense_idx is not None and defense_idx < len(data_array):
                defense_val = data_array[defense_idx]

            player = AllInOnePlayerData(
                player_name=_normalize_name(name_val),
                overall=_safe_decimal(overall_val),
                offense=_safe_decimal(offense_val),
                defense=_safe_decimal(defense_val),
            )
            players.append(player)

        except (IndexError, KeyError, TypeError) as e:
            logger.debug("Skipping record at pointer %d: %s", ptr, e)
            continue

    return players


def _find_sveltekit_stats_node(
    ndjson_objects: list[dict],
    identifier_field: str,
) -> tuple[list | None, list[int] | None]:
    """Find the SvelteKit data node containing player statistics.

    Searches through both the main data object and deferred chunks for
    a node whose data array contains a field map with the given identifier.

    Args:
        ndjson_objects: Parsed NDJSON objects from the response
        identifier_field: A field name that identifies the stats field map
                         (e.g., 'player_name')

    Returns:
        Tuple of (data_array, pointer_array) or (None, None) if not found
    """
    for obj in ndjson_objects:
        obj_type = obj.get("type")

        if obj_type == "data":
            # Main data object - search through nodes
            for node in obj.get("nodes", []):
                if node is None or not isinstance(node, dict):
                    continue
                if node.get("type") != "data":
                    continue

                data_array = node.get("data", [])
                result = _find_stats_in_data_array(data_array, identifier_field)
                if result is not None:
                    return data_array, result

        elif obj_type == "chunk":
            # Deferred chunk - search its data array directly
            data_array = obj.get("data", [])
            result = _find_stats_in_data_array(data_array, identifier_field)
            if result is not None:
                return data_array, result

    return None, None


def _find_stats_in_data_array(
    data_array: list,
    identifier_field: str,
) -> list[int] | None:
    """Find the pointer array for stats records within a data array.

    Looks for a list of monotonically increasing integers (the pointer array)
    immediately followed by or associated with a dict containing the identifier
    field (the field map for the first record).

    Args:
        data_array: The flat data list to search
        identifier_field: Field name to identify the correct field map

    Returns:
        The pointer array if found, None otherwise
    """
    if not data_array or not isinstance(data_array, list):
        return None

    # Strategy: look for the top-level structure dict that has a 'stats' key
    # pointing to the pointer array, or find the pointer array directly
    for i, item in enumerate(data_array):
        if not isinstance(item, dict):
            continue

        # Check if this dict references a 'stats' field pointing to a list index
        stats_idx = item.get("stats")
        if stats_idx is not None and isinstance(stats_idx, int):
            if stats_idx < len(data_array) and isinstance(data_array[stats_idx], list):
                candidate = data_array[stats_idx]
                if _is_pointer_array(candidate, data_array, identifier_field):
                    return candidate

        # Check if this dict references a 'players' field pointing to a list index
        players_idx = item.get("players")
        if players_idx is not None and isinstance(players_idx, int):
            if players_idx < len(data_array) and isinstance(
                data_array[players_idx], list
            ):
                candidate = data_array[players_idx]
                if _is_pointer_array(candidate, data_array, identifier_field):
                    return candidate

    # Fallback: scan for any list of integers that looks like a pointer array
    for i, item in enumerate(data_array):
        if isinstance(item, list) and len(item) > 10:
            if _is_pointer_array(item, data_array, identifier_field):
                return item

    return None


def _is_pointer_array(
    candidate: list,
    data_array: list,
    identifier_field: str,
) -> bool:
    """Check if a candidate list is a valid pointer array.

    A valid pointer array contains integers that point to per-record field
    map dicts in the data_array, where at least the first pointed-to dict
    contains the identifier_field key.

    Args:
        candidate: List to check
        data_array: The containing data array
        identifier_field: Expected field name in the pointed-to dicts

    Returns:
        True if this is a valid pointer array
    """
    if not candidate or not all(isinstance(x, int) for x in candidate[:5]):
        return False

    # Check that the first pointer leads to a dict with the identifier field
    first_ptr = candidate[0]
    if first_ptr >= len(data_array):
        return False

    target = data_array[first_ptr]
    return isinstance(target, dict) and identifier_field in target


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

    def fetch_all(self, season: str | None = None) -> dict[str, ScraperResult]:
        """Fetch all available all-in-one metrics.

        Args:
            season: NBA season string (e.g. "2024-25"). Passed to scrapers
                    that support historical data. If None, fetches current season.

        Returns:
            Dict mapping source name to ScraperResult
        """
        results = {}

        scrapers = [
            ("EPM", lambda: self.fetch_epm(season=season)),
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

    def _fetch_sveltekit_data(self, url: str) -> list[dict]:
        """Fetch and parse a SvelteKit __data.json endpoint.

        Args:
            url: The __data.json URL to fetch

        Returns:
            List of parsed NDJSON objects

        Raises:
            httpx.HTTPError: On HTTP errors
            json.JSONDecodeError: On invalid JSON
        """
        response = self._client.get(
            url,
            headers={
                **BROWSER_HEADERS,
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return _parse_sveltekit_ndjson(response.text)

    def fetch_epm(self, season: str | None = None) -> ScraperResult:
        """Fetch EPM data from dunksandthrees.com via SvelteKit data endpoint.

        dunksandthrees.com is a SvelteKit app. The __data.json endpoint returns
        player data in SvelteKit's compressed indexed format without needing
        JavaScript rendering.

        The response is NDJSON with the main data in the first line's node[2]
        containing fields: player_name, off (O-EPM), def (D-EPM), tot (total EPM).

        Args:
            season: NBA season string (e.g. "2024-25"). The endpoint uses the
                    ending year as a query param (e.g. ?season=2025).
                    Supports seasons from 2001-02 through present.
                    If None, fetches the current season.
        """
        result = ScraperResult(source="EPM")

        try:
            url = "https://dunksandthrees.com/epm/__data.json"
            if season:
                # Convert "2024-25" -> 2025 (ending year)
                ending_year = int(season.split("-")[0]) + 1
                url = f"{url}?season={ending_year}"

            ndjson = self._fetch_sveltekit_data(url)

            data_array, pointer_array = _find_sveltekit_stats_node(
                ndjson, "player_name"
            )

            if data_array is None or pointer_array is None:
                result.error = (
                    "Could not find player stats node in EPM __data.json. "
                    "The SvelteKit data format may have changed."
                )
                return result

            players = _extract_sveltekit_players(
                data_array=data_array,
                pointer_array=pointer_array,
                name_field="player_name",
                overall_field="tot",
                offense_field="off",
                defense_field="def",
            )

            if players:
                result.players = players
                result.success = True
            else:
                result.error = "Parsed EPM __data.json but extracted 0 players"

        except httpx.HTTPError as e:
            result.error = f"HTTP error fetching EPM __data.json: {e}"
        except json.JSONDecodeError as e:
            result.error = f"Invalid JSON from EPM __data.json: {e}"
        except Exception as e:
            result.error = f"Error parsing EPM data: {e}"

        return result

    def fetch_darko(self) -> ScraperResult:
        """Fetch DARKO DPM data from darko.app via SvelteKit data endpoint.

        darko.app is a SvelteKit app. The __data.json endpoint returns player
        data with DPM (Daily Plus-Minus) metrics in the same compressed format.

        Fields: player_name, dpm (total), o_dpm (offensive), d_dpm (defensive).
        """
        result = ScraperResult(source="DARKO")

        try:
            ndjson = self._fetch_sveltekit_data(
                "https://darko.app/__data.json"
            )

            data_array, pointer_array = _find_sveltekit_stats_node(
                ndjson, "player_name"
            )

            if data_array is None or pointer_array is None:
                result.error = (
                    "Could not find player stats node in DARKO __data.json. "
                    "The SvelteKit data format may have changed."
                )
                return result

            players = _extract_sveltekit_players(
                data_array=data_array,
                pointer_array=pointer_array,
                name_field="player_name",
                overall_field="dpm",
                offense_field="o_dpm",
                defense_field="d_dpm",
            )

            if players:
                result.players = players
                result.success = True
            else:
                result.error = "Parsed DARKO __data.json but extracted 0 players"

        except httpx.HTTPError as e:
            result.error = f"HTTP error fetching DARKO __data.json: {e}"
        except json.JSONDecodeError as e:
            result.error = f"Invalid JSON from DARKO __data.json: {e}"
        except Exception as e:
            result.error = f"Error parsing DARKO data: {e}"

        return result

    def fetch_lebron(self) -> ScraperResult:
        """Fetch LEBRON data from bball-index.com.

        The LEBRON dashboard is JavaScript-rendered with no accessible public API
        or data endpoint. The data is loaded dynamically via a JS application
        that cannot be accessed through simple HTTP requests.

        This scraper attempts to find server-rendered data but will likely fail.
        To obtain LEBRON data, consider:
        - Using a headless browser (Playwright/Selenium) to render the JS
        - Contacting BBall Index for API access
        - Manually downloading data from their interactive tools
        """
        result = ScraperResult(source="LEBRON")

        try:
            response = self._client.get(
                "https://www.bball-index.com/lebron-database/"
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Check for HTML tables (in case they add server-rendered data)
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

            # Check for Google Sheets embeds (inline-google-spreadsheet-viewer plugin)
            if not result.players:
                igsv_tables = soup.find_all(class_="igsv-table")
                if igsv_tables:
                    logger.info(
                        "Found igsv-table elements; data may be in Google Sheets embed"
                    )

            if result.players:
                result.success = True
            else:
                result.error = (
                    "LEBRON data is rendered via JavaScript and cannot be scraped "
                    "with static HTTP requests. The bball-index.com dashboard "
                    "requires a headless browser (Playwright/Selenium) or direct "
                    "API access from BBall Index."
                )

        except httpx.HTTPError as e:
            result.error = f"HTTP error: {e}"
        except Exception as e:
            result.error = f"Error: {e}"

        return result

    def fetch_rpm(self) -> ScraperResult:
        """Fetch xRAPM data from xrapm.com as a replacement for ESPN RPM.

        ESPN has removed RPM from their website. The original RPM creator,
        Jeremias Engelmann, publishes the metric under its original name
        xRAPM (Expected Regularized Adjusted Plus-Minus) at xrapm.com.

        The page contains a single HTML table (id="sortableTable") with all
        ~650 NBA players. Values include percentile rankings in parentheses
        (e.g., "7.2 (99)").

        Note: The xRAPM HTML is malformed - tbody rows lack opening <tr> tags,
        causing standard row-based parsers to fail. We parse by collecting all
        <td> elements from tbody and grouping them by the known column count.
        """
        result = ScraperResult(source="RPM")

        try:
            response = self._client.get("https://xrapm.com")
            response.raise_for_status()

            # Use html.parser (not lxml) because the HTML is malformed:
            # rows in tbody lack opening <tr> tags, and lxml drops them.
            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.find("table", {"id": "sortableTable"})
            if not table:
                table = soup.find("table", {"class": "table1"})
            if not table:
                table = soup.find("table")

            if not table:
                result.error = (
                    "No table found on xrapm.com. "
                    "Site structure may have changed."
                )
                return result

            # Parse headers to determine column count and positions
            headers = []
            thead = table.find("thead")
            if thead:
                for th in thead.find_all("th"):
                    headers.append(_clean_header(th.get_text(strip=True)))

            # Determine column indices
            # Expected: Player, Team, Offense, Defense(*), Total
            num_cols = len(headers) if headers else 5
            name_idx = 0
            offense_idx = 2
            defense_idx = 3
            total_idx = 4

            for i, h in enumerate(headers):
                if h in ("PLAYER", "NAME"):
                    name_idx = i
                elif h in ("TOTAL", "XRAPM", "RPM", "RAPM"):
                    total_idx = i
                elif h.startswith("OFFENSE") or h in ("OFF",):
                    offense_idx = i
                elif h.startswith("DEFENSE") or h in ("DEF",):
                    defense_idx = i

            # Try standard row-based parsing first
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

            if rows and rows[0].find_all("td"):
                # Standard parsing works
                for row in rows:
                    self._parse_xrapm_row(
                        row.find_all(["td", "th"]),
                        name_idx, offense_idx, defense_idx, total_idx,
                        result,
                    )
            else:
                # Malformed HTML fallback: collect all <td> from tbody and
                # group by column count since <tr> tags are missing
                if tbody:
                    all_tds = tbody.find_all("td")
                else:
                    all_tds = table.find_all("td")

                if not all_tds:
                    result.error = "No table cells found on xrapm.com"
                    return result

                logger.debug(
                    "xRAPM: using TD-grouping fallback (%d cells, %d cols)",
                    len(all_tds), num_cols,
                )

                for i in range(0, len(all_tds) - num_cols + 1, num_cols):
                    cells = all_tds[i : i + num_cols]
                    self._parse_xrapm_row(
                        cells,
                        name_idx, offense_idx, defense_idx, total_idx,
                        result,
                    )

            result.success = len(result.players) > 0
            if not result.success:
                result.error = "No player rows parsed from xRAPM table"

        except httpx.HTTPError as e:
            result.error = f"HTTP error fetching xrapm.com: {e}"
        except Exception as e:
            result.error = f"Error parsing xRAPM data: {e}"

        return result

    def _parse_xrapm_row(
        self,
        cells: list,
        name_idx: int,
        offense_idx: int,
        defense_idx: int,
        total_idx: int,
        result: ScraperResult,
    ) -> None:
        """Parse a single row of xRAPM data from table cells.

        Args:
            cells: List of BeautifulSoup td/th elements
            name_idx: Column index for player name
            offense_idx: Column index for offensive value
            defense_idx: Column index for defensive value
            total_idx: Column index for total value
            result: ScraperResult to append player data to
        """
        if len(cells) < 3:
            return

        # Get player name - may be wrapped in a link
        name_cell = cells[name_idx]
        link = name_cell.find("a")
        name = (
            link.get_text(strip=True) if link else name_cell.get_text(strip=True)
        )

        if not name:
            return

        def _extract_value(cell_text: str) -> str | None:
            """Extract numeric value, stripping percentile in parens.

            xRAPM shows values like "7.2 (99)" where (99) is percentile.
            """
            cell_text = cell_text.strip()
            if not cell_text:
                return None
            match = re.match(r"^(-?\d+\.?\d*)", cell_text)
            return match.group(1) if match else None

        overall_val = None
        offense_val = None
        defense_val = None

        if total_idx < len(cells):
            overall_val = _extract_value(cells[total_idx].get_text(strip=True))

        if offense_idx < len(cells):
            offense_val = _extract_value(cells[offense_idx].get_text(strip=True))

        if defense_idx < len(cells):
            defense_val = _extract_value(cells[defense_idx].get_text(strip=True))

        player = AllInOnePlayerData(
            player_name=_normalize_name(name),
            overall=_safe_decimal(overall_val),
            offense=_safe_decimal(offense_val),
            defense=_safe_decimal(defense_val),
        )
        result.players.append(player)


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

        # Also index the ASCII-transliterated form for diacritical matching
        ascii_name = _to_ascii(normalized)
        if ascii_name != normalized:
            lookup[ascii_name] = player_id

        # Also add last name only for common lookups
        parts = normalized.split()
        if len(parts) >= 2:
            lookup[parts[-1]] = player_id
            # ASCII last name too
            ascii_last = _to_ascii(parts[-1])
            if ascii_last != parts[-1]:
                lookup[ascii_last] = player_id

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

    # Try ASCII transliteration (e.g., "Jokić" -> "Jokic")
    ascii_normalized = _to_ascii(normalized)
    if ascii_normalized != normalized and ascii_normalized in lookup:
        return lookup[ascii_normalized]

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
