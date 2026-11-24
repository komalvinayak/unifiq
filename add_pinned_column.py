"""
One-off script: adds 'pinned' header at column L (12) of brain_notes sheet.
Run once: .\\venv\\Scripts\\python.exe add_pinned_column.py
"""
import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "unifiq-db")
CREDS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "sheets_creds.json")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
client = gspread.authorize(creds)
print(f"Opening spreadsheet: {SPREADSHEET_NAME}")
sheet = client.open(SPREADSHEET_NAME).worksheet("brain_notes")

headers = sheet.row_values(1)
print(f"Current headers ({len(headers)}): {headers}")

if len(headers) >= 12:
    print("Column L already exists:", headers[11])
else:
    sheet.update_cell(1, 12, "pinned")
    print("Done! Column L 'pinned' header added.")
