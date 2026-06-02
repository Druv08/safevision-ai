"""
test_opencv.py
--------------
Quick sanity check that OpenCV can access the webcam.

Controls:
    Press 'q' to quit the window.

Run from the project root:
    python ai-model/inference/test_opencv.py
"""

import cv2


def main():
    # 0 = default webcam. Change to 1, 2, ... for external cameras.
    cap = cv2.VideoCapture(0)

    # If the webcam could not be opened, exit gracefully
    if not cap.isOpened():
        print("Could not access the webcam.")
        print("Tip: close other apps using the camera (Zoom, Teams, browser tabs)")
        print("     or check Windows camera privacy settings.")
        return

    print("Webcam opened. Press 'q' in the video window to quit.")

    try:
        while True:
            # Read a single frame from the webcam
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame from webcam. Exiting.")
                break

            # Show the frame in a window
            cv2.imshow("SafeVision AI - Webcam Test", frame)

            # Wait 1ms for a key press; quit on 'q'
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        # Always release the camera and close windows, even on error
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam released. Test finished.")


if __name__ == "__main__":
    main()
