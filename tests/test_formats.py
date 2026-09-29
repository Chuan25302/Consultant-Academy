import pytest

from src.agents.formats import FORMAT_PROFILES, KIT_SPECS, LEVEL_GUIDE, profile_for

PILLARS = ["TECHNICAL", "INDUSTRY", "FRAMEWORK",
           "SOFTSKILL", "COMPLIANCE", "SUSTAINABILITY"]


@pytest.mark.parametrize("pillar", PILLARS)
def test_every_pillar_has_a_complete_profile(pillar):
    p = FORMAT_PROFILES[pillar]
    assert len(p.sections) == 2, "two middle sections per issue (A2)"
    assert all(title and intent for title, intent in p.sections)
    assert p.kit in KIT_SPECS
    assert len(p.scenes) >= 5, "scene pool must allow no-repeat rotation"


def test_no_two_pillars_share_a_section_title():
    titles = [t for p in FORMAT_PROFILES.values() for t, _ in p.sections]
    assert len(titles) == len(set(titles)), "identical titles re-create the sameness"


def test_all_three_kits_are_used_by_some_pillar():
    used = {p.kit for p in FORMAT_PROFILES.values()}
    assert used == set(KIT_SPECS)


def test_level_guide_covers_l1_l2_l3():
    assert set(LEVEL_GUIDE) == {1, 2, 3}
    assert all(len(v) > 20 for v in LEVEL_GUIDE.values())


@pytest.mark.parametrize("pillar", PILLARS)
def test_known_pillar_returns_its_own_profile(pillar):
    assert profile_for(pillar) is FORMAT_PROFILES[pillar]


def test_unknown_pillar_falls_back_to_technical():
    assert profile_for("NOPE") is FORMAT_PROFILES["TECHNICAL"]


def test_checklist_kit_forbids_square_bracket_syntax():
    instructions = KIT_SPECS["checklist"].instructions
    assert "- ☐ " in instructions, "must teach ☐ character"
    assert "ห้าม" in instructions, "must forbid square-bracket syntax"


def test_calculator_kit_requires_source_attribution():
    instructions = KIT_SPECS["calculator"].instructions
    assert "ที่มา" in instructions, "must require source attribution"
    assert "ห้าม LaTeX" in instructions, "must forbid LaTeX notation"
