import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent
INSTRUCTIONS_PATH = BASE_DIR / "instructions.txt"

MODEL = "gpt-5.6-luna"


def load_configuration():
    """Load local configuration and validate required settings."""

    load_dotenv(BASE_DIR / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    vector_store_id = os.getenv("OPENAI_PAGE_VECTOR_STORE_ID")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. Check your local .env file."
        )

    if not vector_store_id:
        raise RuntimeError(
            "OPENAI_PAGE_VECTOR_STORE_ID was not found. "
            "Check your local .env file."
        )

    if not INSTRUCTIONS_PATH.exists():
        raise RuntimeError("instructions.txt was not found.")

    instructions = INSTRUCTIONS_PATH.read_text(
        encoding="utf-8"
    ).strip()

    return instructions, vector_store_id


def extract_cited_pages(response):
    """Extract page-level source citations returned by file search."""

    cited_page_files = []

    for output_item in response.output:
        if output_item.type != "message":
            continue

        for content_item in output_item.content:
            if content_item.type != "output_text":
                continue

            for annotation in content_item.annotations:
                if annotation.type != "file_citation":
                    continue

                if annotation.filename not in cited_page_files:
                    cited_page_files.append(annotation.filename)

    page_pattern = re.compile(
        r"^(?P<document>.+)__page_(?P<page>\d+)\.txt$"
    )

    cited_pages = []

    for filename in cited_page_files:
        match = page_pattern.match(filename)

        if match:
            cited_pages.append(
                {
                    "filename": f"{match.group('document')}.pdf",
                    "page": int(match.group("page")),
                }
            )
        else:
            cited_pages.append(
                {
                    "filename": filename,
                    "page": None,
                }
            )

    return cited_pages


def ask_consultant(question):
    """Answer one question using the FHWA MSAT source corpus."""

    question = question.strip()

    if not question:
        raise ValueError("No question entered.")

    instructions, vector_store_id = load_configuration()

    retrieval_instructions = f"""
{instructions}

Additional source-grounding rules:

1. Use only information retrieved from the FHWA MSAT page-level vector store.
2. Each retrieved text file represents one electronic PDF page.
3. Each page begins with the original PDF filename and electronic page number.
4. Cite substantive conclusions as:
   [original PDF filename, electronic PDF page number]
5. Do not use outside knowledge to fill gaps.
6. Distinguish FHWA guidance from appendix prototype language.
7. State clearly when the retrieved material does not support an answer.
8. Do not invent project-specific traffic, emissions, modeling, or design data.
"""

    client = OpenAI()

    response = client.responses.create(
        model=MODEL,
        instructions=retrieval_instructions,
        input=question,
        tools=[
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
                "max_num_results": 12,
            }
        ],
        include=["file_search_call.results"],
    )

    return {
        "answer": response.output_text,
        "sources": extract_cited_pages(response),
    }