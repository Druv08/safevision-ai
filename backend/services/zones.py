"""
Polygon zones per camera, and the PPE policy each one enforces.

Polygons are stored in normalised image coordinates (x, y in 0..1, origin top
left), so they survive a change of stream resolution and can be drawn on any
snapshot. A person is in a zone when their ground point (the bottom centre of
their box, where their feet are) lies inside the polygon.

Policies:
    both      helmet and vest required
    helmet    helmet required
    vest      vest required
    none      nothing required (a bare head here is not a violation)
    no_entry  nobody may be here: any person inside is a zone intrusion

Where zones overlap, the strictest combination applies: the required PPE is the
union of all zones containing the point, and any no_entry zone makes it an
intrusion. Outside every zone the camera's default policy applies.
"""

from dataclasses import dataclass, field

POLICIES = ("both", "helmet", "vest", "none", "no_entry")
DEFAULT_POLICIES = ("both", "helmet", "vest", "none")  # a camera default cannot be no_entry
REQUIRED = {
    "both": frozenset({"helmet", "vest"}),
    "helmet": frozenset({"helmet"}),
    "vest": frozenset({"vest"}),
    "none": frozenset(),
    "no_entry": frozenset(),
}
MAX_POINTS = 64
MIN_AREA = 1e-4  # of the frame; rejects degenerate (near-zero-area) polygons

Point = tuple[float, float]


@dataclass(frozen=True)
class Zone:
    id: str | None
    name: str
    policy: str
    polygon: tuple[Point, ...]


@dataclass(frozen=True)
class Requirement:
    """What applies at one point of the image."""

    items: frozenset  # PPE that must be worn here
    item_zone: dict = field(default_factory=dict)  # item -> id of the zone requiring it (None = camera default)
    no_entry_zone: str | None = None  # id of a no-entry zone containing the point
    zone_ids: tuple = ()  # every zone containing the point


DEFAULT_REQUIREMENT = Requirement(REQUIRED["both"], {"helmet": None, "vest": None})


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def _on_segment(p: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if abs(cross) > eps:
        return False
    return min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps and min(a[1], b[1]) - eps <= p[1] <= max(
        a[1], b[1]
    ) + eps


def point_in_polygon(p: Point, polygon) -> bool:
    """Ray casting; points on an edge or vertex count as inside."""
    x, y = p
    inside = False
    n = len(polygon)
    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        if _on_segment(p, a, b):
            return True
        if (a[1] > y) != (b[1] > y):
            x_cross = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < x_cross:
                inside = not inside
    return inside


def polygon_area(polygon) -> float:
    n = len(polygon)
    return abs(sum(polygon[i][0] * polygon[(i + 1) % n][1] - polygon[(i + 1) % n][0] * polygon[i][1]
                   for i in range(n))) / 2


def _segments_cross(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)

    o1, o2, o3, o4 = orient(p1, p2, q1), orient(p1, p2, q2), orient(q1, q2, p1), orient(q1, q2, p2)
    if o1 != o2 and o3 != o4:
        return True
    return (o1 == 0 and _on_segment(q1, p1, p2)) or (o2 == 0 and _on_segment(q2, p1, p2)) or (
        o3 == 0 and _on_segment(p1, q1, q2)) or (o4 == 0 and _on_segment(p2, q1, q2))


def validate_polygon(points) -> tuple[Point, ...]:
    """Normalised, simple (non-self-intersecting) polygon with 3..64 points, or ValueError."""
    try:
        poly = tuple((float(p[0]), float(p[1])) for p in points)
    except (TypeError, ValueError, IndexError):
        raise ValueError("polygon must be a list of [x, y] pairs") from None
    if not 3 <= len(poly) <= MAX_POINTS:
        raise ValueError(f"polygon needs 3 to {MAX_POINTS} points")
    if any(not (0.0 <= v <= 1.0) for p in poly for v in p):
        raise ValueError("polygon coordinates must be normalised to 0..1")
    n = len(poly)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):  # adjacent edges share a vertex
                continue
            if _segments_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                raise ValueError("polygon edges cross each other")
    if polygon_area(poly) < MIN_AREA:
        raise ValueError("polygon is too small or its points are in a line")
    return poly


def ground_point(box, frame_w: int, frame_h: int) -> Point:
    """Normalised bottom-centre of a person box (where the feet are)."""
    x1, _, x2, y2 = box
    return (min(1.0, max(0.0, (x1 + x2) / 2 / frame_w)), min(1.0, max(0.0, y2 / frame_h)))


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
class ZoneMap:
    """The zones of one camera plus its default policy outside them."""

    def __init__(self, zones: list[Zone], default_policy: str = "both"):
        if default_policy not in DEFAULT_POLICIES:
            raise ValueError(f"default policy must be one of {DEFAULT_POLICIES}")
        for z in zones:
            if z.policy not in POLICIES:
                raise ValueError(f"unknown zone policy {z.policy!r}")
        self.zones = list(zones)
        self.default_policy = default_policy

    def requirement(self, point: Point) -> Requirement:
        inside = [z for z in self.zones if point_in_polygon(point, z.polygon)]
        if not inside:
            items = REQUIRED[self.default_policy]
            return Requirement(items, {item: None for item in items})
        item_zone = {}
        for z in inside:
            for item in REQUIRED[z.policy]:
                item_zone.setdefault(item, z.id)
        no_entry = next((z.id for z in inside if z.policy == "no_entry"), None)
        return Requirement(frozenset(item_zone), item_zone, no_entry, tuple(z.id for z in inside))


def zones_from_rows(rows: list[dict]) -> list[Zone]:
    return [Zone(r.get("id"), r["name"], r["policy"], tuple(tuple(p) for p in r["polygon"])) for r in rows]
