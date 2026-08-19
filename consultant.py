import os
import re
from pathlib import Path
import json

from dotenv import load_dotenv
from openai import OpenAI
from discipline_config import (
    load_discipline_json,
    load_discipline_text,
)

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

def get_missing_screening_facts(project_facts):
    """
    Return missing decision-critical facts for the
    urban-highway FHWA MSAT screening pathway.

    Important:
    False is a known value.
    Only None means the fact is missing.
    """

    if not isinstance(project_facts, dict):
        raise ValueError(
            "project_facts must be a dictionary."
        )

    screening_fields = {
        "adds_significant_capacity":
            "Whether the project creates new capacity or "
            "adds significant capacity",
        "design_year_aadt":
            "Applicable design-year AADT",
        "near_populated_area":
            "Proximity to populated areas",
    }

    return [
        label
        for field, label in screening_fields.items()
        if project_facts.get(field) is None
    ]

def build_decision_critical_section(project_facts):
    """
    Build the Decision-Critical Missing Information section
    deterministically from structured project facts.
    """

    items = []

    if project_facts.get("adds_significant_capacity") is None:
        items.append(
            "1. **Whether the project creates new capacity or adds "
            "significant capacity.** This fact is needed to determine "
            "whether the FHWA higher-potential urban-highway pathway "
            "applies. [fhwa_nepa_msat_memorandum_2023.pdf, "
            "electronic PDF page 6]"
        )

    if project_facts.get("design_year_aadt") is None:
        number = len(items) + 1

        items.append(
            f"{number}. **Applicable design-year AADT.** "
            "FHWA identifies approximately 140,000–150,000 AADT or "
            "greater as the screening range for the higher-potential "
            "urban-highway pathway, while recognizing that project "
            "conditions may warrant a different range. "
            "[fhwa_nepa_msat_memorandum_2023.pdf, "
            "electronic PDF page 6]"
        )

    if project_facts.get("near_populated_area") is None:
        number = len(items) + 1

        items.append(
            f"{number}. **Proximity to populated areas.** "
            "FHWA identifies proximity to populated areas as an "
            "additional condition of the higher-potential "
            "urban-highway pathway. "
            "[fhwa_nepa_msat_memorandum_2023.pdf, "
            "electronic PDF page 6]"
        )

    if not items:
        return ""

    return (
        "## Decision-Critical Missing Information\n\n"
        "The following information is needed before the preliminary "
        "urban-highway MSAT screening category can be selected:\n\n"
        + "\n\n".join(items)
        + "\n\n"
    )

