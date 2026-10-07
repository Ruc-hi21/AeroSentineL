"""Project-wide settings. Change values here, not inside the modules."""

from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]  # repo root; parents[0]=src, parents[1]=repo
RAW_DATA_DIR = ROOT / "data" / "raw"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

# Dataset & reproducibility
DATASET = "FD001"
MODEL_VERSION = "v2"  # v2: multi-scale trend/drift features + blended risk ensemble
SEED = 42

# Raw C-MAPSS columns (26 per row)
ID_COLS = ["unit", "cycle"]
SETTING_COLS = [f"setting_{i}" for i in range(1, 4)]
SENSOR_COLS = [f"sensor_{i}" for i in range(1, 22)]  # sensor_1..sensor_21 per C-MAPSS spec
RAW_COLUMNS = ID_COLS + SETTING_COLS + SENSOR_COLS

# Labeling & split
RUL_CAP = 125  # early-life cycles treated as equally healthy (piecewise-linear target)
TEST_SIZE = 0.2  # fraction of engine units held out for validation

# Sensor selection
CONSTANT_STD_THRESHOLD = 0.01  # sensors with lower std carry no signal

# Component health analysis
BASELINE_CYCLES = 30  # first N cycles of each training engine = healthy reference
HEALTH_SMOOTHING = 5  # rolling window used to smooth the health score
ABNORMAL_QUANTILE = 0.99  # health score above this baseline quantile = abnormal
# Health score above this multiple of the abnormal threshold = critical. On FD001 validation
# units the threshold is ~1.0 and engines within 15 cycles of failure have a median score ~3.
CRITICAL_HEALTH_MULTIPLE = 2.0
RANGE_MARGIN = 0.1  # readings beyond training min/max by this share of the range are flagged

# Feature engineering (all causal: a feature at cycle t only uses cycles <= t of the same unit).
# Chosen by 5-fold GroupKFold CV on the training engines: going from one 30-cycle window to
# these multi-scale stats, trends and drift raised CV risk accuracy 0.889 -> 0.946 and cut
# CV RUL RMSE 15.3 -> 8.9 cycles.
ROLLING_WINDOW = 30  # sensor-trend smoothing in sensor scoring; shorter unit histories are flagged for review
ROLLING_WINDOWS = (5, 15, 30)  # rolling mean / std
EWM_ALPHAS = (0.05, 0.1, 0.3)  # exponentially weighted means: slow to fast memory
SLOPE_WINDOWS = (15, 30, 50)  # least-squares trend of each sensor over the last N cycles
BASELINE_CYCLES_PER_UNIT = 15  # drift = smoothed reading minus the unit's own first-N-cycle mean
DRIFT_SMOOTHING = 5

# Risk bands, most severe first: a unit falls in the first band whose RUL limit it is <= to.
# These limits are a design choice, not a validated standard.
RISK_BANDS = ["NORMAL", "AT_RISK", "HIGH_RISK", "FAILURE_LIKELY"]
RISK_LIMITS = {"FAILURE_LIKELY": 15, "HIGH_RISK": 30, "AT_RISK": 60}
LOW_CONFIDENCE = 0.6  # risk predictions with lower probability are flagged for review
# Risk = (1 - blend) * classifier probabilities + blend * band probabilities implied by the RUL
# regressor (Gaussian with this sd around its prediction). blend is picked by CV during training.
RISK_BLEND_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
RISK_BLEND_SIGMA = 8.0  # cycles

# Training
# 0 = use default XGBoost params (~20 s). On FD001, 20 Optuna trials took ~4 min
# and changed validation RMSE by < 0.1, so tuning is opt-in: --trials 20
OPTUNA_TRIALS = 0
CV_FOLDS = 3  # GroupKFold splits for optional Optuna tuning
REPORT_CV_FOLDS = 5  # GroupKFold splits for the reported CV metrics and the blend choice
RUL_INTERVAL = (0.1, 0.9)  # quantile pair yielding the 80% prediction interval

# Explainability
TOP_K_FACTORS = 5  # top SHAP sensors returned per unit in the dashboard
