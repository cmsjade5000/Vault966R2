from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")
