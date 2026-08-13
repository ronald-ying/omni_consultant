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


def assess_project(project_facts):
    """Screen a project's likely FHWA MSAT analysis category."""

    if not isinstance(project_facts, dict):
        raise ValueError("project_facts must be a dictionary.")

    project_lines = []

    for field, value in project_facts.items():
        readable_field = field.replace("_", " ").title()
        project_lines.append(f"- {readable_field}: {value}")

    project_description = "\n".join(project_lines)

    question = f"""
Evaluate the following project under the FHWA MSAT guidance.

PROJECT FACTS
=============
{project_description}

TASK
====
Provide a preliminary MSAT screening assessment.

Determine, based only on the supplied project facts and retrieved FHWA
guidance, which of the following appears most applicable:

1. No meaningful potential MSAT effects / exempt
2. Low potential MSAT effects / qualitative analysis
3. Higher potential MSAT effects / quantitative analysis
4. Cannot determine from the available facts

For the assessment:

- explain the reasoning;
- cite the FHWA source and electronic PDF page supporting each
  screening criterion;
- distinguish supplied project facts from FHWA requirements or guidance;
- identify every material fact that is still missing;
- do not assume missing project information;
- state that the result is a preliminary screening recommendation,
  not a substitute for agency coordination or professional judgment.
- Treat null, None, unknown, blank, or omitted values as missing information.
- Never infer a missing project fact from the project description.
- If one or more decision-critical facts needed to select an FHWA category are missing, select:
  "Cannot determine from the available facts"
  unless the known facts independently establish a category.
- Identify which missing facts are decision-critical and explain why each matters under FHWA guidance.
- Separate:
  Known project facts
  Missing project facts
  FHWA screening criteria
  Preliminary conclusion
"""

    return ask_consultant(question)

def draft_screening_memo(project_facts):
    """Draft an FHWA-grounded MSAT screening memorandum."""

    if not isinstance(project_facts, dict):
        raise ValueError("project_facts must be a dictionary.")

    project_lines = []

    for field, value in project_facts.items():
        readable_field = field.replace("_", " ").title()

        if value is None:
            display_value = "Not provided"
        else:
            display_value = value

        project_lines.append(
            f"- {readable_field}: {display_value}"
        )

    project_description = "\n".join(project_lines)

    critical_fields = [
        "design_year_aadt",
        "adds_significant_capacity",
        "near_populated_area",
    ]

    has_missing_screening_data = any(
        project_facts.get(field) is None
        for field in critical_fields
    )

    if has_missing_screening_data:
        information_section_title = (
            "Decision-Critical Missing Information"
        )
    else:
        information_section_title = (
            "Information Needed for Analysis Development"
        )

    question = f"""
Prepare a draft MSAT screening memorandum for the project below.

PROJECT FACTS
=============
{project_description}

MEMORANDUM REQUIREMENTS
=======================

Write a concise professional technical memorandum suitable for review
by an environmental project manager or transportation air-quality lead.

Use these sections:

# MSAT Screening Memorandum

## Project

Identify the project name and basic project information supplied.

## Purpose

Briefly explain that the memorandum provides a preliminary screening
under FHWA MSAT guidance.

## Project Facts

Summarize only facts explicitly supplied in the project data.
Do not convert missing values into assumptions.

## Preliminary MSAT Determination

Select one:

1. No meaningful potential MSAT effects / exempt
2. Low potential MSAT effects / qualitative analysis
3. Higher potential MSAT effects / quantitative analysis
4. Cannot determine from the available facts

State the determination clearly near the beginning.

## FHWA Screening Basis

Compare the supplied project facts against the applicable FHWA
screening criteria.

For every substantive FHWA criterion, cite:
[original PDF filename, electronic PDF page number]

Clearly distinguish:

- supplied project facts;
- FHWA guidance;
- professional inference.

## {information_section_title}

Use this exact section title. Do not rename it.

If this section is "Decision-Critical Missing Information":
- include only facts whose absence prevents the screening category
  from being selected;
- for the urban-highway higher-potential pathway, focus on:
  significant/new capacity, design-year AADT, and proximity to
  populated areas;
- do not characterize truck traffic or vehicle mix as independently
  decision-critical unless needed to resolve the applicable FHWA
  screening pathway.

If this section is "Information Needed for Analysis Development":
- the preliminary screening category is already supportable;
- identify information needed to scope or perform the subsequent
  analysis;
- do not describe these items as decision-critical screening
  deficiencies.

## Recommended Next Steps

Identify the next technical or coordination steps supported by the
screening.

## Limitations

State that:

- this is a preliminary screening assessment;
- it is based only on supplied project information and retrieved FHWA
  guidance;
- it is not a substitute for agency coordination or professional
  judgment.

WRITING STANDARD
================

- Use professional environmental-consulting language.
- Be concise.
- Do not invent project facts.
- Do not invent FHWA criteria.
- Do not introduce outside regulatory requirements.
- Do not state that a quantitative analysis is required unless the
  supplied facts support that conclusion under the retrieved guidance.

QA AND TECHNICAL WRITING RULES
==============================

- Treat the FHWA 140,000–150,000 AADT value as a screening range,
  not an inflexible regulatory threshold.

- Use FHWA's term "populated areas." Do not substitute "receptors"
  or "sensitive receptors" for the screening criterion.

- When discussing incomplete or unavailable information for
  project-specific MSAT health-impact analysis, use Appendix C as the
  primary FHWA source.

- When describing detailed MOVES inputs or quantitative modeling
  procedures, cite the FHWA quantitative MSAT/MOVES FAQ.

- Every FHWA screening criterion, numerical range, or procedural
  recommendation must have an inline source citation.

- Clearly distinguish:
  1. supplied project facts;
  2. FHWA guidance;
  3. professional inference.

- Avoid repeating the same project fact or FHWA criterion in multiple
  sections.
"""

    result = ask_consultant(question)

    answer = result["answer"]

    if has_missing_screening_data:
        answer = answer.replace(
            "## Missing Information\n\n"
            "### Decision-Critical Missing Information",
            "## Decision-Critical Missing Information",
        )

        answer = answer.replace(
            "## Missing Information",
            "## Decision-Critical Missing Information",
        )

    else:
        answer = answer.replace(
            "## Missing Information",
            "## Information Needed for Analysis Development",
        )

    result["answer"] = answer

    return result