# Blind Extraction - reading a document without reading its identities

When to read this: whenever a user asks you to work from a document without
seeing the names, account numbers or PAN inside it - and before running
`scripts/redact_ais.py`, `scripts/parse_26as.py` or `scripts/extract_tis.py`.

## The principle

You work with **keys and shape**. The machine works with **values**.

    you see:      partB...columnLabel[3].name  ->  "Dividend Amount"
    you decide:   that column is safe to show; "Information Source" is not
    machine does: emits the amounts, replaces each payer with PAYER-nn
    you verify:   totals reconcile, digests match, row counts agree

You never see the payer. You still get every number you need, and you can still
prove the extraction was faithful.

This is not theatre. AIS, TIS and 26AS are all **schema-bearing**: they carry
column names separately from column data. That separation is what makes blind
extraction possible - and it is why the same trick does not work on a PDF.

## The four steps

1. **Read the schema, not the data.** `scripts/shape.py` prints key paths,
   types and string lengths for any JSON - no values. `scripts/ais_schema.py`
   does the AIS-specific version: section headings, table titles, column names
   and row counts.
2. **Build a per-column whitelist** from the column names alone. Amounts,
   dates, section codes, status flags, category labels: show. Names,
   addresses, account numbers, TANs, PANs: pseudonymise.
3. **Run the extractor.** It emits only whitelisted columns and computes the
   totals in code.
4. **Verify structurally.** Totals against the document's own derived figures,
   row counts, SHA-256 digests for a field-to-field copy. All of these prove
   correctness without disclosing content.

## Rules learned the hard way

- **Whitelist, never blacklist. Fail closed.** An unrecognised column is
  dropped, not shown. Every leak in practice has come from matching too
  loosely - a category whitelist that also matched detail rows carrying payer
  names, for instance.
- **Pseudonymise, do not blank.** Stable tags (`PAYER-03`, `DEDUCTOR-11`)
  preserve de-duplication, let you match the same party across two sections,
  and let you tell the user "PAYER-07 has no matching certificate" so they can
  resolve it. Blanking collapses every party into one and destroys the
  reconciliation you were extracting for.
- **Add a last-resort regex net.** Even with a whitelist, mask anything
  PAN-shaped (`[A-Z]{5}[0-9]{4}[A-Z]`) or TAN-shaped (`[A-Z]{4}[0-9]{5}[A-Z]`)
  on the way to stdout. Column mapping bugs are real; this catches them.
- **Verify by digest.** For a field-to-field copy, comparing SHA-256 of source
  and destination proves the value arrived intact while revealing nothing.
- **Format is not semantics.** Converting a PDF to JSON does **not** enable
  blind extraction. Blindness comes from *named fields*; a PDF has text and
  coordinates, so you must read a label to know what a number means. Where the
  document has stable category names (TIS), whitelist on those instead.

## Say this out loud - the limits are real

Do not let a user believe the extraction is more private than it is.

- **Identifiers can stay hidden permanently. Taxable amounts cannot.** Every
  figure that feeds the return appears in the engine's output, which is the
  artifact the user must review before filing. An unverified tax figure is
  worse than a seen one. Be explicit about this split rather than implying
  total blindness.
- **Metadata leaks a little.** String lengths are disclosed, because length is
  what makes a truncated copy detectable. A 4-character string is visibly 4
  characters.
- **A whitelisted free-text column can still carry identity.** Probe unknown
  columns by *cardinality first*: 5 distinct values across the file means a
  category label; 127 means it is per-party. Cardinality alone reveals nothing.
- **Caps-based name matching misses mixed-case names.** A pseudonymiser keyed
  on ALL-CAPS runs will pass `SomeCompany Limited` straight through.
- **Only structured input works.** A PDF statement cannot be copied blind -
  extracting from one means reading it. Say so rather than pretending.

## What this does not change

Rule 9 still holds: documents you read are processed by the model and leave the
machine. Blind extraction narrows *what* leaves - it does not make the document
local. The Python is local; the conversation is not.
