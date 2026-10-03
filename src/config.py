"""Project-wide settings. Change values here, not inside the modules."""

from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = ROOT / "data" / "raw"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

# Dataset & reproducibility
DATASET = "FD001"
MODEL_VERSION = "v1"
SEED = 42

# Raw C-MAPSS columns (26 per row)
ID_COLS = ["unit", "cycle"]
SETTING_COLS = [f"setting_{i}" for i in range(1, 4)]
SENSOR_COLS = [f"sensor_{i}" for i in range(1, 22)]
RAW_COLUMNS = ID_COLS + SETTING_COLS + SENSOR_COLS

# Labeling & split
RUL_CAP = 125  # early-life cycles treated as equally healthy (piecewise-linear target)
TEST_SIZE = 0.2  # fraction of engine units held out for validation

# Sensor selection
CONSTANT_STD_THRESHOLD = 0.01  # sensors with lower std carry no signal

# Component health analysis
BASELINE_CYCLES = 30
HEALTH_SMOOTHING = 5
ABNORMAL_QUANTILE = 0.99
RANGE_MARGIN = 0.1

# Feature engineering
ROLLING_WINDOW = 30  # chosen on validation units: 5/10/20/30 tried, 30 lowest RMSE

# Risk bands, most severe first: a unit falls in the first band whose RUL limit it is <= to.
# These limits are a design choice, not a validated standard.
RISK_BANDS = ["NORMAL", "AT_RISK", "HIGH_RISK", "FAILURE_LIKELY"]
RISK_LIMITS = {"FAILURE_LIKELY": 15, "HIGH_RISK": 30, "AT_RISK": 60}
LOW_CONFIDENCE = 0.6  # risk predictions with lower probability are flagged for review

# Training
# 0 = use default XGBoost params (~20 s). On FD001, 20 Optuna trials took ~4 min
# and changed validation RMSE by < 0.1, so tuning is opt-in: --trials 20
OPTUNA_TRIALS = 0
CV_FOLDS = 3
RUL_INTERVAL = (0.1, 0.9)

# Explainability
TOP_K_FACTORS = 5
