import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import io
from supabase import create_client, Client
from utils.db import (
    get_supabase_client, get_next_document_no, get_users,
    get_barcode_master, upload_barcode_master,
    save_header, get_header_by_doc_no,
    save_line_item, get_line_items_by_doc_no,
    cancel_session
)
from utils.shelf_life import calculate_shelf_life
from utils.report import generate_report_excel
import os

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CDRSL Barcode & Expiry System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a237e 0%, #0d47a1 50%, #1565c0 100%);
        color: white;
        padding: 20px 30px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p  { margin: 4px 0 0; opacity: 0.85; font-size: 0.95rem; }
    .doc-badge {
        background: #e3f2fd; color: #0d47a1;
        padding: 6px 16px; border-radius: 20px;
        font-weight: 700; font-size: 1.1rem;
        display: inline-block; margin-bottom: 10px;
        border: 2px solid #1565c0;
    }
    .remark-exists {
        background: #fff3e0; border-left: 4px solid #f57c00;
        padding: 10px 16px; border-radius: 6px; margin: 8px 0;
        font-weight: 600; color: #e65100;
    }
    .remark-new {
        background: #e8f5e9; border-left: 4px solid #388e3c;
        padding: 10px 16px; border-radius: 6px; margin: 8px 0;
        font-weight: 600; color: #1b5e20;
    }
    .scan-card {
        background: #f8f9fa; border: 1px solid #dee2e6;
        border-radius: 10px; padding: 18px; margin-bottom: 16px;
    }
    .progress-bar-custom {
        background: #e0e0e0; border-radius: 8px;
        height: 22px; margin: 8px 0;
    }
    .footer {
        text-align: center; color: #888; font-size: 0.8rem;
        margin-top: 40px; padding: 10px;
        border-top: 1px solid #eee;
    }
    .stButton > button {
        border-radius: 8px; font-weight: 600;
    }
    .cancel-btn > button { background-color: #ef5350 !important; color: white !important; }
    [data-testid="metric-container"] {
        background: #f0f4ff; border-radius: 8px; padding: 12px;
        border: 1px solid #c5cae9;
    }
</style>
""", unsafe_allow_html=True)

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>📦 CDRSL Barcode & Expiry Management System</h1>
  <p>Inward Inspection · Barcode Verification · Shelf Life Tracking</p>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar Navigation ──────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/barcode.png", width=70)
    st.title("Navigation")
    now = datetime.now()
    st.info(f"🕐 {now.strftime('%d-%b-%Y  %H:%M:%S')}")

    menu = st.radio("Go to", [
        "🏠 Dashboard",
        "👤 User Setup",
        "📂 Master Upload",
        "📋 New Inward Session",
        "🔍 Scan & Capture",
        "📊 Reports"
    ])
    st.markdown("---")
    st.markdown('<div class="footer">Created by <b>Sweetson Joseph</b><br>CDRSL © 2025</div>', unsafe_allow_html=True)

# ─── Session State Defaults ───────────────────────────────────────────────────
for key, val in {
    "current_doc_no": None,
    "header_saved": False,
    "scan_active": False,
    "scanned_items": [],
    "serial_counter": 1,
    "header_data": {},
    "cancelled": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

supabase = get_supabase_client()

# ══════════════════════════════════════════════════════════════════════════════
# 🏠 DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if menu == "🏠 Dashboard":
    st.subheader("📊 Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    try:
        total_sessions = supabase.table("inward_headers").select("id", count="exact").execute()
        total_items    = supabase.table("inward_line_items").select("id", count="exact").execute()
        total_users    = supabase.table("cdrsl_users").select("id", count="exact").execute()
        total_master   = supabase.table("barcode_master").select("id", count="exact").execute()
        col1.metric("📋 Sessions", total_sessions.count or 0)
        col2.metric("🔖 Items Scanned", total_items.count or 0)
        col3.metric("👤 Users", total_users.count or 0)
        col4.metric("📂 Master Records", total_master.count or 0)
    except Exception as e:
        st.warning(f"Could not load stats: {e}")

    st.markdown("---")
    st.markdown("### 📌 Recent Sessions")
    try:
        recent = supabase.table("inward_headers").select("*").order("created_at", desc=True).limit(10).execute()
        if recent.data:
            df = pd.DataFrame(recent.data)[["document_no","invoice_no","inward_date","status","created_at"]]
            df.columns = ["Document No","Invoice No","Inward Date","Status","Created At"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No sessions yet. Start a new inward session.")
    except Exception as e:
        st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 👤 USER SETUP
# ══════════════════════════════════════════════════════════════════════════════
elif menu == "👤 User Setup":
    st.subheader("👤 User Setup")
    st.markdown("Manage verifiers / operators for barcode & expiry verification.")

    tab1, tab2 = st.tabs(["➕ Add User", "📋 Existing Users"])

    with tab1:
        with st.form("add_user_form"):
            c1, c2 = st.columns(2)
            name   = c1.text_input("Full Name *")
            email  = c2.text_input("Email *")
            c3, c4 = st.columns(2)
            role   = c3.selectbox("Role", ["Verifier", "Supervisor", "Admin"])
            dept   = c4.text_input("Department")
            google_id = st.text_input("Google Account / Employee ID")
            active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("✅ Add User", use_container_width=True)
            if submitted:
                if not name or not email:
                    st.error("Name and Email are required.")
                else:
                    try:
                        res = supabase.table("cdrsl_users").insert({
                            "name": name, "email": email, "role": role,
                            "department": dept, "google_id": google_id,
                            "is_active": active
                        }).execute()
                        st.success(f"✅ User '{name}' added successfully!")
                    except Exception as e:
                        st.error(f"Error adding user: {e}")

    with tab2:
        try:
            users = supabase.table("cdrsl_users").select("*").order("name").execute()
            if users.data:
                df = pd.DataFrame(users.data)[["name","email","role","department","is_active"]]
                df.columns = ["Name","Email","Role","Department","Active"]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No users found.")
        except Exception as e:
            st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 📂 MASTER UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
elif menu == "📂 Master Upload":
    st.subheader("📂 Barcode Master Upload")
    st.markdown("""
    Upload your barcode master Excel/CSV file.  
    **Required columns:** `item_no`, `barcode`, `description`  
    *(Optional: `uom`, `category`)*
    """)

    uploaded = st.file_uploader("Choose Excel or CSV file", type=["xlsx","xls","csv"])
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
            df.columns = [c.strip().lower().replace(" ","_") for c in df.columns]
            st.write(f"**Preview** — {len(df)} rows, {len(df.columns)} columns")
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)

            required = ["item_no","barcode","description"]
            missing  = [c for c in required if c not in df.columns]
            if missing:
                st.error(f"Missing required columns: {missing}")
            else:
                if st.button("⬆️ Upload to Supabase", use_container_width=True, type="primary"):
                    with st.spinner("Uploading..."):
                        records = df[required + [c for c in ["uom","category"] if c in df.columns]].to_dict("records")
                        for rec in records:
                            rec["barcode"] = str(rec["barcode"]).strip()
                            rec["item_no"] = str(rec["item_no"]).strip()
                        # Upsert by barcode
                        supabase.table("barcode_master").upsert(records, on_conflict="barcode").execute()
                    st.success(f"✅ {len(records)} records uploaded successfully!")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.markdown("---")
    st.markdown("### 📋 Current Master Records")
    try:
        master = supabase.table("barcode_master").select("*").order("item_no").execute()
        if master.data:
            df_m = pd.DataFrame(master.data)
            cols = [c for c in ["item_no","barcode","description","uom","category","created_at"] if c in df_m.columns]
            st.dataframe(df_m[cols], use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(master.data)} records")
        else:
            st.info("No master records yet.")
    except Exception as e:
        st.error(f"Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 📋 NEW INWARD SESSION
# ══════════════════════════════════════════════════════════════════════════════
elif menu == "📋 New Inward Session":
    st.subheader("📋 New Inward Session — Header Details")

    # Auto-generate document number
    if st.session_state.current_doc_no is None or not st.session_state.header_saved:
        try:
            doc_no = get_next_document_no(supabase)
        except Exception as e:
            doc_no = "CDRSL/BARCODE/001"
            st.warning(f"Could not fetch doc no: {e}")
        st.session_state.current_doc_no = doc_no
        st.session_state.header_saved   = False
        st.session_state.scanned_items  = []
        st.session_state.serial_counter = 1
        st.session_state.cancelled      = False

    st.markdown(f'<div class="doc-badge">📄 Document No: {st.session_state.current_doc_no}</div>', unsafe_allow_html=True)
    st.caption(f"Session Date & Time: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")

    with st.form("header_form"):
        st.markdown("#### 🧾 Invoice & Entry Details")
        c1, c2 = st.columns(2)
        invoice_no  = c1.text_input("1. Invoice No *")
        boe_no      = c2.text_input("2. Bill of Entry No *")

        c3, c4 = st.columns(2)
        boe_date    = c3.date_input("3. Bill of Entry Date", value=date.today())
        inward_date = c4.date_input("4. Inward Date at Port", value=date.today())

        c5, c6 = st.columns(2)
        goods_receipt_date = c5.date_input("5. Date of Goods Receipt at Warehouse", value=date.today())
        file_no            = c6.text_input("6. File No")

        c7, c8 = st.columns(2)
        container_no       = c7.text_input("7. Container No")
        invoice_lines      = c8.number_input("8. No of Item Lines in Invoice", min_value=1, value=1)

        c9, c10 = st.columns(2)
        actual_lines       = c9.number_input("9. Actual No of Item Lines Received", min_value=1, value=1)
        expiry_required    = c10.selectbox("10. Expiry Required", ["Yes","No"])

        expiry_threshold   = st.slider("11. Expiry Threshold %", min_value=0, max_value=100, value=70,
                                       help="Items with shelf life below this % will be flagged")

        st.markdown("#### 👤 Verification Officer")
        try:
            users = get_users(supabase)
            user_names = [u["name"] for u in users]
        except:
            user_names = ["User not configured"]
        verified_by = st.selectbox("Barcode/Expiry Verification done by", user_names)

        submitted = st.form_submit_button("✅ Save Header & Start Scanning", use_container_width=True, type="primary")

        if submitted:
            if not invoice_no or not boe_no:
                st.error("Invoice No and Bill of Entry No are required.")
            else:
                header = {
                    "document_no": st.session_state.current_doc_no,
                    "session_datetime": datetime.now().isoformat(),
                    "invoice_no": invoice_no,
                    "boe_no": boe_no,
                    "boe_date": str(boe_date),
                    "inward_date": str(inward_date),
                    "goods_receipt_date": str(goods_receipt_date),
                    "file_no": file_no,
                    "container_no": container_no,
                    "invoice_lines": int(invoice_lines),
                    "actual_lines": int(actual_lines),
                    "expiry_required": expiry_required,
                    "expiry_threshold": float(expiry_threshold),
                    "verified_by": verified_by,
                    "status": "Active"
                }
                try:
                    save_header(supabase, header)
                    st.session_state.header_saved = True
                    st.session_state.header_data  = header
                    st.success("✅ Header saved! Go to 'Scan & Capture' to start scanning.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error saving header: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 🔍 SCAN & CAPTURE
# ══════════════════════════════════════════════════════════════════════════════
elif menu == "🔍 Scan & Capture":
    st.subheader("🔍 Scan & Capture")

    if not st.session_state.header_saved:
        st.warning("⚠️ Please create and save a header first in 'New Inward Session'.")
        st.stop()

    h = st.session_state.header_data
    exp_required = h.get("expiry_required","No")
    actual_lines = h.get("actual_lines", 0)
    scanned_count = len(st.session_state.scanned_items)

    # ── Top Info Bar ──────────────────────────────────────────────────────────
    st.markdown(f'<div class="doc-badge">📄 {st.session_state.current_doc_no}</div>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Invoice No", h.get("invoice_no","—"))
    c2.metric("Expected Lines", actual_lines)
    c3.metric("Scanned", scanned_count)
    c4.metric("Remaining", max(0, actual_lines - scanned_count))

    # Progress
    pct = int((scanned_count / actual_lines * 100)) if actual_lines > 0 else 0
    st.progress(pct / 100, text=f"Progress: {scanned_count}/{actual_lines} items ({pct}%)")

    if st.session_state.cancelled:
        st.error("🚫 Session was CANCELLED. No further scanning allowed.")
        st.stop()

    if scanned_count >= actual_lines:
        st.success(f"🎉 All {actual_lines} items have been scanned! Session complete.")
        if st.button("📊 View Report", type="primary"):
            st.info("Go to Reports section.")
        st.stop()

    # ── Cancel Button ─────────────────────────────────────────────────────────
    st.markdown("---")
    col_cancel = st.columns([4,1])[1]
    with col_cancel:
        if st.button("🚫 Cancel Session", help="Cancel this scanning session"):
            if st.session_state.current_doc_no:
                try:
                    cancel_session(supabase, st.session_state.current_doc_no)
                    st.session_state.cancelled = True
                    st.session_state.header_saved = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Cancel error: {e}")

    # ── Scan Input ────────────────────────────────────────────────────────────
    st.markdown("### 📷 Scan Barcode")
    with st.container():
        st.markdown('<div class="scan-card">', unsafe_allow_html=True)
        barcode_input = st.text_input(
            "Scan / Enter Barcode",
            key="barcode_scan",
            placeholder="Scan or type barcode and press Enter...",
            help="Place cursor here and scan with barcode reader"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    if barcode_input:
        barcode_input = str(barcode_input).strip()

        # Lookup in master
        try:
            master_res = supabase.table("barcode_master").select("*").eq("barcode", barcode_input).execute()
        except Exception as e:
            st.error(f"DB error: {e}")
            st.stop()

        in_master = len(master_res.data) > 0
        master_rec = master_res.data[0] if in_master else {}

        serial_no = f"{st.session_state.current_doc_no}/{st.session_state.serial_counter:04d}"

        if in_master:
            st.markdown('<div class="remark-exists">⚠️ Already Barcode Exists in Master</div>', unsafe_allow_html=True)
            remark   = "Already Barcode Exists"
            item_no  = master_rec.get("item_no","")
            desc     = master_rec.get("description","")

            st.info(f"**Item No:** {item_no}  |  **Description:** {desc}")

        else:
            st.markdown('<div class="remark-new">🆕 New Item — Not in Master</div>', unsafe_allow_html=True)
            remark = "New Item"
            with st.form(f"new_item_form_{barcode_input}"):
                st.markdown("#### Enter New Item Details")
                cn1, cn2 = st.columns(2)
                item_no = cn1.text_input("Item No *")
                desc    = cn2.text_input("Description *")
                save_new = st.form_submit_button("Next →", type="primary")
                if not save_new:
                    st.stop()
                if not item_no or not desc:
                    st.error("Item No and Description are required.")
                    st.stop()

        # ── Expiry Capture ────────────────────────────────────────────────────
        # Note: As per spec point F.5 – both enabled & disabled capture mfg/expiry
        st.markdown("#### 📅 Manufacturing & Expiry Details")

        # Allow multiple expiry entries for same item
        num_expiry = st.number_input("No. of Expiry Entries for this item", min_value=1, max_value=20, value=1,
                                     help="One item may have multiple expiry batches")

        expiry_entries = []
        for i in range(int(num_expiry)):
            st.markdown(f"**Expiry Entry {i+1}**")
            ec1, ec2, ec3 = st.columns(3)
            mfg_date = ec1.date_input(f"Mfg Date #{i+1}", value=date.today(), key=f"mfg_{i}")
            exp_date  = ec2.date_input(f"Expiry Date #{i+1}", value=date.today(), key=f"exp_{i}")
            qty       = ec3.number_input(f"Qty #{i+1}", min_value=0, value=1, key=f"qty_{i}")

            # Shelf life calculation
            inward_dt = date.fromisoformat(h.get("inward_date", str(date.today())))
            total_days = (exp_date - mfg_date).days
            remaining  = (exp_date - inward_dt).days
            shelf_pct  = round((remaining / total_days * 100), 2) if total_days > 0 else 0.0
            threshold  = h.get("expiry_threshold", 70)
            flag       = "⚠️ BELOW THRESHOLD" if shelf_pct < threshold else "✅ OK"
            ec1.caption(f"Shelf Life: **{shelf_pct}%** {flag}")
            expiry_entries.append({
                "mfg_date": str(mfg_date),
                "expiry_date": str(exp_date),
                "qty": int(qty),
                "shelf_life_pct": shelf_pct
            })

        if st.button("✅ Confirm & Save Item", type="primary", use_container_width=True):
            saved_ok = True
            for idx, entry in enumerate(expiry_entries):
                line_serial = f"{serial_no}{'.' if len(expiry_entries)>1 else ''}{idx+1 if len(expiry_entries)>1 else ''}"
                line = {
                    "document_no": st.session_state.current_doc_no,
                    "serial_no": line_serial,
                    "item_no": item_no,
                    "barcode": barcode_input,
                    "description": desc,
                    "remark": remark,
                    "mfg_date": entry["mfg_date"],
                    "expiry_date": entry["expiry_date"],
                    "qty": entry["qty"],
                    "shelf_life_pct": entry["shelf_life_pct"],
                    "verified_by": h.get("verified_by",""),
                    "expiry_required": exp_required,
                    "inward_date": h.get("inward_date",""),
                }
                try:
                    save_line_item(supabase, line)
                    st.session_state.scanned_items.append(line)
                except Exception as e:
                    st.error(f"Error saving item: {e}")
                    saved_ok = False
                    break

            if saved_ok:
                st.session_state.serial_counter += 1
                # If new item, add to master
                if not in_master:
                    try:
                        supabase.table("barcode_master").insert({
                            "item_no": item_no,
                            "barcode": barcode_input,
                            "description": desc
                        }).execute()
                    except:
                        pass
                st.success(f"✅ Item '{barcode_input}' saved! Serial: {serial_no}")
                st.rerun()

    # ── Scanned Items Table ───────────────────────────────────────────────────
    if st.session_state.scanned_items:
        st.markdown("---")
        st.markdown("### 📋 Scanned Items This Session")
        df_scan = pd.DataFrame(st.session_state.scanned_items)
        cols = [c for c in ["serial_no","item_no","barcode","description","mfg_date","expiry_date","shelf_life_pct","qty","remark"] if c in df_scan.columns]
        st.dataframe(df_scan[cols], use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# 📊 REPORTS
# ══════════════════════════════════════════════════════════════════════════════
elif menu == "📊 Reports":
    st.subheader("📊 Barcode & Expiry Report")

    # Select session
    try:
        sessions = supabase.table("inward_headers").select("document_no,invoice_no,inward_date,status").order("created_at", desc=True).execute()
        session_opts = [f"{s['document_no']} | {s['invoice_no']} | {s['inward_date']}" for s in sessions.data]
    except:
        session_opts = []

    if not session_opts:
        st.info("No sessions found.")
        st.stop()

    selected = st.selectbox("Select Session", session_opts)
    doc_no = selected.split(" | ")[0].strip()

    if st.button("🔍 Load Report", type="primary"):
        try:
            hdr_res = supabase.table("inward_headers").select("*").eq("document_no", doc_no).execute()
            lns_res = supabase.table("inward_line_items").select("*").eq("document_no", doc_no).order("serial_no").execute()

            if not hdr_res.data:
                st.error("Header not found.")
                st.stop()

            hdr  = hdr_res.data[0]
            lines = lns_res.data

            # ── Report Header ─────────────────────────────────────────────────
            st.markdown("---")
            st.markdown("### 📄 Barcode & Expiry Report")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Document No", hdr.get("document_no",""))
            col2.metric("Date & Time", str(hdr.get("session_datetime",""))[:16])
            col3.metric("Inward Date", hdr.get("inward_date",""))
            col4.metric("Expiry Threshold %", f"{hdr.get('expiry_threshold',0)}%")

            col5, col6, col7 = st.columns(3)
            col5.metric("Invoice No", hdr.get("invoice_no",""))
            col6.metric("File No", hdr.get("file_no",""))
            col7.metric("Bill of Entry No", hdr.get("boe_no",""))

            st.caption(f"**Container No:** {hdr.get('container_no','')}  |  **Status:** {hdr.get('status','')}  |  **Verified By:** {hdr.get('verified_by','')}")

            # ── Line Details ──────────────────────────────────────────────────
            st.markdown("### 📋 Line Details")
            if lines:
                df = pd.DataFrame(lines)
                threshold = hdr.get("expiry_threshold", 70)

                def flag_shelf(pct):
                    if pct is None: return "—"
                    return f"{pct}% ⚠️" if pct < threshold else f"{pct}% ✅"

                display_cols = {
                    "serial_no": "Serial No",
                    "item_no": "Item No",
                    "description": "Item Description",
                    "barcode": "Barcode",
                    "expiry_date": "Expiry Date",
                    "mfg_date": "Manufacturing Date",
                    "shelf_life_pct": "Shelf Life %",
                    "qty": "Item Qty",
                    "remark": "Remarks",
                    "verified_by": "Verified By"
                }
                df_report = df[[c for c in display_cols.keys() if c in df.columns]].rename(columns=display_cols)
                if "Shelf Life %" in df_report.columns:
                    df_report["Shelf Life %"] = df_report["Shelf Life %"].apply(
                        lambda x: f"{x}% ⚠️" if x is not None and x < threshold else (f"{x}% ✅" if x is not None else "—")
                    )
                st.dataframe(df_report, use_container_width=True, hide_index=True)

                # ── Download ──────────────────────────────────────────────────
                st.markdown("---")
                st.markdown("### ⬇️ Download Report")
                try:
                    excel_bytes = generate_report_excel(hdr, lines)
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=excel_bytes,
                        file_name=f"{doc_no.replace('/','-')}_Report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"Report generation error: {e}")
            else:
                st.info("No line items found for this session.")

        except Exception as e:
            st.error(f"Error loading report: {e}")
