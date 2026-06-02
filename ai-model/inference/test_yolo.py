"""
test_yolo.py
------------
Quick sanity check that Ultralytics YOLO is installed correctly
and that we can run inference on a sample image.

Run from the project root:
    python ai-model/inference/test_yolo.py
"""

try:
    # YOLO class from the ultralytics package
    from ultralytics import YOLO

    # Load a small pretrained YOLOv8 model (downloads automatically on first run)
    print("Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")

    # Run prediction on a sample image hosted by Ultralytics
    image_url = "https://ultralytics.com/images/bus.jpg"
    print(f"Running prediction on: {image_url}")

    # save=True writes the annotated image into runs/detect/predict/
    results = model.predict(source=image_url, save=True)

    print("YOLO test ran successfully.")
    print("Check the 'runs/detect/predict/' folder for the output image.")

except Exception as e:
    # Catch any error so beginners get a clear message instead of a raw stack trace
    print("YOLO test failed.")
    print(f"Error: {e}")
