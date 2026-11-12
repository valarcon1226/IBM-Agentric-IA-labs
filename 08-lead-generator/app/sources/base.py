"""Source adapter interface (DECISIONES-08 L2).

Every lead source — the demo directory today, a real client directory or Google Places
tomorrow — implements the same `search(keyword, location) -> list[RawLead]`. Adding a new
source is adding a new adapter, nothing else in the pipeline changes.
"""

from abc import ABC, abstractmethod

from app.schemas import RawLead


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def search(self, keyword: str, location: str) -> list[RawLead]:
        """Return every raw lead this source has for `keyword` in `location`."""
