# Apple Tasting

A mobile-first blind apple tasting app.

## Run locally
1. `python -m venv .venv`
2. Activate it.
3. `pip install -r requirements.txt`
4. `python app.py`
5. Open http://localhost:5000

SQLite is created automatically on first run.

## V1 behavior
- No accounts/login.
- Host gets an unguessable private admin URL.
- Participants join by name.
- Up to 50 numbered apples.
- Custom apples supported.
- Ratings 0.0–10.0 and optional notes.
- Autosave and completion states.
- Host can open, close, reopen, remove accidental participants.
- Results use submitted ratings and recalculate after reopening.
- Participant-facing tasting pages never receive apple names.

## Next iteration
- Add true QR rendering (currently shareable URL).
- Expand/import the apple catalog after confirming a permitted data source.
- Add a staged, one-at-a-time reveal mode.
- Add browser-local participant resume.
- Add production database/deployment configuration.
