"""Train a text-based occasion/outfit classifier from the updated dataset fields."""
import json
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from config import MODEL_DIR, MODEL_PATH, REPORTS_DIR, METRICS_PATH, CLASSIFICATION_REPORT_PATH, CONFUSION_MATRIX_PATH, RANDOM_STATE, TEST_SIZE
from src.data_loader import load_dataset


def _make_text(frame: pd.DataFrame) -> pd.Series:
    columns = ["outfit_name", "outfit_type", "clothing_items", "fabric", "recommended_colors", "styling_tips"]
    return frame[columns].fillna("").astype(str).agg(" ".join, axis=1).str.replace(r"\s+", " ", regex=True).str.strip()


def train_model():
    """Train/test the classification model, save it, and write evaluation reports.

    This model predicts the outfit's `occasion` (e.g., Formal Wear, Wedding Wear, Party Wear, Casual Wear, College Wear).
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    df = load_dataset()
    df = df[df["occasion"].str.strip().ne("")].copy()
    df["ml_text"] = _make_text(df)
    
    counts = df["occasion"].value_counts()
    eligible = df[df["occasion"].map(counts).ge(2)].copy()
    
    if eligible["occasion"].nunique() < 2 or len(eligible) < 10:
        raise ValueError("Not enough labeled occasion categories to train a meaningful classifier.")

    X_train, X_test, y_train, y_test = train_test_split(
        eligible["ml_text"], eligible["occasion"],
        test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=eligible["occasion"]
    )

    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=30000, sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE)),
    ])
    
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, predictions))
    labels = sorted(set(y_test) | set(predictions))
    report = classification_report(y_test, predictions, labels=labels, zero_division=0)
    cm = confusion_matrix(y_test, predictions, labels=labels)
    
    joblib.dump(model, MODEL_PATH)
    CLASSIFICATION_REPORT_PATH.write_text(str(report), encoding="utf-8")

    # Generate confusion matrix plot
    try:
        import matplotlib.pyplot as plt
        fig_width = max(8, min(18, len(labels) * 0.65))
        fig_height = max(6, min(16, len(labels) * 0.55))
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        image = ax.imshow(cm, interpolation="nearest", aspect="auto")
        ax.set_title("Outfit occasion classification — confusion matrix")
        fig.colorbar(image, ax=ax)
        ax.set_xlabel("Predicted occasion")
        ax.set_ylabel("Actual occasion")
        ax.set_xticks(range(len(labels)), labels=labels, rotation=45, fontsize=8)
        ax.set_yticks(range(len(labels)), labels=labels, fontsize=8)
        fig.tight_layout()
        fig.savefig(CONFUSION_MATRIX_PATH, dpi=160)
        plt.close(fig)
    except Exception as exc:
        print(f"Warning: could not create confusion matrix image: {exc}")

    metrics = {
        "task": "predict outfit occasion from outfit text fields",
        "target_column": "occasion",
        "algorithm": "TF-IDF + Logistic Regression",
        "total_eligible_rows": int(len(eligible)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "class_count": int(eligible["occasion"].nunique()),
        "accuracy": accuracy,
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "model_file": str(MODEL_PATH.name),
        "note": "Metrics are measured on the held-out test split.",
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    train_model()