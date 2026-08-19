You are extracting project facts from a transportation project document.

This is DOCUMENT INTAKE ONLY.

Do not apply FHWA MSAT screening guidance.
Do not use outside knowledge.
Do not guess missing project facts.

Answer only from the supplied project document.

EXTRACTION RULES

1. If the document does not support an answer, return null.

2. Preserve the distinction between:
   - explicitly stated facts;
   - reasonable direct extraction from the document;
   - professional judgments that the document itself does not make.

3. For design_year:
   - return a year only when the document establishes it as the
     applicable project design year;
   - a future analysis year appearing somewhere in the document is
     not automatically the design year;
   - if ambiguous, return null and explain the ambiguity.

4. For design_year_aadt:
   - return a value only if the document clearly identifies the
     relevant design-year AADT;
   - if multiple AADT values exist and the applicable value is
     ambiguous, return null and explain the ambiguity.

5. For adds_significant_capacity:
   - return true only when the document establishes new,
     significant, or substantial capacity;
   - return false only when the document supports that conclusion;
   - otherwise return null;
   - do not independently decide that reconstruction, widening,
     interchange modification, or a lane addition constitutes
     significant capacity unless the source supports that
     characterization.

6. For near_populated_area:
   - return true if the document establishes proximity to homes,
     schools, businesses, neighborhoods, populated areas, downtown
     areas, or equivalent development;
   - return false only when the document supports that conclusion;
   - otherwise return null.

7. For major_intermodal_freight_facility:
   - absence of discussion is not false;
   - return null unless the document supports true or false;
   - references to freight, trucks, rail, or industrial activity
     do not by themselves establish a major intermodal freight
     facility.

8. For meaningful_truck_traffic_change:
   - absence of truck information is not false;
   - return null unless the document supports true or false;
   - general freight activity does not by itself establish a
     meaningful project-related truck traffic change.

9. project_description may be a concise grounded synthesis of the
   proposed project.

10. For every non-null answer, provide short source evidence.
    Preserve PDF page, DOCX paragraph, or DOCX table markers when
    available.

11. Do not use evidence from one field to manufacture an unsupported
    answer for another field.

12. Put conflicting, ambiguous, or materially unresolved information
    in uncertainties.

The purpose of this extraction is to create a defensible evidence
record for later professional reasoning. Conservative null values are
preferable to unsupported conclusions.

SUPPORT CLASSIFICATION

For every extracted field, classify the strength of the source support.

Use exactly one of:

explicit
The document directly states the fact or value.

direct
The fact follows unambiguously from the document without requiring
professional or regulatory judgment, even if the exact wording is
not stated.

inferred
The document contains evidence suggesting a particular conclusion,
but reaching that conclusion requires interpretation or professional
judgment.

unsupported
The document does not establish a defensible value.

Rules:

- Every field must receive a support classification.

- If support is "unsupported", the extracted value must be null.

- A value classified as "inferred" is provisional evidence only.
  It must not be treated as a resolved project fact without later
  professional review or stronger supporting evidence.

- Do not upgrade repeated language about goals, needs, improvements,
  or benefits into a definitive technical classification.

- In particular, statements about providing adequate capacity,
  improving operations, reducing congestion, reconstruction,
  widening, or adding connections do not by themselves establish
  "significant capacity" for MSAT screening. If such evidence
  suggests significant capacity but does not establish it, a true
  value may be returned only with support = "inferred".

- Absence of identification is not affirmative evidence of false.
  If a document merely fails to identify a major intermodal freight
  facility, use null with support = "unsupported", unless the source
  affirmatively supports a false conclusion.

- Use "direct" conservatively. If a knowledgeable consultant would
  reasonably need to make a judgment call, use "inferred".