from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.service import ServiceCategory
from app.schemas.service import ServiceCreate


def make(**overrides: Any) -> ServiceCreate:
    data: dict[str, Any] = {
        "name": "City Hospital",
        "category": "hospital",
        "latitude": 28.6,
        "longitude": 77.2,
    }
    data.update(overrides)
    return ServiceCreate.model_validate(data)


def test_valid_minimal() -> None:
    service = make()
    assert service.rating is None
    assert service.metadata is None


@pytest.mark.parametrize("raw", ["ATM", "atm", "Atms", " atm ", "ATMS"])
def test_category_is_case_insensitive(raw: str) -> None:
    assert make(category=raw).category is ServiceCategory.ATM


@pytest.mark.parametrize("raw", ["bank", "", "s", 3])
def test_unknown_category_rejected(raw: object) -> None:
    with pytest.raises(ValidationError):
        make(category=raw)


def test_name_is_trimmed() -> None:
    assert make(name="  Corner Shop  ").name == "Corner Shop"


@pytest.mark.parametrize("name", ["", "   ", "x" * 201])
def test_bad_names_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        make(name=name)


def test_name_of_200_chars_after_trim_ok() -> None:
    assert len(make(name=" " + "x" * 200 + " ").name) == 200


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", 90.1),
        ("latitude", -91),
        ("longitude", 180.01),
        ("longitude", -200),
        ("latitude", float("nan")),
        ("longitude", float("inf")),
        ("latitude", "NaN"),
        ("longitude", "-Infinity"),
    ],
)
def test_bad_coordinates_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        make(**{field: value})


@pytest.mark.parametrize("rating", [0, 5, 4.5, "3.0", Decimal("2.50")])
def test_valid_ratings(rating: object) -> None:
    assert make(rating=rating).rating is not None


@pytest.mark.parametrize("rating", [-0.1, 5.1, 4.55, "NaN", "Infinity"])
def test_invalid_ratings(rating: object) -> None:
    with pytest.raises(ValidationError):
        make(rating=rating)


@pytest.mark.parametrize("metadata", [[1, 2], "text", 42, True])
def test_metadata_must_be_object(metadata: object) -> None:
    with pytest.raises(ValidationError):
        make(metadata=metadata)


def test_metadata_size_capped() -> None:
    assert make(metadata={"k": "v" * 10_000}).metadata is not None
    with pytest.raises(ValidationError):
        make(metadata={"k": "v" * 10_300})
