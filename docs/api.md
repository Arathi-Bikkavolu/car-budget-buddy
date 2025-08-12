# API (v0.1.0)

Base URL (dev): http://localhost:8000

## POST /snapshot

Req (example):
{
"make": "Toyota", "model": "Yaris", "year": 2018,
"mileage": 42000, "fuel": "Petrol", "transmission": "Manual",
"body": "Hatchback", "color": "Grey", "postcode": "EH1 1YZ", "price": 6500
}
Res (shape):
{ id, summary: { title, specList: [[k,v], ...] }, photoThumbs: [..], description }

## POST /budget

Req (example): see the Budget page form; matches the frontend payload.
Res (shape): { monthly: { finance, fuelOrCharge, insurance, ved, parking, maintenance, total }, warnings: [], valueScore }

## POST /compare

Req: { carA: <BudgetIn>, carB: <BudgetIn> }
Res: { carA: <BudgetOut>, carB: <BudgetOut>, diffs: [..], charts: {barPng, radarPng}, winner }
