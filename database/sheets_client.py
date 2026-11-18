# ── sheets_client.py ─────────────────────────────────────────────────
# All Google Sheets operations live here.
# This is your permanent database — data never disappears.
#
# How it works:
# gspread is a Python library that talks to Google Sheets API.
# We authenticate using a service account (a bot Google account).
# Then we can read/write any sheet like a Python list.
# ─────────────────────────────────────────────────────────────────────

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from config.settings import GOOGLE_SHEETS_CREDENTIALS, SPREADSHEET_NAME


def _connect():
    """
    Creates a connection to Google Sheets.

    Two ways to authenticate:
    1. Local development: reads credentials from JSON file
    2. Streamlit Cloud: reads credentials from st.secrets

    Returns the spreadsheet object.
    """
    # Permissions we need from Google
    if "gcp_service_account" in st.secrets:
        # ── Streamlit Cloud: use secrets ─────────────────────────────
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # ── Local development: use JSON file ─────────────────────────
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            GOOGLE_SHEETS_CREDENTIALS, scope
        )


def get_all_rows(sheet_name: str) -> list:
    """
    Reads all rows from a sheet.
    Returns a list of dictionaries — one dict per row.

    Example return:
    [
        {"project_id": "1", "name": "MBA Case", "status": "Active"},
        {"project_id": "2", "name": "Assignment", "status": "Done"},
    ]
    """
    try:
        spreadsheet = _connect()
        sheet = spreadsheet.worksheet(sheet_name)
        return sheet.get_all_records()
    except Exception as e:
        st.error(f"Could not read {sheet_name}: {e}")
        return []


def add_row(sheet_name: str, row: list):
    """
    Adds one new row at the bottom of a sheet.

    row must be a list matching the column order.
    Example: ["P001", "MBA Case Competition", "Active", "2026-12-15"]
    """
    try:
        spreadsheet = _connect()
        sheet = spreadsheet.worksheet(sheet_name)
        sheet.append_row(row)
        return True
    except Exception as e:
        st.error(f"Could not save to {sheet_name}: {e}")
        return False


def update_row(sheet_name: str, row_number: int, new_values: list):
    """
    Updates an existing row.
    row_number starts at 2 (row 1 is the header).
    """
    try:
        spreadsheet = _connect()
        sheet = spreadsheet.worksheet(sheet_name)
        # Update the entire row at once
        for col, value in enumerate(new_values, start=1):
            sheet.update_cell(row_number, col, value)
        return True
    except Exception as e:
        st.error(f"Could not update row in {sheet_name}: {e}")
        return False


def delete_row(sheet_name: str, row_number: int):
    """
    Deletes a row by its row number.
    row_number starts at 2 (row 1 is the header).
    """
    try:
        spreadsheet = _connect()
        sheet = spreadsheet.worksheet(sheet_name)
        sheet.delete_rows(row_number)
        return True
    except Exception as e:
        st.error(f"Could not delete from {sheet_name}: {e}")
        return False


def get_as_dataframe(sheet_name: str) -> pd.DataFrame:
    """
    Reads a sheet and returns it as a pandas DataFrame.
    Useful for displaying tables and doing analysis.
    """
    rows = get_all_rows(sheet_name)
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame()


def log_activity(event_type: str, details: str):
    """
    Logs any activity to the command_log sheet.
    Used by Command Centre to show the activity feed.

    Example: log_activity("Task Added", "Submit report under MBA project")
    """
    from utils.date_utils import now_date_str, now_time_str
    add_row("command_log", [now_date_str(), now_time_str(), event_type, details])
