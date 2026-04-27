"""
Database utility functions for CDRSL Barcode System.
Uses Supabase as the backend.
"""

import os
import streamlit as st
from supabase import create_client, Client


def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client.
    Reads credentials from Streamlit secrets or environment variables.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        st.error(
            "⚠️ Supabase credentials not configured.\n\n"
            "Add `SUPABASE_URL` and `SUPABASE_KEY` to `.streamlit/secrets.toml` "
            "or as environment variables."
        )
        st.stop()

    return create_client(url, key)


def get_next_document_no(supabase: Client) -> str:
    """
    Auto-generate the next document number in the series CDRSL/BARCODE/XXX.
    """
    PREFIX = "CDRSL/BARCODE/"
    try:
        res = (
            supabase.table("inward_headers")
            .select("document_no")
            .like("document_no", f"{PREFIX}%")
            .order("document_no", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            last = res.data[0]["document_no"]
            # Extract the numeric part
            try:
                num = int(last.replace(PREFIX, ""))
            except ValueError:
                num = 0
            return f"{PREFIX}{num + 1:03d}"
        else:
            return f"{PREFIX}001"
    except Exception:
        return f"{PREFIX}001"


def get_users(supabase: Client) -> list:
    """Return all active users from cdrsl_users table."""
    res = supabase.table("cdrsl_users").select("*").eq("is_active", True).order("name").execute()
    return res.data or []


def get_barcode_master(supabase: Client) -> list:
    """Return all barcode master records."""
    res = supabase.table("barcode_master").select("*").execute()
    return res.data or []


def upload_barcode_master(supabase: Client, records: list) -> None:
    """Upsert barcode master records."""
    supabase.table("barcode_master").upsert(records, on_conflict="barcode").execute()


def save_header(supabase: Client, header: dict) -> None:
    """Insert a new inward header record."""
    supabase.table("inward_headers").insert(header).execute()


def get_header_by_doc_no(supabase: Client, doc_no: str) -> dict:
    """Retrieve header by document number."""
    res = (
        supabase.table("inward_headers")
        .select("*")
        .eq("document_no", doc_no)
        .execute()
    )
    return res.data[0] if res.data else {}


def save_line_item(supabase: Client, line: dict) -> None:
    """Insert a scanned line item."""
    supabase.table("inward_line_items").insert(line).execute()


def get_line_items_by_doc_no(supabase: Client, doc_no: str) -> list:
    """Retrieve all line items for a document."""
    res = (
        supabase.table("inward_line_items")
        .select("*")
        .eq("document_no", doc_no)
        .order("serial_no")
        .execute()
    )
    return res.data or []


def cancel_session(supabase: Client, doc_no: str) -> None:
    """Mark a session as Cancelled."""
    supabase.table("inward_headers").update(
        {"status": "Cancelled"}
    ).eq("document_no", doc_no).execute()
