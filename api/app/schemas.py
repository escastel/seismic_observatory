"""Typed request and response models for the seismic API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventFilters(BaseModel):
    country: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_magnitude: float | None = None
    max_magnitude: float | None = None
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "EventFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be earlier than or equal to date_to")
        if self.min_magnitude is not None and self.max_magnitude is not None:
            if self.min_magnitude > self.max_magnitude:
                raise ValueError("min_magnitude must be less than or equal to max_magnitude")
        return self


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    updated: datetime
    time: datetime
    mag: float
    place: str
    longitude: float
    latitude: float
    depth_km: float | None
    country: str
    continent: str
    subregion: str
    source_topic: str


class EventsResponse(BaseModel):
    items: list[EventResponse]
    count: int
    limit: int
    offset: int


class CountryCount(BaseModel):
    country: str
    count: int


class CountryStatsResponse(BaseModel):
    items: list[CountryCount]


class TimelineItem(BaseModel):
    period: str
    count: int


class TimelineResponse(BaseModel):
    bucket: Literal["day", "week", "month"]
    items: list[TimelineItem]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]
