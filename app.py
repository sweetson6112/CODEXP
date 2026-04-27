import streamlit as st
from supabase import create_client
from datetime import date

# ========================
# CONFIG
# ========================
SUPABASE_URL = "https://gkqgraihqxneolqgfbhi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdrcWdyYWlocXhuZW9scWdmYmhpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcyMjQxMzYsImV4cCI6MjA5MjgwMDEzNn0.SRybsWa5fyou2mqOKHMPY_VA5CtGZuerr8asWhikIIQ"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="ERP Barcode System", layout="wide")

# ========================
# REMOVE STREAMLIT HEADER
# ========================
st.markdown("""
<style>
header {visibility: hidden;}
[data-testid="stToolbar"] {display: none;}
footer {visibility: hidden;}

.block-container {
    padding-top: 1rem;
}

/* SAP STYLE */
.main {
    background-color: #f0f2f5;
}

section[data-testid="stSidebar"] {
    background-color: #0a1f44;
    color: white;
}

section[data-testid="stSidebar"] * {
    color: white !important;
}

.card {
    background: white;
    padding: 16px;
    border-radius: 6px;
    border: 1px solid #ddd;
    margin-bottom: 12px;
}

.section-title {
    font-weight: 600;
    font-size: 18px;
    margin-bottom: 10px;
}

.stButton>button {
    background-color: #0a6ed1;
    color: white;
    border-radius: 4px;
    height: 36px;
}
</style>
""", unsafe_allow_html=True)

# ========================
# SESSION INIT
# ========================
if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
    st.session_state.count = 0
    st.session_state.data = []
    st.session_state.actual = 0

# ========================
# SIDEBAR NAV
# ========================
menu = st.sidebar.radio("Menu", [
    "Dashboard",
    "Header Entry",
    "Scanning",
    "Report"
])

# ========================
# FUNCTIONS
# ========================

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
    if not mfg or not exp:
        return None
    total = (exp - mfg).days
    remaining = (exp - inward).days
    return round((remaining / total) * 100, 2) if total > 0 else 0


def check_barcode(barcode):
    res = supabase.table("barcode_master") \
        .select("*") \
        .eq("barcode", barcode).execute()
    return res.data


# ========================
# DASHBOARD
# ========================
if menu == "Dashboard":

    st.title("📊 Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Documents", 24)
    col2.metric("Completed", 18)
    col3.metric("In Progress", 5)
    col4.metric("Cancelled", 1)


# ========================
# HEADER ENTRY
# ========================
elif menu == "Header Entry":

    st.title("📄 Header Entry")

    doc_no = generate_doc_no()
    st.success(f"Document No: {doc_no}")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        invoice = st.text_input("Invoice No")

    with col2:
        inward = st.date_input("Inward Date")

    with col3:
        actual = st.number_input("Actual Lines", min_value=1)

    with col4:
        expiry = st.selectbox("Expiry Required", ["Yes", "No"])

    if st.button("Save Header"):
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

        st.success("Header Saved")


# ========================
# SCANNING
# ========================
elif menu == "Scanning":

    st.title("📡 Scanning")

    if not st.session_state.doc_id:
        st.warning("Create Header First")
        st.stop()

    progress = st.session_state.count / st.session_state.actual
    st.progress(progress)

    col1, col2 = st.columns([3,1])

    with col1:
        barcode = st.text_input("Scan Barcode")

    with col2:
        st.metric("Scanned", st.session_state.count)

    if barcode:

        data = check_barcode(barcode)

        if data:
            item = data[0]
            remark = "Exists"
            item_no = item["item_no"]
            desc = item["description"]
        else:
            remark = "New"
            item_no = st.text_input("Item No")
            desc = st.text_input("Description")

        mfg = st.date_input("MFG Date")
        exp = st.date_input("Expiry Date")

        if st.button("Add Item"):

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

            st.success(f"{remark} | Shelf: {shelf}%")

    if st.session_state.count >= st.session_state.actual:
        st.success("All items scanned")

    if st.button("Cancel"):
        st.error("Cancelled")
        st.stop()


# ========================
# REPORT
# ========================
elif menu == "Report":

    st.title("📊 Report")

    doc_id = st.text_input("Enter Document ID")

    if st.button("Fetch"):

        header = supabase.table("documents").select("*").eq("id", doc_id).execute()
        lines = supabase.table("line_items").select("*").eq("document_id", doc_id).execute()

        st.subheader("Header")
        st.write(header.data)

        st.subheader("Lines")
        st.dataframe(lines.data)