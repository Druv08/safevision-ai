import cv2
from pathlib import Path
from services.model_service import get_model, get_helmet_model, get_person_model
from services.video_detection_service import save_violation

# v1 model (17-class construction-safety) class IDs for helmet detection
V1_HARDHAT_CLS = 4
V1_NO_HARDHAT_CLS = 6

# 5-class model class IDs for vest detection
VEST_CLS = 3
NO_VEST_CLS = 4


def detect_image(image_path):

    vest_model = get_model()
    h_model = get_helmet_model()
    person_model = get_person_model()

    vest_results = vest_model.predict(source=image_path, conf=0.25, verbose=False)
    helmet_results = h_model.predict(source=image_path, conf=0.25, verbose=False)
    person_results = person_model.predict(source=image_path, conf=0.5, classes=[0], verbose=False)

    def get_box_overlap(box_a, box_b):
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
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

    helmet_boxes = []
    no_helmet_boxes = []
    vest_boxes = []
    no_vest_boxes = []

    for result in helmet_results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            if cls_id == V1_HARDHAT_CLS:
                helmet_boxes.append((xyxy, conf))
            elif cls_id == V1_NO_HARDHAT_CLS:
                no_helmet_boxes.append((xyxy, conf))

    for result in vest_results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            if cls_id == VEST_CLS:
                vest_boxes.append((xyxy, conf))
            elif cls_id == NO_VEST_CLS:
                no_vest_boxes.append((xyxy, conf))

    person_boxes = []
    if person_results and len(person_results) > 0 and person_results[0].boxes is not None:
        for box in person_results[0].boxes:
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            person_boxes.append((xyxy, conf))

    detections = []

    # First pass: a detected helmet only counts as "worn" when it sits on a
    # person's head. When people are present but the helmet is on nobody's head
    # (held in hand, carried, lying nearby) it must surface as "No Helmet".
    worn_helmet_boxes = []
    held_helmet_boxes = []
    for h_box, conf in helmet_boxes:
        worn = any(is_helmet_on_head(h_box, p_box) for p_box, _ in person_boxes)
        if worn or not person_boxes:
            detections.append({"class_id": 1, "confidence": round(conf, 3)})
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

    # Second pass: emit "No Helmet" only for helmet/no-helmet boxes that are NOT
    # duplicates of a worn helmet.
    for h_box, conf in held_helmet_boxes:
        if overlaps_worn(h_box):
            continue
        detections.append({"class_id": 2, "confidence": round(conf, 3)})
    for nh_box, conf in no_helmet_boxes:
        if overlaps_worn(nh_box):
            continue
        detections.append({"class_id": 2, "confidence": round(conf, 3)})
    for _, conf in vest_boxes:
        detections.append({"class_id": 3, "confidence": round(conf, 3)})
    for _, conf in no_vest_boxes:
        detections.append({"class_id": 4, "confidence": round(conf, 3)})
    for _, p_conf in person_boxes:
        detections.append({"class_id": 0, "confidence": round(p_conf, 3)})

    violations = []
    for _, conf in no_helmet_boxes:
        violations.append(("Helmet Missing", "High", conf))
    for _, conf in no_vest_boxes:
        violations.append(("Safety Vest Missing", "Medium", conf))

    helmet_worn = 0
    no_helmet_count = 0
    vest_worn = 0
    no_vest_count = 0
    extra_violations = []

    for p_box, _ in person_boxes:
        has_helmet = any(is_helmet_on_head(h, p_box) for h, _ in helmet_boxes)
        has_no_helmet = any(get_box_overlap(nh, p_box) >= 0.2 for nh, _ in no_helmet_boxes)

        # Helmet overlaps the person but is NOT on the head (e.g. held in hand).
        # The V1 model fires "Helmet" class instead of "No Hardhat" in this case,
        # so we catch it here and treat it as a missing-helmet situation.
        helmet_held_not_worn = (
            not has_helmet
            and any(get_box_overlap(h, p_box) >= 0.15 for h, _ in helmet_boxes)
        )

        has_vest = any(get_box_overlap(v, p_box) >= 0.2 for v, _ in vest_boxes)
        has_no_vest = any(get_box_overlap(nv, p_box) >= 0.2 for nv, _ in no_vest_boxes)

        if has_helmet:
            helmet_worn += 1
        elif has_no_helmet or helmet_held_not_worn:
            no_helmet_count += 1
            # V1 model didn't fire "No Hardhat" — log the violation ourselves
            if helmet_held_not_worn and not has_no_helmet:
                held_conf = max((c for _, c in helmet_boxes), default=0.5)
                extra_violations.append(("Helmet Missing", "High", held_conf))

        if has_vest:
            vest_worn += 1
        elif has_no_vest:
            no_vest_count += 1

    # Merge extra violations, skipping types already logged by V1 model
    existing_types = {v[0] for v in violations}
    for ev in extra_violations:
        if ev[0] not in existing_types:
            violations.append(ev)

    summary = {
        "total_persons": len(person_boxes),
        "helmet_worn": helmet_worn,
        "no_helmet": no_helmet_count,
        "vest_worn": vest_worn,
        "no_vest": no_vest_count,
    }

    frame = None
    for violation_type, severity, conf in violations:
        if frame is None:
            frame = cv2.imread(image_path)
        save_violation(
            frame=frame,
            source_name=Path(image_path).name,
            frame_number=1,
            violation_type=violation_type,
            severity=severity,
            confidence=conf
        )

    return detections, summary
