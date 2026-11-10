from sqlalchemy import select

from docurisk.database import SessionLocal
from docurisk.models import User


async def save_user(
    telegram_user_id: int,
    telegram_chat_id: int,
    username: str | None,
    first_name: str | None
) -> User:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_user_id == telegram_user_id
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                username=username,
                first_name=first_name
            )

            session.add(user)
        else:
            user.telegram_chat_id = telegram_chat_id
            user.username = username
            user.first_name = first_name

        await session.commit()
        await session.refresh(user)

        return user