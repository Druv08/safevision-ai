from services.model_service import get_model


def detect_image(image_path):

    model = get_model()

    results = model.predict(
        source=image_path,
        conf=0.4,
        verbose=False
    )

    detections = []

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

    return detections