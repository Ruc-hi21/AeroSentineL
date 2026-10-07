<p align="center">
  <img src="assets/banner.svg" alt="AeroSentinel — Airplane flying animation" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-In%20Progress-yellow?style=for-the-badge" alt="Status: In Progress" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/Dataset-NASA%20C--MAPSS-0B3D91?style=for-the-badge&logo=nasa&logoColor=white" alt="NASA C-MAPSS" />
</p>

# ✈️ AeroSentinel

> **Predicts Remaining Useful Life (RUL) and classifies failure risk — *Normal / At Risk / High Risk / Failure Likely* — for turbofan engine components, with explainable predictions behind every result.**

---

## 🖥️ Dashboard UI — Mission Control

A Streamlit "mission control" dashboard that calls the Python pipeline directly:

![3D Digital Twin — every sensor pinned to its engine station](assets/screenshot_digital_twin.png)

```bash
pip install -r requirements.txt
python -m scripts.download_data        # NASA C-MAPSS FD001 into data/raw/
python -m training.train               # trains model v2 (~6 min), writes reports/
streamlit run app/streamlit_app.py
```

| Page | What you get |
|---|---|
| **Mission Control** | Live 3D engine hologram, one-click sample launch, fleet threat radar (distance from centre = predicted RUL), animated KPIs, AI insights, 3D degradation surface |
| **Upload & Analyze** | Scanning drop zone, pipeline animation replaying each stage with the run's real numbers, then the uploaded data straight into the 3D twin |
| **3D Digital Twin** | Procedural Three.js turbofan (fan, LPC, HPC, combustor, HPT, LPT, nozzle) with all 21 sensors pinned to their engine stations, airflow particles, bloom, exploded view, diagnostic scan and a cycle-by-cycle **life replay**: sensors drift, modules heat up, the risk band escalates with alerts. Click any sensor for a deep-dive chart |
| Component Health · RUL & Risk · Explainability | Animated gauges, neon charts, SHAP drivers per unit |
| Model Evaluation · Error Analysis · Export | Verified metrics vs. baselines, per-band detail, forensics, CSV/JSON downloads |

Keyboard on the twin: `Space` play/pause · `E` exploded view · `S` scan · `C` cinema mode · `Esc` reset camera.
The 3D engine ships with a vendored Three.js r186 bundle (MIT), so it works offline.

---

## 🔍 Problem

Maintenance teams need to detect abnormal component conditions early and predict failure likelihood, so they can act **preventively** instead of relying on fixed maintenance schedules. Reading raw sensor telemetry manually is slow and easy to get wrong.

---

## 💡 Solution

AeroSentinel is a machine learning pipeline trained on the **NASA C-MAPSS FD001** turbofan engine degradation dataset. It cleans and analyzes sensor telemetry, predicts RUL via regression, classifies failure risk into four actionable bands, and explains which sensors drove each prediction — served through a Streamlit mission-control dashboard with a 3D digital twin.

---

## 📦 Dataset

| Property | Details |
|---|---|
| **Name** | NASA C-MAPSS FD001 |
| **Source** | [NASA Prognostics Data Repository](https://data.nasa.gov/dataset/C-MAPSS-Aircraft-Engine-Simulator-Data/xaut-bemq) |
| **Domain** | Turbofan engine degradation simulation |
| **Training units** | 100 engines — run-to-failure trajectories |
| **Test units** | 100 engines — partial trajectories |
| **Sensors** | 21 sensor channels + 3 operational settings per cycle |
| **Fault mode** | Single (HPC degradation) |
| **Operating condition** | Single (sea level) |
| **Target variable** | Remaining Useful Life (RUL) — cycles until failure |

---

## 🏗️ Architecture

```
Dataset Upload → Validation → Cleaning → Component Health Analysis
       ↓
Feature Engineering → RUL Regressor + Failure-Risk Classifier
       ↓
Explainability (SHAP) → Streamlit dashboard + Three.js digital twin
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

### Dashboard

| Technology | Purpose |
|---|---|
| Streamlit | Multi-page dashboard, custom component host |
| Three.js (vendored r186) | 3D digital twin: procedural turbofan, bloom, particles |
| Plotly | Neon-themed charts, 3D degradation surface |

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

## 📊 Evaluation Metrics (model v2)

| | Old model (v1) | **Model v2** |
|---|---|---|
| Risk accuracy · 5-fold CV over training engines | 0.889 | **0.943** |
| Risk accuracy · 20 held-out engines, every cycle | 0.883 | **0.941** |
| Risk macro-F1 · held-out engines | 0.798 | **0.880** |
| Risk accuracy · official test set (100 engines, last cycle) | 0.870 | **0.890** |
| RUL RMSE · held-out engines (cycles) | 15.07 | **8.62** |
| RUL RMSE · official test set (cycles) | 17.09 | **12.31** |
| RUL R² · official test set | 0.831 | **0.912** |

What changed: causal multi-scale features (rolling mean/std over 5/15/30 cycles, exponentially weighted means,
15/30/50-cycle trend slopes and drift from each engine's own early-life baseline — 197 features per cycle), and a risk
model that blends the XGBoost classifier with band probabilities implied by the XGBoost RUL regressor. Every choice was
made with GroupKFold CV on training engines only; the test set was scored once at the end.

On the 100-engine test set every risk-band miss is an adjacent band (8 of the 11 within 5 cycles of a band limit), and no
truly high-risk or failure-likely engine is predicted Normal. With one prediction per engine, test accuracy has a
standard error of about ±3 points.

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

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🤝 Contributing

Internal OJT capstone project — **not currently accepting external contributions**.


## Benchmark & Performance Standards

The predictive models within AeroSentinel adhere to C-MAPSS FD001 standards:
- **RUL Prediction Target**: RMSE < 18.0 cycles on withheld test units — v2 achieves 12.3.
- **Risk Classification Target**: Macro F1 > 0.85 across the four bands — v2 achieves 0.88 on held-out
  engines and 0.83 on the official test set.
- **Telemetry Latency**: Stream inference under 25ms per engine cycle.
