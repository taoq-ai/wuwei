"""Static contract for generic role charters."""

from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHARTERS = ROOT / "charters"
FILES = (
    "_common.md", "_common-authoring.md", "planner.md", "lead.md",
    "builder.md", "sentinel-arch.md", "sentinel-quality.md",
    "sentinel-security.md", "sentinel-goal.md", "shepherd.md", "steward.md",
)

BANNED = re.compile(
    r"\u2014|(?i:https?://|www\.)|(?i:(?<![a-z0-9])[a-z]{2,5}[-_][0-9]+(?![a-z0-9]))|"
    r"\b[CUGD](?=[0-9A-Z]*[0-9])[0-9A-Z]{8,}\b|"
    r"[\U0001F000-\U0001FAFF\u2600-\u27BF]",
)


def charter_text():
    return {p.name: p.read_text(encoding="utf-8") for p in CHARTERS.glob("*.md")}


def test_charter_set_and_frontmatter():
    texts = charter_text()
    assert set(texts) == set(FILES)
    for name, body in texts.items():
        assert re.match(r"\A---\nversion: [0-9]+\.[0-9]+\.[0-9]+\n---\n", body), name


def test_numbered_checklists_are_ordered():
    for name, body in charter_text().items():
        expected = 1
        for line in body.splitlines():
            if line.startswith("## "):
                expected = 1
            elif match := re.match(r"^(\d+)\. ", line):
                assert int(match.group(1)) == expected, (name, line)
                expected += 1


def test_generic_content_lint():
    for name, body in charter_text().items():
        assert not BANNED.search(body), name
        assert "Learned rules" not in body, name


def test_generic_patterns_cover_case_without_english_false_positives():
    for value in ("ab-123", "AB_123", "D" + "0" * 8, "G" + "0" * 8):
        assert BANNED.search(value), value
    assert BANNED.search("HTTPS://example.invalid")
    for sentence in ("Tell the user.", "Commit when done.", "Write a JSON table.",
                     "Open an ADR.", "Use TDD.", "Read CHANGELOG."):
        assert not BANNED.search(sentence), sentence


def test_charter_sentences_have_one_home():
    seen = {}
    for name, body in charter_text().items():
        for line in body.splitlines():
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                normalized = re.sub(r"^\s*(?:\d+\.|-)?\s*", "", sentence).strip().lower()
                if normalized and normalized[-1] in ".!?":
                    assert normalized not in seen or seen[normalized] == name, (normalized, seen.get(normalized), name)
                    seen[normalized] = name


@pytest.mark.parametrize("name", ["arch", "quality", "security", "goal"])
def test_sentinel_agents_carry_clean_probes(name):  # #672
    text = (ROOT / "agents" / f"sentinel-{name}.md").read_text()
    assert "runs every probe, test and mutant in a copy under its `Scratch:` directory" in text


BLOCKING = re.compile(
    r"\bwait(?:s|ing)?\s+for\s+(?:the\s+|its\s+|each\s+|every\s+|all\s+)?(?:required\s+)?"
    r"(?:agent|turn|seats?|builders?|sentinels?|checks?|verdicts?)\b"
    r"|\bblock\s+until\b|\bforeground\b|\bturns?\s+returns?\b"
    r"|\b(?:through|with)\s+bash\b(?!\s+in\s+the\s+background)"
    r"|\bwith\s+agent\b(?!\s+in\s+the\s+background)", re.I)
INSTRUCTIONS = ("skills/*/SKILL.md", "charters/*.md", "agents/*.md", "docs/site/agent.md")


def test_no_blocking_instruction_in_skills_or_charters():
    found = [(str(path.relative_to(ROOT)), match.group(0))
             for pattern in INSTRUCTIONS for path in sorted(ROOT.glob(pattern))
             for match in BLOCKING.finditer(path.read_text(encoding="utf-8"))]
    assert found == []


