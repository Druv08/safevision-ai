"""Zone geometry and per-zone PPE policy (no weights, synthetic detections)."""

import numpy as np
import pytest

from services.pipeline import Det, FrameDets, Person, Pipeline, PipelineConfig
from services.zones import (
    Zone,
    ZoneMap,
    ground_point,
    point_in_polygon,
    validate_polygon,
)

SQUARE = ((0.2, 0.2), (0.6, 0.2), (0.6, 0.6), (0.2, 0.6))
# Concave "L": the notch (0.5..0.8, 0.1..0.5) is outside
L_SHAPE = ((0.1, 0.1), (0.5, 0.1), (0.5, 0.5), (0.8, 0.5), (0.8, 0.8), (0.1, 0.8))


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("point,inside", [
    ((0.4, 0.4), True),
    ((0.1, 0.4), False),
    ((0.2, 0.4), True),   # on an edge
    ((0.6, 0.6), True),   # on a vertex
    ((0.61, 0.4), False),
])
def test_point_in_square(point, inside):
    assert point_in_polygon(point, SQUARE) is inside


@pytest.mark.parametrize("point,inside", [
    ((0.3, 0.3), True),
    ((0.7, 0.3), False),  # in the notch of the L
    ((0.7, 0.7), True),
    ((0.9, 0.7), False),
])
def test_point_in_concave_polygon(point, inside):
    assert point_in_polygon(point, L_SHAPE) is inside


def test_validate_polygon_accepts_and_normalises():
    assert validate_polygon([[0.2, 0.2], [0.6, 0.2], [0.6, 0.6]]) == ((0.2, 0.2), (0.6, 0.2), (0.6, 0.6))
    assert validate_polygon(L_SHAPE) == L_SHAPE


@pytest.mark.parametrize("points,message", [
    ([[0.1, 0.1], [0.5, 0.5]], "3 to 64"),
    ([[0, 0]] * 65, "3 to 64"),
    ([[0.1, 0.1], [1.5, 0.1], [0.5, 0.5]], "normalised"),
    ([[-0.1, 0.1], [0.5, 0.1], [0.5, 0.5]], "normalised"),
    ([[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]], "too small"),  # collinear
    ([[0.1, 0.1], [0.6, 0.6], [0.6, 0.1], [0.1, 0.6]], "cross"),  # bow tie
    ("not a polygon", "pairs"),
    ([[0.1], [0.2], [0.3]], "pairs"),
])
def test_validate_polygon_rejects(points, message):
    with pytest.raises(ValueError, match=message):
        validate_polygon(points)


def test_ground_point_is_bottom_centre_normalised_and_clamped():
    assert ground_point((100, 50, 200, 400), 1000, 500) == (0.15, 0.8)
    assert ground_point((900, 100, 1100, 600), 1000, 500) == (1.0, 1.0)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
def zmap(*zones, default="both"):
    return ZoneMap([Zone(f"z{i}", f"zone {i}", policy, poly) for i, (policy, poly) in enumerate(zones)], default)


def test_default_policy_applies_outside_all_zones():
    req = zmap(("none", SQUARE), default="vest").requirement((0.9, 0.9))
    assert req.items == {"vest"} and req.item_zone == {"vest": None} and req.zone_ids == ()


@pytest.mark.parametrize("policy,items", [
    ("both", {"helmet", "vest"}), ("helmet", {"helmet"}), ("vest", {"vest"}), ("none", set()), ("no_entry", set()),
])
def test_each_policy_inside_its_zone(policy, items):
    req = zmap((policy, SQUARE)).requirement((0.4, 0.4))
    assert req.items == items
    assert req.no_entry_zone == ("z0" if policy == "no_entry" else None)


def test_overlapping_zones_take_the_union_and_any_no_entry():
    inner = ((0.3, 0.3), (0.5, 0.3), (0.5, 0.5), (0.3, 0.5))
    req = zmap(("helmet", SQUARE), ("vest", inner), ("none", SQUARE)).requirement((0.4, 0.4))
    assert req.items == {"helmet", "vest"}
    assert req.item_zone == {"helmet": "z0", "vest": "z1"}
    assert req.zone_ids == ("z0", "z1", "z2")
    assert zmap(("both", SQUARE), ("no_entry", inner)).requirement((0.4, 0.4)).no_entry_zone == "z1"


def test_invalid_policies_are_rejected():
    with pytest.raises(ValueError):
        zmap(("hardhat", SQUARE))
    with pytest.raises(ValueError):
        zmap(default="no_entry")


# ---------------------------------------------------------------------------
# Pipeline with zones (frame 1000 x 500; person feet at x=0.15, y=0.8)
# ---------------------------------------------------------------------------
W, H, FPS = 1000, 500, 10
LEFT = ((0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0))  # bottom-left quarter, where the person stands


