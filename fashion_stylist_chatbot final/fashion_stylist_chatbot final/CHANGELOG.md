# StyleMate AI update notes

## Updated package

- Added a compact, branded Streamlit chat layout with a warm neutral/purple theme.
- Added contextual one-click replies for common follow-up questions and quick-start prompts.
- Changed New Chat so an empty conversation is not inserted into SQLite until the first message is sent.
- Updated chat history listing to hide conversations that contain no messages.
- Made first-message titles cleaner and more readable.
- Added optional explicit capture of fit, height, skin-tone, and body-shape preference wording without claiming the catalog can guarantee those matches.
- Changed catalog ranking to exclude looks that mention user-rejected or unavailable items instead of merely penalizing them.
- Added clear feedback when no catalog look remains after applying exclusions.
- Added a Windows double-click launcher, a project theme, a logo asset, setup documentation, and regression tests.
- Preserved the original CSVs, processed catalog files, existing model, and classification reports from the packaged project.

## Validation performed for this package

- Python syntax compilation completed successfully for the app, database, source modules, and tests.
- Seven automated regression tests passed: preference extraction, unavailable-item extraction, optional fit preference, substitution rules, recommendation exclusion, empty-chat history behaviour, and persistent chat/title behaviour.
- A full Streamlit browser session was not launched in the packaging environment because Streamlit is not installed there. The Windows launcher checks dependencies and installs `requirements.txt` on first run.
