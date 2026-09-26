from pathlib import Path
import yaml

SKILL_DIRS = [
    Path.cwd() / ".agents" / "skills",
    Path.home() / ".agents" / "skills",
]

def find_skills():
    """Map each skill name to its description and SKILL.md path."""
    skills = {}
    for directory in SKILL_DIRS:
        for path in sorted(directory.glob("*/SKILL.md")):
            try:
                # Split YAML frontmatter from markdown body[cite: 11]
                _, frontmatter, _ = path.read_text().split("---", 2)
                meta = yaml.safe_load(frontmatter)
                description = " ".join(meta["description"].split())
                skills[meta["name"]] = {"description": description, "path": path}
            except Exception as e:
                print(f"Failed to load skill {path}: {e}")
    return skills

# Global dictionary holding active skills[cite: 11]
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
    # Target the local project's skill directory
    target_dir = Path.cwd() / ".agents" / "skills" / name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    skill_file = target_dir / "SKILL.md"
    
    # Construct the file with required YAML frontmatter
    content = f"---\nname: {name}\ndescription: {description}\n---\n{instructions}"
    skill_file.write_text(content)
    
    # Reload in place so any module holding a reference to SKILLS sees the update
    reload_skills()
    
    return f"Successfully created skill '{name}' at {skill_file}. It is now active."