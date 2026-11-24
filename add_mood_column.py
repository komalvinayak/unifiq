"""
One-off script: adds 'mood' header at column K (11) of brain_notes sheet.
Run once: python add_mood_column.py
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

if len(headers) >= 11:
    print("Column K already exists:", headers[10])
else:
    sheet.update_cell(1, 11, "mood")
    print("Done! Column K 'mood' header added.")
