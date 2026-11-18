# UNIFIQ Setup Guide
Complete step-by-step instructions to get UNIFIQ running on your laptop and deploy it online.

---

## What You Need Before Starting
- Python 3.11 installed on your laptop
- A Google account
- A GitHub account

---

## STEP 1 — Get Free API Keys

### Gemini API Keys (get 3 for rotation)
1. Go to: https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy and save the key
4. Repeat 2 more times to get 3 keys (they're free)

### Groq API Key (backup AI)
1. Go to: https://console.groq.com
2. Sign up → go to "API Keys" → Create
3. Copy and save the key

---

## STEP 2 — Set Up Google Sheets

### Create the spreadsheet
1. Go to Google Sheets: https://sheets.google.com
2. Create a new spreadsheet
3. Name it: `UNIFIQ_DATABASE`

### Create these 4 tabs (sheets)
Click the "+" at the bottom to add each tab:

**Tab 1: projects**
Add this header row (Row 1):
```
project_id | name | description | deadline | status | created_date
```

**Tab 2: tasks**
Add this header row (Row 1):
```
task_id | project_id | task_name | priority | due_date | status | created_date
```

**Tab 3: brain_notes**
Add this header row (Row 1):
```
note_id | content | category | date | time
```

**Tab 4: command_log**
Add this header row (Row 1):
```
date | time | event_type | details
```

---

## STEP 3 — Create Google Service Account

This is a "bot" Google account that lets your app access Google Sheets.

1. Go to: https://console.cloud.google.com
2. Create a new project (name it "UNIFIQ")
3. Go to "APIs & Services" → "Library"
4. Search "Google Sheets API" → Enable it
5. Search "Google Drive API" → Enable it
6. Go to "IAM & Admin" → "Service Accounts"
7. Click "Create Service Account"
   - Name: `unifiq-bot`
   - Click "Done"
8. Click the service account → "Keys" tab → "Add Key" → JSON
9. Download the JSON file — rename it to `sheets_creds.json`
10. Put this file in your UNIFIQ project folder

### Share your spreadsheet with the service account
1. Open the JSON file and find the `"client_email"` value
   - It looks like: `unifiq-bot@unifiq-xxxxx.iam.gserviceaccount.com`
2. Open your Google Sheets spreadsheet
3. Click Share → paste that email → give "Editor" access

---

## STEP 4 — Set Up on Your Laptop

### Clone or download the project
```bash
# If using git:
git clone https://github.com/YOUR_USERNAME/unifiq.git
cd unifiq

# OR just unzip the project folder and cd into it
cd unifiq
```

### Create the .env file
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```
GEMINI_KEY_1=AIzaSy_your_first_key_here
GEMINI_KEY_2=AIzaSy_your_second_key_here
GEMINI_KEY_3=AIzaSy_your_third_key_here
GROQ_API_KEY=gsk_your_groq_key_here
GOOGLE_SHEETS_CREDENTIALS=sheets_creds.json
SPREADSHEET_NAME=UNIFIQ_DATABASE
```

### Install Python packages
```bash
pip install -r requirements.txt
```

### Run the app
```bash
streamlit run app.py
```

The app opens at: http://localhost:8501

---

## STEP 5 — Push to GitHub

```bash
# Initialize git (first time only)
git init
git add .
git commit -m "Initial UNIFIQ commit"

# Create repo on github.com then:
git remote add origin https://github.com/YOUR_USERNAME/unifiq.git
git push -u origin main
```

**IMPORTANT:** Never push `.env` or `sheets_creds.json` — they're in `.gitignore` already.

---

## STEP 6 — Deploy on Streamlit Community Cloud (Free)

1. Go to: https://share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Select your GitHub repo → `main` branch → `app.py`

### Add secrets on Streamlit Cloud
1. In your app settings → "Secrets" tab
2. Add this (replace with your real values):

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN RSA PRIVATE KEY-----\nyour-private-key\n-----END RSA PRIVATE KEY-----\n"
client_email = "unifiq-bot@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"

GEMINI_KEY_1 = "AIzaSy_your_first_key"
GEMINI_KEY_2 = "AIzaSy_your_second_key"
GEMINI_KEY_3 = "AIzaSy_your_third_key"
GROQ_API_KEY = "gsk_your_groq_key"
SPREADSHEET_NAME = "UNIFIQ_DATABASE"
```

The gcp_service_account values come from your `sheets_creds.json` file.

3. Click "Save" → Streamlit redeploys automatically

Your app is now live at: `https://YOUR_APP_NAME.streamlit.app`

---

## Project Folder Structure
```
unifiq/
├── app.py                      ← Main entry point (run this)
├── requirements.txt            ← Python packages
├── Dockerfile                  ← For Docker deployment
├── .env                        ← Your secrets (never commit this)
├── .env.example                ← Template for .env
├── sheets_creds.json           ← Google credentials (never commit this)
│
├── config/
│   └── settings.py             ← All constants and config
│
├── ai/
│   ├── gemini_client.py        ← Gemini AI with key rotation
│   └── embeddings_client.py   ← Text → vector conversion
│
├── database/
│   ├── sheets_client.py        ← All Google Sheets operations
│   └── chroma_client.py        ← ChromaDB vector search
│
├── modules/
│   ├── command_centre.py       ← Dashboard (Module 1)
│   ├── project_task_manager.py ← Projects + UNI bot (Module 2)
│   └── brain/
│       ├── brain_core.py       ← Dump thoughts, browse notes
│       ├── brain_map.py        ← Visual knowledge graph
│       └── brain_rag.py        ← Ask My Brain (manual RAG)
│
└── utils/
    └── date_utils.py           ← IST date/time helpers
```

---

## Common Issues

**"Could not read projects"** → Check your Google Sheets credentials and that the sheet is shared with the service account email.

**"Quota exceeded"** → Gemini key rate limit hit. The app auto-rotates to next key. If all 3 fail, it uses Groq.

**"ChromaDB error"** → This fixes itself on page refresh (the hybrid persistence rebuilds from Sheets).

**Brain map not loading** → Need at least 2 notes with different content first.

---

## Interview Talking Points

**"Why Google Sheets as a database?"**
> It's free, persistent, and I can see my data visually. For a personal tool at this scale, it handles everything. I can query, update, delete — all via the gspread Python library.

**"Why ChromaDB?"**
> I needed a vector database for semantic search. ChromaDB runs locally, is free, persists to disk, and is pure Python. No server setup like Weaviate, no paid tier like Pinecone.

**"Why not use LangChain?"**
> LangChain wraps everything in abstractions I can't explain. I built the RAG pipeline manually — embed the question with Google's API, search ChromaDB for top 5 similar notes, build a context string, pass it to Gemini. Every step is visible and I can defend every line in an interview.

**"How does the AI bot (UNI) work?"**
> I send Gemini the user's natural language command plus the list of existing projects as context. I instruct it to return a strict JSON format like `{"action": "add_task", "task_name": "...", "project_id": "..."}`. Then I parse that JSON and perform the actual database operation. No magic — just structured prompting.

**"What if the AI API goes down?"**
> I have 3 Gemini keys that rotate automatically. If all hit rate limits, the app falls back to Groq (which uses Llama 3). The fallback logic is in `ai/gemini_client.py`.
