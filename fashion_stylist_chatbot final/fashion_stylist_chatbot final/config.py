"""Central configuration for AI Fashion Stylist."""
from pathlib import Path

# The project root is the folder containing this file.
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
PROCESSED_DIR = DATASET_DIR / "processed"
MODEL_DIR = BASE_DIR / "models"
DATABASE_DIR = BASE_DIR / "database"
REPORTS_DIR = BASE_DIR / "reports"

DATABASE_PATH = DATABASE_DIR / "fashion_stylist.db"
MODEL_PATH = MODEL_DIR / "category_model.joblib"
METRICS_PATH = REPORTS_DIR / "metrics.json"
CLASSIFICATION_REPORT_PATH = REPORTS_DIR / "classification_report.txt"
CONFUSION_MATRIX_PATH = REPORTS_DIR / "confusion_matrix.png"

DATASET_FILES = [
    "formal_wear.csv",
    "wedding_wear.csv",
    "party_wear.csv",
    "casual_wear.csv",
    "college_wear.csv",
]

RANDOM_STATE = 42
TEST_SIZE = 0.20