"""Load and validate the updated StyleMate Fashion CSV files."""
from pathlib import Path
from typing import Optional
import pandas as pd
from config import DATASET_DIR

DATASET_FILES = [
    "formal_wear.csv",
    "wedding_wear.csv",
    "party_wear.csv",
    "casual_wear.csv",
    "college_wear.csv",
]

EXPECTED_COLUMNS = [
    "outfit_id", "gender", "age_group", "occasion", "specific_event",
    "outfit_name", "outfit_type", "clothing_items", "recommended_colors",
    "skin_tone", "skin_tone_color_match", "body_type", "height_category",
    "season", "fabric", "footwear", "earrings", "jewelry", "watch",
    "bag_or_clutch", "other_accessories", "dupatta_or_scarf_styling",
    "styling_tips", "modesty_level"
]


def _read_csv(path: Path) -> pd.DataFrame:
    """Read UTF-8/UTF-8-BOM CSV data."""
    if not path.exists():
        raise FileNotFoundError(f"Required dataset file was not found: {path}")
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        # Strip string whitespace from headers and values
        df.columns = [c.strip() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].str.strip()
        return df
    except Exception as exc:
        raise ValueError(f"Could not read CSV file {path}: {exc}") from exc


def resolve_dataset_dir(base_dir: Path = DATASET_DIR) -> Path:
    """Locate the folder containing the 5 CSV files."""
    candidates = [
        Path(base_dir),
        Path("dataset"),
        Path("StyleMate_Dataset/dataset"),
        Path("StyleMate_Dataset"),
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "formal_wear.csv").exists():
            return candidate
    raise FileNotFoundError(f"Could not locate dataset CSV files in candidates: {candidates}")


def load_dataset(dataset_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load and concatenate all 5 CSV category files into a single unified DataFrame."""
    target_dir = resolve_dataset_dir(dataset_dir or DATASET_DIR)
    dfs = []
    
    for filename in DATASET_FILES:
        filepath = target_dir / filename
        df = _read_csv(filepath)
        
        missing = set(EXPECTED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"File {filename} is missing required columns: {missing}")
            
        dfs.append(df)

    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df


def dataset_summary(df: pd.DataFrame) -> dict:
    """Return summary metrics for logging and verification."""
    return {
        "total_outfits": int(len(df)),
        "by_occasion": {str(k): int(v) for k, v in df.groupby("occasion").size().items()},
        "by_age_group": {str(k): int(v) for k, v in df.groupby("age_group").size().items()},
        "by_gender": {str(k): int(v) for k, v in df.groupby("gender").size().items()},
    }