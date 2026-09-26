from pathlib import Path
import yaml

# Order matters for precedence: later directories win when names collide.
# Global (home) skills load first so a project can deliberately shadow one.
SKILL_DIRS = [
    Path.home() / ".agents" / "skills",
    Path.cwd() / ".agents" / "skills",
]


def _load_one(path):
    try:
        text = path.read_text()
        _, frontmatter, body = text.split("---", 2)
        meta = yaml.safe_load(frontmatter) or {}
        if "name" not in meta or "description" not in meta:
            raise ValueError("SKILL.md frontmatter needs both 'name' and 'description'")
        description = " ".join(meta["description"].split())
        return meta["name"], {"description": description, "path": path}
    except ValueError as e:
        # Most likely fewer/more than two '---' delimiters, or missing keys.
        raise ValueError(f"malformed frontmatter in {path}: {e}")


def find_skills():
    """Map each skill name to its description and SKILL.md path.

    Directories are walked in SKILL_DIRS order, so a later directory's skill
    silently wins a name collision - project-local skills (loaded last)
    intentionally override global ones of the same name.
    """
    skills = {}
    for directory in SKILL_DIRS:
        for path in sorted(directory.glob("*/SKILL.md")):
            try:
                name, entry = _load_one(path)
                skills[name] = entry
            except Exception as e:
                print(f"Failed to load skill {path}: {e}")
    return skills


# Global dictionary holding active skills
SKILLS = find_skills()


def reload_skills():
    """Refresh the active skills in place so existing references stay valid."""
    SKILLS.clear()
    SKILLS.update(find_skills())
    return SKILLS


def skills_prompt():
    if not SKILLS:
        return "- No skills currently loaded."
    return "\n".join(f"- {name}: {s['description']}" for name, s in SKILLS.items())


def read_skill(name: str) -> str:
    """Open a skill and return its full instructions."""
    if name not in SKILLS:
        return f"No skill named '{name}'."
    return SKILLS[name]["path"].read_text()


def write_skill(name: str, description: str, instructions: str) -> str:
    """Creates a new skill directory, writes the SKILL.md file, and reloads the active skills."""
    # Target the local project's skill directory, so a self-taught skill
    # applies here first and can be promoted to global manually later.
    target_dir = Path.cwd() / ".agents" / "skills" / name
    target_dir.mkdir(parents=True, exist_ok=True)

    skill_file = target_dir / "SKILL.md"

    content = f"---\nname: {name}\ndescription: {description}\n---\n{instructions}"
    skill_file.write_text(content)

    reload_skills()

    return f"Successfully created skill '{name}' at {skill_file}. It is now active."