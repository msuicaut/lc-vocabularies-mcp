# lc-vocabularies-mcp — MCP server for Library of Congress linked data APIs
# Copyright (C) 2026  May S. Chan (University of Toronto)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from mcp.server.fastmcp import FastMCP
import requests
import traceback
import xml.etree.ElementTree as ET

mcp = FastMCP("lc vocabularies mcp server")

# ---------------------------------------------------------------------------
# Internal helper — shared response-parsing logic for all suggest2 endpoints.
# All public tools call this; only the URL and params differ between tools.
# ---------------------------------------------------------------------------

def _call_suggest2(url: str, params: dict) -> dict:
    """
    Make a GET request to any id.loc.gov suggest2 endpoint and return a
    normalised dict with a 'results' list of {label, uri} pairs, or an
    'error' key if something went wrong.
    """
    headers = {"User-Agent": "lc vocabularies mcp server/1.0 (contact: ms.chan@utoronto.ca)"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        try:
            data = response.json()
        except Exception as json_err:
            return {
                "error": f"Failed to parse JSON: {json_err}",
                "raw_response": response.text,
                "type": type(json_err).__name__,
                "traceback": traceback.format_exc(),
            }

        # Primary format: dict with 'hits' key (suggest2 standard)
        if isinstance(data, dict) and "hits" in data:
            results = []
            for hit in data["hits"]:
                label = hit.get("aLabel") or hit.get("label") or ""
                uri = hit.get("uri") or ""
                results.append({"label": label, "uri": uri})
            return {"results": results}

        # Fallback A: list of dicts with label/uri keys
        if (
            isinstance(data, list)
            and len(data) > 0
            and isinstance(data[0], dict)
            and ("aLabel" in data[0] or "label" in data[0])
            and "uri" in data[0]
        ):
            results = []
            for hit in data:
                label = hit.get("aLabel") or hit.get("label") or ""
                uri = hit.get("uri") or ""
                results.append({"label": label, "uri": uri})
            return {"results": results}

        # Fallback B: [query, [labels], [uris]] (older suggest API shape)
        if (
            isinstance(data, list)
            and len(data) >= 3
            and isinstance(data[1], list)
            and isinstance(data[2], list)
        ):
            if len(data[1]) != len(data[2]):
                return {
                    "error": "Mismatch in lengths of label and URI lists in API response",
                    "data": data,
                }
            results = []
            for label_item, uri_item in zip(data[1], data[2]):
                results.append({
                    "label": str(label_item) if label_item is not None else "",
                    "uri": str(uri_item) if uri_item is not None else "",
                })
            return {"results": results}

        return {"error": "Unexpected API response format", "data": data}

    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


# ---------------------------------------------------------------------------
# Internal helper — geographic subdivision check via MADS/RDF JSON-LD.
# Called automatically for the top 6 results of every LCSH search.
# Limit of 6 reflects H 180's general maximum of six subject headings per work.
# ---------------------------------------------------------------------------

def _check_geographic_subdivision(uri: str, headers: dict) -> bool | None:
    """
    Fetch the .madsrdf.json record for a subject heading URI and return whether
    the heading is a member of collection_SubdivideGeographically.
    Returns True, False, or None if the check could not be completed.

    Uses https:// for the HTTP request (id.loc.gov redirects http:// to https://)
    but matches against both http:// and https:// forms of the node @id, since
    the JSON-LD graph may use either form depending on the record.
    """
    MADS_COLLECTION = "http://www.loc.gov/mads/rdf/v1#isMemberOfMADSCollection"
    try:
        canonical = uri.rstrip("/")
        safe_uri = canonical.replace("http://", "https://")
        response = requests.get(safe_uri + ".madsrdf.json", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        # The response is a JSON-LD graph — a list of nodes.
        # Find the main concept node whose @id matches the canonical URI
        # in either http:// or https:// form.
        if isinstance(data, list):
            for node in data:
                node_id = node.get("@id", "").rstrip("/")
                if isinstance(node, dict) and (node_id == canonical or node_id == safe_uri):
                    for entry in node.get(MADS_COLLECTION, []):
                        if "SubdivideGeographically" in entry.get("@id", ""):
                            return True
                    return False
        return None
    except Exception:
        return None


def _enrich_with_geographic(results: list, headers: dict) -> list:
    """
    For the top 6 results, add a maySubdivideGeographically field by calling
    _check_geographic_subdivision on each URI.  Results beyond the top 6 are
    returned as-is without enrichment.

    The limit of 6 reflects H 180's general maximum of six subject headings
    per work, ensuring enrichment covers all headings likely to be assigned.
    """
    enriched = []
    for i, result in enumerate(results):
        if i < 6 and result.get("uri"):
            may_subdivide = _check_geographic_subdivision(result["uri"], headers)
            enriched.append({**result, "maySubdivideGeographically": may_subdivide})
        else:
            enriched.append(result)
    return enriched


# ---------------------------------------------------------------------------
# LCSH tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_lcsh(query: str) -> dict:
    """
    Search Library of Congress Subject Headings (LCSH) by left-anchored
    string match using the public suggest2 API.
    Returns a dictionary with the top results. The top 6 results
    automatically include a maySubdivideGeographically field (True/False/None)
    derived from the MADS/RDF authority record, reflecting the general maximum
    of six subject headings per work per H 180.
    """
    headers = {"User-Agent": "lc vocabularies mcp server/1.0 (contact: ms.chan@utoronto.ca)"}
    response = _call_suggest2(
        url="https://id.loc.gov/authorities/subjects/suggest2",
        params={"q": query, "count": 25},
    )
    if "results" in response:
        response["results"] = _enrich_with_geographic(response["results"], headers)
    return response


@mcp.tool()
def search_lcsh_keyword(query: str) -> dict:
    """
    Search Library of Congress Subject Headings (LCSH) by keyword using
    the public suggest2 API.  Use this when a left-anchored search returns
    no results or the heading may not start with the query term.
    Returns a dictionary with the top results. The top 6 results
    automatically include a maySubdivideGeographically field (True/False/None)
    derived from the MADS/RDF authority record, reflecting the general maximum
    of six subject headings per work per H 180.
    """
    headers = {"User-Agent": "lc vocabularies mcp server/1.0 (contact: ms.chan@utoronto.ca)"}
    response = _call_suggest2(
        url="https://id.loc.gov/authorities/subjects/suggest2",
        params={"q": query, "searchtype": "keyword", "count": 50},
    )
    if "results" in response:
        response["results"] = _enrich_with_geographic(response["results"], headers)
    return response


# ---------------------------------------------------------------------------
# LCNAF tools — one per name entity type
# ---------------------------------------------------------------------------

@mcp.tool()
def search_personal_name(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for PERSONAL NAMES
    (individuals) using the public suggest2 API.
    Use this for authors, composers, artists, and other individual persons
    (MARC 100 / 600 / 700).
    For family names (dynasties, clans, noble houses) use search_family_name.
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "PersonalName", "count": 25},
    )


@mcp.tool()
def search_personal_name_keyword(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for PERSONAL NAMES
    (individuals) using keyword search.
    Use this when a left-anchored personal name search returns no results,
    or when the name may not start with the query term
    (e.g. searching "Darwin" to find "Darwin, Charles, 1809-1882").
    For family names use search_family_name_keyword.
    For corporate bodies use search_corporate_name_keyword.
    For geographic names use search_geographic_name_keyword.
    For meetings use search_meeting_name_keyword.
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "PersonalName", "searchtype": "keyword", "count": 50},
    )


