---
name: onboard_codebase
description: Use when dropped into an unfamiliar repository or asked to understand how a codebase works before making changes.
---
# Onboard a Codebase

Build an accurate mental model of an unfamiliar repo quickly, then summarize it. Read before writing.

## 1. Orient (fast)
- `ls` the root. Note language(s), package manifests (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`), and config.
- Read the docs: `README`, `CONTRIBUTING`, `docs/`. They often state the entry point and how to run things.
- `git log --oneline -20` — recent activity reveals what's actively worked on.

## 2. Find the entry points
- Locate the `main`/start file: search for `if __name__ == "__main__"`, `func main`, `app.listen`, `createServer`, or the manifest's `main`/`scripts`.
- Trace one request/command end-to-end from entry point to a leaf function. This is the single most useful thing you can do.
- Note where side effects happen (DB, network, filesystem).

## 3. Map the structure
Produce a coarse map (adjust to the project):
- **top-level dirs**: what each one is for.
- **modules/packages**: responsibilities and how they depend on each other.
- **data flow**: config → entry → services → storage, and how layers talk.
- **external deps**: databases, APIs, queues, and where they're configured.
Use `grep`/`rg` to answer specifics (e.g. `rg "import" src/ | head`), not guesses.

## 4. Establish the workflow
- Determine how to **install**, **run**, and **test** from the manifest scripts or docs. Report the exact commands.
- Try running the test suite to confirm the setup works. If it fails, note why — that's valuable context.

## 5. Identify conventions
- Code style, error-handling patterns, naming conventions, how config/secrets are supplied.
- Testing patterns and directory layout. Follow these when you make changes.

## 6. Deliver a summary
Answer, concisely:
- **What it is**: one sentence on the project's purpose.
- **Stack**: language, framework, key libraries, storage.
- **Layout**: the important directories and what lives there.
- **Entry point**: where execution starts and the main flow.
- **How to run & test**: exact commands.
- **Conventions**: anything a contributor must follow.
- **Open questions**: uncertainties you still have.

Keep it tight and factual. Cite `file:line` for the key claims so the reader can verify. Do not start editing until this picture is shared and agreed.
