from pydantic import BaseModel, Field


class RatingWrite(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=300)


class MyRating(BaseModel):
    can_rate: bool
    stars: int | None = None
    comment: str | None = None


class RatingPublic(BaseModel):
    stars: int
    comment: str | None = None
    author: str