@mcp.tool()
def search_corporate_name(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for CORPORATE BODY
    NAMES using the public suggest2 API.
    Use this for organizations, institutions, universities, government
    bodies, publishers, and other corporate entities (MARC 110 / 610 / 710).
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "CorporateName", "count": 25},
    )


@mcp.tool()
def search_geographic_name(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for GEOGRAPHIC NAMES
    using the public suggest2 API.
    Use this for place names used as headings or added entries, distinct from
    LCSH geographic subject headings (MARC 151 / 651 / 751).
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "Geographic", "count": 25},
    )


@mcp.tool()
def search_meeting_name(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for MEETING / CONFERENCE
    NAMES using the public suggest2 API.
    Use this for named conferences, congresses, symposia, and similar events
    (MARC 111 / 611 / 711).
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "ConferenceName", "count": 25},
    )


@mcp.tool()
def search_meeting_name_keyword(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for MEETING / CONFERENCE
    NAMES using keyword search.
    Use this when a left-anchored meeting name search returns no results,
    or when the conference name may not start with the query term
    (e.g. searching "climate" to find "World Conference on Climate Change").
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "ConferenceName", "searchtype": "keyword", "count": 50},
    )


@mcp.tool()
def search_corporate_name_keyword(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for CORPORATE BODY
    NAMES using keyword search.
    Use this when a left-anchored corporate name search returns no results,
    or when the organization name may not start with the query term
    (e.g. searching "Toronto" to find "University of Toronto").
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "CorporateName", "searchtype": "keyword", "count": 50},
    )


