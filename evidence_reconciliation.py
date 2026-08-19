import re


DESCRIPTIVE_FIELDS = [
    "project_name",
    "facility_type",
    "project_description",
]


STRICT_FIELDS = [
    "design_year",
    "design_year_aadt",
    "adds_significant_capacity",
    "near_populated_area",
    "major_intermodal_freight_facility",
    "meaningful_truck_traffic_change",
]


PROJECT_FIELDS = (
    DESCRIPTIVE_FIELDS
    + STRICT_FIELDS
)


STRONG_SUPPORT = {
    "explicit",
    "direct",
}


def normalize_string(value):
    """Normalize strings only for equality comparison."""

    if not isinstance(value, str):
        return value

    value = value.casefold().strip()
    value = re.sub(r"\s+", " ", value)

    return value


def values_match(left, right):
    """Return True when two values are deterministically equivalent."""

    if isinstance(left, str) and isinstance(right, str):
        return (
            normalize_string(left)
            == normalize_string(right)
        )

    return left == right


def build_observations(
    field,
    source_intakes,
):
    """Build source-level observations for one field."""

    observations = []

    for source in source_intakes:
        intake = source["intake"]

        value = intake.get(field)

        evidence = (
            intake.get("evidence", {})
            .get(field)
        )

        support = (
            intake.get("support", {})
            .get(field, "unsupported")
        )

        observations.append(
            {
                "source_document":
                    source["source_document"],
                "value": value,
                "support": support,
                "evidence": evidence,
            }
        )

    return observations


def unique_values(observations):
    """
    Return deterministically unique non-null values.
    """

    values = []

    for observation in observations:
        value = observation["value"]

        if value is None:
            continue

        if not any(
            values_match(
                value,
                existing,
            )
            for existing in values
        ):
            values.append(value)

    return values


def reconcile_descriptive_field(
    field,
    source_intakes,
):
    """
    Preserve descriptive variants rather than treating
    different wording as a factual conflict.
    """

    observations = build_observations(
        field,
        source_intakes,
    )

    usable = [
        observation
        for observation in observations
        if (
            observation["value"] is not None
            and observation["support"]
            != "unsupported"
        )
    ]

    if not usable:
        return {
            "status": "unresolved",
            "resolved_value": None,
            "candidate_values": [],
            "observations": observations,
        }

    candidates = unique_values(
        usable
    )

    if len(candidates) == 1:
        status = (
            "resolved_multiple_sources"
            if len(usable) > 1
            else "resolved_single_source"
        )

        return {
            "status": status,
            "resolved_value": candidates[0],
            "candidate_values": candidates,
            "observations": observations,
        }

    return {
        "status": "multiple_descriptions",
        "resolved_value": None,
        "candidate_values": candidates,
        "observations": observations,
    }


def reconcile_strict_field(
    field,
    source_intakes,
):
    """
    Reconcile decision-oriented facts using evidence
    support strength.

    Explicit/direct evidence may resolve a fact.

    Inferred evidence remains provisional and requires
    professional review.

    Unsupported evidence cannot resolve a fact.
    """

    observations = build_observations(
        field,
        source_intakes,
    )

    data_quality_issues = [
        observation
        for observation in observations
        if (
            observation["support"]
            == "unsupported"
            and observation["value"]
            is not None
        )
    ]

    if data_quality_issues:
        return {
            "status": "data_quality_issue",
            "resolved_value": None,
            "candidate_values":
                unique_values(
                    data_quality_issues
                ),
            "observations": observations,
        }

    strong = [
        observation
        for observation in observations
        if (
            observation["value"] is not None
            and observation["support"]
            in STRONG_SUPPORT
        )
    ]

    inferred = [
        observation
        for observation in observations
        if (
            observation["value"] is not None
            and observation["support"]
            == "inferred"
        )
    ]

    strong_values = unique_values(
        strong
    )

    inferred_values = unique_values(
        inferred
    )

    if len(strong_values) > 1:
        return {
            "status": "conflict",
            "resolved_value": None,
            "candidate_values":
                strong_values,
            "observations": observations,
        }

    if len(strong_values) == 1:
        resolved_value = (
            strong_values[0]
        )

        lower_support_disagreement = any(
            not values_match(
                resolved_value,
                value,
            )
            for value in inferred_values
        )

        if lower_support_disagreement:
            status = (
                "resolved_with_lower_support_disagreement"
            )
        elif len(strong) > 1:
            status = (
                "resolved_multiple_sources"
            )
        else:
            status = (
                "resolved_single_source"
            )

        return {
            "status": status,
            "resolved_value":
                resolved_value,
            "candidate_values":
                strong_values,
            "observations": observations,
        }

    if inferred_values:
        return {
            "status":
                "professional_review_required",
            "resolved_value": None,
            "candidate_values":
                inferred_values,
            "observations": observations,
        }

    return {
        "status": "unresolved",
        "resolved_value": None,
        "candidate_values": [],
        "observations": observations,
    }


def reconcile_field(
    field,
    source_intakes,
):
    """Route each field to its reconciliation strategy."""

    if field in DESCRIPTIVE_FIELDS:
        return reconcile_descriptive_field(
            field,
            source_intakes,
        )

    return reconcile_strict_field(
        field,
        source_intakes,
    )


def reconcile_project_intakes(
    source_intakes,
):
    """
    Create a project knowledge record from multiple
    independent document extractions.
    """

    fields = {}

    for field in PROJECT_FIELDS:
        fields[field] = reconcile_field(
            field,
            source_intakes,
        )

    project_facts = {
        field:
            result["resolved_value"]
        for field, result
        in fields.items()
    }

    return {
        "project_facts":
            project_facts,
        "fields":
            fields,
        "sources":
            source_intakes,
    }