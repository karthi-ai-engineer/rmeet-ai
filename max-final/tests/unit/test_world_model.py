"""The fact sheet loads and is consistent: places, people, dates inside / outside the window, references, canaries."""

import copy

import pytest

from world import model


@pytest.fixture(scope="module")
def world():
    return model.load()


def test_the_real_fact_sheet_has_no_problems(world):
    assert model.problems(world) == []


def test_agreed_shape(world):
    playable = [p["id"] for p in world["people"] if p.get("playable")]
    assert playable == ["prince", "praga", "rachitaa", "karthi"]
    kinds = [f["name"].rsplit(".", 1)[1] for f in world["files"]]
    assert len(world["files"]) == 40 and kinds.count("xlsx") == 12 and kinds.count("pptx") == 12
    assert kinds.count("pdf") == 8 and kinds.count("docx") == 5
    pdf_kinds = [f.get("spec", {}).get("pdf") or f.get("kind_note") for f in world["files"] if f["name"].endswith(".pdf")]
    assert sorted(pdf_kinds) == sorted(["text", "text", "table", "table", "chart", "chart", "scanned", "scanned"])
    assert sum(1 for f in world["files"] if len(f["versions"]) > 1) == 3      # the 3 old/new cases


def broken(world, change):
    w = copy.deepcopy(world)
    change(w)
    return " | ".join(model.problems(w))


def test_unknown_place_and_author(world):
    assert "unknown place" in broken(world, lambda w: w["events"][0].update(place="nowhere"))
    assert "not a member" in broken(world, lambda w: w["events"][0].update(by="praga"))   # Praga isn't in Product Planning


def test_private_channel_author_must_be_inside(world):
    e = next(i for i, e in enumerate(world["events"]) if e["place"] == "pp-budget")
    assert "not a member" in broken(world, lambda w: w["events"][e].update(by="rachitaa"))


def test_answerable_facts_must_be_inside_the_window(world):
    i = next(i for i, e in enumerate(world["events"]) if e["id"] == "e401")
    assert "outside the reading window" in broken(world, lambda w: w["events"][i].update(wd=-25))


def test_old_facts_must_really_be_old(world):
    i = next(i for i, e in enumerate(world["events"]) if e["id"] == "e602")
    assert "not old enough" in broken(world, lambda w: w["events"][i].update(wd=-20))


def test_fact_pointing_nowhere(world):
    assert "unknown event" in broken(world, lambda w: w["facts"][0].update(at=[{"event": "e999"}]))
    assert "unknown file" in broken(world, lambda w: w["facts"][0].update(at=[{"file": "nope", "v": 1}]))


def test_reply_must_be_in_the_same_place_and_later(world):
    i = next(i for i, e in enumerate(world["events"]) if e["id"] == "e102")
    assert "reply" in broken(world, lambda w: w["events"][i].update(reply_to="e401"))


def test_canary_in_a_public_must_phrase(world):
    assert "canary" in broken(world, lambda w: w["events"][0]["must"].append("BLUEHERON"))


def test_unknown_data_reference(world):
    f = next(i for i, f in enumerate(world["files"]) if f["id"] == "gpu-budget")
    assert "unknown data" in broken(world, lambda w: w["files"][f]["spec"]["sheets"][0]["rows"][1].__setitem__(3, "$budget.nope"))


def test_roles_are_whole(world):
    """A comma inside {...} silently splits a YAML value (found 27 Nov 2026: 'parts buyer (CPU')."""
    praga = next(p for p in world["people"] if p["id"] == "praga")
    assert praga["role"] == "parts buyer (CPU, GPU, memory, SSD)"
    assert "empty value" in broken(world, lambda w: w["people"][0].update({"GPU": None}))
