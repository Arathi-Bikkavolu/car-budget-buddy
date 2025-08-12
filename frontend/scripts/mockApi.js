/* mockApi.js (v2)
 * What: client for API with a dev toggle; falls back to local mocks
 * Why: I want to flip a flag and hit FastAPI without rewriting pages
 */

const USE_REAL_API = true;                   // flip to false to go offline
const API_BASE = "http://localhost:8000";   // align with uvicorn port

export const Api = {
  snapshotEnrich: async (payload) => {
    if (USE_REAL_API) {
      return postJson(`${API_BASE}/snapshot`, payload);
    }
    return mockSnapshot(payload);
  },

  budgetEstimate: async (payload) => {
    if (USE_REAL_API) {
      return postJson(`${API_BASE}/budget`, payload);
    }
    return mockBudget(payload);
  },

  compare: async (payload) => {
    if (USE_REAL_API) {
      return postJson(`${API_BASE}/compare`, payload);
    }
    return mockCompare(payload);
  },
};

// ----------------- fetch helpers -----------------
async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ----------------- mock fallbacks (unchanged from earlier) -----------------
async function mockSnapshot(payload) {
  await wait(200);
  const make = (payload.make || "Make").trim();
  const model = (payload.model || "Model").trim();
  const year = payload.year || "2019";
  const fuel = payload.fuel || "Petrol";
  const transmission = payload.transmission || "Manual";
  const body = payload.body || "Hatchback";

  const title = `${make} ${model} (${year})`;
  const specList = [
    ["Fuel", fuel],
    ["Transmission", transmission],
    ["Body", body],
    ["Mileage", payload.mileage ? `${payload.mileage} miles` : "—"],
    ["Colour", payload.color || "—"],
    ["Postcode", payload.postcode || "—"],
    ["Asking Price", payload.price ? `\u00A3${payload.price}` : "—"],
  ];

  const photoThumbs = [
    "https://images.unsplash.com/photo-1483721310020-03333e577078?q=80&w=800",
    "https://images.unsplash.com/photo-1483729558449-99ef09a8c325?q=80&w=800",
    "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?q=80&w=800",
  ];

  const description = `${title} • ${fuel}, ${transmission} ${body}. A representative image is shown.`;

  return { id: crypto.randomUUID(), summary: { title, specList }, photoThumbs, description };
}

async function mockBudget(payload) {
  await wait(200);
  // same math as before (shortened here to keep file readable)
  const num = (v) => Number(String(v || "").replace(/[^\d.\-]/g, "")) || 0;
  const price = num(payload.price), deposit = num(payload.deposit);
  const term = Math.max(1, num(payload.termMonths) || 12);
  const apr = num(payload.aprPct) / 100;
  const annualMileage = Math.max(1, num(payload.annualMileage) || 8000);
  const fuelType = payload.fuelType || "Petrol";
  const economy = Math.max(1, num(payload.economy) || 45);
  const unitPrice = num(payload.unitPrice) || 1.55;
  const parking = num(payload.parkingPerMonth) || 0;

  const principal = Math.max(0, price - deposit);
  const r = apr / 12;
  const finance = principal > 0 && apr > 0 ? (principal * r) / (1 - Math.pow(1 + r, -term)) : 0;

  const milesPerMonth = annualMileage / 12;
  const litresPerMile = 4.54609 / (economy || 40);
  const fuelMonthly = fuelType === "EV"
    ? (milesPerMonth * (economy / 62.1371) * unitPrice)
    : (milesPerMonth * litresPerMile * unitPrice);

  const ii = payload.insuranceInputs || {};
  let insuranceBase = 600; if ((ii.age||27) < 25) insuranceBase *= 1.35; if ((ii.yearsLicensed||2) < 2) insuranceBase *= 1.20;
  insuranceBase *= (1 - Math.min((ii.ncbYears||0) * 0.05, 0.35)); if (ii.claims5y === "Y") insuranceBase *= 1.25; if ((ii.points||0) >= 3) insuranceBase *= 1.10;
  const insuranceMonthly = (insuranceBase * 1.12) / 12;

  const vedMonthly = (fuelType === "EV" ? 0 : 180/12);
  const maintenanceMonthly = (payload.maintenancePerYear ? payload.maintenancePerYear/12 : 35);

  const monthly = { finance, fuelOrCharge: fuelMonthly, insurance: insuranceMonthly, ved: vedMonthly, parking, maintenance: maintenanceMonthly };
  const total = Object.values(monthly).reduce((a, b) => a + b, 0);

  return { monthly: roundAll({ ...monthly, total }), warnings: [], valueScore: String(Math.max(10, 1000 - total).toFixed(0)) };
}

async function mockCompare(payload) {
  await wait(200);
  const a = await mockBudget(payload.carA);
  const b = await mockBudget(payload.carB);
  const diffs = [];
  const diffKeys = ["finance", "fuelOrCharge", "insurance", "ved", "parking", "maintenance", "total"];
  diffKeys.forEach(k => {
    const d = (a.monthly[k] || 0) - (b.monthly[k] || 0);
    if (Math.abs(d) > 1) diffs.push(`${k} is ${d > 0 ? "higher" : "lower"} by \u00A3${Math.abs(d).toFixed(2)} for Car A vs B.`);
  });
  const winner = a.monthly.total < b.monthly.total ? "A" : (a.monthly.total > b.monthly.total ? "B" : null);
  return { carA: a, carB: b, diffs, charts: { barPng: null, radarPng: null }, winner };
}

const wait = (ms) => new Promise(r => setTimeout(r, ms));
const roundAll = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, Number(v.toFixed(2))]));