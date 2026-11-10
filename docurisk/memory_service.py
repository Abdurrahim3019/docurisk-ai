from sqlalchemy import select

from docurisk.database import SessionLocal
from docurisk.models import ChatMessage, Conversation


async def get_or_create_conversation(user_id: int) -> Conversation:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.is_active.is_(True)
            )
            .order_by(Conversation.id.desc())
        )

        conversation = result.scalars().first()

        if conversation is None:
            conversation = Conversation(
                user_id=user_id,
                title="Yeni sənəd analizi",
                is_active=True
            )

            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

        return conversation


async def save_message(
    conversation_id: int,
    role: str,
    content: str
) -> ChatMessage:
    async with SessionLocal() as session:
        chat_message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content
        )

        session.add(chat_message)
        await session.commit()
        await session.refresh(chat_message)

        return chat_message