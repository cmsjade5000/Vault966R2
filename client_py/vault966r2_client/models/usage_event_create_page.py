from enum import Enum


class UsageEventCreatePage(str, Enum):
    DETAIL = "detail"
    DISCOVER = "discover"
    LIBRARY = "library"
    WATCHLIST = "watchlist"

    def __str__(self) -> str:
        return str(self.value)
