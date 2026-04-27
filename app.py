import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Barcode ERP", layout="wide")

# =========================
# UI CLEAN (REMOVE HEADER)
# =========================
st.markdown("""
<style>
header {visibility:hidden;}
[data-testid="stToolbar"] {display:none;}
footer {visibility:hidden;}

.main {background-color:#f0f2f5;}

section[data-testid="stSidebar"] {
    background-color:#0a1f44;
}
section[data-testid="stSidebar"] * {
    color:white !important;
}

.custom-footer {
    position: fixed;
    bottom: 10px;
    right: 20px;
    font-size: 12px;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="custom-footer">Created by <b>Sweetson Joseph</b></div>',
    unsafe_allow_html=True
)

# =========================
# DATABASE (SQLite)
# =========================
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_no TEXT,
    invoice_no TEXT,
    actual_lines INTEGER,
    expiry_required BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER,
    serial_no INTEGER,
    item_no TEXT,
    barcode TEXT,
    description TEXT,
    remark TEXT,
    mfg_date TEXT,
    expiry_date TEXT,
    shelf_life REAL
)
""")

conn.commit()

# =========================
# SESSION STATE
# =========================
if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
    st.session_state.count = 0
    st.session_state.actual = 0
    st.session_state.inward = None

# =========================
# FUNCTIONS
# =========================
def generate_doc_no():
    c.execute("SELECT document_no FROM documents ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row:
        num = int(row[0].split("/")[-1]) + 1
    else:
        num = 1
    return f"CDRSL/BARCODE/{str(num).zfill(3)}"


def shelf_life(mfg, exp, inward):
    if not mfg or not exp or not inward:
        return None
    total = (exp - mfg).days
    remaining = (exp - inward).days
    return round((remaining / total) * 100, 2) if total > 0 else 0


# =========================
# SIDEBAR
# =========================
st.sidebar.title("📦 ERP Menu")

menu = st.sidebar.radio("", [
    "Dashboard",
    "Header Entry",
    "Scanning",
    "Report"
])

st.sidebar.markdown("---")
st.sidebar.markdown("**Created by Sweetson Joseph**")

# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":

    st.title("📊 Dashboard")

    c.execute("SELECT COUNT(*) FROM documents")
    total_docs = c.fetchone()[0]

    col1, col2 = st.columns(2)
    col1.metric("Documents", total_docs)
    col2.metric("Scanned Items", st.session_state.count)

# =========================
# HEADER ENTRY
# =========================
elif menu == "Header Entry":

    st.title("📄 Header Entry")

    doc_no = generate_doc_no()
    st.success(f"Document No: {doc_no}")

    col1, col2, col3 = st.columns(3)

    with col1:
        invoice = st.text_input("Invoice No")

    with col2:
        inward = st.date_input("Inward Date")

    with col3:
        actual = st.number_input("Actual Lines", min_value=1)

    expiry = st.selectbox("Expiry Required", ["Yes", "No"])

    if st.button("💾 Save Header"):

        c.execute("""
        INSERT INTO documents (document_no, invoice_no, actual_lines, expiry_required)
        VALUES (?, ?, ?, ?)
        """, (doc_no, invoice, actual, expiry == "Yes"))

        conn.commit()

        st.session_state.doc_id = c.lastrowid
        st.session_state.actual = actual
        st.session_state.count = 0
        st.session_state.inward = inward

        st.success("✅ Header Saved")

# =========================
# SCANNING
# =========================
elif menu == "Scanning":

    st.title("📡 Scanning")

    if not st.session_state.doc_id:
        st.warning("⚠ Create header first")
        st.stop()

    progress = st.session_state.count / st.session_state.actual
    st.progress(progress)

    barcode = st.text_input("Scan Barcode")

    item_no = st.text_input("Item No")
    desc = st.text_input("Description")

    mfg = st.date_input("Manufacturing Date")
    exp = st.date_input("Expiry Date")

    if st.button("➕ Add Item"):

        shelf = shelf_life(mfg, exp, st.session_state.inward)

        c.execute("""
        INSERT INTO line_items
        (document_id, serial_no, item_no, barcode, description, remark, mfg_date, expiry_date, shelf_life)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            st.session_state.doc_id,
            st.session_state.count + 1,
            item_no,
            barcode,
            desc,
            "OK",
            str(mfg),
            str(exp),
            shelf
        ))

        conn.commit()

        st.session_state.count += 1

        st.success(f"Added | Shelf Life: {shelf}%")

    if st.session_state.count >= st.session_state.actual:
        st.success("🎉 All items scanned")

    if st.button("🛑 Cancel"):
        st.error("Cancelled")
        st.stop()

# =========================
# REPORT
# =========================
elif menu == "Report":

    st.title("📊 Report")

    doc_id = st.number_input("Enter Document ID", min_value=1)

    if st.button("Fetch"):

        c.execute("SELECT * FROM documents WHERE id=?", (doc_id,))
        header = c.fetchall()

        c.execute("SELECT * FROM line_items WHERE document_id=?", (doc_id,))
        lines = c.fetchall()

        st.subheader("Header")
        st.write(header)

        df = pd.DataFrame(lines, columns=[
            "ID","DocID","Serial","Item No","Barcode",
            "Desc","Remark","MFG","EXP","Shelf"
        ])

        st.subheader("Line Items")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "⬇ Download CSV",
            df.to_csv(index=False),
            "report.csv"
        )
