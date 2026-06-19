"""
test_trained_model.py
---------------------
Run a quick prediction check using the trained SafeVision YOLOv8n model.

This script:
1. Loads the trained weights from the training run.
2. Uses only the first 10 test images.
3. Saves annotated prediction images into the predictions folder.
4. Prints detected classes and confidence scores for each image.
"""

from pathlib import Path


# --- Paths -------------------------------------------------------------------

# This file lives in ai-model/inference/, so two parents up is the project root.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

MODEL_PATH = (
	PROJECT_ROOT
	/ "ai-model"
	/ "outputs"
	/ "training-runs"
	/ "safevision_yolov8n_v1"
	/ "weights"
	/ "best.pt"
)

TEST_IMAGES_DIR = (
	PROJECT_ROOT / "ai-model" / "datasets" / "raw" / "construction-safety-yolo" / "test" / "images"
)

PREDICTIONS_DIR = PROJECT_ROOT / "ai-model" / "outputs" / "predictions"
PREDICTION_RUN_NAME = "day3_test_predictions"


# --- Settings ----------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.25
MAX_TEST_IMAGES = 10

# MVP classes that should be easy to spot in the console output.
MVP_CLASSES = {
	"Hardhat",
	"NO-Hardhat",
	"NO-Safety Vest",
	"Person",
	"Safety Vest",
}


def collect_test_images(images_dir: Path, limit: int) -> list[Path]:
	"""Return the first N test images in a stable sorted order."""
	valid_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
	images = sorted(
		path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in valid_suffixes
	)
	return images[:limit]


def format_detection(class_name: str, confidence: float, class_id: int | None = None) -> str:
	"""Format one detection line for beginner-friendly console output."""
	if class_id is None:
		return f"{class_name} ({confidence:.3f})"
	return f"{class_name} [class_id={class_id}] ({confidence:.3f})"


def main() -> int:
	# Import ultralytics only when we are ready to run inference.
	try:
		from ultralytics import YOLO
	except ImportError:
		print("[ERROR] ultralytics is not installed in the current Python environment.")
		print("Install it with: pip install ultralytics")
		return 1

	print("=" * 70)
	print("SafeVision AI - trained model prediction test")
	print("=" * 70)
	print(f"Model path          : {MODEL_PATH}")
	print(f"Test images folder   : {TEST_IMAGES_DIR}")
	print(f"Prediction output dir: {PREDICTIONS_DIR / PREDICTION_RUN_NAME}")
	print(f"Confidence threshold : {CONFIDENCE_THRESHOLD}")
	print(f"Max test images      : {MAX_TEST_IMAGES}")
	print("MVP classes          : Hardhat, NO-Hardhat, NO-Safety Vest, Person, Safety Vest")
	print("=" * 70)

	# Safety checks before doing any inference work.
	if not MODEL_PATH.is_file():
		print(f"\n[ERROR] Trained model not found at:\n  {MODEL_PATH}")
		return 1

	if not TEST_IMAGES_DIR.is_dir():
		print(f"\n[ERROR] Test images folder not found at:\n  {TEST_IMAGES_DIR}")
		return 1

	test_images = collect_test_images(TEST_IMAGES_DIR, MAX_TEST_IMAGES)
	if not test_images:
		print(f"\n[ERROR] No test images found in:\n  {TEST_IMAGES_DIR}")
		return 1

	try:
		print("\nLoading trained model...")
		model = YOLO(str(MODEL_PATH))

		print(f"Running prediction on {len(test_images)} image(s)...\n")
		results = model.predict(
			source=[str(image_path) for image_path in test_images],
			conf=CONFIDENCE_THRESHOLD,
			save=True,
			project=str(PREDICTIONS_DIR),
			name=PREDICTION_RUN_NAME,
			exist_ok=True,
			verbose=False,
		)
	except Exception as exc:
		print(f"\n[ERROR] Prediction failed: {exc}")
		return 1

	# Ultralytics exposes the class-name map on the loaded model.
	class_names = getattr(model, "names", {})

	print("\n" + "=" * 70)
	print("Prediction summary")
	print("=" * 70)
	print(f"Model path          : {MODEL_PATH}")
	print(f"Number of test images: {len(test_images)}")
	print(f"Output folder        : {PREDICTIONS_DIR / PREDICTION_RUN_NAME}")
	print("=" * 70)

	for result in results:
		image_path = Path(result.path)
		print(f"\nImage: {image_path.name}")

		boxes = getattr(result, "boxes", None)
		if boxes is None or len(boxes) == 0:
			print("  Detected: none")
			continue

		detections = []
		mvp_detections = []

		for box in boxes:
			class_id = int(box.cls.item()) if hasattr(box.cls, "item") else int(box.cls)
			confidence = float(box.conf.item()) if hasattr(box.conf, "item") else float(box.conf)
			class_name = class_names.get(class_id, str(class_id))
			detections.append(format_detection(class_name, confidence, class_id))

			if class_name in MVP_CLASSES:
				mvp_detections.append(format_detection(class_name, confidence, class_id))

		print("  Detected:")
		for item in detections:
			print(f"    - {item}")

		print("  MVP detections:")
		if mvp_detections:
			for item in mvp_detections:
				print(f"    - {item}")
		else:
			print("    - none")

	print("\n" + "=" * 70)
	print("Prediction test completed successfully.")
	print("Annotated images were saved with the model's drawn boxes and labels.")
	print("=" * 70)

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