@mcp.tool()
def search_geographic_name_keyword(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for GEOGRAPHIC NAMES
    using keyword search.
    Use this when a left-anchored geographic name search returns no results,
    or when the place name may not start with the query term.
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "Geographic", "searchtype": "keyword", "count": 50},
    )


@mcp.tool()
def search_family_name(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for FAMILY NAMES
    using the public suggest2 API.
    Use this for dynasties, noble houses, clans, and other named family groups
    established as authority headings (MARC 100 first indicator 3 / 600 / 700).
    Family name headings are distinct from personal name headings and are
    entered under the family surname followed by the word "family", e.g.
    "Kennedy family" or "Rothschild family".
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "FamilyName", "count": 25},
    )


@mcp.tool()
def search_family_name_keyword(query: str) -> dict:
    """
    Search Library of Congress Name Authorities (LCNAF) for FAMILY NAMES
    using keyword search.
    Use this when a left-anchored family name search returns no results,
    or when the family name may not start with the query term
    (e.g. searching "Tudor" to find "Tudor family").
    Returns a dictionary with the top results.
    """
    return _call_suggest2(
        url="https://id.loc.gov/authorities/names/suggest2",
        params={"q": query, "rdftype": "FamilyName", "searchtype": "keyword", "count": 50},
    )


# ---------------------------------------------------------------------------
# Scope note retrieval
# ---------------------------------------------------------------------------

SKOS_NOTE       = "http://www.w3.org/2004/02/skos/core#note"
SKOS_SCOPE_NOTE = "http://www.w3.org/2004/02/skos/core#scopeNote"
SKOS_PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"

