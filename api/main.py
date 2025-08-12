"""
What: Minimal FastAPI app for Car Budget Buddy (snapshot, budget, compare)
Why: Give the frontend real JSON so I can iterate quickly; mirror the mock shapes
Inputs: HTTP JSON payloads for /snapshot, /budget, /compare
Outputs: JSON responses matching the mock API contracts
Future:
  - Real image/spec enrichment (Wikipedia/Commons, CarQuery) in /snapshot
  - Deterministic VED from GOV.UK tables
  - Better insurance estimator with postcode & risk groups
Author-notes:
  - Keep formulas transparent; round to 2 decimals at the edge of the API.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# ----------------------------
# App + CORS (dev-friendly)
# ----------------------------
load_dotenv()
app = FastAPI(title="Car Budget Buddy API", version="0.1.0")

allow_origins_env = os.getenv("ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in allow_origins_env.split(",")] if allow_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Pydantic models (payloads)
# ----------------------------
FuelType = Literal["Petrol", "Diesel", "Hybrid", "EV"]
Transmission = Literal["Manual", "Automatic"]

class SnapshotIn(BaseModel):
    make: str
    model: str
    year: int
    mileage: Optional[int] = None
    fuel: Optional[FuelType] = None
    transmission: Optional[Transmission] = None
    body: Optional[str] = None
    color: Optional[str] = None
    postcode: Optional[str] = None
    price: Optional[float] = None

class SnapshotOut(BaseModel):
    id: str
    summary: Dict[str, Any]
    photoThumbs: List[str]
    description: str

class InsuranceInputs(BaseModel):
    age: int = Field(27, ge=16, description="Driver age")
    yearsLicensed: int = Field(2, ge=0)
    ncbYears: int = Field(0, ge=0)
    claims5y: Literal["Y", "N"] = "N"
    points: int = Field(0, ge=0)
    postcode: Optional[str] = None
    parking: Optional[Literal["Street", "Drive", "Garage"]] = None
    usage: Optional[Literal["SDP", "SDP+Commute"]] = None

class VED(BaseModel):
    firstRegYYYYMM: Optional[str] = None
    co2: Optional[int] = None
    isEV: Optional[bool] = None

class BudgetIn(BaseModel):
    price: float = 0.0
    deposit: float = 0.0
    termMonths: int = 12
    aprPct: float = 0.0
    annualMileage: int = 8000
    fuelType: FuelType = "Petrol"
    economy: float = 45.0  # mpg for ICE; kWh/100km for EV
    unitPrice: float = 1.55  # £/L petrol/diesel OR £/kWh for EV
    parkingPerMonth: float = 0.0
    maintenancePerYear: Optional[float] = None
    insuranceInputs: Optional[InsuranceInputs] = None
    ved: Optional[VED] = None

class MonthlyOut(BaseModel):
    finance: float
    fuelOrCharge: float
    insurance: float
    ved: float
    parking: float
    maintenance: float
    total: float

class BudgetOut(BaseModel):
    monthly: MonthlyOut
    warnings: List[str]
    valueScore: str

class CompareIn(BaseModel):
    carA: BudgetIn
    carB: BudgetIn

class CompareOut(BaseModel):
    carA: BudgetOut
    carB: BudgetOut
    diffs: List[str]
    charts: Dict[str, Optional[str]]
    winner: Optional[Literal["A", "B"]]

# ----------------------------
# Utility functions (math)
# ----------------------------
UK_GALLON_LITRES = 4.54609
KM_PER_MILE = 1.60934
MILES_PER_100KM = 62.1371
IPT_RATE = 0.12  # Insurance Premium Tax 12%


def round2(x: float) -> float:
    return float(f"{x:.2f}")


def amortized_monthly_payment(principal: float, apr_pct: float, term_months: int) -> float:
    """Standard loan formula. Returns 0 if principal or APR are zero.
    Args:
        principal: amount financed (price - deposit)
        apr_pct: annual percentage rate in percent (e.g., 7.9)
        term_months: months
    Returns: monthly repayment
    """
    if principal <= 0 or apr_pct <= 0 or term_months <= 0:
        return 0.0
    r = (apr_pct / 100.0) / 12.0
    return principal * r / (1 - math.pow(1 + r, -term_months))


def fuel_monthly_cost(annual_mileage: int, fuel_type: FuelType, economy: float, unit_price: float) -> float:
    """Compute monthly energy cost.
    ICE: economy is mpg; convert to L/mile and multiply by £/L.
    EV: economy is kWh/100km; convert to kWh/mile and multiply by £/kWh.
    """
    miles_per_month = max(1.0, annual_mileage / 12.0)

    if fuel_type == "EV":
        # kWh per mile = (kWh per 100km) / miles per 100km
        kwh_per_mile = max(0.01, economy) / MILES_PER_100KM
        return miles_per_month * kwh_per_mile * unit_price
    else:
        # litres per mile from mpg (UK gallon)
        mpg = max(1.0, economy)
        litres_per_mile = UK_GALLON_LITRES / mpg
        return miles_per_month * litres_per_mile * unit_price


def insurance_estimate(inputs: Optional[InsuranceInputs]) -> float:
    """Very rough, transparent estimator for demo. Annual -> monthly + IPT.
    I will improve this later with postcode & risk groups.
    """
    if not inputs:
        annual = 600.0
    else:
        annual = 600.0
        if inputs.age < 25:
            annual *= 1.35
        if inputs.yearsLicensed < 2:
            annual *= 1.20
        annual *= (1 - min(inputs.ncbYears * 0.05, 0.35))
        if inputs.claims5y == "Y":
            annual *= 1.25
        if inputs.points >= 3:
            annual *= 1.10
        # TODO(arathi): add postcode, parking, usage multipliers later

    monthly = (annual * (1 + IPT_RATE)) / 12.0
    return monthly


def ved_monthly(ved: Optional[VED], fallback_is_ev: bool) -> float:
    """Placeholder until I wire real GOV.UK tables. EV=0, else flat £180/y.
    """
    is_ev = fallback_is_ev or bool(ved and ved.isEV)
    annual = 0.0 if is_ev else 180.0
    return annual / 12.0


def maintenance_monthly(maintenance_per_year: Optional[float]) -> float:
    if maintenance_per_year is None:
        return 35.0  # simple default
    return maintenance_per_year / 12.0


# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/snapshot", response_model=SnapshotOut)
def snapshot(payload: SnapshotIn) -> SnapshotOut:
    """Return representative images + spec table + tiny description.
    For now I use placeholder Unsplash images and echo the spec summary.
    """
    make = payload.make.strip().title()
    model = payload.model.strip().title()
    year = payload.year
    fuel = payload.fuel or "Petrol"
    transmission = payload.transmission or "Manual"
    body = payload.body or "Hatchback"

    title = f"{make} {model} ({year})"
    spec_list = [
        ["Fuel", fuel],
        ["Transmission", transmission],
        ["Body", body],
        ["Mileage", f"{payload.mileage} miles" if payload.mileage else "—"],
        ["Colour", payload.color or "—"],
        ["Postcode", payload.postcode or "—"],
        ["Asking Price", f"\u00A3{payload.price}" if payload.price else "—"],
    ]

    photo_thumbs = [
        "https://images.unsplash.com/photo-1483721310020-03333e577078?q=80&w=800",
        "https://images.unsplash.com/photo-1483729558449-99ef09a8c325?q=80&w=800",
        "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?q=80&w=800",
    ]

    description = (
        f"{title} • {fuel}, {transmission} {body}. Representative images shown. "
        f"Upload advert photos for exact interior/exterior."
    )

    return SnapshotOut(
        id=os.urandom(8).hex(),
        summary={"title": title, "specList": spec_list},
        photoThumbs=photo_thumbs,
        description=description,
    )


@app.post("/budget", response_model=BudgetOut)
def budget(payload: BudgetIn) -> BudgetOut:
    principal = max(0.0, (payload.price or 0.0) - (payload.deposit or 0.0))
    finance = amortized_monthly_payment(principal, payload.aprPct or 0.0, payload.termMonths or 0)

    fuel_charge = fuel_monthly_cost(
        annual_mileage=payload.annualMileage,
        fuel_type=payload.fuelType,
        economy=payload.economy,
        unit_price=payload.unitPrice,
    )

    insurance = insurance_estimate(payload.insuranceInputs)
    ved = ved_monthly(payload.ved, fallback_is_ev=(payload.fuelType == "EV"))
    maintenance = maintenance_monthly(payload.maintenancePerYear)
    parking = float(payload.parkingPerMonth or 0.0)

    monthly = {
        "finance": round2(finance),
        "fuelOrCharge": round2(fuel_charge),
        "insurance": round2(insurance),
        "ved": round2(ved),
        "parking": round2(parking),
        "maintenance": round2(maintenance),
    }
    total = round2(sum(monthly.values()))

    warnings: List[str] = []
    value_score = str(max(10, int(1000 - total)))

    return BudgetOut(monthly=MonthlyOut(total=total, **monthly), warnings=warnings, valueScore=value_score)


@app.post("/compare", response_model=CompareOut)
def compare(payload: CompareIn) -> CompareOut:
    a = budget(payload.carA)
    b = budget(payload.carB)

    diffs: List[str] = []
    for k in ["finance", "fuelOrCharge", "insurance", "ved", "parking", "maintenance", "total"]:
        da = getattr(a.monthly, k)
        db = getattr(b.monthly, k)
        diff = round2(da - db)
        if abs(diff) > 1.0:
            more = "higher" if diff > 0 else "lower"
            diffs.append(f"{k} is {more} by \u00A3{abs(diff):.2f} for Car A vs B.")

    winner: Optional[Literal["A", "B"]]
    if a.monthly.total < b.monthly.total:
        winner = "A"
    elif a.monthly.total > b.monthly.total:
        winner = "B"
    else:
        winner = None

    return CompareOut(
        carA=a,
        carB=b,
        diffs=diffs,
        charts={"barPng": None, "radarPng": None},  # TODO(arathi): generate later
        winner=winner,
    )