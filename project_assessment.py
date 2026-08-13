import json
from pathlib import Path

from consultant import assess_project


BASE_DIR = Path(__file__).resolve().parent
PROJECT_PATH = BASE_DIR / "project.json"


def main():
    if not PROJECT_PATH.exists():
        raise SystemExit("project.json was not found.")

    with PROJECT_PATH.open(encoding="utf-8") as file:
        project_facts = json.load(file)

    result = assess_project(project_facts)

    print("\nOmni Consultant — MSAT Screening")
    print("=" * 40)
    print(result["answer"])

    if result["sources"]:
        print("\nRetrieved source pages:")

        for source in result["sources"]:
            if source["page"] is not None:
                print(
                    f"- {source['filename']}, "
                    f"electronic PDF page {source['page']}"
                )
            else:
                print(f"- {source['filename']}")


if __name__ == "__main__":
    main()