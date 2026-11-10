import re
from sqlalchemy import select
from docurisk.database import SessionLocal
from docurisk.models import Analysis, Document


def extract_analysis_values(
    full_report: str
) -> tuple[int, int, str]:
    risk_match = re.search(
        r"Risk balı:\s*(\d{1,3})/100",
        full_report
    )

    benefit_match = re.search(
        r"Fayda balı:\s*(\d{1,3})/100",
        full_report
    )

    level_match = re.search(
        r"Risk səviyyəsi:\s*([^\n]+)",
        full_report
    )

    if not risk_match or not benefit_match or not level_match:
        raise ValueError(
            "AI hesabatından bal məlumatları çıxarıla bilmədi."
        )

    risk_score = int(risk_match.group(1))
    benefit_score = int(benefit_match.group(1))
    risk_level = level_match.group(1).strip()

    return risk_score, benefit_score, risk_level


async def save_analysis(
    document_id: int,
    full_report: str
) -> Analysis:
    risk_score, benefit_score, risk_level = (
        extract_analysis_values(full_report)
    )

    async with SessionLocal() as session:
        analysis = Analysis(
            document_id=document_id,
            risk_score=risk_score,
            benefit_score=benefit_score,
            risk_level=risk_level,
            full_report=full_report
        )

        document = await session.get(
            Document,
            document_id
        )

        if document is not None:
            document.status = "analyzed"

        session.add(analysis)
        await session.commit()
        await session.refresh(analysis)

        return analysis
async def get_latest_analysis_context(
    user_id: int
) -> tuple[str, str] | None:
    async with SessionLocal() as session:
        statement = (
            select(
                Document.extracted_text,
                Analysis.full_report
            )
            .join(
                Analysis,
                Analysis.document_id == Document.id
            )
            .where(Document.user_id == user_id)
            .order_by(Analysis.id.desc())
            .limit(1)
        )

        result = await session.execute(statement)
        row = result.first()

        if row is None:
            return None

        return row.extracted_text, row.full_report