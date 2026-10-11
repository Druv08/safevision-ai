from config import settings
from services.model_service import get_helmet_model, get_model, get_person_model, model_version
from services.violations_service import save_violation

# v1 model (17-class construction-safety) class IDs for helmet detection
V1_HARDHAT_CLS = 4
V1_NO_HARDHAT_CLS = 6

# 5-class model class IDs for vest detection
VEST_CLS = 3
NO_VEST_CLS = 4


def get_box_overlap(box_a, box_b):
    """Fraction of box_a's area that lies inside box_b."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    if area_a <= 0.0:
        return 0.0
    return inter / area_a


def is_helmet_on_head(h_box, p_box):
    """
    Returns True only when the helmet bounding box sits on the head zone
    (top-centre) of the person bounding box — i.e. actually worn.

    Rejects helmets held in hand, raised, carried on shoulder, floating
    above the head (model false positives on background objects), or lying
    nearby by requiring ALL of:
    - helmet vertical centre in the head zone: between the very top of the
      person box and the top 30 % of the height (not floating above it)
    - helmet bottom edge reaches down ONTO the head (>=10 % of height) but
      not as far as the chest (<=42 %) — a box entirely above the person is
      not worn
    - helmet horizontally centred over the head: its x-centre must lie in
      the middle 60 % of the person box (a hand-held helmet is off to the
      side, even when raised level with the head)
    - the helmet must not be wider than the person (a box covering the whole
      upper body is not a worn helmet)
    """
    px1, py1, px2, py2 = p_box
    person_h = py2 - py1
    person_w = px2 - px1
    if person_h <= 0 or person_w <= 0:
        return False

    hx1, hy1, hx2, hy2 = h_box

    # Minimal horizontal overlap — helmet must be roughly above the person
    horiz_overlap = max(0.0, min(hx2, px2) - max(hx1, px1))
    if horiz_overlap <= 0:
        return False

    # Normalised Y positions relative to top of person box (0 = top, 1 = bottom)
    norm_center_y = ((hy1 + hy2) / 2.0 - py1) / person_h
    norm_bottom_y = (hy2 - py1) / person_h

    # Normalised X centre of the helmet relative to the person box width
    norm_center_x = ((hx1 + hx2) / 2.0 - px1) / person_w

    # A real helmet is much narrower than the person's full width
    helmet_w_ratio = (hx2 - hx1) / person_w

    return (
        0.0 <= norm_center_y <= 0.30   # vertically in the head zone (not above it)
        and 0.10 <= norm_bottom_y <= 0.42  # sits onto the head, not floating above / down to chest
        and 0.20 <= norm_center_x <= 0.80  # horizontally over the head, not to the side
        and helmet_w_ratio <= 0.85     # not a body-sized box
    )


def _det(class_id, box, conf):
    """One API detection: class, confidence and the xyxy pixel box (for UI overlays)."""
    return {"class_id": class_id, "confidence": round(conf, 3), "box": [round(float(v), 1) for v in box]}


def evaluate(helmet_boxes, no_helmet_boxes, vest_boxes, no_vest_boxes, person_boxes):
    """
    Apply the PPE rules to (xyxy, conf) boxes.

    Returns (detections, summary, violations). `violations` is a list of
    (type, confidence) with at most one entry per person per type, built only
    from boxes that survive filtering and overlap a detected person.
    """
    detections = []

    # First pass: a detected helmet only counts as "worn" when it sits on a
    # person's head. When people are present but the helmet is on nobody's head
    # (held in hand, carried, lying nearby) it must surface as "No Helmet".
    worn_helmet_boxes = []
    held_helmet_boxes = []
    for h_box, conf in helmet_boxes:
        worn = any(is_helmet_on_head(h_box, p_box) for p_box, _ in person_boxes)
        if worn or not person_boxes:
            detections.append(_det(1, h_box, conf))
            if worn:
                worn_helmet_boxes.append(h_box)
        else:
            held_helmet_boxes.append((h_box, conf))

    def overlaps_worn(box):
        # The helmet model often emits several overlapping boxes over the same
        # head (e.g. a tight "worn" box plus a larger one covering the chest).
        # Anything sitting on a head already judged as worn is a duplicate and
        # must not be reported as a violation.
        return any(get_box_overlap(box, wb) >= 0.5 for wb in worn_helmet_boxes)

    # Second pass: drop duplicates of a worn helmet. Only what survives here
    # may become a "No Helmet" detection or violation.
    held_helmet_boxes = [(b, c) for b, c in held_helmet_boxes if not overlaps_worn(b)]
    no_helmet_boxes = [(b, c) for b, c in no_helmet_boxes if not overlaps_worn(b)]

    for b, conf in held_helmet_boxes + no_helmet_boxes:
        detections.append(_det(2, b, conf))
    for b, conf in vest_boxes:
        detections.append(_det(3, b, conf))
    for b, conf in no_vest_boxes:
        detections.append(_det(4, b, conf))
    for b, p_conf in person_boxes:
        detections.append(_det(0, b, p_conf))

    helmet_worn = no_helmet_count = vest_worn = no_vest_count = 0
    violations = []

    for p_box, _ in person_boxes:
        has_helmet = any(is_helmet_on_head(h, p_box) for h, _ in helmet_boxes)
        # Helmet overlapping the person but NOT on the head (e.g. held in hand):
        # the v1 model fires "Hardhat" rather than "NO-Hardhat" here.
        missing_helmet_confs = [c for nh, c in no_helmet_boxes if get_box_overlap(nh, p_box) >= 0.2]
        missing_helmet_confs += [c for h, c in held_helmet_boxes if get_box_overlap(h, p_box) >= 0.15]

        has_vest = any(get_box_overlap(v, p_box) >= 0.2 for v, _ in vest_boxes)
        missing_vest_confs = [c for nv, c in no_vest_boxes if get_box_overlap(nv, p_box) >= 0.2]

        if has_helmet:
            helmet_worn += 1
        elif missing_helmet_confs:
            no_helmet_count += 1
            violations.append(("no_helmet", max(missing_helmet_confs)))

        if has_vest:
            vest_worn += 1
        elif missing_vest_confs:
            no_vest_count += 1
            violations.append(("no_vest", max(missing_vest_confs)))

    summary = {
        "total_persons": len(person_boxes),
        "helmet_worn": helmet_worn,
        "no_helmet": no_helmet_count,
        "vest_worn": vest_worn,
        "no_vest": no_vest_count,
    }
    return detections, summary, violations


def _boxes(results, wanted):
    """{cls_id: [(xyxy, conf), ...]} for the class ids in `wanted`."""
    out = {cls_id: [] for cls_id in wanted}
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id in out:
                out[cls_id].append((box.xyxy[0].tolist(), float(box.conf[0])))
    return out


def analyze_frame(frame):
    """Run all three models on one BGR frame and apply the PPE rules."""
    conf = settings.ppe_confidence
    vest = _boxes(get_model().predict(frame, conf=conf, verbose=False), (VEST_CLS, NO_VEST_CLS))
    helmet = _boxes(
        get_helmet_model().predict(frame, conf=conf, verbose=False),
        (V1_HARDHAT_CLS, V1_NO_HARDHAT_CLS),
    )
    person = _boxes(
        get_person_model().predict(frame, conf=settings.person_confidence, classes=[0], verbose=False),
        (0,),
    )
    return evaluate(
        helmet[V1_HARDHAT_CLS],
        helmet[V1_NO_HARDHAT_CLS],
        vest[VEST_CLS],
        vest[NO_VEST_CLS],
        person[0],
    )


def detect_image(frame, source="image"):
    detections, summary, violations = analyze_frame(frame)
    version = model_version()
    for vtype, conf in violations:
        save_violation(frame, vtype, conf, source, version)
    return detections, summary
