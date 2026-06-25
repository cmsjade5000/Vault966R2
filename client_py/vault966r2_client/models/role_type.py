from enum import Enum


class RoleType(str, Enum):
    ACTOR = "ACTOR"
    DIRECTOR = "DIRECTOR"
    WRITER = "WRITER"

    def __str__(self) -> str:
        return str(self.value)
