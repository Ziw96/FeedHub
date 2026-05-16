from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class Transaction:
    project: str
    street: str
    district: str
    market_segment: Optional[str]
    property_type: str
    type_of_sale: str
    contract_date: str
    price_sgd: Optional[int]
    area_sqft: Optional[float]
    area_sqm: Optional[float]
    unit_price_psf: Optional[int]
    type_of_area: Optional[str]
    tenure: Optional[str]
    floor_range: Optional[str]
    no_of_units: int = 1
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d
