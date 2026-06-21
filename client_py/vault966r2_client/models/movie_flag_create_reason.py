from enum import Enum


class MovieFlagCreateReason(str, Enum):
    BROKEN_LINK = "Broken link"
    HUMAN_REVIEW = "Human review"
    METADATA_CLEANUP = "Metadata cleanup"
    MISSING_POSTER = "Missing poster"
    MOVIE_MISMATCH = "Movie mismatch"
    NEEDS_RUNTIME = "Needs runtime"
    OTHER = "Other"
    POSTERBACKDROP_ISSUE = "Poster/backdrop issue"
    VERIFY_IDENTITY = "Verify identity"
    WRONG_RUNTIMEYEAR = "Wrong runtime/year"

    def __str__(self) -> str:
        return str(self.value)