def bare_head(tid=1, x=100):
    """Person with a no_helmet box on the head and no vest evidence; feet at ((x+50)/1000, 0.8)."""
    return FrameDets([Person((x, 50, x + 100, 400), 0.9, track_id=tid)],
                     no_helmet=[Det((x + 30, 45, x + 70, 90), 0.7)],
                     no_vest=[Det((x + 10, 130, x + 90, 280), 0.6)])


def run(zones, frames, window=2.0):
    pipe = Pipeline(config=PipelineConfig(window_s=window, clear_s=1.0), tracker=object(), zones=zones)
    pipe.frame_size = (W, H)
    opened, closed, obs = [], [], []
    for n, dets in enumerate(frames):
        r = pipe.step(dets, n / FPS)
        opened += r.opened
        closed += r.closed
        obs += r.observations
    c, o = pipe.finish()
    return opened, closed + c, obs + o


def test_bare_head_in_none_zone_is_not_a_violation():
    opened, closed, obs = run(zmap(("none", LEFT)), [bare_head()] * 40)
    assert opened == [] and closed == []
    assert obs == []  # nothing was required, so it does not count towards compliance


def test_helmet_zone_flags_only_the_helmet_and_records_the_zone():
    opened, _, obs = run(zmap(("helmet", LEFT)), [bare_head()] * 40)
    assert [(e.type, e.zone_id) for e in opened] == [("no_helmet", "z0")]
    assert [(o.item, o.outcome) for o in obs] == [("helmet", "violation")]


def test_default_policy_outside_zones_still_flags_both():
    elsewhere = ((0.6, 0.0), (1.0, 0.0), (1.0, 0.4), (0.6, 0.4))
    opened, _, _ = run(zmap(("none", elsewhere)), [bare_head()] * 40)
    assert sorted((e.type, e.zone_id) for e in opened) == [("no_helmet", None), ("no_vest", None)]


def test_no_entry_zone_raises_intrusion_after_the_window():
    fully_equipped = FrameDets(
        [Person((100, 50, 200, 400), 0.9, track_id=1)],
        helmet=[Det((130, 45, 170, 90), 0.8)], vest=[Det((110, 130, 190, 280), 0.9)],
    )
    opened, closed, _ = run(zmap(("no_entry", LEFT), default="none"), [fully_equipped] * 15)
    assert opened == []  # 1.5 s < 2 s window
    opened, closed, _ = run(zmap(("no_entry", LEFT), default="none"), [fully_equipped] * 30)
    assert [(e.type, e.zone_id, e.track_id) for e in opened] == [("zone_intrusion", "z0", 1)]
    assert closed[0].start_s == 0.0 and closed[0].end_s == pytest.approx(2.9)


def test_walking_out_of_a_required_zone_ends_the_episode():
    zones = zmap(("helmet", LEFT), default="none")
    inside = [bare_head(x=100)] * 30           # feet at x=0.15: in the helmet zone
    outside = [bare_head(x=700)] * 20          # feet at x=0.75: default "none"
    opened, closed, _ = run(zones, inside + outside)
    assert len(opened) == 1
    assert closed[0].end_s == pytest.approx(2.9)  # ended when they left the zone, not at the end of the clip


def test_two_people_in_different_zones():
    right = ((0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0))
    zones = zmap(("helmet", LEFT), ("no_entry", right), default="none")
    a, b = bare_head(tid=1, x=100), bare_head(tid=2, x=700)
    both = FrameDets(a.persons + b.persons, no_helmet=a.no_helmet + b.no_helmet, no_vest=a.no_vest + b.no_vest)
    opened, _, _ = run(zones, [both] * 30)
    assert sorted((e.track_id, e.type) for e in opened) == [(1, "no_helmet"), (2, "zone_intrusion")]


def test_snapshot_draws_zones_and_frame_size_comes_from_the_frame():
    pipe = Pipeline(config=PipelineConfig(window_s=0.0), zones=zmap(("helmet", LEFT)))
    r = pipe.step(bare_head(tid=None), 0.0, np.zeros((H, W, 3), np.uint8))
    assert pipe.frame_size == (W, H)
    assert [e.type for e in r.opened] == ["no_helmet"]
    assert r.opened[0].snapshot.startswith(b"\xff\xd8")


def test_zones_without_frame_size_is_an_error():
    pipe = Pipeline(config=PipelineConfig(), tracker=object(), zones=zmap(("helmet", LEFT)))
    with pytest.raises(ValueError, match="frame size"):
        pipe.step(bare_head(), 0.0)
