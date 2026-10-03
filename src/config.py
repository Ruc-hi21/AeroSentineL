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
RUL_CAP = 125
TEST_SIZE = 0.2

# Sensor selection
CONSTANT_STD_THRESHOLD = 0.01

# Component health analysis
BASELINE_CYCLES = 30
HEALTH_SMOOTHING = 5
ABNORMAL_QUANTILE = 0.99
RANGE_MARGIN = 0.1

# Feature engineering
ROLLING_WINDOW = 30

# Risk bands
RISK_BANDS = ["NORMAL", "AT_RISK", "HIGH_RISK", "FAILURE_LIKELY"]
RISK_LIMITS = {"FAILURE_LIKELY": 15, "HIGH_RISK": 30, "AT_RISK": 60}
LOW_CONFIDENCE = 0.6

# Training
OPTUNA_TRIALS = 0
CV_FOLDS = 3
RUL_INTERVAL = (0.1, 0.9)

# Explainability
TOP_K_FACTORS = 5
