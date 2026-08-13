import json
import re
import sys
from datetime import date
from pathlib import Path

from consultant import draft_screening_memo


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"


def slugify(value):
    """Convert a project name into a safe filename."""

    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)

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

    with project_path.open(encoding="utf-8") as file:
        project_facts = json.load(file)

    result = draft_screening_memo(project_facts)

    project_name = project_facts.get(
        "project_name",
        "Unnamed Project",
    )

    output_filename = (
        f"{slugify(project_name)}_"
        f"msat_screening_memo.md"
    )

    OUTPUT_DIR.mkdir(exist_ok=True)

    output_path = OUTPUT_DIR / output_filename

    memo_text = (
        f"Generated: {date.today().isoformat()}\n\n"
        f"{result['answer'].strip()}\n"
    )

    if result["sources"]:
        memo_text += "\n\n---\n\n## Retrieved Source Pages\n\n"

        for source in result["sources"]:
            if source["page"] is not None:
                memo_text += (
                    f"- {source['filename']}, "
                    f"electronic PDF page {source['page']}\n"
                )
            else:
                memo_text += f"- {source['filename']}\n"

    output_path.write_text(
        memo_text,
        encoding="utf-8",
    )

    print("\nMSAT screening memo created:")
    print(output_path)


if __name__ == "__main__":
    main()