@pytest.mark.parametrize("sentence,blocking", [
    ("Launch it with the rest of the launch set in one message (Parallel dispatch) and wait for the turn to return in the planner session.", True),
    ("Wait for the Agent call to return in the planner session.", True),
    ("execute the returned `command` through Bash, using the workspace's recorded executable", True),
    ("Wait for all required verdicts before a fix or PR raise.", True),
    ("When the turn returns, do each item's next step.", True),
    ("for `continue`, do the same with Agent `resume` set to the returned `resume`", True),
    ("launch that steward with Agent exactly as returned", True),
    ("Block until the seat stops.", True),
    ("Run the suite in the foreground.", True),
    ("Launch it with Agent in the background with the rest of the launch set in one message (Parallel dispatch), then take the next ready action.", False),
    ("run the returned `command` through Bash in the background, using the workspace's recorded executable", False),
    ("The fix round and the PR raise start only once every required verdict is received.", False),
    ("launch that steward with Agent in the background exactly as returned", False),
    ("the planner stays available to the owner while seats run", False),
    ("Never launch one and wait for it before the next.", False),
])
def test_blocking_pattern_samples(sentence, blocking):
    assert bool(BLOCKING.search(sentence)) is blocking


def test_plain_tone_rule_has_five_items_and_ships_in_every_agent():
    body = (CHARTERS / "_common-authoring.md").read_text(encoding="utf-8")
    section = "## Plain tone" + body.split("## Plain tone", 1)[1].split("\n## ", 1)[0]
    assert [int(line.split(".")[0]) for line in section.splitlines() if re.match(r"\d+\. ", line)] == [1, 2, 3, 4, 5]
    for phrase in ("20", "35", "one idea", "the owner", "#362"):
        assert phrase in section, phrase
    for role in ("planner", "lead", "builder", "sentinel-arch", "sentinel-quality", "sentinel-security",
                 "sentinel-goal", "shepherd", "steward"):
        assert section.strip() in (ROOT / "agents" / f"{role}.md").read_text(encoding="utf-8"), role


def test_no_charter_holds_its_own_verdict_format():
    # #665: the format lives in cli/wuwei/verdict.py FORMAT; agents build renders it.
    texts = charter_text()
    assert "`CLASS: PASS|N.A.|FINDING <id>`" not in texts["_common.md"]
    assert not [name for name, body in texts.items() if "## Verdict format" in body]
def test_skills_ask_the_owner_step_card_a_command_prints():
    # #599, part 14: an owner question comes from next; the command prints its card; no host terminal.
    ASK = ('An owner question comes from `wuwei next`: a command that refuses with an Owner step card '
           'prints it; ask it with AskUserQuestion as printed, then run the same command again on Yes')
    for name in ('wuwei-plan', 'wuwei-retro', 'wuwei-report'):
        skill = (ROOT / f"skills/{name}/SKILL.md").read_text(encoding="utf-8")
        assert ASK in skill and 'decision route' not in skill and 'wuwei decide' not in skill, name
    assert 'Never show the owner a host-terminal command' in (ROOT / "skills/wuwei-plan/SKILL.md").read_text()


def test_a_seat_finding_has_its_route():
    """#646: seats record a small fix with note --fix; the planner adds it. #842: no ticket wall;
    a due tracker update comes back from wuwei next as a duty row."""
    texts = charter_text()
    assert 'wuwei note --fix "<title>"' in texts["builder.md"]
    assert 'wuwei note --fix "<title>"' in texts["lead.md"]
    assert "wuwei plan add <id> --from-finding" in texts["planner.md"]
    assert "An item needs no ticket to start" in texts["planner.md"]
    assert "lists a duty, write its content and run its record command" in texts["planner.md"]  # #844
    assert "tracker.required" not in texts["lead.md"]


def test_gate_copies_start_empty_and_match_the_tree():
    # #734: a copy a gate checks is new and empty, and extras against the tree are listed.
    anchors = ("in a new, empty directory under your brief's `Scratch:` directory",
               "`git ls-tree -r --name-only <sha>`", "list each extra file in the verdict")
    common = charter_text()["_common.md"]
    assert all(common.count(anchor) == 1 for anchor in anchors)
    for agent in (ROOT / "agents").glob("sentinel-*.md"):
        assert all(anchor in agent.read_text(encoding="utf-8") for anchor in anchors), agent.name


def test_approval_wording_reaches_every_gate_and_the_planner():  # #731
    for role in ("sentinel-arch", "sentinel-quality", "sentinel-security", "sentinel-goal"):
        text = (ROOT / "agents" / f"{role}.md").read_text(encoding="utf-8")
        assert "Approved as:" in text and "scope" in text, role
    assert "--note" in (ROOT / "agents/planner.md").read_text(encoding="utf-8")
    assert "--note" in (ROOT / "skills/wuwei-plan/SKILL.md").read_text(encoding="utf-8")
    assert "Approved as:" in (ROOT / "docs/site/daily.md").read_text(encoding="utf-8")
