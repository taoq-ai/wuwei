"""Offline contract for shipped skill triggering evals."""

from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path):
    content = path.read_text()
    parts = content.split("---", 2)
    assert len(parts) == 3 and not parts[0].strip(), path
    fields = {}
    for line in parts[1].strip().splitlines():
        match = re.fullmatch(r"([a-z_]+):\s*(.+)", line)
        assert match, (path, line)
        key, value = match.groups()
        assert key not in fields, (path, key)
        fields[key] = value[1:-1] if value[0] in "'\"" and value[-1] == value[0] else value
    assert parts[2].strip(), path
    return fields


def test_skill_eval_coverage():
    skills = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
    assert skills
    counts = Counter()
    cases = list((ROOT / "evals").glob("*/prompt.md"))
    assert cases
    for prompt in cases:
        case = prompt.parent
        prompt_fields = frontmatter(prompt)
        assert prompt_fields["name"] == case.name
        tags = prompt_fields["tags"]
        assert tags.startswith("[") and tags.endswith("]"), case
        kind = {tag.strip() for tag in tags[1:-1].split(",")}
        assert len(kind & {"should-trigger", "should-not-trigger"}) == 1, case
        grader_paths = list((case / "graders").glob("*.md"))
        assert len(grader_paths) == 1, case
        grader = frontmatter(grader_paths[0])
        assert grader["type"] == "tool_used", case
        assert grader["tool"] == "Skill", case
        match = re.fullmatch(r'"skill"\\s\*:\\s\*"\(wuwei:\)\?([\w-]+)"', grader["input_match"])
        assert match, (case, grader["input_match"])
        skill = match.group(1)
        assert re.search(grader["input_match"], f'{{"skill":"wuwei:{skill}"}}'), case
        assert skill in skills, (case, skill)
        assert kind == {"should-trigger" if "should-trigger" in kind else "should-not-trigger", skill}, case
        assert grader["name"] == f"{case.name}-skill", case
        if "should-trigger" in kind:
            assert grader["min"] == "1" and "max" not in grader, case
            counts[skill, "positive"] += 1
        else:
            assert grader["min"] == "0" and grader["max"] == "0", case
            counts[skill, "negative"] += 1
    assert {path.parent.parent for path in (ROOT / "evals").glob("*/graders/*.md")} == {path.parent for path in cases}
    for skill in skills:
        assert counts[skill, "positive"] >= 5, (skill, counts)
        assert counts[skill, "negative"] >= 5, (skill, counts)


def test_skill_eval_ci_and_docs():
    workflow = (ROOT / ".github/workflows/tests.yml").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "skill-evals:" in workflow
    assert "secrets.ANTHROPIC_API_KEY" in workflow
    assert "ANTHROPIC_API_KEY is not set; skipping skill evals" in workflow
    assert "claude plugin eval . --trust-plugin --ablation none --threshold 0.9 --json" in workflow
    assert "claude plugin eval . --trust-plugin --ablation none --threshold 0.9 --json" in readme
    assert "ANTHROPIC_API_KEY" in readme
    assert "any case scores below 0.9" in readme
