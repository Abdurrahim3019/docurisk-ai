import asyncio
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from docurisk.ai_service import (
    analyze_document,
    answer_document_question
)
from docurisk.analysis_service import (
    save_analysis,
    get_latest_analysis_context
)
from docurisk.config import settings
from docurisk.database import init_database
from docurisk.document_service import (
    save_document,
    save_extracted_text
)
from docurisk.memory_service import (
    get_or_create_conversation,
    save_message
)
from docurisk.pdf_service import extract_text_from_pdf
from docurisk.user_service import save_user
dp = Dispatcher()


@dp.message(CommandStart())
async def start_command(message: Message):
    telegram_user = message.from_user

    if telegram_user is None:
        return

    user = await save_user(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=message.chat.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name
    )

    conversation = await get_or_create_conversation(user.id)

    welcome_text = (
        "Salam! Mən DocuRisk AI botuyam.\n\n"
        "Müqavilə və ya başqa rəsmi sənəd göndər. "
        "Sənəddəki mümkün riskləri və faydaları analiz edəcəyəm."
    )

    await save_message(
        conversation_id=conversation.id,
        role="user",
        content="/start"
    )

    await save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=welcome_text
    )

    await message.answer(welcome_text)
@dp.message(F.document)
async def document_message(message: Message, bot: Bot):
    telegram_user = message.from_user
    telegram_document = message.document

    if telegram_user is None or telegram_document is None:
        return

    file_name = Path(
        telegram_document.file_name
        or f"document_{telegram_document.file_unique_id}.pdf"
    ).name

    if Path(file_name).suffix.lower() != ".pdf":
        await message.answer(
            "Hazırda yalnız PDF sənədləri qəbul edirəm."
        )
        return

    max_file_size = 10 * 1024 * 1024

    if (
        telegram_document.file_size is not None
        and telegram_document.file_size > max_file_size
    ):
        await message.answer(
            "PDF faylı 10 MB-dan böyük olmamalıdır."
        )
        return

    user = await save_user(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=message.chat.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name
    )

    conversation = await get_or_create_conversation(user.id)

    user_storage = Path("storage") / str(user.id)
    user_storage.mkdir(parents=True, exist_ok=True)

    saved_file_name = f"{uuid4().hex}_{file_name}"
    file_path = user_storage / saved_file_name

    await bot.download(
        telegram_document,
        destination=str(file_path)
    )

    document = await save_document(
        user_id=user.id,
        conversation_id=conversation.id,
        telegram_file_id=telegram_document.file_id,
        file_name=file_name,
        mime_type=telegram_document.mime_type,
        storage_path=str(file_path)
    )

    try:
        extracted_text = await asyncio.to_thread(
            extract_text_from_pdf,
            str(file_path)
        )

        if not extracted_text:
            await message.answer(
                "PDF qəbul edildi, amma daxilində oxuna bilən mətn tapılmadı."
            )
            return

        await save_extracted_text(
            document_id=document.id,
            extracted_text=extracted_text
        )

    except Exception as error:
        print(f"PDF oxuma xətası: {error}")

        await message.answer(
            "PDF qəbul edildi, amma mətn oxunarkən xəta baş verdi."
        )
        return

    user_memory_text = f"[PDF sənədi göndərildi] {file_name}"

    await save_message(
        conversation_id=conversation.id,
        role="user",
        content=user_memory_text
    )

    await message.answer(
        "PDF mətni oxundu. AI sənədi analiz edir..."
    )

    try:
        analysis_text = await asyncio.to_thread(
            analyze_document,
            extracted_text
        )
    except Exception as error:
        print(f"AI analiz xətası: {error}")

        await message.answer(
            "Sənəd oxundu, amma AI analizi zamanı xəta baş verdi."
        )
        return
    try:
        saved_analysis = await save_analysis(
            document_id=document.id,
            full_report=analysis_text
        )

        print(
            f"Analiz bazaya yazıldı. "
            f"Analysis ID: {saved_analysis.id}"
        )

    except Exception as error:
        print(f"Analizi bazaya yazma xətası: {error}")

        await message.answer(
            "AI hesabatı hazırlandı, amma nəticə bazaya yazılmadı."
        )

    response_text = (
        f"PDF analiz edildi.\n\n"
        f"Sənəd: {file_name}\n"
        f"Sənəd ID: {document.id}\n\n"
        f"{analysis_text}"
    )

    await save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text
    )

    # Telegram bir mesajda maksimum 4096 simvol qəbul edir.
    for start in range(0, len(response_text), 4000):
        await message.answer(
            response_text[start:start + 4000]
        )

@dp.message(F.text)
async def text_message(message: Message):
    telegram_user = message.from_user

    if telegram_user is None or message.text is None:
        return

    user = await save_user(
        telegram_user_id=telegram_user.id,
        telegram_chat_id=message.chat.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name
    )

    conversation = await get_or_create_conversation(user.id)

    await save_message(
        conversation_id=conversation.id,
        role="user",
        content=message.text
    )

    context = await get_latest_analysis_context(
        user_id=user.id
    )

    if context is None:
        response_text = (
            "Sualı cavablandırmaq üçün əvvəlcə "
            "bir PDF sənədi göndər."
        )
    else:
        document_text, full_report = context

        await message.answer(
            "Sualını son sənəd əsasında araşdırıram..."
        )

        try:
            response_text = await asyncio.to_thread(
                answer_document_question,
                message.text,
                document_text,
                full_report
            )
        except Exception as error:
            print(f"Suala cavab xətası: {error}")
            response_text = (
                "Sual cavablandırılarkən xəta baş verdi."
            )

    await save_message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text
    )

    for start in range(0, len(response_text), 4000):
        await message.answer(
            response_text[start:start + 4000]
        )

async def main():
    await init_database()

    bot = Bot(token=settings.bot_token)

    print("DocuRisk AI botu başladıldı...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())