
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
import re

st.set_page_config(page_title="Account Reconciliation Tracker", layout="wide")

st.title("Month-End Account Reconciliation — Prototype (BC format)")
st.caption("Uploader Business Central Trial Balance direkte. Vælg beløbskolonne, se grupper og subtotaler, markér afstemning/review og gem SharePoint-links.")

STATE_FILE = "recon_state.json"

# ---------- State helpers ----------
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
recon_state = state.get("recon", {})

# ---------- File upload ----------
uploaded = st.file_uploader("Upload Trial Balance fra Business Central (Excel)", type=["xlsx"])
if uploaded is None:
    st.info("Upload din Trial Balance fra BC. Kolonnenavne og rækkefølge kan stå præcis som i filen. Du kan også teste med Sample_TB_All.xlsx.")
    st.stop()

tb = pd.read_excel(uploaded, sheet_name=0)

# Mandatory columns we rely on (as in your file)
required_cols = ["Nummer","Navn","Kontotype","Sammentælling","Rapporterings kontokategori","Kontokategori","Type"]
missing = [c for c in required_cols if c not in tb.columns]
if missing:
    st.error(f"Mangler kolonner i filen: {missing}. Appen forventer Business Central-overskrifterne.")
    st.stop()

# ---------- Choose amount column ----------
numeric_candidates = [c for c in tb.columns if (pd.api.types.is_numeric_dtype(tb[c]) and c != "Nummer")]
if not numeric_candidates:
    st.error("Kunne ikke finde en numerisk beløbskolonne (fx 'Bevægelse' eller 'Saldo til dato').")
    st.stop()

amount_col = st.selectbox("Vælg beløbskolonne", options=numeric_candidates, index=0, help="Vælg kolonnen med beløb for måneden/perioden.")
tb["_amount"] = tb[amount_col].fillna(0.0).astype(float)

# Keep original order reference and numeric sorter for Nummer
tb["_row"] = np.arange(len(tb))
try:
    tb["_num"] = pd.to_numeric(tb["Nummer"], errors="coerce")
except Exception:
    tb["_num"] = np.arange(len(tb))

# ---------- Utility: parse 'Sammentælling' expressions ----------
def parse_totaling(expr):
    if not isinstance(expr, str):
        expr = str(expr) if expr is not None else ""
    expr = expr.strip()
    if not expr:
        return set()
    parts = re.split(r"[ ,;+|/]+", expr)
    result = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if ".." in p:
            a, b = p.split("..", 1)
            try:
                start = int(a.strip()); end = int(b.strip())
                if end < start: start, end = end, start
                for n in range(start, end+1):
                    result.add(str(n))
            except ValueError:
                pass
        else:
            if re.fullmatch(r"\d+", p):
                result.add(str(int(p)))
    return result

def build_amount_lookup(df):
    lookup = {}
    for _, r in df.iterrows():
        num = str(r["Nummer"])
        try:
            num_norm = str(int(float(num)))
        except Exception:
            num_norm = num
        lookup[num_norm] = float(r["_amount"])
    return lookup

amount_lookup = build_amount_lookup(tb)

def all_contributors_zero(expr):
    nums = parse_totaling(expr)
    if not nums:
        return False  # don't hide if we cannot resolve contributors
    for n in nums:
        if abs(amount_lookup.get(n, 0.0)) > 1e-9:
            return False
    return True

is_sum_row = tb["Kontotype"].astype(str).str.lower().str.contains("sum")

def compute_total_from_sammentaelling(row):
    expr = row.get("Sammentælling", "")
    nums = parse_totaling(expr)
    if not nums:
        return np.nan
    s = 0.0
    for n in nums:
        s += amount_lookup.get(n, 0.0)
    return s

tb["_computed_subtotal"] = np.where(is_sum_row, tb.apply(compute_total_from_sammentaelling, axis=1), np.nan)

# ---------- View controls ----------
st.sidebar.header("Visning")
show_subtotals = st.sidebar.checkbox('Vis subtotaler', value=True)
view = st.sidebar.selectbox("Visning", ["Kontoplan-rækkefølge", "Rapporteringskategori"])
filters = st.sidebar.multiselect("Filter", ["Kun ikke afstemt", "Kun ikke reviewet"])
show_subtotals = st.sidebar.checkbox("Vis subtotaler", value=True)

# ---------- Balance check ----------
total_sum = float(tb["_amount"].sum())
st.subheader("Balance check")
st.write(f"**Total (skal være 0):** {total_sum:,.2f}")
st.caption(f"Beløbskolonne: **{amount_col}**")

# Legend
with st.expander("Vis forklaring/legende"):
    st.write("**Type** = 'Resultatopgørelse' (P&L) eller 'Balance'.")
    st.write("Subtotalrækker (Kontotype med 'sum') udregnes fra 'Sammentælling'.")

