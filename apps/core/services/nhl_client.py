import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

NHL_API_BASE = "https://api-web.nhle.com"

# All 32 NHL team abbreviations — used for roster seeding.
# Stable since 2021 (last expansion: Seattle Kraken). Update if a 33rd team joins.
NHL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
]


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,          # waits 1s, 2s, 4s between retries
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers["User-Agent"] = "nhl-fantasy-engine/0.1"
    return session


class NHLClient:
    def __init__(self):
        self.session = _build_session()

    def get_schedule(self, date: str) -> dict:
        """Fetch all games for a date. date format: YYYY-MM-DD."""
        url = f"{NHL_API_BASE}/v1/schedule/{date}"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_boxscore(self, game_id: int) -> dict:
        """Fetch full boxscore for a single game."""
        url = f"{NHL_API_BASE}/v1/gamecenter/{game_id}/boxscore"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_roster(self, team_abbrev: str) -> dict:
        """Fetch current season roster for a team."""
        url = f"{NHL_API_BASE}/v1/roster/{team_abbrev}/current"
        resp = self.session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

