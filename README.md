[README.txt](https://github.com/user-attachments/files/21793211/README.txt)
# Account Reconciliation Tracker — Prototype

This folder contains a small Streamlit app you can deploy online (free) on Streamlit Community Cloud.

## Files
- app.py — the Streamlit app
- requirements.txt — Python dependencies
- Sample_Trial_Balance.xlsx — sample trial balance for testing

## Deploy ONLINE (Streamlit Community Cloud)
1. Create a free GitHub account if you don't have one: https://github.com
2. Create a new repository (name it e.g. recon-prototype).
3. Upload `app.py`, `requirements.txt`, and `Sample_Trial_Balance.xlsx` to the repository root.
4. Go to https://share.streamlit.io/ and sign in with GitHub.
5. Click **'New app'** → Select your repo and branch → set `app.py` as the app file → Deploy.
6. Wait for the build (1–2 minutes). Your app gets a public URL you can share with the team.

## Run LOCALLY (optional)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- Your checkmarks and timestamps are stored in a local file `recon_state.json` when running online or locally.
- Replace the sample Excel with your real trial balance when testing.