# ---------- Render table ----------
def stamp_for(acc_key, rs):
    parts = []
    if rs.get("reconciled", False):
        parts.append(f"Afstemt af {rs.get('reconciled_by','(ukendt)')} {rs.get('reconciled_at','')}")
    if rs.get("reviewed", False):
        parts.append(f"Reviewet af {rs.get('reviewed_by','(ukendt)')} {rs.get('reviewed_at','')}")
    return " • ".join(parts) if parts else "—"

def render_account_row(r):
    acc_key = str(r["Nummer"])
    rs = recon_state.get(acc_key, {})
    colA, colB, colC, colT, colD, colE, colF, colG = st.columns([0.8, 2.0, 1.2, 1.0, 1.6, 1.0, 0.9, 1.8])
    colA.write(str(r["Nummer"]))
    colB.write(str(r["Navn"]))
    colC.write(f"{float(r['_amount']):,.2f}")
    colT.write(str(r["Type"]))  # show account Type (P&L or Balance)
    new_link = colD.text_input(" ", value=rs.get("doc_link",""), key=f"link_{acc_key}", placeholder="https://org.sharepoint.com/...")
    recon = colE.checkbox(" ", value=rs.get("reconciled", False), key=f"recon_{acc_key}")
    review = colF.checkbox(" ", value=rs.get("reviewed", False), key=f"review_{acc_key}")
    colG.write(stamp_for(acc_key, rs))

    changed = False
    if new_link != rs.get("doc_link",""):
        rs["doc_link"] = new_link; changed = True

    if recon != rs.get("reconciled", False):
        rs["reconciled"] = recon; changed = True
        if recon:
            rs["reconciled_by"] = state.get("user","Current User")
            rs["reconciled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            rs.pop("reconciled_by", None); rs.pop("reconciled_at", None)

    if review != rs.get("reviewed", False):
        rs["reviewed"] = review; changed = True
        if review:
            rs["reviewed_by"] = state.get("user","Current User")
            rs["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            rs.pop("reviewed_by", None); rs.pop("reviewed_at", None)

    if changed:
        recon_state[acc_key] = rs

def render_sum_row(r):
    amount = r["_computed_subtotal"]
    if pd.isna(amount):
        amount = r["_amount"]
    st.markdown(
        f"<div style='padding:6px 8px;border:1px solid #eee;background:#fafafa;border-radius:8px;margin:4px 0;'>"
        f"<b>Subtotal</b> — {str(r['Navn'])} (#{str(r['Nummer'])}) "
        f"<span style='float:right;'><b>{float(amount):,.2f}</b></span>"
        f"</div>",
        unsafe_allow_html=True
    )

def apply_mark_filters(df):
    is_account = ~df["Kontotype"].astype(str).str.lower().str.contains("sum")
    fdf = df.copy()
    if "Kun ikke afstemt" in filters:
        mask = fdf["Nummer"].astype(str).map(lambda k: not recon_state.get(str(k), {}).get("reconciled", False))
        fdf = fdf[mask | ~is_account]
    if "Kun ikke reviewet" in filters:
        mask = fdf["Nummer"].astype(str).map(lambda k: not recon_state.get(str(k), {}).get("reviewed", False))
        fdf = fdf[mask | ~is_account]
    return fdf

def render_group(df, title=None):
    if title is not None:
        st.markdown(f"### {title}")
    df = apply_mark_filters(df)

    for _, r in df.iterrows():
        if str(r["Kontotype"]).lower().find("sum") != -1 and show_subtotals:
            render_sum_row(r)
        else:
            render_account_row(r)

    st.divider()

# ---------- View modes ----------
if st.sidebar.radio("Sortering i gruppe", ["Numerisk kontonr.", "Filens rækkefølge"], index=0) == "Numerisk kontonr.":
    tb["_sort_key"] = tb["_num"]
else:
    tb["_sort_key"] = tb["_row"]

if view == "Kontoplan-rækkefølge":
    ordered = tb.sort_values(["_row"]).reset_index(drop=True)
    render_group(ordered, title=None)
else:
    for grp, gdf in tb.groupby("Rapporterings kontokategori", dropna=False):
        gdf = gdf.sort_values(["_sort_key","Nummer","_row"]).reset_index(drop=True)
        title = grp if pd.notna(grp) else "(Uden kategori)"
        render_group(gdf, title=title)

# Persist any interaction
state["recon"] = recon_state
if "last_uploaded" not in state:
    state["last_uploaded"] = {"by":"Current User","at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

st.success("Klar. Alle konti (P&L og Balance) vises. 'Type' fremgår i tabellen. Subtotaler beregnes fra 'Sammentælling'.")
