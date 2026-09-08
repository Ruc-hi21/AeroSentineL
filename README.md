<p align="center">
  <img src="https://img.shields.io/badge/Status-In%20Progress-yellow?style=for-the-badge" alt="Status: In Progress" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/Dataset-NASA%20C--MAPSS-0B3D91?style=for-the-badge&logo=nasa&logoColor=white" alt="NASA C-MAPSS" />
</p>

# ✈️ AeroSentinel

> **Predicts Remaining Useful Life (RUL) and classifies failure risk — *Normal / At Risk / High Risk / Failure Likely* — for turbofan engine components, with explainable predictions behind every result.**

**Team-88** — Aarohi & Prem

---

## ⚠️ Implementation Status

> [!IMPORTANT]
> This README describes the **intended, complete system**. The table below shows what's actually built right now.

| Component | Status |
|---|---|
| Data pipeline (`load_data`, `clean_data`, `compute_rul`, `split_by_unit`) | ✅ Built and verified against real data |
| Sensor degradation analysis (correlation + monotonicity ranking) | ✅ Built and verified against real data |
| Component health analysis | ❌ Not started |
| RUL regression model | ❌ Not started |
| Failure-risk classifier (4-band) | ❌ Not started |
| Explainability (SHAP) | ❌ Not started |
| Backend API (FastAPI) | ❌ Not started |
| Frontend dashboard (React) | ❌ Not started |

---

## 🔍 Problem

Maintenance teams need to detect abnormal component conditions early and predict failure likelihood, so they can act **preventively** instead of relying on fixed maintenance schedules. Reading raw sensor telemetry manually is slow and easy to get wrong.

---

## 💡 Solution

AeroSentinel is a machine learning pipeline trained on the **NASA C-MAPSS FD001** turbofan engine degradation dataset. It cleans and analyzes sensor telemetry, predicts RUL via regression, classifies failure risk into four actionable bands, and explains which sensors drove each prediction — served through a FastAPI backend and a React dashboard.

> [!NOTE]
> **Dataset note:** The project brief originally referenced an unrelated Telecom Churn dataset. This was identified as a mismatch and corrected to NASA C-MAPSS FD001, which actually supports RUL regression and degradation analysis. See `docs/22_ADRs.md` (ADR-008) for the full record of that decision.

---

## 🏗️ Architecture

```
Dataset Upload → Validation → Cleaning → Component Health Analysis
       ↓
Feature Engineering → RUL Regressor + Failure-Risk Classifier
       ↓
Explainability (SHAP) → FastAPI → React Dashboard
```

Full design rationale lives in `docs/` — see [Documentation](#-documentation) below.

---

## 🛠️ Tech Stack

### Backend / ML

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core language |
| pandas, numpy | Data handling |
| scikit-learn | Baselines, preprocessing, metrics |
| XGBoost | RUL regression, failure-risk classification |
| SHAP | Explainability |
| FastAPI | REST API |

### Frontend

| Technology | Purpose |
|---|---|
| React | UI framework |
| Vite | Build tooling |
| Recharts | Degradation curves, health timeline charts |

---

## ✨ Features

- **Dataset upload & validation** — ingest raw sensor telemetry with schema checks
- **Data cleaning** — handle missing values, duplicates, type errors
- **Component health analysis** — classify components as normal or abnormal
- **Degradation curve visualization** — track sensor drift over engine cycles
- **RUL regression** — predict cycles remaining until failure
- **4-band failure-risk classification** — Normal / At Risk / High Risk / Failure Likely
- **Explainability** — surface top contributing sensors per prediction via SHAP
- **Model evaluation dashboard** — interactive metrics and performance views

---

## 📊 Evaluation Metrics

| Category | Metrics | Status |
|---|---|---|
| **Regression** | RMSE, MAE | 🔜 TBD — not yet measured |
| **Classification** | Accuracy, Precision, Recall, F1-Score, ROC-AUC per risk band | 🔜 TBD — not yet measured |

> Numbers will be filled in once both models are trained — see `docs/10_Model_Card.md` for the same discipline applied in full.

---

## 📁 Project Structure

```
aerosentinel/
├── docs/                    # Full documentation set — BRD, PRD, TRD, HLD, LLD, etc.
├── src/
│   ├── data/                # ✅ Built — load, clean, compute RUL, split
│   ├── analysis/            # ✅ Built — sensor degradation ranking
│   ├── features/            # ❌ Not yet built
│   ├── models/              # ❌ Not yet built
│   └── explainability/      # ❌ Not yet built
├── backend/                 # ❌ Not yet built — FastAPI
├── frontend/                # ❌ Not yet built — React + Vite
├── data/
│   ├── raw/                 # Place dataset files here
│   └── processed/           # Pipeline outputs
├── tests/
└── requirements.txt
```

---

## 🔌 API Reference

> [!NOTE]
> Not yet implemented — specification only. See `docs/07_API_Specification.md`.

| Endpoint | Purpose |
|---|---|
| `POST /analyze` | Submit a dataset for analysis |
| `GET /analyze/{jobId}` | Retrieve results: health, RUL, risk band, top contributing sensors |
| `GET /model-metrics` | Versioned evaluation metadata |
| `GET /health` | Service / model readiness |

Once the backend exists, interactive docs will be auto-generated by FastAPI at `/docs`.

---

## 📚 Documentation

Full design documentation lives in `docs/`:

> BRD · PRD · TRD · HLD · LLD · Database Design · API Specification · UX Requirements · Data Science Architecture · Model Card · Security · Testing Strategy · CI/CD · Observability · Deployment · Roadmap

---

## ⚠️ Limitations

- Trained and evaluated on **FD001 only** — a single operating condition and single fault mode, not the full C-MAPSS complexity.
- **Simulated data**, not real operational aircraft telemetry.
- Small engine count (**100 training units**) — meaningful overfitting risk.
- Risk-band thresholds are a **design choice**, not a validated regulatory standard.

---

## 🛡️ Responsible Use

> [!CAUTION]
> AeroSentinel is a **decision-support tool**. It is **not** a certified airworthiness determination, must **not** be used for real-time in-flight safety decisions, and does **not** replace certified maintenance procedures. Predictions inform human review — they do not trigger autonomous maintenance action.

---

## 👥 Team

**Team-88** — Aarohi & Prem

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🤝 Contributing

Internal OJT capstone project — **not currently accepting external contributions**.