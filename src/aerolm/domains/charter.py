"""The v1 charter contract. Unknown facts remain null; airports are not inferred from cities."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlightLeg(StrictModel):
    origin: str | None = Field(default=None, pattern=r"^[A-Z]{3,4}$")
    destination: str | None = Field(default=None, pattern=r"^[A-Z]{3,4}$")
    departure_date: date | None = None
    departure_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    time_zone: Literal["UTC", "local"] | None = None


class CharterRequest(StrictModel):
    request_type: Literal["charter"] = "charter"
    trip_type: Literal["one_way", "round_trip", "multi_leg"] | None = None
    legs: list[FlightLeg] = Field(default_factory=list, max_length=20)
    passengers: int | None = Field(default=None, ge=1, le=1000, strict=True)
    aircraft_category: (
        Literal[
            "turboprop", "light_jet", "midsize_jet", "super_midsize_jet", "heavy_jet", "helicopter"
        ]
        | None
    ) = None
    aircraft_preference: str | None = Field(default=None, max_length=160)
    return_date: date | None = None
    budget: str | None = Field(default=None, max_length=160)
    special_requirements: list[str] = Field(default_factory=list, max_length=30)
    contact_email: str | None = Field(default=None, max_length=254)

    @model_validator(mode="after")
    def validate_itinerary(self) -> "CharterRequest":
        if self.return_date and self.legs and self.legs[0].departure_date:
            if self.return_date < self.legs[0].departure_date:
                raise ValueError("return_date must not precede departure_date")
        return self


def review_warnings(value: BaseModel, text: str) -> list[str]:
    data = CharterRequest.model_validate(value.model_dump())
    warnings = []
    if not data.legs or any(not leg.origin or not leg.destination for leg in data.legs):
        warnings.append("Confirm departure and arrival airports; city names are ambiguous.")
    if not data.legs or any(not leg.departure_date for leg in data.legs):
        warnings.append("Confirm departure dates, including the year.")
    if any(leg.departure_time and not leg.time_zone for leg in data.legs):
        warnings.append("Confirm the time zone for the requested departure time.")
    if data.passengers is None:
        warnings.append("Confirm passenger count.")
    if data.trip_type == "round_trip" and data.return_date is None:
        warnings.append("Confirm return date.")
    warnings.append("Human review required before quoting, dispatching, or booking.")
    return warnings
