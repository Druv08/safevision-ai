import cv2
from pathlib import Path
from services.model_service import get_model
from services.video_detection_service import save_violation


def detect_image(image_path):

    model = get_model()

    results = model.predict(
        source=image_path,
        conf=0.4,
        verbose=False
    )

    detections = []
    frame = None

    for result in results:

        if result.boxes is None:
            continue

        boxes = result.boxes

        for box in boxes:

            cls_id = int(box.cls[0])
            conf = float(box.conf[0])

            detections.append({
                "class_id": cls_id,
                "confidence": round(conf, 3)
            })

            # Check for Helmet Missing (2) or Safety Vest Missing (4)
            violation_type = None
            severity = None
            if cls_id == 2:
                violation_type = "Helmet Missing"
                severity = "High"
            elif cls_id == 4:
                violation_type = "Safety Vest Missing"
                severity = "Medium"

            if violation_type:
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

    return detections