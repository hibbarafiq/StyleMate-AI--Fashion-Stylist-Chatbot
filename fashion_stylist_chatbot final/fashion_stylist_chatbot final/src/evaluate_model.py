"""Inspect model reports and run a simple saved-model prediction check."""
import json
import joblib
from config import MODEL_PATH, METRICS_PATH, CLASSIFICATION_REPORT_PATH
from src.data_loader import load_dataset


def evaluate_saved_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError("Trained model not found. Run: python -m src.train_model")
    model = joblib.load(MODEL_PATH)
    df = load_dataset()
    sample = df.iloc[0]
    text = " ".join(str(sample.get(col, "")) for col in [
        "outfit_name", "outfit_type", "clothing_items", "fabric", "recommended_colors"
    ])
    prediction = str(model.predict([text])[0]) if model else "N/A"
    result = {
        "sample_outfit_id": str(sample["outfit_id"]),
        "actual_occasion": str(sample["occasion"]),
        "predicted_category": prediction,
        "metrics_file_exists": METRICS_PATH.exists(),
        "classification_report_exists": CLASSIFICATION_REPORT_PATH.exists(),
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    evaluate_saved_model()