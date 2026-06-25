from enum import Enum


class UsageEventCreateEventName(str, Enum):
    DISCOVER_RAIL_OPENED = "discover_rail_opened"
    FILTERS_APPLIED = "filters_applied"
    LIBRARY_SEARCH_SUBMITTED = "library_search_submitted"
    MOVIE_DETAILS_OPENED = "movie_details_opened"
    PERSONALIZED_RECOMMENDATIONS_SHOWN = "personalized_recommendations_shown"
    PREFERENCE_TOGGLED = "preference_toggled"
    RANDOM_PICK_REQUESTED = "random_pick_requested"
    VIEW_CHANGED = "view_changed"

    def __str__(self) -> str:
        return str(self.value)
