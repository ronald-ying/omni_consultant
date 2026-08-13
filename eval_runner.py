import json
import re
import subprocess
from pathlib import Path
from typing import Any
import unicodedata
from consultant import ask_consultant

DASH_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2212": "-",  # minus sign
    }
)


def normalize_text(value: str) -> str:
    """Normalize Unicode, Markdown, punctuation, and whitespace."""

    value = unicodedata.normalize("NFKC", value)

    value = value.translate(
        str.maketrans(
            {
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2212": "-",
                "\u200b": None,
                "\u200c": None,
                "\u200d": None,
                "\ufeff": None,
            }
        )
    )

    # Remove Markdown emphasis.
    value = value.replace("**", "").replace("__", "")

    # Treat punctuation, including hyphens, as word separators.
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value)

    return " ".join(value.casefold().split())

BASE_DIR = Path(__file__).resolve().parent
APP_PATH = BASE_DIR / "app.py"
EVAL_CASES_PATH = BASE_DIR / "eval_cases.json"

REFUSAL_PHRASES = (
    "cannot be determined",
    "not provided",
    "do not contain",
    "does not contain",
    "insufficient information",
    "not available",
    "cannot determine",
)

PROJECT_VALUE_PATTERNS = (
    re.compile(
        r"(?:your|the)\s+project(?:'s)?\s+(?:2045\s+)?"
        r"aadt\s+(?:is|=|of)\s+[\d,]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"2045\s+aadt\s+(?:is|=)\s+[\d,]+",
        re.IGNORECASE,
    ),
)


def extract_source_pages(output: str) -> dict[str, set[int]]:
    """Extract PDF filenames and pages from inline and listed citations."""

    citation_pattern = re.compile(
        r"(?P<filename>[A-Za-z0-9_.-]+\.pdf),\s*"
        r"electronic PDF page(?:s)?\s+"
        r"(?P<pages>\d+(?:\s*[–-]\s*\d+)?)",
        re.IGNORECASE,
    )

    sources: dict[str, set[int]] = {}

    for match in citation_pattern.finditer(output):
        filename = match.group("filename")
        page_expression = (
            match.group("pages")
            .replace("–", "-")
            .replace(" ", "")
        )

        if "-" in page_expression:
            start_text, end_text = page_expression.split("-", maxsplit=1)
            start_page = int(start_text)
            end_page = int(end_text)

            page_numbers = range(start_page, end_page + 1)
        else:
            page_numbers = [int(page_expression)]

        sources.setdefault(filename, set()).update(page_numbers)

    return sources


def run_application(question: str) -> tuple[int, str]:
    """Call the consultant engine directly."""

    try:
        result = ask_consultant(question)

        output = result["answer"]

        if result["sources"]:
            output += "\n\nRetrieved source pages:\n"

            for source in result["sources"]:
                if source["page"] is not None:
                    output += (
                        f"- {source['filename']}, "
                        f"electronic PDF page {source['page']}\n"
                    )
                else:
                    output += f"- {source['filename']}\n"

        return 0, output

    except Exception as error:
        return 1, f"ERROR: {error}"
    output = completed.stdout

    if completed.stderr:
        output += f"\nSTDERR:\n{completed.stderr}"

    return completed.returncode, output


def evaluate_case(case: dict[str, Any]) -> tuple[bool, list[str], str]:
    return_code, output = run_application(case["question"])
    output_normalized = normalize_text(output)
    failures: list[str] = []

    if return_code != 0:
        failures.append(
            f"Application exited with status {return_code}."
        )

    for required_text in case.get("must_include_all", []):
        if normalize_text(required_text) not in output_normalized:
            failures.append(
                f"Missing required text: {required_text!r}"
            )

    any_terms = case.get("must_include_any", [])

    if any_terms and not any(
        normalize_text(term) in output_normalized
    for term in any_terms
    ):
        failures.append(
            "None of the acceptable terms appeared: "
            + ", ".join(repr(term) for term in any_terms)
        )

    cited_sources = extract_source_pages(output)

    for required_file in case.get("required_source_files", []):
        if required_file not in cited_sources:
            failures.append(
                f"Required source was not cited: {required_file}"
            )

    acceptable_pages = case.get("acceptable_source_pages", {})

    for filename, allowed_pages in acceptable_pages.items():
        cited_pages = cited_sources.get(filename, set())
        allowed_page_set = set(allowed_pages)

        if filename in cited_sources and not (
            cited_pages & allowed_page_set
        ):
            failures.append(
                f"{filename} cited pages {sorted(cited_pages)}, "
                f"but expected one of {sorted(allowed_page_set)}."
            )

    if case.get("must_refuse", False):
        if not any(
                normalize_text(phrase) in output_normalized
                for phrase in REFUSAL_PHRASES
        ):
            failures.append(
                "Expected an explicit unsupported-information refusal."
            )

    if case.get("must_not_claim_project_value", False):
        for pattern in PROJECT_VALUE_PATTERNS:
            match = pattern.search(output)

            if match:
                failures.append(
                    "Possible invented project-specific value: "
                    f"{match.group(0)!r}"
                )
                break

    return not failures, failures, output


def main() -> int:
    if not APP_PATH.exists():
        print(f"ERROR: app.py not found at {APP_PATH}")
        return 1

    if not EVAL_CASES_PATH.exists():
        print(
            f"ERROR: eval_cases.json not found at "
            f"{EVAL_CASES_PATH}"
        )
        return 1

    with EVAL_CASES_PATH.open(encoding="utf-8") as file:
        evaluation_data = json.load(file)

    cases = evaluation_data["cases"]

    print(
        f"Running {len(cases)} FHWA MSAT evaluation cases.\n"
        "Each case makes one live API request.\n"
    )

    passed_count = 0
    failed_outputs: list[tuple[str, str]] = []

    for index, case in enumerate(cases, start=1):
        case_id = case["id"]

        print(f"[{index}/{len(cases)}] {case_id}")

        try:
            passed, failures, output = evaluate_case(case)
        except Exception as error:
            print(f"  FAIL: Unexpected error: {error}\n")
            failed_outputs.append(
                (case_id, str(error))
            )
            continue

        if passed:
            passed_count += 1
            print("  PASS\n")
        else:
            print("  FAIL")

            for failure in failures:
                print(f"   - {failure}")

            print()
            failed_outputs.append((case_id, output))

    failed_count = len(cases) - passed_count

    print("=" * 50)
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Total:  {len(cases)}")

    if failed_outputs:
        print("\nFailed-case outputs:")

        for case_id, output in failed_outputs:
            print("\n" + "-" * 50)
            print(case_id)
            print("-" * 50)
            print(output.strip())

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())