def draft_screening_memo(project_facts):
    """Draft an FHWA-grounded MSAT screening memorandum."""

    if not isinstance(project_facts, dict):
        raise ValueError(
            "project_facts must be a dictionary."
        )

    # ---------------------------------------------------------
    # Convert structured project facts into readable prompt text
    # ---------------------------------------------------------

    project_lines = []

    for field, value in project_facts.items():
        readable_field = (
            field.replace("_", " ").title()
        )

        if value is None:
            display_value = "Not provided"
        elif value is True:
            display_value = "Yes"
        elif value is False:
            display_value = "No"
        else:
            display_value = value

        project_lines.append(
            f"- {readable_field}: {display_value}"
        )

    project_description = "\n".join(
        project_lines
    )

    # ---------------------------------------------------------
    # Determine missing screening facts deterministically
    # ---------------------------------------------------------

    missing_screening_facts = (
        get_missing_screening_facts(
            project_facts
        )
    )

    has_missing_screening_data = bool(
        missing_screening_facts
    )

    if has_missing_screening_data:
        information_section_title = (
            "Decision-Critical Missing Information"
        )

        missing_screening_text = "\n".join(
            f"- {fact}"
            for fact in missing_screening_facts
        )

    else:
        information_section_title = (
            "Information Needed for Analysis Development"
        )

        missing_screening_text = "- None"

    # ---------------------------------------------------------
    # Build the grounded memo request
    # ---------------------------------------------------------

    question = f"""
Prepare a draft MSAT screening memorandum for the project below.

PROJECT FACTS
=============
{project_description}


DETERMINISTIC SCREENING STATUS
==============================

The following decision-critical urban-highway screening facts are
missing according to the structured project data:

{missing_screening_text}

This list was calculated by software from the structured project
facts.

You MUST follow these rules:

- Do not add a non-null project fact to the list of
  decision-critical missing information.

- A value of False is a known project fact. It is not missing.

- Only a value of None / Not provided is missing.

- If proximity to populated areas is supplied as Yes/True,
  do not request confirmation of proximity as decision-critical
  missing information.

- If design-year AADT is supplied, do not identify design-year
  AADT as missing.

- If significant-capacity status is supplied, do not identify
  significant-capacity status as missing.

- Truck traffic and vehicle mix are not independently
  decision-critical for the urban-highway higher-potential
  screening pathway unless the project facts and FHWA guidance
  establish that they are necessary to resolve another applicable
  screening pathway.

- Supporting information that would be useful for later analysis
  may be discussed separately, but it must not be characterized as
  a missing screening fact.


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

Do not describe a supplied True or False value as unknown.

## Preliminary MSAT Determination

Select one:

1. No meaningful potential MSAT effects / exempt
2. Low potential MSAT effects / qualitative analysis
3. Higher potential MSAT effects / quantitative analysis
4. Cannot determine from the available facts

State the determination clearly.

Do not force a category when decision-critical project facts are
missing unless the known facts independently establish another
category.

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

Use this exact H2 section title.

Do not rename it.

If the title is "Decision-Critical Missing Information":

- list ONLY the screening facts identified in the
  DETERMINISTIC SCREENING STATUS section above;

- do not add other project facts;

- explain why each listed missing fact matters under FHWA guidance;

- do not ask for confirmation of facts that have already been
  supplied.

If the title is "Information Needed for Analysis Development":

- the preliminary screening category is already supportable;

- identify information needed to scope, document, or perform the
  subsequent MSAT analysis;

- do not describe those items as missing screening criteria or
  decision-critical deficiencies.

## Recommended Next Steps

Identify the next technical or coordination steps supported by the
screening.

If decision-critical facts are missing, the first next steps should
focus on obtaining those exact facts.

## Limitations

State that:

- this is a preliminary screening assessment;

- it is based only on supplied project information and retrieved
  FHWA guidance;

- it is not a substitute for agency coordination or professional
  judgment.


WRITING STANDARD
================

- Use professional environmental-consulting language.

- Be concise.

- Do not invent project facts.

- Do not invent FHWA criteria.

- Do not introduce outside regulatory requirements.

- Do not state that quantitative analysis is required unless the
  supplied facts support that conclusion under the retrieved FHWA
  guidance.

- Treat the FHWA 140,000–150,000 AADT value as a screening range,
  not an inflexible regulatory threshold.

- Use FHWA's term "populated areas" when applying that screening
  criterion.

- Do not substitute "receptors" or "sensitive receptors" for the
  populated-area screening criterion.

- When discussing incomplete or unavailable information concerning
  project-specific MSAT health-impact analysis, use Appendix C as
  the primary FHWA source.

- When describing detailed MOVES inputs or quantitative modeling
  procedures, cite the FHWA quantitative MSAT/MOVES FAQ.

- Every FHWA screening criterion, numerical range, or procedural
  recommendation must have an inline source citation.

- Clearly distinguish:
  1. supplied project facts;
  2. FHWA guidance;
  3. professional inference.

- Avoid repeating the same project fact or FHWA criterion in
  multiple sections.
"""

    # ---------------------------------------------------------
    # Generate memo using existing FHWA retrieval engine
    # ---------------------------------------------------------

    result = ask_consultant(
        question
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            "ask_consultant() did not return a dictionary."
        )

    if "answer" not in result:
        raise RuntimeError(
            "ask_consultant() result does not contain 'answer'."
        )

    answer = result["answer"]

    if not isinstance(answer, str):
        raise RuntimeError(
            "ask_consultant() returned an invalid answer."
        )

    # ---------------------------------------------------------
    # Deterministically replace the missing-information section
    # ---------------------------------------------------------

    if has_missing_screening_data:
        deterministic_section = (
            build_decision_critical_section(
                project_facts
            )
        )

        pattern = (
            r"(?ms)^##\s+(?:Missing Information|"
            r"Decision-Critical Missing Information)\s*$"
            r".*?"
            r"(?=^##\s|\Z)"
        )

        answer, replacement_count = re.subn(
            pattern,
            deterministic_section,
            answer,
            count=1,
        )

        if replacement_count == 0:
            raise RuntimeError(
                "Could not locate the Decision-Critical "
                "Missing Information section in the generated memo."
            )

    else:
        answer = re.sub(
            r"^##\s+Missing Information\s*$",
            "## Information Needed for Analysis Development",
            answer,
            flags=re.MULTILINE,
        )

        answer = re.sub(
            r"^###\s+Information Needed for Analysis Development\s*$",
            "## Information Needed for Analysis Development",
            answer,
            flags=re.MULTILINE,
        )

    result["answer"] = answer

    return result


def extract_project_facts_from_document(
    document_text,
    source_name,
):
    """
    Extract structured project facts from a project document.

    This function performs document fact extraction only.
    It does not apply FHWA MSAT screening criteria.
    """

    if not document_text.strip():
        raise ValueError(
            "No project document text was provided."
        )

    load_dotenv(BASE_DIR / ".env")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. "
            "Check your local .env file."
        )

    client = OpenAI()

    schema = load_discipline_json(
        "msat",
        "intake_schema.json",
    )

    instructions = load_discipline_text(
        "msat",
        "intake_instructions.md",
    )

    response = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=f"""
SOURCE DOCUMENT
===============
{source_name}

DOCUMENT TEXT
=============
{document_text}
""",
        text={
            "format": {
                "type": "json_schema",
                "name": "project_document_intake",
                "schema": schema,
                "strict": True,
            }
        },
    )

    return json.loads(
        response.output_text
    )