from enum import StrEnum


class UsageEventCreatePage(StrEnum):
    DETAIL = "detail"
    DISCOVER = "discover"
    LIBRARY = "library"
    WATCHLIST = "watchlist"

    def __str__(self) -> str:
        return str(self.value)
