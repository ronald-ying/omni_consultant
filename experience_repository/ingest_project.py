import sys

from pathlib import Path

from document_reader import (
    SUPPORTED_EXTENSIONS,
)

from experience_repository.store import (
    connect,
    get_or_create_project,
    get_project_summary,
    initialize_database,
    link_document_to_project,
    register_document,
)


SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
}


def should_skip(path):
    """Skip temporary or repository-internal files."""

    if path.name.startswith("~$"):
        return True

    for part in path.parts:
        if part in SKIP_DIRECTORIES:
            return True

    return False


def find_files(path):
    """
    Find project files.

    All file types are cataloged, even if Omni
    Consultant cannot yet extract their text.
    """

    path = Path(
        path
    ).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Path not found: {path}"
        )

    if path.is_file():
        return [path]

    files = [
        item
        for item in path.rglob("*")
        if (
            item.is_file()
            and not should_skip(item)
        )
    ]

    return sorted(
        files
    )


def is_extractable(path):
    """Return whether current document_reader supports the file."""

    return (
        Path(path)
        .suffix
        .casefold()
        in SUPPORTED_EXTENSIONS
    )


def main():
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage:\n"
            "python -m "
            "experience_repository.ingest_project "
            "\"Project Name\" "
            "\"path_to_project_folder\""
        )

    project_name = (
        sys.argv[1]
    )

    source_path = Path(
        sys.argv[2]
    ).resolve()

    files = find_files(
        source_path
    )

    if not files:
        raise SystemExit(
            "No project files were found."
        )

    connection = connect()

    try:
        initialize_database(
            connection
        )

        (
            project_id,
            project_created,
        ) = get_or_create_project(
            connection,
            project_name,
        )

        print(
            "\n# Omni Consultant — "
            "Experience Repository"
        )

        print(
            f"\nProject: {project_name}"
        )

        print(
            f"Project ID: {project_id}"
        )

        print(
            "Project status: "
            + (
                "created"
                if project_created
                else "existing"
            )
        )

        print(
            f"\nFound {len(files)} file(s).\n"
        )

        new_documents = 0
        existing_documents = 0

        for path in files:
            extractable = (
                is_extractable(path)
            )

            (
                document_id,
                is_new,
            ) = register_document(
                connection,
                path,
                extractable=extractable,
            )

            link_document_to_project(
                connection,
                project_id,
                document_id,
            )

            if is_new:
                new_documents += 1
                status = "NEW"

            else:
                existing_documents += 1
                status = "EXISTING"

            text_status = (
                "text-supported"
                if extractable
                else "catalog-only"
            )

            print(
                f"[{status}] "
                f"[{text_status}] "
                f"{path.name}"
            )

        summary = (
            get_project_summary(
                connection,
                project_id,
            )
        )

        print(
            "\nRepository update complete."
        )

        print(
            "\nProject summary:"
        )

        print(
            f"  Documents: "
            f"{summary['document_count']}"
        )

        print(
            f"  Text-extractable: "
            f"{summary['extractable_count']}"
        )

        print(
            f"  Newly registered: "
            f"{new_documents}"
        )

        print(
            f"  Already known: "
            f"{existing_documents}"
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()