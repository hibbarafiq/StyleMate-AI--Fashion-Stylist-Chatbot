"""Clean and export combined StyleMate Fashion dataset tables."""
import json
import pandas as pd
from sklearn.model_selection import train_test_split
from config import PROCESSED_DIR, REPORTS_DIR
from src.data_loader import load_dataset, dataset_summary


def preprocess_data():
    """Create normalized combined dataset tables and a reproducible train/test split.

    The ML target is the `occasion` field (e.g., Formal Wear, Wedding Wear, Party Wear, Casual Wear, College Wear).
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    df = load_dataset()

    # Trim text cells while preserving internal spacing/punctuation
    for column in df.columns:
        if df[column].dtype == "object":
            df[column] = df[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )

    # Filter non-empty rows and construct ML text representation
    df = df[df["occasion"].str.strip().ne("")].copy()
    feature_cols = [
        "outfit_name", "outfit_type", "clothing_items",
        "recommended_colors", "fabric", "footwear", "styling_tips"
    ]
    df["ml_text"] = df[feature_cols].agg(" ".join, axis=1).str.replace(r"\s+", " ", regex=True).str.strip()
    df = df[df["ml_text"].str.len().gt(0)].copy()

    # Export combined processed dataset
    df.to_csv(PROCESSED_DIR / "processed_fashion_dataset.csv", index=False, encoding="utf-8-sig")

    # Perform reproducible stratified train/test split
    counts = df["occasion"].value_counts()
    eligible = df[df["occasion"].map(counts).ge(2)].copy()
    rare = df[df["occasion"].map(counts).lt(2)].copy()

    if len(eligible) >= 5 and eligible["occasion"].nunique() >= 2:
        train, test = train_test_split(
            eligible, test_size=0.20, random_state=42, stratify=eligible["occasion"]
        )
        train = pd.concat([train, rare], ignore_index=True)
    else:
        train = df.copy()
        test = df.iloc[0:0].copy()

    train.to_csv(PROCESSED_DIR / "train.csv", index=False, encoding="utf-8-sig")
    test.to_csv(PROCESSED_DIR / "test.csv", index=False, encoding="utf-8-sig")

    # Generate summary report
    summary = dataset_summary(df)
    summary["clean_outfit_rows"] = int(len(df))
    summary["train_rows"] = int(len(train))
    summary["test_rows"] = int(len(test))
    summary["target_column"] = "occasion"

    (REPORTS_DIR / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(preprocess_data(), indent=2, ensure_ascii=False))