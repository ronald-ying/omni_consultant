import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DISCIPLINES_DIR = BASE_DIR / "disciplines"


def get_discipline_dir(discipline):
    """Return the configured directory for a discipline."""

    discipline_dir = (
        DISCIPLINES_DIR / discipline
    ).resolve()

    if not discipline_dir.exists():
        raise RuntimeError(
            f"Discipline configuration was not found: "
            f"{discipline}"
        )

    return discipline_dir


def load_discipline_text(
    discipline,
    filename,
):
    """Load a text instruction file for a discipline."""

    path = (
        get_discipline_dir(discipline)
        / filename
    )

    if not path.exists():
        raise RuntimeError(
            f"Discipline instruction file was not found: "
            f"{path}"
        )

    return path.read_text(
        encoding="utf-8"
    ).strip()


def load_discipline_json(
    discipline,
    filename,
):
    """Load a JSON configuration file for a discipline."""

    path = (
        get_discipline_dir(discipline)
        / filename
    )

    if not path.exists():
        raise RuntimeError(
            f"Discipline JSON file was not found: "
            f"{path}"
        )

    with path.open(
        encoding="utf-8"
    ) as file:
        return json.load(file)