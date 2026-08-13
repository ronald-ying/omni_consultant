import json
import re
import sys
from pathlib import Path

from consultant import draft_screening_memo
from docx_writer import write_screening_docx


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"


def slugify(value):
    """Create a safe filename from a project name."""

    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    return value.strip("_") or "project"


def main():
    project_filename = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "project.json"
    )

    project_path = BASE_DIR / project_filename

    if not project_path.exists():
        raise SystemExit(
            f"Project file was not found: {project_path}"
        )

    with project_path.open(
        encoding="utf-8"
    ) as file:
        project_facts = json.load(file)

    result = draft_screening_memo(
        project_facts
    )

    project_name = project_facts.get(
        "project_name",
        "Unnamed Project",
    )

    output_filename = (
        f"{slugify(project_name)}_"
        f"msat_screening_memo.docx"
    )

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    output_path = (
        OUTPUT_DIR
        / output_filename
    )

    write_screening_docx(
        markdown_text=result["answer"],
        project_facts=project_facts,
        output_path=output_path,
    )

    print(
        "\nMSAT screening Word memorandum created:"
    )

    print(output_path)


if __name__ == "__main__":
    main()