---
name: assigning-lc-subject-headings
description: Assigns Library of Congress Subject Headings (LCSH) from bibliographic descriptions using the lc-vocabularies-mcp-server tools. Use when a user provides a title page, table of contents, publisher description, or other bibliographic information and asks for subject headings or cataloging metadata. Always use lc-vocabularies-mcp-server tools exclusively for all lookups; disclose when drawing on outside knowledge.
---

# Assigning LC Subject Headings

## Overview

This skill assigns appropriate Library of Congress subject headings from bibliographic descriptions. All authority lookups MUST use the lc-vocabularies-mcp-server tools. If cataloging knowledge outside those tools is applied (e.g., LCGFT genre/form terms), disclose this explicitly in the response.

**Scope:** Subject analysis only. Do not search for or report name authority headings for the
work's own creators or contributors (authors, editors, translators, etc.). Do search for and
report personal names, family names, and corporate/meeting names when the work is *about* those
entities — these are name-as-subject headings and are fully in scope.

## Workflow

When given a bibliographic description (title page, table of contents, publisher blurb, or similar):

1. Identify candidate subjects: persons, families, corporate bodies, meetings, places, and themes
   that the work is *about* — not the work's own creators or contributors
2. Search all relevant subject heading types using the protocols below
3. Check geographic subdivision eligibility for relevant topical headings
4. Retrieve scope notes only when two or more confirmed headings could plausibly apply to the
   same concept and the distinction cannot be resolved from the heading labels alone.
5. Report results grouped by heading type, with URIs, noting any headings unconfirmed by the tools.
   Do not include MARC field tags or indicators in responses. Present headings by type
   (topical subject, corporate name subject, geographic name subject, etc.) with URIs and notes only.
6. Disclose any genre/form terms or other cataloging conventions applied from outside the tools

## Parallelization and Triage

Searches are slow when run sequentially. To minimize round-trips, apply this three-round structure:

### Round 1 — Triage (before touching the tools)

Read the bibliographic description and produce a candidate list, grouped by type:

- **Personal and family names to search (as subjects):** only when the work is substantially
  about a specific person or family. Skip persons unlikely to be established in LCNAF (obscure
  historical figures, recent thesis authors, etc.) — note as probable NACO gaps rather than
  wasting a search call.
  - If a personal name on the source includes a middle name or initial, list it twice as separate
    Round 2 candidates: once as the full form (e.g. `Westwood, Jean Miles`) and once as
    surname + forename only (e.g. `Westwood, Jean`). Both fire in Round 2 simultaneously — do
    not wait for the full form to fail before queuing the shorter form.
  - If a name is predictably common (e.g. a generic surname with a common forename), flag it
    during triage so that all `get_authority_record` calls needed in Round 3 are batched together
    in one parallel group rather than retrieved one at a time.
- **Corporate/geographic/meeting names to search:** only if the work is substantially about an
  institution, place, or event.
- **Topical headings to search:** identify 4–8 core concepts, sized to fit the 6–10 heading
  budget *before any searches begin*. The budget is a hard constraint on the Round 1 candidate
  list, not a post-hoc culling instruction — if the candidate list exceeds budget at triage,
  drop the weakest candidates now. Prefer concrete, well-established LCSH strings over
  speculative or compound phrases. Do not search the same concept twice with minor wording
  variation in the same round.
- **Scope notes needed:** note any pairs of confirmed headings where the labels alone do not
  resolve which applies — retrieve scope notes for these in Round 3 only, never pre-emptively.

### Round 2 — Parallel first-pass searches

Fire all Round 1 candidates simultaneously in a single batch. Use left-anchored searches
(`search_lcsh`, `search_corporate_name`, etc.) as the default. Only use keyword variants in Round 2
if the left-anchored form is clearly unsuitable (e.g. meeting names, or a concept unlikely to
start with the first word of the heading).

For personal names with middle names or initials: fire both the full form and the
surname+forename form in the same Round 2 batch. The keyword fallback (step 3 of the personal
name protocol) remains a Round 3 fallback only if both forms miss.

