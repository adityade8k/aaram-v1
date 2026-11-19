"""Keep the authored teaching protocol fixed and separate from measured results."""

import json
from pathlib import Path
from collections import Counter


PROJECT_ROOT = Path(__file__).parents[1]
PROTOCOL = json.loads((PROJECT_ROOT / "benchmarks" / "ari_teaching" / "cases.json").read_text(encoding="utf-8"))


def test_teaching_scripts_cover_each_planned_category_twice() -> None:
    """The planned eight-script comparison has unique cases and balanced categories."""
    cases = PROTOCOL["cases"]
    assert len({case["id"] for case in cases}) == len(cases) == 8
    assert Counter(case["category"] for case in cases) == {
        "forgotten-step": 2,
        "informed-choice": 2,
        "missing-prerequisite": 2,
        "prepared-handoff": 2,
    }
    assert PROTOCOL["planned_repetitions"] == 3


def test_each_fixed_turn_has_observable_criteria_and_traceable_sources() -> None:
    """Scorers can evaluate each turn without inferring a rubric or asking for mode labels."""
    modes = set(PROTOCOL["modes"])
    assert modes == {"Tell", "Guide", "Ask", "Offer", "Hand over"}
    criterion_ids = []
    criteria = list(PROTOCOL["common_critical_failures"])
    for case in PROTOCOL["cases"]:
        assert len(case["turns"]) >= 2
        criteria.extend(case["critical_failures"])
        for turn in case["turns"]:
            assert turn["prompt"].strip()
            assert turn["acceptable_modes"] and set(turn["acceptable_modes"]) <= modes
            assert turn["criteria"]
            criteria.extend(turn["criteria"])
    for criterion in criteria:
        criterion_ids.append(criterion["id"])
        assert criterion["description"].strip()
        assert criterion["sources"]
        for reference in criterion["sources"]:
            source, separator, location = reference.partition(":")
            assert separator and location and source in PROTOCOL["sources"]
    assert len(criterion_ids) == len(set(criterion_ids))
    assert (PROJECT_ROOT / PROTOCOL["sources"]["shop"]["path"]).is_file()


def test_scoring_template_contains_no_measured_outcomes() -> None:
    """Provisional scripts and planned repetitions cannot masquerade as experiment results."""
    assert "not validated or scored" in PROTOCOL["status"]
    assert "results" not in PROTOCOL
    assert all(value in (None, "", []) for value in PROTOCOL["scoring_template"].values())
    for case in PROTOCOL["cases"]:
        assert not {"score", "passed", "results", "runs"} & case.keys()
        for turn in case["turns"]:
            assert not {"score", "reply", "passed"} & turn.keys()
