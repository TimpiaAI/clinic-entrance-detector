"""YOLO fine-tuning utilities for clinic-specific person detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TrainerConfig:
    dataset_dir: str = "datasets/clinic_person"
    base_model: str = "yolov8n.pt"
    epochs: int = 40
    imgsz: int = 640
    batch: int = 16
    device: str = "cpu"
    project: str = "runs/train"
    name: str = "clinic_person_finetune"


def _count_files(path: Path, suffix: str) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob(f"*{suffix}")))


def _write_dataset_yaml(dataset_dir: Path) -> Path:
    yaml_path = dataset_dir / "dataset.yaml"
    content = (
        f"path: {dataset_dir.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: person\n"
    )
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def run_training(config: TrainerConfig, logger: Any) -> Path:
    """Fine-tune YOLO model on collected dataset and return best weight path."""
    dataset_dir = Path(config.dataset_dir)
    images_train = dataset_dir / "images" / "train"
    images_val = dataset_dir / "images" / "val"
    labels_train = dataset_dir / "labels" / "train"
    labels_val = dataset_dir / "labels" / "val"

    n_train_images = _count_files(images_train, ".jpg") + _count_files(images_train, ".png")
    n_val_images = _count_files(images_val, ".jpg") + _count_files(images_val, ".png")
    n_train_labels = _count_files(labels_train, ".txt")
    n_val_labels = _count_files(labels_val, ".txt")

    if n_train_images < 20 or n_val_images < 5:
        raise ValueError(
            "Not enough data to train. Need at least 20 train images and 5 val images. "
            f"Current: train={n_train_images}, val={n_val_images}"
        )

    if n_train_labels < n_train_images or n_val_labels < n_val_images:
        raise ValueError(
            "Missing labels for some images. Ensure every image has a matching .txt label file."
        )

    yaml_path = _write_dataset_yaml(dataset_dir)

    logger.info(
        "Starting training",
        extra={
            "extra": {
                "dataset": str(dataset_dir),
                "base_model": config.base_model,
                "epochs": config.epochs,
                "imgsz": config.imgsz,
                "batch": config.batch,
                "device": config.device,
            }
        },
    )

    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("ultralytics is required for training") from exc

    model = YOLO(config.base_model)
    model.train(
        data=str(yaml_path),
        epochs=int(config.epochs),
        imgsz=int(config.imgsz),
        batch=int(config.batch),
        device=config.device,
        project=config.project,
        name=config.name,
        pretrained=True,
        workers=2,
        patience=max(10, int(config.epochs) // 4),
        close_mosaic=10,
        verbose=True,
    )

    best_path = Path(config.project) / config.name / "weights" / "best.pt"
    if not best_path.exists():
        last_path = Path(config.project) / config.name / "weights" / "last.pt"
        if last_path.exists():
            return last_path
        raise FileNotFoundError("Training completed but no weight file was found")

    logger.info("Training completed", extra={"extra": {"best_model": str(best_path)}})
    return best_path
