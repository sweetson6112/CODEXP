# =========================
# FILE: app.py
# =========================
import streamlit as st
from datetime import datetime, date
import pandas as pd
from supabase import create_client

# -------------------------
# CONFIG
# -------------------------
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_KEY"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Barcode Scanner", layout="wide")

# -------------------------
# SESSION STATE
# -------------------------
if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
if "serial" not in st.session_state:
    st.session_state.serial = 1

# -------------------------
# UTIL FUNCTIONS
# -------------------------
def generate_doc_no():
    res = supabase.table("documents").select("document_no").order("created_at", desc=True).limit(1).execute()
    if res.data:
        last = int(res.data[0]['document_no'].split('/')[-1])
    else:
        last = 0
    return f"CDRSL/BARCODE/{str(last+1).zfill(3)}"


def calc_shelf_life(mfg, exp):
    if not mfg or not exp:
        return None
    total = (exp - mfg).days
    remaining = (exp - date.today()).days
    if total <= 0:
        return 0
    return round((remaining / total) * 100, 2)


def check_barcode(barcode):
    res = supabase.table("barcode_master").select("*").eq("barcode", barcode).execute()
    return res.data

# -------------------------
# LOGIN (Simple Placeholder)
# -------------------------
st.sidebar.title("User")
user_email = st.sidebar.text_input("Email")

# -------------------------
# MASTER UPLOAD
# -------------------------
st.sidebar.subheader("Upload Barcode Master")
file = st.sidebar.file_uploader("Upload CSV", type=["csv"])

if file:
    df = pd.read_csv(file)
    supabase.table("barcode_master").insert(df.to_dict(orient="records")).execute()
    st.sidebar.success("Uploaded!")

# -------------------------
# HEADER
# -------------------------
st.title("📦 Barcode & Expiry Scanner")

st.subheader("Header Entry")

invoice = st.text_input("Invoice No")
bill_no = st.text_input("Bill of Entry No")
bill_date = st.date_input("Bill Entry Date")
inward_date = st.date_input("Inward Date")
warehouse_date = st.date_input("Warehouse Date")
file_no = st.text_input("File No")
container = st.text_input("Container No")
expected_lines = st.number_input("Expected Lines", min_value=1)
actual_lines = st.number_input("Actual Lines", min_value=1)
expiry_required = st.checkbox("Expiry Required")
expiry_threshold = st.number_input("Expiry Threshold %", value=20)

if st.button("Create Document"):
    doc_no = generate_doc_no()

    res = supabase.table("documents").insert({
        "document_no": doc_no,
        "created_at": str(datetime.now()),
        "invoice_no": invoice,
        "bill_entry_no": bill_no,
        "bill_entry_date": str(bill_date),
        "inward_date": str(inward_date),
        "warehouse_date": str(warehouse_date),
        "file_no": file_no,
        "container_no": container,
        "expected_lines": expected_lines,
        "actual_lines": actual_lines,
        "expiry_required": expiry_required,
        "expiry_threshold": expiry_threshold,
        "created_by": user_email
    }).execute()

    st.session_state.doc_id = res.data[0]['id']
    st.success(f"Document Created: {doc_no}")

# -------------------------
# SCANNING
# -------------------------
if st.session_state.doc_id:
    st.subheader("Scan Items")

    if st.session_state.serial > actual_lines:
        st.success("All items scanned")
        st.stop()

    barcode = st.text_input("Scan Barcode")

    if barcode:
        result = check_barcode(barcode)

        if result:
            remark = "Already Barcode Exists"
            item_no = result[0]['item_no']
            desc = result[0]['description']
        else:
            remark = "New Item"
            item_no = st.text_input("Item No")
            desc = st.text_input("Description")

        st.write("Remark:", remark)

        mfg = None
        exp = None
        shelf = None

        if expiry_required:
            mfg = st.date_input("MFG Date")
            exp = st.date_input("Expiry Date")
            shelf = calc_shelf_life(mfg, exp)
            st.write("Shelf Life %:", shelf)

        if st.button("Save Line"):
            supabase.table("line_items").insert({
                "document_id": st.session_state.doc_id,
                "serial_no": st.session_state.serial,
                "item_no": item_no,
                "barcode": barcode,
                "description": desc,
                "mfg_date": str(mfg) if mfg else None,
                "expiry_date": str(exp) if exp else None,
                "shelf_life": shelf,
                "remark": remark,
                "verified_by": user_email
            }).execute()

            st.session_state.serial += 1
            st.success("Saved")
            st.rerun()

    if st.button("Cancel Scanning"):
        st.session_state.doc_id = None
        st.session_state.serial = 1
        st.warning("Scanning Cancelled")

# -------------------------
# REPORT
# -------------------------
st.subheader("Reports")

if st.button("Load Report"):
    data = supabase.table("line_items").select("*").execute().data
    df = pd.DataFrame(data)
    st.dataframe(df)

# =========================
# FILE: requirements.txt
# =========================
# streamlit
# supabase
# pandas
# python-dotenv

# =========================
# SQL (RUN IN SUPABASE)
# =========================
# create table barcode_master (
# id uuid default gen_random_uuid() primary key,
# item_no text,
# barcode text,
# description text
# );

# create table documents (
# id uuid default gen_random_uuid() primary key,
# document_no text,
# created_at timestamp,
# invoice_no text,
# bill_entry_no text,
# bill_entry_date date,
# inward_date date,
# warehouse_date date,
# file_no text,
# container_no text,
# expected_lines int,
# actual_lines int,
# expiry_required boolean,
# expiry_threshold float,
# created_by text
# );

# create table line_items (
# id uuid default gen_random_uuid() primary key,
# document_id uuid,
# serial_no int,
# item_no text,
# barcode text,
# description text,
# mfg_date date,
# expiry_date date,
# shelf_life float,
# remark text,
# verified_by text
# );
