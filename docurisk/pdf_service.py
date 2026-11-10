from pypdf import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)

    if reader.is_encrypted:
        raise ValueError("Şifrələnmiş PDF sənədi oxuna bilmir.")

    extracted_pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""

        extracted_pages.append(
            f"--- Səhifə {page_number} ---\n"
            f"{page_text.strip()}"
        )

    return "\n\n".join(extracted_pages).strip()