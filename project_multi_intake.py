import json
import sys
from pathlib import Path

from consultant import (
    extract_project_facts_from_document,
)

from document_reader import (
    SUPPORTED_EXTENSIONS,
    extract_document_text,
)
from evidence_reconciliation import (
    PROJECT_FIELDS,
    reconcile_project_intakes,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"


def display_value(value):
    if value is None:
        return "UNKNOWN"

    if value is True:
        return "YES"

    if value is False:
        return "NO"

    return str(value)


def find_documents(path):
    """
    Accept either one document or a directory containing
    project documents.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Input path was not found: {path}"
        )

    if path.is_file():
        if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {path.suffix}"
            )

        return [path]

    documents = [
        item
        for item in path.rglob("*")
        if (
            item.is_file()
            and item.suffix.casefold()
            in SUPPORTED_EXTENSIONS
        )
    ]

    return sorted(documents)


def extract_source_document(path):
    """Extract one source document independently."""

    print("\n" + "=" * 70)
    print(f"Reading: {path.name}")
    print("=" * 70)

    document_text = extract_document_text(
        path
    )

    print(
        f"Extracted {len(document_text):,} characters."
    )

    print("Extracting structured facts...")

    intake = (
        extract_project_facts_from_document(
            document_text=document_text,
            source_name=path.name,
        )
    )

    return {
        "source_document": str(path),
        "intake": intake,
    }


def print_source_intake(source):
    """Display facts extracted from one document."""

    intake = source["intake"]

    print(
        f"\nSource: "
        f"{Path(source['source_document']).name}"
    )

    for field in PROJECT_FIELDS:
        value = intake.get(field)

        print(
            f"  {field}: "
            f"{display_value(value)}"
        )


def print_reconciliation(record):
    """
    Display the unified project evidence record.
    """

    print("\n")
    print("=" * 70)
    print("Omni Consultant — Multi-Document Evidence Record")
    print("=" * 70)

    for field in PROJECT_FIELDS:
        field_record = record[
            "fields"
        ][field]

        status = field_record[
            "status"
        ]

        value = field_record[
            "resolved_value"
        ]

        label = (
            field.replace("_", " ").title()
        )

        print(f"\n{label}")
        print("-" * len(label))

        print(
            f"Status: {status}"
        )

        print(
            f"Resolved value: "
            f"{display_value(value)}"
        )

        print("Evidence:")

        has_evidence = False

        for observation in field_record[
            "observations"
        ]:
            if (
                observation["value"] is None
                and not observation["evidence"]
            ):
                continue

            has_evidence = True

            source_name = Path(
                observation[
                    "source_document"
                ]
            ).name

            print(
                f"  - {source_name}"
            )

            print(
                f"    Value: "
                f"{display_value(observation['value'])}"
            )
            print(
                f"    Support: "
                f"{observation['support']}"
            )

            if observation["evidence"]:
                print(
                    f"    Evidence: "
                    f"{observation['evidence']}"
                )

        if not has_evidence:
            print(
                "  - No source established this fact."
            )


def print_conflicts(record):
    """Highlight fields requiring human judgment."""

    conflicts = []

    for field, field_record in (
        record["fields"].items()
    ):
        if field_record["status"] == "conflict":
            conflicts.append(
                field
            )

    if not conflicts:
        return

    print("\n")
    print("=" * 70)
    print("PROFESSIONAL REVIEW REQUIRED")
    print("=" * 70)

    print(
        "\nThe following facts conflict across "
        "project documents and were NOT resolved "
        "automatically:"
    )

    for field in conflicts:
        print(
            f"- {field.replace('_', ' ').title()}"
        )


def save_record(record):
    """Save the project evidence record."""

    PROJECTS_DIR.mkdir(
        exist_ok=True
    )

    project_name = (
        record["project_facts"].get(
            "project_name"
        )
        or "multi_document_project"
    )

    safe_name = "".join(
        character.lower()
        if character.isalnum()
        else "_"
        for character in project_name
    )

    safe_name = "_".join(
        part
        for part in safe_name.split("_")
        if part
    )

    path = (
        PROJECTS_DIR
        / f"{safe_name}_knowledge_record.json"
    )

    path.write_text(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def confirm():
    while True:
        value = input(
            "\nSave this reconciled project record? "
            "[yes/no]: "
        ).strip().casefold()

        if value in {"yes", "y"}:
            return True

        if value in {"no", "n"}:
            return False

        print("Enter yes or no.")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage:\n"
            "python project_multi_intake.py "
            "\"path_to_project_folder\""
        )

    input_path = Path(
        sys.argv[1]
    ).resolve()

    documents = find_documents(
        input_path
    )

    if not documents:
        raise SystemExit(
            "No supported project documents were found."
        )

    print(
        f"\nFound {len(documents)} supported document(s)."
    )

    for document in documents:
        print(
            f"- {document.name}"
        )

    source_intakes = []

    for document in documents:
        source = extract_source_document(
            document
        )

        source_intakes.append(
            source
        )

        print_source_intake(
            source
        )

    record = reconcile_project_intakes(
        source_intakes
    )

    print_reconciliation(
        record
    )

    print_conflicts(
        record
    )

    if not confirm():
        raise SystemExit(
            "Project record was not saved."
        )

    record_path = save_record(
        record
    )

    print(
        "\nProject knowledge record saved:"
    )

    print(
        record_path
    )


if __name__ == "__main__":
    main()