@mcp.tool()
def get_scope_note(uri: str) -> dict:
    """
    Retrieve the scope note (usage guidance) for an LC authority record
    using its URI.

    Best used with LCSH subject heading URIs
    (https://id.loc.gov/authorities/subjects/...), where scope notes are
    common and carry meaningful cataloging guidance.

    Also works with LCNAF name authority URIs
    (https://id.loc.gov/authorities/names/...), but scope notes are rare
    for name records — a missing note is normal and does not indicate an
    error.

    uri: the full URI returned by any search tool, e.g.
         https://id.loc.gov/authorities/subjects/sh85021262
         https://id.loc.gov/authorities/names/n79133651

    Returns the preferred label, scope note text, and — for name authority
    URIs — a warning that scope notes are uncommon for name records.
    """
    canonical = uri.rstrip("/")

    # Detect record type from the URI path so we can attach a warning for
    # name authority records, where scope notes are uncommon.
    is_name_authority = "/authorities/names/" in canonical
    is_subject = "/authorities/subjects/" in canonical

    if not is_name_authority and not is_subject:
        return {
            "error": (
                "Unrecognised URI pattern. Expected a URI containing "
                "'/authorities/subjects/' or '/authorities/names/'."
            ),
            "uri": canonical,
        }

    # The skos.json endpoint returns raw JSON-LD: a flat list of graph nodes.
    # We find the node whose @id matches the canonical URI, then extract
    # skos:note (used by LC) and skos:scopeNote (the formal SKOS property).
    url = canonical + ".skos.json"
    headers = {"User-Agent": "lc vocabularies mcp server/1.0 (contact: ms.chan@utoronto.ca)"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        try:
            graph = response.json()
        except Exception as json_err:
            return {
                "error": f"Failed to parse JSON: {json_err}",
                "raw_response": response.text,
                "type": type(json_err).__name__,
                "traceback": traceback.format_exc(),
            }

        if not isinstance(graph, list):
            return {"error": "Unexpected response format: expected a JSON-LD list", "data": graph}

        # Find the main concept node — its @id is the canonical URI
        concept_node = next(
            (node for node in graph if isinstance(node, dict) and node.get("@id") == canonical),
            None,
        )

        if concept_node is None:
            return {"error": f"Could not find concept node for URI: {canonical}"}

        # Extract preferred label
        pref_label = ""
        for entry in concept_node.get(SKOS_PREF_LABEL, []):
            if isinstance(entry, dict):
                pref_label = entry.get("@value", "")
                break

        # Extract note text — LC uses skos:note; skos:scopeNote is also checked
        # as a fallback for records that use the formal property.
        note_values = []
        for prop in (SKOS_NOTE, SKOS_SCOPE_NOTE):
            for entry in concept_node.get(prop, []):
                if isinstance(entry, dict):
                    text = entry.get("@value", "").strip()
                    if text and text not in note_values:
                        note_values.append(text)

        result = {
            "uri": canonical,
            "prefLabel": pref_label,
            "scopeNote": note_values[0] if len(note_values) == 1 else (note_values or None),
        }

        if not note_values:
            result["message"] = "No scope note found for this record."

        # Attach a contextual warning for name authority records so the caller
        # knows a missing note is expected and not a failure.
        if is_name_authority:
            result["warning"] = (
                "This is a name authority record. Scope notes are uncommon for "
                "name records — a missing note does not indicate an error."
            )

        return result

    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


# ---------------------------------------------------------------------------
# Full authority record retrieval
# ---------------------------------------------------------------------------

# XML namespace map used when parsing .rdf (RDF/XML) authority records
_RDF_NS = {
    "rdf":    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs":   "http://www.w3.org/2000/01/rdf-schema#",
    "skos":   "http://www.w3.org/2004/02/skos/core#",
    "mads":   "http://www.loc.gov/mads/rdf/v1#",
    "schema": "http://schema.org/",
    "owl":    "http://www.w3.org/2002/07/owl#",
    "bf":     "http://id.loc.gov/ontologies/bibframe/",
    "identifiers": "http://id.loc.gov/vocabulary/identifiers/",
}


def _rdf_text(el) -> str:
    """Return stripped text content of an XML element, or ''."""
    return (el.text or "").strip()


def _rdf_resource(el) -> str:
    """Return the rdf:resource attribute of an XML element, or ''."""
    return el.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource", "").strip()


def _rdf_label_for(root, uri: str) -> str | None:
    """
    Search the RDF/XML graph for a node with rdf:about == uri and return
    its rdfs:label, skos:prefLabel, or mads:authoritativeLabel text.
    Returns None if not found.
    """
    for el in root:
        about = el.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")
        if about.rstrip("/") == uri.rstrip("/"):
            for tag in (
                "{http://www.w3.org/2000/01/rdf-schema#}label",
                "{http://www.w3.org/2004/02/skos/core#}prefLabel",
                "{http://www.loc.gov/mads/rdf/v1#}authoritativeLabel",
            ):
                child = el.find(tag)
                if child is not None and child.text:
                    return child.text.strip()
    return None


@mcp.tool()
def get_authority_record(uri: str) -> dict:
    """
    Retrieve the full authority record for an LC name or subject authority URI.

    Returns structured data including: preferred label, variant names,
    birth and death dates, birth and death places, gender, nationality,
    occupation, field of activity, LC classification number (for subject
    headings), and source citations.

    Works with both LCNAF name authority URIs
    (https://id.loc.gov/authorities/names/...) and LCSH subject heading URIs
    (https://id.loc.gov/authorities/subjects/...).

    uri: the full URI returned by any search tool, e.g.
         https://id.loc.gov/authorities/names/n92033083
         https://id.loc.gov/authorities/subjects/sh85021262

    Returns a dict with all available fields. Fields absent from the
    authority record are omitted from the result rather than returned as null.
    """
    canonical = uri.rstrip("/")
    safe_canonical = canonical.replace("http://", "https://")

    is_name_authority = "/authorities/names/" in canonical
    is_subject        = "/authorities/subjects/" in canonical

    if not is_name_authority and not is_subject:
        return {
            "error": (
                "Unrecognised URI pattern. Expected a URI containing "
                "'/authorities/subjects/' or '/authorities/names/'."
            ),
            "uri": canonical,
        }

    headers = {"User-Agent": "lc vocabularies mcp server/1.0 (contact: ms.chan@utoronto.ca)"}

    try:
        response = requests.get(safe_canonical + ".rdf", headers=headers, timeout=10)
        response.raise_for_status()

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as xml_err:
            return {
                "error": f"Failed to parse RDF/XML: {xml_err}",
                "raw_response": response.text[:2000],
                "traceback": traceback.format_exc(),
            }

        # Find the primary Description element — the one whose rdf:about
        # matches the canonical URI (try both http:// and https:// forms).
        primary = None
        for el in root:
            about = el.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "").rstrip("/")
            if about in (canonical, safe_canonical):
                primary = el
                break

        if primary is None:
            return {
                "error": "Could not find primary Description element in RDF/XML",
                "uri": canonical,
                "top_level_elements": [el.tag for el in root][:20],
            }

        result = {"uri": canonical}

        # ── Preferred / authoritative label ──────────────────────────────────
        for tag in (
            "{http://www.loc.gov/mads/rdf/v1#}authoritativeLabel",
            "{http://www.w3.org/2004/02/skos/core#}prefLabel",
            "{http://www.w3.org/2000/01/rdf-schema#}label",
        ):
            el = primary.find(tag)
            if el is not None and el.text:
                result["prefLabel"] = el.text.strip()
                break

        # ── Record type(s) ────────────────────────────────────────────────────
        record_types = []
        for el in primary.findall("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}type"):
            res = _rdf_resource(el)
            if res:
                record_types.append(res.split("#")[-1].split("/")[-1])
        if record_types:
            result["recordTypes"] = record_types

        # ── Variant / alternate labels ────────────────────────────────────────
        variant_labels = []
        for tag in (
            "{http://www.w3.org/2004/02/skos/core#}altLabel",
            "{http://www.loc.gov/mads/rdf/v1#}variantLabel",
        ):
            for el in primary.findall(tag):
                lbl = _rdf_text(el)
                if lbl and lbl not in variant_labels:
                    variant_labels.append(lbl)

        # Also follow mads:hasVariant blank nodes / linked nodes
        for el in primary.findall("{http://www.loc.gov/mads/rdf/v1#}hasVariant"):
            for child in el:
                for label_tag in (
                    "{http://www.loc.gov/mads/rdf/v1#}variantLabel",
                    "{http://www.w3.org/2000/01/rdf-schema#}label",
                ):
                    lbl_el = child.find(label_tag)
                    if lbl_el is not None and lbl_el.text:
                        lbl = lbl_el.text.strip()
                        if lbl and lbl not in variant_labels:
                            variant_labels.append(lbl)
            res = _rdf_resource(el)
            if res:
                lbl = _rdf_label_for(root, res)
                if lbl and lbl not in variant_labels:
                    variant_labels.append(lbl)

        if variant_labels:
            result["variantLabels"] = variant_labels

        # ── RWO node — biographical data lives here ───────────────────────────
        # The madsrdf:identifiesRWO element wraps a madsrdf:RWO child that
        # holds birth/death dates, places, occupation, fieldOfActivity, etc.
        rwo = None
        for identifies_rwo_el in primary.findall("{http://www.loc.gov/mads/rdf/v1#}identifiesRWO"):
            candidate = identifies_rwo_el.find("{http://www.loc.gov/mads/rdf/v1#}RWO")
            if candidate is not None:
                rwo = candidate
                break

        # Search node for biographical fields — checks both primary and rwo
        def _find_first(tag):
            el = primary.find(tag)
            if el is None and rwo is not None:
                el = rwo.find(tag)
            return el

        def _find_all(tag):
            els = primary.findall(tag)
            if rwo is not None:
                els = els + rwo.findall(tag)
            return els

        # ── Biographical fields (single-value) ────────────────────────────────
        for field, *tags in [
            ("birthDate",  "{http://www.loc.gov/mads/rdf/v1#}birthDate",
                           "{http://schema.org/}birthDate"),
            ("deathDate",  "{http://www.loc.gov/mads/rdf/v1#}deathDate",
                           "{http://schema.org/}deathDate"),
            ("gender",     "{http://www.loc.gov/mads/rdf/v1#}gender",
                           "{http://schema.org/}gender"),
        ]:
            for tag in tags:
                el = _find_first(tag)
                if el is not None:
                    val = _rdf_text(el) or _rdf_resource(el)
                    if val:
                        if val.startswith("http"):
                            val = val.rstrip("/").split("/")[-1]
                        result[field] = val
                        break

        # ── Multi-value nested fields ─────────────────────────────────────────
        def _extract_nested_labels(parent_el, inner_tag):
            values = []
            for wrapper in parent_el.findall(inner_tag) if parent_el is not None else []:
                for child in wrapper:
                    for lbl_tag in (
                        "{http://www.loc.gov/mads/rdf/v1#}authoritativeLabel",
                        "{http://www.w3.org/2000/01/rdf-schema#}label",
                    ):
                        for lbl_el in child.findall(lbl_tag):
                            lang = lbl_el.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                            if not lang and lbl_el.text:
                                val = lbl_el.text.strip()
                                if val and val not in values:
                                    values.append(val)
                                break
                res = _rdf_resource(wrapper)
                if res:
                    lbl = _rdf_label_for(root, res)
                    if lbl and lbl not in values:
                        values.append(lbl)
            return values

        MADS = "http://www.loc.gov/mads/rdf/v1#"

        for field, outer_tag, inner_tag in [
            ("birthPlace",       f"{{{MADS}}}birthPlace",       f"{{{MADS}}}Geographic"),
            ("deathPlace",       f"{{{MADS}}}deathPlace",        f"{{{MADS}}}Geographic"),
            ("associatedLocale", f"{{{MADS}}}associatedLocale",  f"{{{MADS}}}Geographic"),
        ]:
            vals = _extract_nested_labels(rwo, outer_tag) + _extract_nested_labels(primary, outer_tag)
            seen = []
            for v in vals:
                if v not in seen:
                    seen.append(v)
            if seen:
                result[field] = seen[0] if len(seen) == 1 else seen

        def _extract_doubly_nested_labels(parent_el, outer_tag, inner_tag):
            values = []
            for outer in (parent_el.findall(outer_tag) if parent_el is not None else []):
                for child in outer:
                    for inner in child.findall(inner_tag):
                        for topic in inner:
                            for lbl_tag in (
                                f"{{{MADS}}}authoritativeLabel",
                                "{http://www.w3.org/2000/01/rdf-schema#}label",
                            ):
                                for lbl_el in topic.findall(lbl_tag):
                                    if lbl_el.text:
                                        val = lbl_el.text.strip()
                                        if val and val not in values:
                                            values.append(val)
                                        break
                        for lbl_tag in (
                            f"{{{MADS}}}authoritativeLabel",
                            "{http://www.w3.org/2000/01/rdf-schema#}label",
                        ):
                            for lbl_el in child.findall(lbl_tag):
                                if lbl_el.text:
                                    val = lbl_el.text.strip()
                                    if val and val not in values:
                                        values.append(val)
            return values

        for field, outer_tag, inner_tag in [
            ("occupation",      f"{{{MADS}}}occupation",      f"{{{MADS}}}occupation"),
            ("fieldOfActivity", f"{{{MADS}}}fieldOfActivity", f"{{{MADS}}}fieldOfActivity"),
        ]:
            vals = (
                _extract_doubly_nested_labels(rwo, outer_tag, inner_tag) +
                _extract_doubly_nested_labels(primary, outer_tag, inner_tag)
            )
            seen = []
            for v in vals:
                if v not in seen:
                    seen.append(v)
            if seen:
                result[field] = seen[0] if len(seen) == 1 else seen

        # ── Associated language ───────────────────────────────────────────────
        assoc_langs = []
        for el in _find_all("{http://www.loc.gov/mads/rdf/v1#}associatedLanguage"):
            for child in el:
                for lbl_el in child.findall("{http://www.loc.gov/mads/rdf/v1#}authoritativeLabel"):
                    lang_attr = lbl_el.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                    if lang_attr == "en" and lbl_el.text:
                        val = lbl_el.text.strip()
                        if val and val not in assoc_langs:
                            assoc_langs.append(val)
        if assoc_langs:
            result["associatedLanguage"] = assoc_langs[0] if len(assoc_langs) == 1 else assoc_langs

        # ── LC Classification numbers (MARC 053 equivalent) ──────────────────
        # madsrdf:classification carries the LCC number LC assigns to this
        # heading. Present on most LCSH subject records; typically absent on
        # name authority records. Multiple values are possible.
        lcc_numbers = []
        for el in primary.findall("{http://www.loc.gov/mads/rdf/v1#}classification"):
            val = _rdf_text(el)
            if val and val not in lcc_numbers:
                lcc_numbers.append(val)
        if lcc_numbers:
            result["lcClassification"] = lcc_numbers[0] if len(lcc_numbers) == 1 else lcc_numbers

        # ── External identifiers (VIAF, ISNI, Wikidata, etc.) ────────────────
        same_as = []
        for el in primary.findall("{http://www.loc.gov/mads/rdf/v1#}identifiesRWO"):
            res = _rdf_resource(el)
            if res and res not in same_as and "id.loc.gov" not in res:
                same_as.append(res)
        for tag in (
            "{http://www.w3.org/2002/07/owl#}sameAs",
            "{http://schema.org/}sameAs",
        ):
            for el in primary.findall(tag):
                res = _rdf_resource(el)
                if res and res not in same_as:
                    same_as.append(res)
        if same_as:
            result["sameAs"] = same_as

        # ── Source citations ──────────────────────────────────────────────────
        sources = []
        notes = []
        for has_source_el in primary.findall("{http://www.loc.gov/mads/rdf/v1#}hasSource"):
            for source_el in has_source_el:
                cite = source_el.find("{http://www.loc.gov/mads/rdf/v1#}citationSource")
                note = source_el.find("{http://www.loc.gov/mads/rdf/v1#}citationNote")
                cite_val = (_rdf_text(cite) or _rdf_resource(cite)) if cite is not None else ""
                note_val = _rdf_text(note) if note is not None else ""
                if cite_val and cite_val not in sources:
                    sources.append(cite_val)
                if note_val and note_val not in notes:
                    notes.append(note_val)

        if sources:
            result["sources"] = sources
        if notes:
            result["citationNotes"] = notes

        # ── Record history ────────────────────────────────────────────────────
        history = []
        RI = "http://id.loc.gov/ontologies/RecordInfo#"
        for admin_el in primary.findall("{http://www.loc.gov/mads/rdf/v1#}adminMetadata"):
            for record_info in admin_el:
                date_el   = record_info.find(f"{{{RI}}}recordChangeDate")
                status_el = record_info.find(f"{{{RI}}}recordStatus")
                source_el = record_info.find(f"{{{RI}}}recordContentSource")
                entry = {}
                if date_el is not None and date_el.text:
                    entry["date"] = date_el.text.strip()
                if status_el is not None and status_el.text:
                    entry["status"] = status_el.text.strip()
                if source_el is not None:
                    for corp in source_el:
                        lbl = corp.find("{http://www.loc.gov/mads/rdf/v1#}authoritativeLabel")
                        if lbl is not None and lbl.text:
                            entry["source"] = lbl.text.strip()
                            break
                if entry:
                    history.append(entry)
        if history:
            result["recordHistory"] = history

        return result

    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }


