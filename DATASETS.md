# Datasets

Datasets are not committed (see `.gitignore`). This table records where each
one came from and which model versions used it. Licences and URLs marked
"TODO: confirm" were not stated in the repository and must be checked before
redistributing data or weights trained on it.

Sources: the `README.roboflow.txt` / `data.yaml` files in each raw dataset
folder, `docs/dataset-notes.md`, and the `ai-model/training/build_*.py` scripts.

| Dataset | Source URL | Licence | Used in |
|---|---|---|---|
| Construction Site Safety (Roboflow Universe, v1, 17 classes) | https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety/dataset/1 | CC BY 4.0 | v1 (`safevision_yolov8n_v1`, the helmet model the backend uses), v2 5-class dataset and everything built on it (v3–v5e) |
| vest-no-vest (Roboflow Universe, v1) | https://universe.roboflow.com/arman-keresh-lbrre/vest-no-vest/dataset/1 | CC BY 4.0 | v2 5-class dataset (`safevision_yolov8n_5class_v2`, the PPE/vest model the backend uses) and later versions |
| Construction Helmet Detection (Roboflow Universe, v2) | https://universe.roboflow.com/construction-helmet-sthqm/construction-helmet-detection-dxplv/dataset/2 | CC BY 4.0 | v4 helmet dataset (`build_safevision_v4_helmet_dataset.py`, `raw/construction-helmet-detection-v2/`) and v5+ |
| helmet-no-helmet (Roboflow Universe, v1) | https://universe.roboflow.com/gbc-tdplg/helmet-no-helmet/dataset/1 | CC BY 4.0 | TODO: confirm (present in `datasets/raw/`; not referenced by name in the build scripts) |
| `helmet-yolo` (head / helmet / person) | TODO: confirm | TODO: confirm | v3 helmet dataset (`build_safevision_v3_helmet_dataset.py`) and v5c / v5d, which build on v3 |
| Webcam captures (self-recorded hard negatives and helmet stability sets) | Recorded locally (`capture_webcam_frames.py`, `prepare_v5*_*.py`) | TODO: confirm (consent of the people filmed) | v5, v5c, v5d, v5e |
| HardHat-Vest Dataset (Kaggle) | TODO: confirm | TODO: confirm | Not used for training (images only, no labels; see `docs/dataset-notes.md`) |
| COCO (via Ultralytics `yolov8n.pt` pretrained weights) | https://cocodataset.org | CC BY 4.0 (annotations); images under their Flickr licences | Person model, and the starting weights for all fine-tuned models |

CC BY 4.0 requires attribution. Keep this file with any distributed weights.
