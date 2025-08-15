
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os

st.set_page_config(page_title="Account Reconciliation Tracker", layout="wide")

st.title("Month-End Account Reconciliation — Prototype")
st.caption("Upload trial balance, mark reconciliations & reviews, and store SharePoint links.")

STATE_FILE = "recon_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

state = load_state()

st.sidebar.header("Controls")
view = st.sidebar.selectbox("View mode", ["Kontoplan-rækkefølge", "Rapporteringskategori"])
filters = st.sidebar.multiselect("Filter", ["Kun ikke afstemt", "Kun ikke reviewet"])

uploaded = st.file_uploader("Upload Trial Balance (Excel)", type=["xlsx"], help="Use the provided sample if needed.")
last_uploaded = state.get("last_uploaded")

# If no file uploaded, use bundled sample (from same folder) if present
default_sample_path = "Sample_Trial_Balance.xlsx"
if uploaded is not None:
    tb = pd.read_excel(uploaded, sheet_name=0)
    state["last_uploaded"] = {
        "by": "Current User",
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    state["recon"] = state.get("recon", {})  # keep old marks when re-uploading (optional)
    save_state(state)
elif os.path.exists(default_sample_path):
    tb = pd.read_excel(default_sample_path, sheet_name=0)
else:
    st.info("Upload an Excel trial balance to begin.")
    st.stop()

# Show last upload info
if state.get("last_uploaded"):
    st.caption(f"Last upload: {state['last_uploaded']['at']} — by {state['last_uploaded']['by']}")

# Normalize expected columns
expected = ["Nummer","Navn","Beløb","Rapporterings kontokategori","Sammentælling","Kontotype","Type","Kontokategori"]
missing = [c for c in expected if c not in tb.columns]
if missing:
    st.error(f"Missing columns in uploaded file: {missing}")
    st.stop()

# Enforce numeric account number ordering where possible
try:
    tb["_num"] = pd.to_numeric(tb["Nummer"], errors="coerce")
except Exception:
    tb["_num"] = np.arange(len(tb))

# Prepare state dict for marks
recon_state = state.get("recon", {})

# Optionally filter not reconciled / not reviewed
def apply_mark_filters(df):
    if "Kun ikke afstemt" in filters:
        df = df[df["Nummer"].astype(str).map(lambda k: not recon_state.get(str(k), {}).get("reconciled", False))]
    if "Kun ikke reviewet" in filters:
        df = df[df["Nummer"].astype(str).map(lambda k: not recon_state.get(str(k), {}).get("reviewed", False))]
    return df

# View mode sorting/grouping
if view == "Kontoplan-rækkefølge":
    view_df = tb.sort_values(["_num","Nummer"])
    group_field = None  # keep original order
else:
    view_df = tb.sort_values(["Rapporterings kontokategori","_num","Nummer"])
    group_field = "Rapporterings kontokategori"

# Compute balance check
total_sum = tb["Beløb"].sum()
st.subheader("Balance check")
st.write(f"**Total (should be 0):** {total_sum:,.2f}")

# Build UI table
def render_rows(df):
    # Only show account rows where Kontotype != 'Fra-sum' (assuming those are totals in BC)
    mask_accounts = df["Kontotype"].astype(str).str.lower() != "fra-sum"
    rows = df[mask_accounts].copy()
    rows = apply_mark_filters(rows)

    # Table columns
    cols = st.columns([0.8, 2.5, 1.2, 1.4, 1.8, 0.9, 1.4])
    cols[0].markdown("**Konto nr.**")
    cols[1].markdown("**Konto navn**")
    cols[2].markdown("**Beløb**")
    cols[3].markdown("**Dokumentlink (SharePoint)**")
    cols[4].markdown("**Afstemt**")
    cols[5].markdown("**Review**")
    cols[6].markdown("**Status**")

    for _, r in rows.iterrows():
        acc_key = str(r["Nummer"])
        rs = recon_state.get(acc_key, {})
        link = rs.get("doc_link", "")
        colA, colB, colC, colD, colE, colF, colG = st.columns([0.8, 2.5, 1.2, 1.4, 1.8, 0.9, 1.4])
        colA.write(str(r["Nummer"]))
        colB.write(str(r["Navn"]))
        colC.write(f"{float(r['Beløb']):,.2f}")
        new_link = colD.text_input(" ", value=link, key=f"link_{acc_key}", placeholder="https://...")
        recon = colE.checkbox(" ", value=rs.get("reconciled", False), key=f"recon_{acc_key}")
        review = colF.checkbox(" ", value=rs.get("reviewed", False), key=f"review_{acc_key}")

        # Status stamp
        stamp = ""
        if recon:
            stamp += f"Afstemt af {rs.get('reconciled_by','(ukendt)')} {rs.get('reconciled_at','')}  "
        if review:
            stamp += f"• Reviewet af {rs.get('reviewed_by','(ukendt)')} {rs.get('reviewed_at','')}"
        colG.write(stamp or "—")

        # Persist interaction
        changed = False
        if new_link != link:
            rs["doc_link"] = new_link
            changed = True

        if recon != rs.get("reconciled", False):
            rs["reconciled"] = recon
            if recon:
                rs["reconciled_by"] = state.get("user","Current User")
                rs["reconciled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            else:
                rs.pop("reconciled_by", None); rs.pop("reconciled_at", None)
            changed = True

        if review != rs.get("reviewed", False):
            rs["reviewed"] = review
            if review:
                rs["reviewed_by"] = state.get("user","Current User")
                rs["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            else:
                rs.pop("reviewed_by", None); rs.pop("reviewed_at", None)
            changed = True

        if changed:
            recon_state[acc_key] = rs

    # Save state after loop
    state["recon"] = recon_state
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

if group_field:
    for group, gdf in view_df.groupby(group_field, dropna=False):
        st.markdown(f"### {group if pd.notna(group) else '(Uden kategori)'}")
        render_rows(gdf)

        # Subtotal (simple sum of rows)
        subtotal = gdf["Beløb"].sum()
        st.markdown(f"**Subtotal: {subtotal:,.2f}**")
        st.divider()
else:
    render_rows(view_df)

st.success("Prototype ready. Use the sidebar to change view or filter. Your marks persist in recon_state.json.")
