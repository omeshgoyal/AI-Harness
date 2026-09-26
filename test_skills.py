"""Tests for the agent skills system.

Three levels:
  1. loader   - skills.py parses SKILL.md files correctly (offline)
  2. tools    - read_skill / write_skill behave correctly (offline)
  3. agent    - the live model actually reaches for the right skill (needs API, --e2e)

Run:
    python3 test_skills.py            # offline tests only (fast, free)
    python3 test_skills.py --e2e      # also runs the live LLM test (costs tokens)
"""

import json
import sys
from pathlib import Path

import yaml

# Make sure we import the project's own modules, not something else on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import skills as skills_mod
from skills import SKILLS, find_skills, read_skill, write_skill, skills_prompt
from tools import TOOLS

PROJECT_SKILL_DIR = Path(__file__).resolve().parent / ".agents" / "skills"

# The skills we expect the harness to ship with.
EXPECTED = {
    "code_review",
    "systematic_debugging",
    "git_workflow",
    "write_tests",
    "onboard_codebase",
}

_results = {"pass": 0, "fail": 0}


def test(fn):
    """Tiny decorator so we don't need pytest."""
    _results  # noqa: B018
    name = fn.__name__
    try:
        fn()
    except AssertionError as e:
        _results["fail"] += 1
        print(f"  FAIL  {name}: {e}")
    except Exception as e:  # noqa: BLE001
        _results["fail"] += 1
        print(f"  ERROR {name}: {type(e).__name__}: {e}")
    else:
        _results["pass"] += 1
        print(f"  ok    {name}")
    return fn


# --------------------------------------------------------------------------- #
# 1. LOADER TESTS
# --------------------------------------------------------------------------- #

def test_all_expected_skills_load():
    missing = EXPECTED - set(SKILLS)
    assert not missing, f"skills not loaded: {sorted(missing)}"


def test_each_skill_has_name_and_description():
    for name, s in SKILLS.items():
        assert name, "empty skill name"
        assert s["description"].strip(), f"{name} has empty description"
        assert len(s["description"]) > 20, f"{name} description too short"


def test_frontmatter_is_valid_and_has_required_keys():
    for name, s in SKILLS.items():
        text = s["path"].read_text()
        assert text.startswith("---"), f"{name} missing opening frontmatter"
        parts = text.split("---", 2)
        assert len(parts) == 3, f"{name} malformed frontmatter"
        meta = yaml.safe_load(parts[1])
        assert set(meta) >= {"name", "description"}, f"{name} missing keys: {meta}"
        assert meta["name"] == name, f"{name} frontmatter name mismatch"


def test_skill_bodies_are_non_trivial():
    for name, s in SKILLS.items():
        body = s["path"].read_text().split("---", 2)[2]
        assert len(body.strip()) > 200, f"{name} body looks empty"


def test_descriptions_are_single_line():
    # skills_prompt() collapses newlines, so multi-line descriptions would silently merge.
    for name, s in SKILLS.items():
        raw = yaml.safe_load(s["path"].read_text().split("---", 2)[1])
        assert "\n" not in raw["description"].strip(), f"{name} description spans lines"


def test_no_duplicate_skill_names_across_dirs():
    # find_skills() overwrites on collision; make sure each name maps to one path.
    seen = {}
    for d in skills_mod.SKILL_DIRS:
        for p in sorted(d.glob("*/SKILL.md")):
            seen.setdefault(p.parent.name, []).append(p)
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dupes, f"duplicate skill names: {dupes}"


def test_skills_prompt_lists_everything():
    prompt = skills_prompt()
    for name in SKILLS:
        assert name in prompt, f"{name} missing from skills_prompt()"


# --------------------------------------------------------------------------- #
# 2. TOOL TESTS
# --------------------------------------------------------------------------- #

def test_read_skill_returns_full_body():
    out = read_skill("code_review")
    assert "Code Review" in out
    assert "---" in out  # includes frontmatter


def test_read_skill_unknown_name_is_graceful():
    out = read_skill("does_not_exist_xyz")
    assert "No skill named" in out


def test_tools_registry_exposes_skill_tools():
    assert "read_skill" in TOOLS and "write_skill" in TOOLS
    assert callable(TOOLS["read_skill"]) and callable(TOOLS["write_skill"])


