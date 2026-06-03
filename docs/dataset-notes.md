# Dataset Notes - SafeVision AI

## Dataset Goal
We need a PPE detection dataset for SafeVision AI that can help us detect workers and safety violations in factory, warehouse, or construction-site footage.

The MVP dataset should support detection of:

- person
- helmet
- vest
- no_helmet
- no_vest

## Why Dataset Selection Matters
The quality of the dataset will directly affect how well the AI model detects PPE violations in real-world conditions.

Important dataset factors:

- Different lighting conditions
- Different camera angles
- Workers close to camera and far from camera
- Multiple workers in one frame
- Crowded construction or factory scenes
- Workers partially visible
- Different helmet colors
- Different vest colors
- Images with and without PPE violations

## Final MVP Classes
Our planned MVP classes are:

| Class Name | Meaning |
| --- | --- |
| person | Worker/person detected in frame |
| helmet | Worker is wearing a safety helmet |
| vest | Worker is wearing a safety vest |
| no_helmet | Worker is missing a safety helmet |
| no_vest | Worker is missing a safety vest |

## Dataset Candidates

| Dataset Name | Source | Classes | Size | Format | Good For | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| HardHat-Vest Dataset | Kaggle | To be checked | To be checked | To be checked | Primary PPE training candidate | Need to verify class names and quality |
| Safety Helmet Wearing Dataset / SHWD | GitHub | Helmet / head-related classes | To be checked | To be checked | Backup for helmet/no-helmet detection | Does not fully cover vest detection |
| Roboflow PPE Datasets | Roboflow Universe | Depends on dataset | Varies | YOLO export possible | Easy YOLO export and quick testing | Quality varies between datasets |
| Construction Site Safety Dataset | Roboflow | Hard hat, vest, person-related classes (17 total) | ~398 labeled images | YOLO export possible | Good for construction-site demo/testing | May be small for strong training |

## Selected Dataset
Primary dataset:

Construction Site Safety Dataset (Roboflow Universe, v1, YOLOv8 export). 17 classes, ~398 labeled images. Stored at `ai-model/datasets/raw/construction-safety-yolo/`.

Backup dataset:

HardHat-Vest dataset (Kaggle) — images-only copy retained at `ai-model/datasets/raw/hardhat-vest-dataset-images-only/` for future labeling experiments.

## Dataset Folder Plan
Datasets should be stored locally like this:

```
ai-model/datasets/
├── raw/
└── processed/
```

Meaning:

- raw/ = original downloaded dataset, untouched
- processed/ = cleaned and fixed dataset ready for YOLO training

Important:
Do not push large datasets to GitHub.

## YOLO Dataset Format Reminder
A YOLO dataset usually looks like this:

```
dataset/
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
├── test/
│   ├── images/
│   └── labels/
└── data.yaml
```

## YOLO Label Format Reminder
Each image has one matching text label file.

Example:

```
worker_001.jpg
worker_001.txt
```

Each line in a YOLO label file follows this format:

```
class_id x_center y_center width height
```

Example:

```
0 0.512 0.438 0.210 0.340
```

Meaning:

- class_id = object class number
- x_center = center x position of box
- y_center = center y position of box
- width = box width
- height = box height

All values are normalized between 0 and 1.

## data.yaml Reminder
A basic data.yaml file should contain:

```yaml
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 5

names:
  0: person
  1: helmet
  2: vest
  3: no_helmet
  4: no_vest
```

## Day 2 Notes

- HardHat-Vest zip from Kaggle turned out to be images-only (no labels, no `data.yaml`). Cannot be used for YOLO training as-is. Renamed locally to `hardhat-vest-dataset-images-only/`.
- Switched to Roboflow Universe "Construction Site Safety" v1, YOLOv8 export.
- Dataset has 17 classes; SafeVision MVP only needs 5 of them.
- Relevant class IDs (from `data.yaml`):
  - `Person` -> 9
  - `Hardhat` -> 4
  - `Safety Vest` -> 12
  - `NO-Hardhat` -> 6
  - `NO-Safety Vest` -> 8
- Split counts: train=307, valid=57, test=34.
- Created `ai-model/training/verify_dataset.py` — a safe verification script (no image scanning, no training).
- Raw datasets and `*.zip` files are gitignored.

## Day 2 Decision

- Primary dataset for MVP training: Roboflow Construction Site Safety v1 (`construction-safety-yolo/`).
- Backup: HardHat-Vest images-only (kept for potential future re-labeling).
- Next step (Day 3+): filter/remap the 17 Roboflow classes down to the 5 SafeVision MVP classes inside `ai-model/datasets/processed/`.
