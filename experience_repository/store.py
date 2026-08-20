import hashlib
import sqlite3
import uuid

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DEFAULT_DB_PATH = (
    BASE_DIR
    / "repository_data"
    / "experience_repository.db"
)

SCHEMA_PATH = (
    Path(__file__)
    .resolve()
    .parent
    / "schema.sql"
)


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect(db_path=None):
    """Open the experience repository database."""

    path = Path(
        db_path
        or DEFAULT_DB_PATH
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        path
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialize_database(
    connection,
):
    """Create repository tables."""

    schema = SCHEMA_PATH.read_text(
        encoding="utf-8"
    )

    connection.executescript(
        schema
    )

    connection.commit()


def sha256_file(path):
    """Calculate a file's SHA-256 hash."""

    digest = hashlib.sha256()

    with Path(path).open(
        "rb"
    ) as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def get_or_create_project(
    connection,
    name,
):
    """
    Return an existing project with the same
    name or create a new project.
    """

    name = name.strip()

    if not name:
        raise ValueError(
            "Project name cannot be blank."
        )

    existing = connection.execute(
        """
        SELECT id, name
        FROM projects
        WHERE lower(name) = lower(?)
        ORDER BY created_at
        LIMIT 1
        """,
        (name,),
    ).fetchone()

    if existing:
        return (
            existing["id"],
            False,
        )

    project_id = str(
        uuid.uuid4()
    )

    connection.execute(
        """
        INSERT INTO projects (
            id,
            name,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (
            project_id,
            name,
            utc_now(),
        ),
    )

    connection.commit()

    return (
        project_id,
        True,
    )


def register_document(
    connection,
    path,
    extractable=False,
):
    """
    Register a document by content hash.

    Identical files are stored once even if they
    appear in multiple locations.
    """

    path = Path(
        path
    ).resolve()

    if not path.is_file():
        raise ValueError(
            f"Not a file: {path}"
        )

    sha256 = sha256_file(
        path
    )

    existing = connection.execute(
        """
        SELECT id
        FROM documents
        WHERE sha256 = ?
        """,
        (sha256,),
    ).fetchone()

    is_new = existing is None

    if existing:
        document_id = (
            existing["id"]
        )

    else:
        document_id = str(
            uuid.uuid4()
        )

        stat = path.stat()

        connection.execute(
            """
            INSERT INTO documents (
                id,
                sha256,
                file_name,
                extension,
                size_bytes,
                extractable,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                sha256,
                path.name,
                path.suffix.casefold(),
                stat.st_size,
                int(extractable),
                utc_now(),
            ),
        )

    stat = path.stat()

    modified_at = datetime.fromtimestamp(
        stat.st_mtime,
        timezone.utc,
    ).isoformat()

    connection.execute(
        """
        INSERT INTO document_locations (
            document_id,
            file_path,
            modified_at,
            last_seen_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(
            document_id,
            file_path
        )
        DO UPDATE SET
            modified_at =
                excluded.modified_at,
            last_seen_at =
                excluded.last_seen_at
        """,
        (
            document_id,
            str(path),
            modified_at,
            utc_now(),
        ),
    )

    connection.commit()

    return (
        document_id,
        is_new,
    )


def link_document_to_project(
    connection,
    project_id,
    document_id,
):
    """Associate a document with a project."""

    connection.execute(
        """
        INSERT OR IGNORE INTO
        project_documents (
            project_id,
            document_id
        )
        VALUES (?, ?)
        """,
        (
            project_id,
            document_id,
        ),
    )

    connection.commit()


def get_project_summary(
    connection,
    project_id,
):
    """Return basic repository statistics."""

    project = connection.execute(
        """
        SELECT *
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    ).fetchone()

    if project is None:
        raise RuntimeError(
            "Project was not found."
        )

    stats = connection.execute(
        """
        SELECT
            COUNT(*) AS document_count,
            SUM(
                CASE
                    WHEN d.extractable = 1
                    THEN 1
                    ELSE 0
                END
            ) AS extractable_count
        FROM project_documents pd

        JOIN documents d
          ON d.id = pd.document_id

        WHERE pd.project_id = ?
        """,
        (project_id,),
    ).fetchone()

    return {
        "project_id":
            project["id"],
        "project_name":
            project["name"],
        "document_count":
            stats["document_count"] or 0,
        "extractable_count":
            stats["extractable_count"] or 0,
    }