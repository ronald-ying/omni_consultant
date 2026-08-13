import json
import re
import sys
from pathlib import Path

from consultant import (
    draft_screening_memo,
    extract_project_facts_from_document,
)
from document_reader import extract_document_text
from docx_writer import write_screening_docx


BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
OUTPUT_DIR = BASE_DIR / "outputs"


def slugify(value):
    value = value.strip().lower()
    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    return value.strip("_") or "project"


def display_value(value):
    if value is None:
        return "UNKNOWN"

    if value is True:
        return "YES"

    if value is False:
        return "NO"

    return str(value)


def print_intake(intake):
    """Show extracted answers and their evidence."""

    labels = {
        "project_name":
            "Project name",
        "facility_type":
            "Facility type",
        "project_description":
            "Project description",
        "design_year":
            "Design year",
        "design_year_aadt":
            "Design-year AADT",
        "adds_significant_capacity":
            "Adds significant capacity",
        "near_populated_area":
            "Near populated areas",
        "major_intermodal_freight_facility":
            "Major intermodal freight facility",
        "meaningful_truck_traffic_change":
            "Meaningful truck-traffic change",
    }

    evidence = intake["evidence"]

    print(
        "\nOmni Consultant — Document Intake"
    )
    print("=" * 60)

    for field, label in labels.items():
        print(
            f"\n{label}: "
            f"{display_value(intake[field])}"
        )

        source_evidence = evidence.get(field)

        if source_evidence:
            print(
                f"  Evidence: {source_evidence}"
            )
        else:
            print(
                "  Evidence: Not established "
                "in source document"
            )

    if intake["uncertainties"]:
        print("\nUncertainties")
        print("-" * 60)

        for uncertainty in intake["uncertainties"]:
            print(
                f"- {uncertainty}"
            )


def build_project_facts(
    intake,
    source_name,
):
    """Convert intake output to the existing project schema."""

    return {
        "project_name":
            intake["project_name"]
            or Path(source_name).stem,
        "facility_type":
            intake["facility_type"],
        "project_description":
            intake["project_description"],
        "design_year":
            intake["design_year"],
        "design_year_aadt":
            intake["design_year_aadt"],
        "adds_significant_capacity":
            intake["adds_significant_capacity"],
        "near_populated_area":
            intake["near_populated_area"],
        "major_intermodal_freight_facility":
            intake[
                "major_intermodal_freight_facility"
            ],
        "meaningful_truck_traffic_change":
            intake[
                "meaningful_truck_traffic_change"
            ],
        "notes":
            f"Project facts extracted from "
            f"{Path(source_name).name}",
    }


def save_intake(
    intake,
    project_facts,
    source_path,
):
    """Save both audit evidence and downstream project JSON."""

    PROJECTS_DIR.mkdir(
        exist_ok=True
    )

    slug = slugify(
        project_facts["project_name"]
    )

    project_path = (
        PROJECTS_DIR
        / f"{slug}.json"
    )

    audit_path = (
        PROJECTS_DIR
        / f"{slug}_intake_audit.json"
    )

    project_path.write_text(
        json.dumps(
            project_facts,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    audit_record = {
        "source_document":
            str(source_path),
        "project_facts":
            project_facts,
        "evidence":
            intake["evidence"],
        "uncertainties":
            intake["uncertainties"],
    }

    audit_path.write_text(
        json.dumps(
            audit_record,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return project_path, audit_path


def generate_memo(project_facts):
    """Use the existing approved screening workflow."""

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    result = draft_screening_memo(
        project_facts
    )

    slug = slugify(
        project_facts["project_name"]
    )

    markdown_path = (
        OUTPUT_DIR
        / f"{slug}_msat_screening_memo.md"
    )

    docx_path = (
        OUTPUT_DIR
        / f"{slug}_msat_screening_memo.docx"
    )

    markdown_path.write_text(
        result["answer"].strip() + "\n",
        encoding="utf-8",
    )

    write_screening_docx(
        markdown_text=result["answer"],
        project_facts=project_facts,
        output_path=docx_path,
    )

    return markdown_path, docx_path


def confirm():
    while True:
        value = input(
            "\nUse these extracted facts for "
            "MSAT screening? [yes/no]: "
        ).strip().casefold()

        if value in {"yes", "y"}:
            return True

        if value in {"no", "n"}:
            return False

        print(
            "Enter yes or no."
        )


def main():
    if len(sys.argv) >= 2:
        source_path = Path(
            sys.argv[1]
        )
    else:
        source_path = Path(
            input(
                "Project description document path: "
            ).strip().strip('"')
        )

    if not source_path.is_absolute():
        source_path = (
            BASE_DIR / source_path
        ).resolve()

    print(
        f"\nReading project document:\n"
        f"{source_path}"
    )

    document_text = extract_document_text(
        source_path
    )

    print(
        f"\nExtracted "
        f"{len(document_text):,} characters."
    )

    print(
        "\nExtracting project facts..."
    )

    intake = (
        extract_project_facts_from_document(
            document_text=document_text,
            source_name=source_path.name,
        )
    )

    print_intake(
        intake
    )

    if not confirm():
        raise SystemExit(
            "Screening cancelled. "
            "Review the intake evidence before proceeding."
        )

    project_facts = build_project_facts(
        intake=intake,
        source_name=source_path.name,
    )

    project_path, audit_path = save_intake(
        intake=intake,
        project_facts=project_facts,
        source_path=source_path,
    )

    print(
        "\nProject intake saved:"
    )
    print(project_path)

    print(
        "\nIntake evidence saved:"
    )
    print(audit_path)

    print(
        "\nRunning FHWA MSAT screening..."
    )

    markdown_path, docx_path = (
        generate_memo(
            project_facts
        )
    )

    print(
        "\nMSAT screening completed."
    )

    print(
        "\nMarkdown memo:"
    )
    print(markdown_path)

    print(
        "\nWord memo:"
    )
    print(docx_path)


if __name__ == "__main__":
    main()