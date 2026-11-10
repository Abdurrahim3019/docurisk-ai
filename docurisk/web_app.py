import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from docurisk.ai_service import analyze_document, answer_document_question
from docurisk.analysis_service import (
    get_latest_analysis_context,
    save_analysis,
)
from docurisk.database import SessionLocal, init_database
from docurisk.document_service import save_document, save_extracted_text
from docurisk.memory_service import get_or_create_conversation, save_message
from docurisk.models import Analysis, Document, User
from docurisk.pdf_service import extract_text_from_pdf
from docurisk.user_service import save_user

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="DocuRisk AI - Web")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

WEB_TELEGRAM_USER_ID = -1
WEB_TELEGRAM_CHAT_ID = -1

_web_user_cache: User | None = None
_web_user_lock = asyncio.Lock()


async def get_web_user() -> User:
    """Mövcud 'Web Demo User' istifadəçisini alır və ya yaradır."""
    global _web_user_cache

    if _web_user_cache is not None:
        return _web_user_cache

    async with _web_user_lock:
        if _web_user_cache is not None:
            return _web_user_cache

        _web_user_cache = await save_user(
            telegram_user_id=WEB_TELEGRAM_USER_ID,
            telegram_chat_id=WEB_TELEGRAM_CHAT_ID,
            username="web_demo",
            first_name="Web Demo User",
        )

        return _web_user_cache


@app.on_event("startup")
async def on_startup():
    await init_database()
    await get_web_user()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})

@app.post("/api/analyze")
async def api_analyze(file: UploadFile = File(...)):
    original_name = Path(file.filename or "document.pdf").name

    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Yalnız PDF sənədləri qəbul edilir.")

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Boş fayl qəbul edilə bilməz.")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="PDF faylı 10 MB-dan böyük olmamalıdır.")

    user = await get_web_user()
    conversation = await get_or_create_conversation(user.id)

    user_storage = Path("storage") / str(user.id)
    user_storage.mkdir(parents=True, exist_ok=True)

    saved_file_name = f"{uuid4().hex}_{original_name}"
    file_path = user_storage / saved_file_name

    with open(file_path, "wb") as f:
        f.write(content)

    document = await save_document(
        user_id=user.id,
        conversation_id=conversation.id,
        telegram_file_id=f"web_{uuid4().hex}",
        file_name=original_name,
        mime_type=file.content_type,
        storage_path=str(file_path),
    )

    try:
        extracted_text = await asyncio.to_thread(extract_text_from_pdf, str(file_path))
    except Exception as error:
        print(f"PDF oxuma xətası: {error}")
        raise HTTPException(status_code=422, detail="PDF mətni oxunarkən xəta baş verdi.")

    if not extracted_text:
        raise HTTPException(status_code=422, detail="PDF daxilində oxuna bilən mətn tapılmadı.")

    await save_extracted_text(document_id=document.id, extracted_text=extracted_text)

    await save_message(
        conversation_id=conversation.id,
        role="user",
        content=f"[Web PDF yükləndi] {original_name}",
    )

    try:
        analysis_text = await asyncio.to_thread(analyze_document, extracted_text)
    except Exception as error:
        print(f"AI analiz xətası: {error}")
        raise HTTPException(status_code=502, detail="AI analizi zamanı xəta baş verdi.")

    try:
        saved_analysis = await save_analysis(document_id=document.id, full_report=analysis_text)
    except ValueError as error:
        print(f"Bal çıxarma xətası: {error}")
        raise HTTPException(status_code=502, detail="AI hesabatından nəticələr çıxarıla bilmədi.")
    except Exception as error:
        print(f"Analizi bazaya yazma xətası: {error}")
        raise HTTPException(status_code=500, detail="Nəticə bazaya yazılarkən xəta baş verdi.")

    await save_message(conversation_id=conversation.id, role="assistant", content=analysis_text)

    return {
        "document_id": document.id,
        "analysis_id": saved_analysis.id,
        "file_name": original_name,
        "risk_score": saved_analysis.risk_score,
        "benefit_score": saved_analysis.benefit_score,
        "risk_level": saved_analysis.risk_level,
        "full_report": analysis_text,
    }


@app.post("/api/question")
async def api_question(question: str = Form(...)):
    question = question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Sual mətni boş ola bilməz.")

    user = await get_web_user()
    context = await get_latest_analysis_context(user_id=user.id)

    if context is None:
        raise HTTPException(status_code=404, detail="Əvvəlcə bir PDF sənədi yükləyin.")

    document_text, full_report = context
    conversation = await get_or_create_conversation(user.id)

    await save_message(conversation_id=conversation.id, role="user", content=question)

    try:
        answer_text = await asyncio.to_thread(
            answer_document_question, question, document_text, full_report
        )
    except Exception as error:
        print(f"Suala cavab xətası: {error}")
        raise HTTPException(status_code=502, detail="Sual cavablandırılarkən xəta baş verdi.")

    await save_message(conversation_id=conversation.id, role="assistant", content=answer_text)

    return {"answer": answer_text}


@app.get("/api/history")
async def api_history():
    user = await get_web_user()

    async with SessionLocal() as session:
        statement = (
            select(
                Analysis.id,
                Analysis.risk_score,
                Analysis.benefit_score,
                Analysis.risk_level,
                Analysis.created_at,
                Document.file_name,
                Document.id.label("document_id"),
            )
            .join(Document, Document.id == Analysis.document_id)
            .where(Document.user_id == user.id)
            .order_by(Analysis.id.desc())
        )

        result = await session.execute(statement)
        rows = result.all()

    return JSONResponse({
        "items": [
            {
                "analysis_id": row.id,
                "document_id": row.document_id,
                "file_name": row.file_name,
                "risk_score": row.risk_score,
                "benefit_score": row.benefit_score,
                "risk_level": row.risk_level,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    })
