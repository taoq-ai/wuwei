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


def test_no_repository_engagement_list():
    assert not (ROOT / "tests/charter_denylist.sha256").exists()
    spec = (ROOT / "specs/019-charters/spec.md").read_text()
    assert "owner-local pre-publish scan (issue #42)" in spec


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


# Every rule bullet of design section 5.3 has one stable home. The amended
# engineering bullet is split into its five standards and the two verdict rows.
RULES = (
    ("tracks", "_common.md", "fewer than about twenty tasks"),
    ("flags", "lead.md", "LLM output used as instructions"),
    ("pre-pr gates", "_common.md", "arch, quality and security run in parallel"),
    ("negotiation budget", "_common.md", "Exceeding the budget is a design reconsideration, never another round"),
    ("re-gate", "_common.md", "Launch a fresh seat only if the original seat is lost"),
    ("cap", "lead.md", "a slot frees at builder handoff"),
    ("seat policy", "planner.md", "model and runtime for each role"),
    ("registers", "sentinel-arch.md", "A value absent from the register"),
    ("verdict shape", "_common.md", "PARK records a decision"),
    ("retro", "_common.md", "Blocked: / Gap: / Change:"),
    ("test first", "builder.md", "observe the expected failure"),
    ("simplest", "builder.md", "avoid an abstraction with one implementation"),
    ("solid", "builder.md", "never add a layer solely to satisfy a principle"),
    ("clean code", "builder.md", "handle errors where the caller can act on them"),
    ("conventions", "builder.md", "Match the repository's established tests"),
    ("quality simplicity", "sentinel-quality.md", "naming what can be deleted and what replaces it"),
    ("quality design", "sentinel-quality.md", "findings that make this change harder to test or change now"),
    ("pre-merge condition", "shepherd.md", '"before X" blocks until X is met'),
    ("simplicity carve-out", "sentinel-quality.md", "Never list trust-boundary validation"),
    ("escalate definition", "_common.md", "ESCALATE is for an owner-only choice"),
    ("no follow-up ticket", "_common.md", "No seat files or promises a follow-up ticket"),
    ("reviewer ladder", "shepherd.md", "rank authors over the past 90 days"),
    ("trust-boundary block", "_common.md", "A trust-boundary security finding always blocks"),
)


@pytest.mark.parametrize("rule,home,anchor", RULES)
def test_section_5_3_rule_has_one_home(rule, home, anchor):
    texts = charter_text()
    hits = [name for name, body in texts.items() if anchor in body]
    assert hits == [home], (rule, hits)
    assert texts[home].count(anchor) == 1, rule


def test_amended_role_rules():
    texts = charter_text()
    assert "WSJF" in texts["lead.md"] and "RICE" in texts["lead.md"]
    assert "wuwei rank" in texts["lead.md"]
    assert "wuwei merge" in texts["shepherd.md"]
    assert "never approve" in texts["_common.md"].lower()
    assert "never deploy" in texts["_common.md"].lower()
    assert "decision record" in texts["_common.md"]
    assert "Reversibility:" in texts["_common.md"]
    assert "proposals/" in texts["_common.md"]
    assert "wuwei promote" in texts["_common-authoring.md"]
    assert "never write either" in texts["_common-authoring.md"]
    assert "never load the changelog" in texts["_common-authoring.md"]
    assert "never dispatch" in texts["steward.md"]
    for anchor in ("Assumptions:", "mandate", "design reconsideration"):
        assert texts["_common.md"].count(anchor) == 1, anchor


def test_gate_and_merge_safety_contract():
    texts = charter_text()
    common = texts["_common.md"]
    lead = texts["lead.md"]
    shepherd = texts["shepherd.md"]
    assert "whole-tree detached copy" in common
    assert "baseline is green" in common
    assert "non-zero test exit is KILLED" in common
    assert "SURVIVED" in common and "on disk" in common
    assert "stop line" in common and "reviewed sha" in common
    assert "moved HEAD is ESCALATE" in common
    assert "LLM output used as instructions" in lead
    assert "threshold" in lead and "MCP config" in lead
    assert "never-auto" in lead and "FULL" in lead
    assert "review body" in shepherd and "PR comment" in shepherd
    assert "An approval covers its `commit_id` only" in shepherd
    assert "fix round is in flight" in shepherd
    assert "park a one-way" not in texts["sentinel-arch.md"]


def test_pre_review_class_sweep():
    texts = charter_text()
    classes = ("AUTH", "VAL", "DOC", "TEST", "INF", "RET", "ERR", "STATE", "CON", "BUD")
    for code in classes:
        assert f"{code}: PASS|N.A.|FINDING" in texts["builder.md"]
        assert sum(code in texts[role] for role in ("sentinel-arch.md", "sentinel-quality.md", "sentinel-security.md")) == 1
    assert "command" in texts["builder.md"]


def test_class_sweep_anchors_first_verbs():
    lines = charter_text()["builder.md"].splitlines()
    verbs = ("Trace", "Trace", "Search", "Trace", "Trace", "Trace", "Inject", "Interleave", "Pass", "Give")
    for code, verb in zip(("AUTH", "VAL", "DOC", "TEST", "INF", "RET", "ERR", "STATE", "CON", "BUD"), verbs):
        assert any(re.search(rf"`{code}: PASS\|N.A.\|FINDING` {verb}\b", line) for line in lines), code


def test_never_auto_path_flag_scope():
    lead = charter_text()["lead.md"]
    assert "Infrastructure, secret, schema and migration paths force FULL and set `trust_surface`" in lead
    assert "Other never-auto paths route to the owner" in lead
    assert "A diff on a configured never-auto path forces FULL" not in lead


def test_writing_for_a_person_names_the_humanizer_and_carries_the_checklist():
    from wuwei import outward
    body = (CHARTERS / "_common-authoring.md").read_text(encoding="utf-8")
    section = "## Writing for a person" + body.split("## Writing for a person", 1)[1].split("\n## ", 1)[0]
    assert "`humanizer`" in section and "embedded mode" in section
    assert [int(line.split(".")[0]) for line in section.splitlines() if re.match(r"\d+\. ", line)] == list(range(1, 11))
    assert "\u2014" not in section and outward.tells(section) == []
    for role in ("planner", "lead", "builder", "sentinel-arch", "sentinel-quality", "sentinel-security",
                 "sentinel-goal", "shepherd", "steward"):
        assert section.strip() in (ROOT / "agents" / f"{role}.md").read_text(encoding="utf-8"), role
    skill = (ROOT / "skills/wuwei-plan/SKILL.md").read_text(encoding="utf-8")
    assert all(phrase in skill for phrase in ("humanizer", "decision show", "Writing for a person"))
