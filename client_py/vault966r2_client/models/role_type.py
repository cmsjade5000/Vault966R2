from enum import StrEnum


class RoleType(StrEnum):
    ACTOR = "ACTOR"
    DIRECTOR = "DIRECTOR"
    WRITER = "WRITER"

    def __str__(self) -> str:
        return str(self.value)
