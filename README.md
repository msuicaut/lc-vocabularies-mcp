# LC Vocabularies MCP

"An experimental MCP (Model Context Protocol) server connecting Claude to the Library of Congress Linked Data APIs for LCSH, LCNAF, and LCGFT authority lookups, developed to investigate the potential of large language models in subject analysis and authority control.

This project was inspired by and built with familiarity with
[cataloger-mcp](https://github.com/kltng/cataloger-mcp) by KL Tang.
The design decisions and enhancements in this version reflect
professional cataloging expertise and knowledge of the LC Subject
Headings Manual.

---

## What This Server Does

LC Vocabularies MCP connects Claude Desktop to the Library of Congress id.loc.gov APIs, allowing you to search and retrieve LC authority data directly within your AI-assisted cataloging workflow.

Once installed, you can ask Claude things like:

- *"Search LCSH for headings related to urban planning"*
- *"Find the name authority record for Margaret Atwood"*
- *"Can the heading 'Architecture' be subdivided geographically?"*
- *"Look up the full authority record for this URI"*

The server handles all the API calls, parses the responses, and returns
structured data Claude can reason about.

---

## Who This Is For

- **Catalogers** using Claude Desktop who want AI-assisted subject heading
  work grounded in real LC authority data
- **Library systems staff** building or evaluating AI-assisted cataloging
  tools and workflows
- **Developers** integrating LC vocabulary lookups into MCP-based systems

If you are approaching this as a developer without a cataloging background,
the tool descriptions and parameter names reflect cataloging conventions
that may benefit from some context — the
[LC Subject Headings Manual (SHM) ](https://www.loc.gov/aba/publications/FreeSHM/freeshm.html), [LC Descriptive Cataloging Manual (DCM) Sections Z1 and Z12](https://www.loc.gov/aba/publications/FreeDCM/freedcm.html) and [LC Genre/Form Terms Manual](https://www.loc.gov/aba/publications/FreeLCGFT/freelcgft.html)
are the authoritative references.

---

## Tools

| Tool | Description |
|------|-------------|
| `search_lcsh` | Left-anchored LCSH search. Top 6 results include `maySubdivideGeographically`. |
| `search_lcsh_keyword` | Keyword LCSH search. Top 6 results include `maySubdivideGeographically`. |
| `search_lcgft` | Left-anchored LCGFT search — genre and form terms. |
| `search_lcgft_keyword` | Keyword LCGFT search. |
| `search_personal_name` | Personal name search (LCNAF) — individuals only. |
| `search_personal_name_keyword` | Keyword personal name search. |
| `search_family_name` | Family name search (LCNAF) — dynasties, clans, noble houses, e.g. "Kennedy family". |
| `search_family_name_keyword` | Keyword family name search. |
| `search_corporate_name` | Corporate body search (LCNAF) — organizations, institutions, government bodies. |
| `search_corporate_name_keyword` | Keyword corporate name search. |
| `search_geographic_name` | Geographic name search (LCNAF) — place names as headings. |
| `search_geographic_name_keyword` | Keyword geographic name search. |
| `search_meeting_name` | Meeting/conference name search (LCNAF) — conferences, congresses, symposia. |
| `search_meeting_name_keyword` | Keyword meeting/conference name search. |
| `get_scope_note` | Retrieve the scope note for any LC authority URI. |
| `get_authority_record` | Retrieve the full authority record via RDF/XML, including biographical data, variant labels, LC classification numbers, and record history. |

---

## Notes on Search Behaviour

**Left-anchored search** matches from the beginning of the authorized
heading string. Searching `Atwood, Margaret` will find that heading, but
searching `Margaret Atwood` will not — the authorized form inverts the
name. When a left-anchored search returns no results, use the keyword
variant of the same tool.

**A recommended fallback sequence for personal names:**

1. Search with the full authorized form including qualifiers such as dates (e.g., `Atwood, Margaret, 1939-`)
2. Retry without middle name or dates (e.g., `Atwood, Margaret`)
3. Use `search_personal_name_keyword` on surname and forename only (e.g., `Atwood Margaret`)
4. If a match looks plausible but uncertain, retrieve the full authority
   record with `get_authority_record` to confirm

**Geographic subdivision eligibility** (`maySubdivideGeographically`) is
checked automatically for the top 6 LCSH results by fetching the
MADS/RDF record for each heading. This reflects membership in the
`collection_SubdivideGeographically` collection and determines whether
a geographic subdivision (`--[Place]`) may be appended to the heading
string. Always verify this field before constructing a subdivided heading.

**Meeting and conference names** return more reliable results when the
year is included in the query (e.g., `Democratic National Convention 1972`),
because authorized headings include year and location qualifiers.

---

## Installation

### Requirements

- Python 3.11 or later
- Claude Desktop (or another MCP-compatible host)

### Install from GitHub

```bash
pip install git+https://github.com/msuicaut/lc-vocabularies-mcp.git
```

### Install from a local clone

```bash
git clone https://github.com/msuicaut/lc-vocabularies-mcp.git
cd lc-vocabularies-mcp
pip install -e .
```

On Windows with Anaconda, use Anaconda Prompt and add
`--break-system-packages` if prompted.

---

## Claude Desktop Configuration

After installation, add the server to your `claude_desktop_config.json`.
Claude Desktop uses a restricted PATH that does not include the Python
bin directory, so the full path to the command is required.

To find your exact path, run the following in Terminal (Mac) or
Anaconda Prompt (Windows):

- **Mac:** `which lc-vocabularies-mcp`
- **Windows:** `where lc-vocabularies-mcp`

The examples below are illustrative only — your actual path will differ
depending on your Python version and installation method.

**Mac (example):**
```json
{
  "mcpServers": {
    "lcvocab": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.13/bin/lc-vocabularies-mcp"
    }
  }
}
```

**Windows/Anaconda (example):**
```json
{
  "mcpServers": {
    "lcvocab": {
      "command": "C:\\Users\\username\\anaconda3\\Scripts\\lc-vocabularies-mcp.exe"
    }
  }
}
```

Always replace the path with the actual output of the `which` or `where`
command on your machine.

**Finding your config file:**

- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

After editing the config, quit Claude Desktop completely and reopen it.
The lcvocab tools will be available in your next conversation.

### Verifying the installation

Once Claude Desktop is open, ask: *"What cataloger tools do you have
available?"* — you should see all sixteen tools listed.

---

## Using with Claude Projects

If you are using this server within a Claude Project, two files in this
repository are provided to help Claude apply consistent cataloging
protocols automatically.

### INSTRUCTIONS.md — paste into the Instructions field

Open your Claude Project, click **Set project instructions**, and paste
the full contents of [`INSTRUCTIONS.md`](INSTRUCTIONS.md) into that
field. This tells Claude how to approach subject heading assignment,
which tools to use, and in what order — including the personal name
fallback protocol and parallel search workflow.

### SKILL.md — upload to the project Files

Upload [`SKILL.md`](SKILL.md) to your project's Files space. This is
the full reference document containing complete search protocols,
examples, and common pitfalls. The project instructions direct Claude
to consult it for detail.

The two files work together: `INSTRUCTIONS.md` tells Claude what to do,
and `SKILL.md` gives it the complete reference to consult when needed.

---

## Troubleshooting

**Tools not appearing in Claude Desktop**

- Confirm the package installed without errors: `pip show lc-vocabularies-mcp`
- Confirm the command is available: `lc-vocabularies-mcp --help` (should
  start the server, not throw an error)
- Check that the config file path is correct for your OS
- Quit Claude Desktop fully (not just close the window) before reopening

**`maySubdivideGeographically` returning `None`**

This means the MADS/RDF check could not be completed for that heading —
usually a transient network issue. Try `get_scope_note` on the URI to
confirm the heading is reachable, then retry the search.

**Left-anchored search returning no results**

Use the keyword variant of the same tool. See the fallback sequence above
for personal names.

**Changes to server.py not taking effect**

Python caches compiled bytecode in `__pycache__` folders. After editing
`server.py`, delete any `__pycache__` folders in the package directory
and restart Claude Desktop fully.

---

## License

GPLv3. See [LICENSE](LICENSE).

---

## Development Note

The code in this project was developed in collaboration with Claude, Anthropic's AI assistant. The design decisions — including tool selection, search protocols, fallback sequences, and the application of LC cataloging practice to the server's behaviour — reflect the author's professional cataloging expertise. Claude handled the implementation of those decisions in Python.

---

## Acknowledgements

This project makes use of the Library of Congress Linked Data Service (id.loc.gov). The Library of Congress provides open access to its authority files through public linked data APIs.

This project was inspired by KL Tang's
[cataloger-mcp](https://github.com/kltng/cataloger-mcp). LC Vocabularies
MCP is a substantial extension for potential use in professional cataloging workflows.


