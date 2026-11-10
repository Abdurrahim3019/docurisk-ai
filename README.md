# DocuRisk AI

AI-powered analysis of contracts, official and legal documents. Upload a PDF and DocuRisk AI highlights **risky clauses, obligations, potential financial losses, beneficial terms and points that need attention** in a clear, structured format.

Built as my 2nd-month project in the AI Engineering program at **LTC Lab**.

## Features
- **Two interfaces:** a web application (FastAPI) and a Telegram chatbot (aiogram)
- **Document risk analysis** with the Gemini API
- **Chat memory (SQLite):** ask follow-up questions about an uploaded document; the conversation and document context are preserved
- PDF text extraction with `pypdf`

## Use cases
- Detecting risky clauses in contracts
- Fast first-pass review of long documents
- Explaining obligations in plain language
- Spotting potential financial and legal risks and beneficial terms

## Tech stack
Python · FastAPI · aiogram · Google Gemini API · SQLAlchemy · SQLite · pypdf · Jinja2

## Project structure
```
docurisk/
  ai_service.py        # LLM prompts: document analysis and follow-up Q&A
  analysis_service.py  # stores and loads analyses
  memory_service.py    # conversation memory
  pdf_service.py       # PDF text extraction
  main.py              # Telegram bot
  web_app.py           # FastAPI web app
run_web.py             # starts the web app
```

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your own BOT_TOKEN and GEMINI_API_KEY

python run_web.py           # web app → http://127.0.0.1:8000
python -m docurisk.main     # Telegram bot
```

> DocuRisk AI gives an AI-assisted first review, not legal advice.
