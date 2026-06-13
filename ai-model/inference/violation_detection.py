import cv2
import csv
import time
import uuid
import argparse
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = PROJECT_ROOT / "ai-model" / "outputs" / "training-runs" / "safevision_yolov8n_5class_v2" / "weights" / "best.pt"

OUTPUT_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "violations"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
CSV_PATH = OUTPUT_DIR / "violations_log.csv"

SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "no_helmet",
    3: "vest",
    4: "no_vest",
}

COOLDOWN_SECONDS = 5


def init_csv():
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "violation_id",
                "timestamp",
                "source",
                "frame_number",
                "violation_type",
                "severity",
                "confidence",
                "screenshot_path"
            ])


def save_violation(frame,
                   source_name,
                   frame_number,
                   violation_type,
                   severity,
                   confidence):

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    violation_id = str(uuid.uuid4())[:8]

    screenshot_name = f"{timestamp}_{violation_type.replace(' ','_')}.jpg"

    screenshot_path = SCREENSHOT_DIR / screenshot_name

    cv2.imwrite(str(screenshot_path), frame)

    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            violation_id,
            timestamp,
            source_name,
            frame_number,
            violation_type,
            severity,
            round(confidence, 3),
            str(screenshot_path)
        ])

    print(f"[VIOLATION] {violation_type}")
    print(f"[SCREENSHOT] {screenshot_path}")


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--source", default="0")
    parser.add_argument("--conf", type=float, default=0.4)

    return parser.parse_args()


def main():

    args = parse_args()

    source = 0 if args.source == "0" else args.source

    model = YOLO(str(MODEL_PATH))

    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print("Cannot open source")
        return

    init_csv()

    last_save = {
        "no_vest": 0,
        "no_helmet": 0
    }

    frame_number = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        frame_number += 1

        results = model.predict(
            frame,
            conf=args.conf,
            verbose=False
        )

        result = results[0]

        current_time = time.time()

        frame_has_no_vest = False
        frame_has_no_helmet = False

        highest_conf_no_vest = 0
        highest_conf_no_helmet = 0

        if result.boxes is not None:

            boxes = result.boxes.xyxy.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy().astype(int)

            for box, conf, cls_id in zip(boxes, confs, classes):

                x1, y1, x2, y2 = map(int, box)

                label = CLASS_NAMES.get(cls_id, str(cls_id))

                color = (0,255,0)

                if label in ["no_vest","no_helmet"]:
                    color = (0,0,255)

                cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)

                cv2.putText(
                    frame,
                    f"{label} {conf:.2f}",
                    (x1,y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2
                )

                if label == "no_vest":
                    frame_has_no_vest = True
                    highest_conf_no_vest = max(highest_conf_no_vest, conf)

                if label == "no_helmet":
                    frame_has_no_helmet = True
                    highest_conf_no_helmet = max(highest_conf_no_helmet, conf)

        # BOTH VIOLATIONS
        if frame_has_no_vest and frame_has_no_helmet:

            if current_time - last_save["no_vest"] > COOLDOWN_SECONDS:

                save_violation(
                    frame,
                    str(source),
                    frame_number,
                    "Vest + Helmet Missing",
                    "Critical",
                    max(highest_conf_no_vest,
                        highest_conf_no_helmet)
                )

                last_save["no_vest"] = current_time
                last_save["no_helmet"] = current_time

        else:

            if frame_has_no_vest:

                if current_time - last_save["no_vest"] > COOLDOWN_SECONDS:

                    save_violation(
                        frame,
                        str(source),
                        frame_number,
                        "Safety Vest Missing",
                        "Medium",
                        highest_conf_no_vest
                    )

                    last_save["no_vest"] = current_time

            if frame_has_no_helmet:

                if current_time - last_save["no_helmet"] > COOLDOWN_SECONDS:

                    save_violation(
                        frame,
                        str(source),
                        frame_number,
                        "Helmet Missing",
                        "High",
                        highest_conf_no_helmet
                    )

                    last_save["no_helmet"] = current_time

        cv2.imshow("SafeVision AI - Violations", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()