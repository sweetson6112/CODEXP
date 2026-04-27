import streamlit as st
from supabase import create_client
from datetime import date
import pandas as pd

# =========================
# CONFIG
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Barcode ERP", layout="wide")

# =========================
# ENTERPRISE UI + REMOVE HEADER
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

.block-container {padding-top:1rem;}

/* Buttons */
.stButton>button {
    background:#0a6ed1;
    color:white;
    border-radius:4px;
    height:36px;
}

/* Footer */
.custom-footer {
    position: fixed;
    bottom: 10px;
    right: 20px;
    font-size: 12px;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

# Footer
st.markdown(
    '<div class="custom-footer">Created by <b>Sweetson Joseph</b></div>',
    unsafe_allow_html=True
)

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
    res = supabase.table("documents") \
        .select("document_no") \
        .order("created_at", desc=True) \
        .limit(1).execute()

    if res.data:
        last = res.data[0]["document_no"]
        num = int(last.split("/")[-1]) + 1
    else:
        num = 1

    return f"CDRSL/BARCODE/{str(num).zfill(3)}"


def shelf_life(mfg, exp, inward):
    if not mfg or not exp or not inward:
        return None
    total = (exp - mfg).days
    remaining = (exp - inward).days
    if total <= 0:
        return 0
    return round((remaining / total) * 100, 2)


def check_barcode(barcode):
    res = supabase.table("barcode_master") \
        .select("*") \
        .eq("barcode", barcode) \
        .execute()
    return res.data


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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Documents", 0)
    col2.metric("Completed", 0)
    col3.metric("In Progress", 0)
    col4.metric("Cancelled", 0)

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

        res = supabase.table("documents").insert({
            "document_no": doc_no,
            "invoice_no": invoice,
            "actual_lines": actual,
            "expiry_required": expiry == "Yes"
        }).execute()

        st.session_state.doc_id = res.data[0]["id"]
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

    if barcode:

        data = check_barcode(barcode)

        if data:
            item = data[0]
            item_no = item["item_no"]
            desc = item["description"]
            remark = "EXISTS"
        else:
            item_no = st.text_input("Item No")
            desc = st.text_input("Description")
            remark = "NEW"

        mfg = st.date_input("Manufacturing Date")
        exp = st.date_input("Expiry Date")

        if st.button("➕ Add Item"):

            shelf = shelf_life(mfg, exp, st.session_state.inward)

            supabase.table("line_items").insert({
                "document_id": st.session_state.doc_id,
                "serial_no": st.session_state.count + 1,
                "item_no": item_no,
                "barcode": barcode,
                "description": desc,
                "remark": remark,
                "mfg_date": mfg,
                "expiry_date": exp,
                "shelf_life_percent": shelf
            }).execute()

            st.session_state.count += 1

            st.success(f"{remark} | Shelf Life: {shelf}%")

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

    doc_id = st.text_input("Enter Document ID")

    if st.button("Fetch Report"):

        header = supabase.table("documents") \
            .select("*") \
            .eq("id", doc_id).execute()

        lines = supabase.table("line_items") \
            .select("*") \
            .eq("document_id", doc_id).execute()

        st.subheader("Header")
        st.write(header.data)

        df = pd.DataFrame(lines.data)

        st.subheader("Line Items")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "⬇ Download CSV",
            df.to_csv(index=False),
            "report.csv"
        )
