from pydantic import BaseModel, ConfigDict

class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {}
        }
    )