### Round 3 — Targeted follow-up only

Run keyword fallbacks, additional searches, scope note retrievals, and authority record
confirmations only for candidates that actually need them based on Round 2 results. Do not run
fallbacks pre-emptively.

When multiple `get_authority_record` calls are needed (e.g. to disambiguate a common name that
returned several candidates), batch all of them into one parallel call group rather than
retrieving records one at a time.

---

## Tool Reference

| Task | Tool |
|---|---|
| Topical subjects (left-anchored) | `lcvocab:search_lcsh` |
| Topical subjects (keyword) | `lcvocab:search_lcsh_keyword` |
| Personal names (left-anchored) | `lcvocab:search_personal_name` |
| Personal names (keyword) | `lcvocab:search_personal_name_keyword` |
| Family names (left-anchored) | `lcvocab:search_family_name` |
| Family names (keyword) | `lcvocab:search_family_name_keyword` |
| Corporate bodies (left-anchored) | `lcvocab:search_corporate_name` |
| Corporate bodies (keyword) | `lcvocab:search_corporate_name_keyword` |
| Geographic names (left-anchored) | `lcvocab:search_geographic_name` |
| Geographic names (keyword) | `lcvocab:search_geographic_name_keyword` |
| Meeting/conference names (left-anchored) | `lcvocab:search_meeting_name` |
| Meeting/conference names (keyword) | `lcvocab:search_meeting_name_keyword` |
| Full authority record | `lcvocab:get_authority_record` |
| Scope note | `lcvocab:get_scope_note` |

---

## Search Protocols

### Personal Names (as subjects)

Use when the work is substantially *about* a specific person. Do not use for the work's own
authors or contributors.

Names on sources often include middle names or fuller forms not reflected in the authorized
heading. Always follow this fallback sequence — do not skip steps.

**Step 1:** Search the full name as it appears on the source.
`lcvocab:search_personal_name` → `Westwood, Jean Miles`

**Step 2:** If the name includes a middle name or initial, fire this simultaneously with Step 1
in Round 2 — do not wait for Step 1 to fail first. Search surname + forename only.
`lcvocab:search_personal_name` → `Westwood, Jean`

**Step 3:** If both Step 1 and Step 2 return no results, keyword search on surname + forename.
`lcvocab:search_personal_name_keyword` → `Westwood Jean`

**Step 4:** If multiple candidates or ambiguous results, retrieve the full authority record to
confirm by checking dates, variant names, and source citations. If multiple records need
checking, batch all `get_authority_record` calls in one parallel group.
`lcvocab:get_authority_record` → `http://id.loc.gov/authorities/names/n92093273`

**Step 5:** Only after all four steps fail should you conclude no authority record exists.

> **Why this matters:** The authorized form of a name frequently omits middle names present on the
> source. A left-anchored search on the fuller form will miss the record entirely without this
> fallback sequence. Example: *Westwood, Jean Miles* (source) → authorized heading
> *Westwood, Jean, 1923-1997*. Firing Steps 1 and 2 in parallel eliminates a sequential
> round-trip in the common case where the full form misses.

> **Ambiguous results:** When a name search returns multiple plausible candidates (e.g. common
> surnames, relatives sharing a name), retrieve authority records for the 2–3 most plausible
> candidates and compare dates, occupations, fields of activity, and source citations. Batch all
> these retrievals into one parallel call group. Do not silently select one candidate. Flag the
> ambiguity explicitly and ask the cataloger to confirm before proceeding.

---

### Family Names (as subjects)

Use for dynasties, noble houses, clans, and other named family groups (e.g. *Kennedy family*,
*Rothschild family*) when the work is substantially *about* that family. These are distinct from
personal name headings and require their own tools.

**Step 1:** Left-anchored search.
`lcvocab:search_family_name` → `Medici family`

**Step 2:** If no results, keyword search.
`lcvocab:search_family_name_keyword` → `Medici`

> **Do not use `search_personal_name` for family names.** The two authority types are indexed
> separately and cross-searching will miss records.

