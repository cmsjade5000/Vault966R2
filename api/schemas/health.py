from typing import Literal

from pydantic import BaseModel, ConfigDict


class LivenessResponse(BaseModel):
    status: Literal["alive"]

    model_config = ConfigDict(extra="forbid")


class ReadinessResponse(BaseModel):
    status: Literal["ready"]

    model_config = ConfigDict(extra="forbid")