def test_write_then_read_roundtrip():
    name = "_tmp_test_skill"
    target = PROJECT_SKILL_DIR / name / "SKILL.md"
    try:
        msg = write_skill(name, "A throwaway skill used only by the test suite.", "# Body\nStep 1.")
        assert "Successfully created" in msg, msg
        assert target.exists(), "SKILL.md was not written"
        assert name in SKILLS, "new skill not reloaded into SKILLS"
        assert "Step 1" in read_skill(name)
    finally:
        # Clean up so the test is idempotent.
        if target.exists():
            target.unlink()
        if target.parent.exists():
            target.parent.rmdir()
        skills_mod.reload_skills()


def test_write_skill_reloads_without_restart():
    before = set(SKILLS)
    name = "_tmp_reload_skill"
    target = PROJECT_SKILL_DIR / name / "SKILL.md"
    try:
        write_skill(name, "Another throwaway skill for reload testing.", "body")
        assert name in SKILLS and name not in before
    finally:
        if target.exists():
            target.unlink()
        if target.parent.exists():
            target.parent.rmdir()
        skills_mod.reload_skills()


# --------------------------------------------------------------------------- #
# 3. AGENT (E2E) TEST - live model, opt-in
# --------------------------------------------------------------------------- #

def run_e2e():
    """Ask the live model something that should trigger a skill, and check it
    reads the right skill within a few turns. Costs tokens.

    This mirrors agent.py's loop: the model may explore (bash, read_file) before
    reading a skill, so we run several turns and only execute safe tools."""
    from llm import get_system_prompt, call_llm

    # Read-only tools we actually run during the test so the loop is faithful to
    # agent.py. Mutating tools are stubbed so the test never edits the repo.
    READ_ONLY_TOOLS = {"read_skill", "read_file", "bash"}

    # (user prompt, acceptable skill names the model should read)
    cases = [
        ("Can you review my changes before I merge?", {"code_review"}),
        ("This function crashes with an IndexError and I don't know why.",
         {"systematic_debugging"}),
        ("Write me some unit tests for this parser.", {"write_tests"}),
        ("I just joined this repo - help me understand how it works.",
         {"onboard_codebase"}),
    ]

    MAX_TURNS = 6
    failures = []

    for prompt, acceptable in cases:
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        skills_read = set()

        for _turn in range(MAX_TURNS):
            message, _usage = call_llm(messages)
            messages.append(message)
            calls = getattr(message, "tool_calls", None) or []
            if not calls:
                break

            for c in calls:
                fn = c.function.name
                if fn == "read_skill":
                    try:
                        skills_read.add(json.loads(c.function.arguments).get("name"))
                    except Exception:  # noqa: BLE001
                        pass

                if fn in READ_ONLY_TOOLS:
                    try:
                        result = str(TOOLS[fn](**json.loads(c.function.arguments)))
                    except Exception as e:  # noqa: BLE001
                        result = f"tool error: {e}"
                else:
                    result = "(skipped: mutating tools are disabled during tests)"

                messages.append({
                    "role": "tool",
                    "tool_call_id": c.id,
                    "name": fn,
                    "content": result,
                })

            if skills_read & acceptable:
                break  # reached for the right skill; stop early

        hit = bool(skills_read & acceptable)
        status = "ok   " if hit else "FAIL "
        print(f"  {status} {prompt!r} -> read_skill={sorted(skills_read) or '(none)'}")
        if not hit:
            failures.append(prompt)

    assert not failures, f"model never read the expected skill for: {failures}"


# --------------------------------------------------------------------------- #

def main():
    run_e2e_flag = "--e2e" in sys.argv

    print("\n== Loader tests ==")
    for fn in [
        test_all_expected_skills_load,
        test_each_skill_has_name_and_description,
        test_frontmatter_is_valid_and_has_required_keys,
        test_skill_bodies_are_non_trivial,
        test_descriptions_are_single_line,
        test_no_duplicate_skill_names_across_dirs,
        test_skills_prompt_lists_everything,
    ]:
        test(fn)

    print("\n== Tool tests ==")
    for fn in [
        test_read_skill_returns_full_body,
        test_read_skill_unknown_name_is_graceful,
        test_tools_registry_exposes_skill_tools,
        test_write_then_read_roundtrip,
        test_write_skill_reloads_without_restart,
    ]:
        test(fn)

    if run_e2e_flag:
        print("\n== Agent E2E tests (live API) ==")
        test(run_e2e)
    else:
        print("\n(skipping live agent tests; run with --e2e to include them)")

    total = _results["pass"] + _results["fail"]
    print(f"\n{_results['pass']}/{total} passed, {_results['fail']} failed")
    sys.exit(1 if _results["fail"] else 0)


if __name__ == "__main__":
    main()
