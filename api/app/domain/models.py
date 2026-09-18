from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterParams:
    year_from: str | None = None
    year_to: str | None = None
    pillars: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    sdgs: tuple[int, ...] = ()
    units: tuple[str, ...] = ()

    def year_bounds(self, default_from: str, default_to: str) -> tuple[str, str]:
        start = self.year_from or default_from
        end = self.year_to or default_to
        if len(start) != 4 or len(end) != 4 or not start.isdigit() or not end.isdigit():
            raise ValueError("year_from and year_to must be four-digit years")
        if start > end:
            raise ValueError("year_from cannot be after year_to")
        return start, end