---

### Corporate Bodies

**Step 1:** Left-anchored search.
`lcvocab:search_corporate_name` → `Democratic National Committee`

**Step 2:** If no results, keyword search — useful when the distinctive word is not first.
`lcvocab:search_corporate_name_keyword` → `Democratic National Committee`

**Step 3:** If the result is ambiguous or has relevant subordinate bodies, retrieve the full
authority record to confirm.

> **Note:** Political parties are established as corporate name headings in LCNAF, not as LCSH
> topical headings. If a topical search for a party name fails, try `lcvocab:search_corporate_name`.

---

### Meeting Names

Meeting names include year and location qualifiers that make left-anchored searches unreliable.

**Step 1:** Left-anchored search on the conference name alone.
`lcvocab:search_meeting_name` → `Democratic National Convention`

**Step 2:** If no results or incomplete results, keyword search including year.
`lcvocab:search_meeting_name_keyword` → `Democratic National Convention 1972`

---

### Topical Subjects

**Step 1:** Left-anchored search on the most likely heading string.
`lcvocab:search_lcsh` → `Women politicians`

**Step 2:** If no results, broaden or reorder terms and use keyword search.
`lcvocab:search_lcsh_keyword` → `women political party leaders`

**Step 3:** Check `maySubdivideGeographically` in results. If `true`, append `--[Place]` as
appropriate (e.g., `--United States`).

**Step 4:** If two or more confirmed headings are plausible for the same concept and the labels
alone do not resolve the choice, retrieve the scope note for the ambiguous heading(s) to determine
which applies.
`lcvocab:get_scope_note` → `http://id.loc.gov/authorities/subjects/sh85147597`

---

### Geographic Names

**Step 1:** Left-anchored search.
`lcvocab:search_geographic_name` → `Utah`

**Step 2:** If no results, keyword search.
`lcvocab:search_geographic_name_keyword` → `Utah`

---

## Disclosure Conventions

When a suggestion relies on knowledge outside the lc-vocabularies-mcp-server tools, flag it clearly.
Example:

> *Note: The genre/form term **Autobiographies** (from LCGFT) would also be appropriate — this is
> based on general cataloging knowledge, not confirmed through these tools.*

---

## Common Pitfalls

- **Creators vs. subjects:** Do not search for or report name authority headings for the work's
  own authors, editors, translators, or other contributors. Personal, family, and corporate name
  tools are used only when those entities are the *subject* of the work.
- **Middle names on sources** are frequently absent from authorized headings — fire both the full
  form and the surname+forename form in Round 2 simultaneously rather than waiting for one to fail.
- **Ambiguous personal name results** — when multiple candidates share a name, batch all
  `get_authority_record` calls into one parallel group, then flag ambiguity to the cataloger.
  Do not silently select one.
- **Political parties** are LCNAF corporate names, not LCSH topical headings.
- **Geographic subdivision** — only append `--[Place]` if `maySubdivideGeographically` is
  confirmed `true` for that heading.
- **Speculative keyword fallbacks are a major source of unnecessary tool calls and latency.**
  If a concept (e.g. "dissonant heritage," "borderlands," "collective trauma") is specialized
  or emerging terminology unlikely to appear verbatim in LCSH, flag it as a probable gap during
  Round 1 triage and do not search for it at all. Two failed search calls per gap add up quickly
  across a session. Only search for a concept if there is a plausible, concrete LCSH string for
  it — not merely because the concept is present in the work.
- **Recent conflict and event headings** may use authorized forms that bear no resemblance to
  intuitive keyword queries. For example, the heading for the 2022 Russian invasion of Ukraine is
  established as *Russian Invasion of Ukraine, 2022* — keyword searches on "Russia Ukraine war",
  "Russo-Ukrainian War", or similar strings return nothing. When both left-anchored and keyword
  searches fail for a well-known recent event, use `lcvocab:get_authority_record` with a URI
  obtained directly from id.loc.gov rather than concluding the heading does not exist.