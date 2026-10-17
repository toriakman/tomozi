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
- 73 suggested apple varieties, plus custom apples.
- Ratings 0.0–10.0 and optional notes.
- Autosave and completion states; submitting makes ratings final.
- Separate confirmation, results-ready screen, and results sharing.
- Host can open, close, reopen, remove accidental participants.
- Results use submitted ratings and recalculate after reopening.
- Participant-facing tasting pages never receive apple names.

## Next iteration
- Add true QR rendering (currently shareable URL).
- Add a staged, one-at-a-time reveal mode.
- Add browser-local participant resume.
- Choose and configure public hosting with persistent storage.

## Hosting

Use Python 3.12 or newer and install `requirements.txt`. Start the production
server with `gunicorn app:app` from the project root; `gunicorn.conf.py` uses
one process and four threads and binds to the hosting provider's `PORT`.
Do not expose the Flask debug server on the public Internet.

Set `APPLE_TASTING_DATA_DIR` to a directory on the hosting provider's persistent
volume. The directory is created if needed, and the app initializes its SQLite
database there. Without this setting, local previews use a database beside
`app.py`. An ephemeral hosting filesystem will lose that database on a redeploy;
use persistent storage before running a real tasting. Keep backups of this
volume and use a single service instance with this SQLite deployment.

The current startup has been tested with a functional create request and a
server restart to verify data retention. Public hosting, HTTPS, and access from
another device still need validation after selecting a provider. Mac preview
data is separate from a new hosted installation.

Host and participant URLs are private access links; save the host dashboard URL.
The share button includes only a summary and the results URL. The production
server omits access logging because request paths contain these private tokens.

## Tests

Run `python -m unittest discover -s tests -v` after installing dependencies.
