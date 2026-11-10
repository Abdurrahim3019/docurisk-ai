from docurisk.database import SessionLocal
from docurisk.models import Document


async def save_document(
    user_id: int,
    conversation_id: int,
    telegram_file_id: str,
    file_name: str,
    mime_type: str | None,
    storage_path: str
) -> Document:
    async with SessionLocal() as session:
        document = Document(
            user_id=user_id,
            conversation_id=conversation_id,
            telegram_file_id=telegram_file_id,
            file_name=file_name,
            mime_type=mime_type,
            storage_path=storage_path,
            status="received"
        )

        session.add(document)
        await session.commit()
        await session.refresh(document)

        return document

async def save_extracted_text(
    document_id: int,
    extracted_text: str
) -> Document:
    async with SessionLocal() as session:
        document = await session.get(Document, document_id)

        if document is None:
            raise ValueError("Sənəd bazada tapılmadı.")

        document.extracted_text = extracted_text
        document.status = "text_extracted"

        await session.commit()
        await session.refresh(document)

        return document