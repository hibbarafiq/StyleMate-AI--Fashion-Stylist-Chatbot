# StyleMate AI — Fashion Stylist Chatbot

StyleMate AI is a local, text-only conversational fashion stylist built with Streamlit, Python, SQLite, and the supplied FashionStylist CSV catalog. It combines transparent rule-based NLP, catalog matching, substitution rules, and an optional TF-IDF + Logistic Regression model for item-category classification.

## Start the app on Windows

**Easiest method:** double-click `RUN_STYLEMATE.bat`. On first run it creates a project virtual environment and installs the packages in `requirements.txt`; this requires an internet connection. When the browser opens, keep the black terminal window open while using StyleMate.

Recommended Python version: **3.12** (Python 3.11 is also supported). The launcher now checks several installed Python versions and writes virtual-environment setup details to `setup_python.log` if it cannot create the environment. If Python is not found, install Python 3.12 from the official Python website and tick **Add python.exe to PATH** during installation. Then reopen VS Code/File Explorer and double-click the launcher again.

Manual start (optional):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

## Main features

- **Chat-style UI:** compact layout, StyleMate branding, quick-start prompts, and contextual one-click replies.
- **Conversational follow-ups:** gathers missing wearer, occasion, age, skin tone, height, and season/weather details in one concise prompt; optional personal details can be skipped.
- **Personalization:** recognizes supported preferences such as season, color, style, modest/Eastern/Western preference, and optional fit/body/skin-tone details when explicitly stated.
- **Alternatives:** suggests substitutions for common unavailable or rejected items. The ranking engine excludes catalog looks that mention a stated unavailable/disliked item; if no suitable look remains, it says so rather than silently repeating the rejected item.
- **Transparent recommendation match:** ranks catalog looks against the details supplied and displays a weighted match percentage. This is a catalog-fit score, not a model accuracy or guarantee.
- **Persistent, isolated chat context:** SQLite stores messages and a separate working profile for each conversation. A new chat starts without the previous chat's event, occasion, or weather details.
- **Preference memory toggle:** when enabled, stable personal preferences can be reused across chats. Event-specific details remain in their original conversation; turning memory off disables cross-chat preference saving.
- **Original data and trained model:** the source CSVs, processed CSVs, trained model, and existing reports are preserved in this package.
- **Regression tests:** greetings, intent routing, contextual alternatives, recommendation exclusions, isolated chat profiles, preference-memory boundaries, database persistence, and titles are covered.

## Project structure

```text
fashion_stylist_chatbot/
├── app.py                         # Streamlit UI and interaction flow
├── database.py                    # SQLite persistence layer
├── config.py                      # Paths, dataset file names, model settings
├── requirements.txt               # Python dependencies
├── RUN_STYLEMATE.bat              # Windows double-click launcher
├── README.md                      # Setup and project notes
├── .streamlit/config.toml         # UI theme defaults
├── assets/stylemate_logo.svg      # Project logo asset
├── dataset/
│   ├── Child/                      # Original item/look CSV files
│   ├── Female/                     # Original item/look CSV files
│   ├── Male/                       # Original item/look CSV files
│   └── processed/                  # Prepared catalog/train/test CSVs
├── models/category_model.joblib    # Existing trained item-category model
├── reports/                        # Classification metrics and reports
├── database/                       # SQLite database created on first run
├── src/
│   ├── nlp_processor.py            # Intent and preference extraction
│   ├── chat_controller.py          # Conversation flow orchestration
│   ├── conversation_manager.py     # In-chat profile/context updates
│   ├── recommendation_engine.py    # Catalog filtering and ranking
│   ├── alternatives.py              # Rule-based item substitutions
│   ├── response_generator.py       # Chat response formatting
│   ├── data_loader.py              # CSV loading and validation
│   ├── preprocessing.py            # Dataset preparation
│   ├── train_model.py               # Model training
│   └── evaluate_model.py            # Held-out evaluation
└── tests/
    ├── test_core.py                 # Regression tests
    └── RUN_TESTS.bat                # Windows test launcher
```

## Dataset and model

The source files are kept in their original locations and names:

```text
dataset/Child/label(p1-841).csv
dataset/Child/look(b1-200).csv
dataset/Female/label(p1-2406).csv
dataset/Female/look(b1-500).csv
dataset/Male/label(p1-1390).csv
dataset/Male/look(b1-300).csv
```

Do not rename these CSV files unless you also update `GROUPS` in `config.py`. The project uses text and structured CSV fields only; it does not use a photo dataset or computer vision.

The included model predicts an item's original `category` from text fields using TF-IDF + Logistic Regression. The held-out accuracy in `reports/metrics.json` is about **98.28%** for the item-category classification task. This is **not** an outfit-recommendation accuracy score. The chatbot does not display this classifier score as if it measured styling quality. The app's recommendations use transparent catalog filtering/ranking rules.

## Chat history and preference storage

- The local SQLite database is created under `database/` when the app first runs. Existing databases are migrated to store a working profile per conversation.
- Chat messages and preference memory remain on the same computer unless the database file is manually moved or deleted.
- The app is intended for a university project/demo, not a multi-user production service. Avoid entering sensitive personal information.
- Existing conversations with no messages are not shown in the sidebar.

## Run the regression tests

With the project virtual environment activated:

```powershell
python -m unittest discover -s tests -v
```

Or double-click `tests/RUN_TESTS.bat`.

The included regression suite covers 31 core behaviors. Passing these tests does not guarantee every possible interaction is bug-free; test the app manually before a class demonstration.

## Current limitations

- NLP uses explicit, transparent keyword/rule extraction, not a hosted generative AI model. It can miss unusual wording or ambiguous requests.
- The original catalog does not provide reliable dedicated labels for every user's skin tone, height, body shape, modesty, or fit preference. Those preferences are kept as conversational context but cannot be guaranteed by catalog matching.
- Substitution ideas are hand-written rules, not learned predictions. Catalog availability is not live shopping stock.
- The model is optional for chat recommendations; its main ML task is item-category classification.
