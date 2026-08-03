import json
import re
from pathlib import Path


def normalize_location(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


class HistoricalSuggester:
    """Conservative, editable company/branch suggestions from historical DTRs."""

    def __init__(self, data=None):
        data = data or {}
        self.routes = data.get("routes", {})
        self.route_companies = data.get("route_companies", {})

    @classmethod
    def from_json(cls, path):
        path = Path(path)
        if not path.exists(): return cls()
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def route_key(origin, destination):
        return f"{normalize_location(origin)}|{normalize_location(destination)}"

    def suggest(self, origin, destination, explicit_company=""):
        route = self.route_key(origin, destination)
        explicit_company = str(explicit_company or "").strip()
        if explicit_company:
            branch = self.route_companies.get(f"{route}|{explicit_company.casefold()}", {}).get("branch", "")
            return explicit_company, branch
        match = self.routes.get(route, {})
        return match.get("company", ""), match.get("branch", "")