# ---------------------------------------------------------------------------
# Resources (optional convenience wrappers)
# ---------------------------------------------------------------------------

@mcp.resource("lcsh://search/{query}")
def lcsh_resource(query: str) -> dict:
    return search_lcsh(query)


@mcp.resource("lcnaf://personal/{query}")
def lcnaf_personal_resource(query: str) -> dict:
    return search_personal_name(query)


@mcp.resource("lcnaf://personal/keyword/{query}")
def lcnaf_personal_keyword_resource(query: str) -> dict:
    return search_personal_name_keyword(query)


@mcp.resource("lcnaf://corporate/{query}")
def lcnaf_corporate_resource(query: str) -> dict:
    return search_corporate_name(query)


@mcp.resource("lcnaf://geographic/{query}")
def lcnaf_geographic_resource(query: str) -> dict:
    return search_geographic_name(query)


@mcp.resource("lcnaf://meeting/{query}")
def lcnaf_meeting_resource(query: str) -> dict:
    return search_meeting_name(query)


@mcp.resource("lcnaf://meeting/keyword/{query}")
def lcnaf_meeting_keyword_resource(query: str) -> dict:
    return search_meeting_name_keyword(query)


@mcp.resource("lcnaf://corporate/keyword/{query}")
def lcnaf_corporate_keyword_resource(query: str) -> dict:
    return search_corporate_name_keyword(query)


@mcp.resource("lcnaf://geographic/keyword/{query}")
def lcnaf_geographic_keyword_resource(query: str) -> dict:
    return search_geographic_name_keyword(query)


@mcp.resource("lcnaf://family/{query}")
def lcnaf_family_resource(query: str) -> dict:
    return search_family_name(query)


@mcp.resource("lcnaf://family/keyword/{query}")
def lcnaf_family_keyword_resource(query: str) -> dict:
    return search_family_name_keyword(query)


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def start_mcp_server(port: int = None):
    """Starts the MCP server in HTTP/SSE mode or stdio mode."""
    import uvicorn

    if port is not None:
        print(f"Starting cataloger mcp server on HTTP port {port}")
        uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=port)
    else:
        print("Starting cataloger mcp server in stdio mode")
        mcp.run()


if __name__ == "__main__":
    import sys

    cli_port = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cli_port = int(sys.argv[1])
    start_mcp_server(port=cli_port)
