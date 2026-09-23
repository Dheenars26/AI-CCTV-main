"""
Vectorised Non-Maximum Suppression, Weighted Box Fusion and score-threshold utilities.

Why this module exists
----------------------
The previous implementation funnelled every YOLO prediction tensor through
``cv2.dnn.NMSBoxes``, which is **class agnostic**: a high-scoring ``Safety Vest`` box and the
``Person`` box covering the same torso suppress each other (measured on the bundled PPE weights,
the ``Person`` class was being deleted by exactly this path). It also applied a single global
score threshold before NMS, so a 0.20-confidence fragment could erase a well-localised 0.9 box of
a different class.

Everything here operates on ``numpy`` arrays of shape ``(N, 4)`` (``xyxy``) plus a parallel score
and class-id vector, which keeps the post-processing cost negligible next to inference.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """Converts centre-form ``(cx, cy, w, h)`` rows into corner-form ``(x1, y1, x2, y2)`` rows."""
    if boxes.size == 0:
        return np.zeros((0, 4), dtype=np.float32)
    cx, cy, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    return np.stack([cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0], axis=1)


def box_iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU between two ``(N, 4)`` / ``(M, 4)`` xyxy arrays, returned as ``(N, M)``."""
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)

    ax1, ay1, ax2, ay2 = a[:, 0][:, None], a[:, 1][:, None], a[:, 2][:, None], a[:, 3][:, None]
    bx1, by1, bx2, by2 = b[:, 0][None, :], b[:, 1][None, :], b[:, 2][None, :], b[:, 3][None, :]

    inter_w = np.clip(np.minimum(ax2, bx2) - np.maximum(ax1, bx1), 0, None)
    inter_h = np.clip(np.minimum(ay2, by2) - np.maximum(ay1, by1), 0, None)
    inter = inter_w * inter_h

    area_a = np.clip(ax2 - ax1, 0, None) * np.clip(ay2 - ay1, 0, None)
    area_b = np.clip(bx2 - bx1, 0, None) * np.clip(by2 - by1, 0, None)
    union = area_a + area_b - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0).astype(np.float32)


def nms(
    boxes: np.ndarray,
    scores: np.ndarray,
    iou_threshold: float = 0.45,
    class_ids: Optional[np.ndarray] = None,
    class_aware: bool = True,
    max_det: int = 300,
) -> np.ndarray:
    """
    Greedy NMS returning the kept indices.

    :param boxes: ``(N, 4)`` xyxy boxes.
    :param scores: ``(N,)`` confidences.
    :param iou_threshold: boxes overlapping more than this are suppressed.
    :param class_ids: ``(N,)`` class ids used to make suppression class-local.
    :param class_aware: when True, only same-class boxes suppress one another (recommended).
    :param max_det: hard cap on returned detections, keeping the highest scoring ones.
    """
    if boxes.size == 0:
        return np.zeros((0,), dtype=np.int64)

    boxes = np.asarray(boxes, dtype=np.float32)
    scores = np.asarray(scores, dtype=np.float32).reshape(-1)
    if class_ids is None or not class_aware:
        class_ids = np.zeros_like(scores, dtype=np.int64)
    else:
        class_ids = np.asarray(class_ids).reshape(-1)

    kept: List[int] = []
    for cid in np.unique(class_ids):
        cls_idx = np.where(class_ids == cid)[0]
        if cls_idx.size == 0:
            continue
        order = cls_idx[np.argsort(-scores[cls_idx], kind="stable")]
        cls_boxes = boxes[order]
        while order.size > 0:
            current = order[0]
            kept.append(int(current))
            if order.size == 1 or len(kept) >= max_det:
                break
            ious = box_iou_matrix(cls_boxes[:1], cls_boxes[1:])[0]
            order = order[1:][ious <= iou_threshold]
            cls_boxes = boxes[order]
        if len(kept) >= max_det:
            break

    if not kept:
        return np.zeros((0,), dtype=np.int64)
    return np.asarray(kept, dtype=np.int64)


def weighted_box_fusion(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    iou_threshold: float = 0.45,
    conf_type: str = "avg",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Weighted Box Fusion for *same class* duplicate clusters.

    YOLO at a low candidate threshold emits 5-15 near-duplicate boxes per object (verified on the
    bundled weights: 12 of the top-12 PPE candidates were the same hard hat). Plain NMS keeps the
    single highest-scoring one, discarding the localisation information held by the rest. WBF
    merges the cluster into one box whose coordinates are the score-weighted average of its
    members, which is both better localised and temporally far more stable - exactly what a
    temporal verification state machine wants.

    :returns: ``(fused_boxes, fused_scores, fused_class_ids, cluster_sizes)`` where
              ``cluster_sizes[k]`` is the number of raw candidates merged into output ``k`` (an
              agreement count that callers can surface as corroboration evidence).
    """
    if boxes.size == 0:
        return boxes, scores, class_ids, np.zeros((0,), dtype=np.int32)

    out_boxes: List[np.ndarray] = []
    out_scores: List[float] = []
    out_classes: List[int] = []
    out_counts: List[int] = []

    for cid in np.unique(class_ids):
        cls_idx = np.where(class_ids == cid)[0]
        order = cls_idx[np.argsort(-scores[cls_idx], kind="stable")]
        cls_boxes = boxes[order].astype(np.float32)
        cls_scores = scores[order].astype(np.float32)

        clusters: List[List[int]] = []
        cluster_boxes: List[np.ndarray] = []
        for i in range(len(cls_boxes)):
            matched = False
            for c_idx in range(len(clusters)):
                ious = box_iou_matrix(cls_boxes[i:i + 1], cluster_boxes[c_idx])[0]
                if float(ious.max()) > iou_threshold:
                    clusters[c_idx].append(i)
                    cluster_boxes[c_idx] = np.vstack([cluster_boxes[c_idx], cls_boxes[i:i + 1]])
                    matched = True
                    break
            if not matched:
                clusters.append([i])
                cluster_boxes.append(cls_boxes[i:i + 1])

        for member_idx, member_boxes in zip(clusters, cluster_boxes):
            member_scores = cls_scores[member_idx]
            weights = member_scores / max(float(member_scores.sum()), 1e-6)
            fused = (member_boxes * weights[:, None]).sum(axis=0)

            if conf_type == "max":
                fused_score = float(member_scores.max())
            elif conf_type == "sum":
                fused_score = float(np.clip(member_scores.sum(), 0.0, 1.0))
            else:
                # Boost by cluster agreement: a box corroborated by k neighbours gains confidence,
                # capped so a single-frame artefact can never present as certainty.
                agreement = len(member_idx)
                fused_score = float(min(0.99, float(member_scores.mean()) * (1.0 + 0.05 * (agreement - 1))))

            out_boxes.append(fused)
            out_scores.append(fused_score)
            out_classes.append(int(cid))
            out_counts.append(len(member_idx))

    if not out_boxes:
        return boxes, scores, class_ids, np.ones(len(boxes), dtype=np.int32)
    return (
        np.asarray(out_boxes, dtype=np.float32),
        np.asarray(out_scores, dtype=np.float32),
        np.asarray(out_classes, dtype=np.int64),
        np.asarray(out_counts, dtype=np.int32),
    )


def resolution_adaptive_threshold(
    base_threshold: float,
    box_areas_norm: np.ndarray,
    reference_area: float = 0.01,
    min_ratio: float = 0.45,
) -> np.ndarray:
    """
    Per-box confidence floor that compensates for the detector's small-object weakness.

    A single global threshold is always a compromise: tuned for large objects it misses goggles on
    a distant worker (3 px in frame), tuned for small objects it admits large false positives.
    Since confidence tracks object *size* far more strongly than correctness, the floor is scaled
    between ``min_ratio`` (tiny boxes) and 1.0 (boxes at or above ``reference_area``).

    :param box_areas_norm: normalised (0-1) box areas.
    :param reference_area: area fraction treated as "large enough" for the full threshold.
    :param min_ratio: lowest multiplier applied to the tiniest boxes.
    :returns: threshold array aligned with ``box_areas_norm``.
    """
    areas = np.asarray(box_areas_norm, dtype=np.float32)
    if areas.size == 0:
        return areas
    # sqrt curve: a 100x smaller object gets a modestly looser floor, not an unbounded one.
    rel_size = np.sqrt(np.clip(areas / max(reference_area, 1e-6), 0.0, 1.0))
    scale = min_ratio + (1.0 - min_ratio) * rel_size
    return (base_threshold * scale).astype(np.float32)


def apply_class_thresholds(
    scores: np.ndarray,
    class_ids: np.ndarray,
    class_thresholds: Optional[Dict[int, float]],
    default_threshold: float,
) -> np.ndarray:
    """
    Builds a boolean keep-mask from per-class thresholds.

    Applying this **before** NMS is what stops a barely-above-floor fragment of one class from
    removing a strong detection of another.
    """
    if scores.size == 0:
        return np.zeros((0,), dtype=bool)

    if not class_thresholds:
        return scores >= default_threshold

    thresholds = np.full(scores.shape, float(default_threshold), dtype=np.float32)
    for cid, thr in class_thresholds.items():
        thresholds[class_ids == cid] = float(thr)
    return scores >= thresholds


def merge_nearby_boxes(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    containment_threshold: float = 0.75,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Removes *contained* duplicates that plain IoU misses.

    Same-class only: a large smoke region and a small fire glowing inside it have a low IoU yet
    describe one physical event, and a person-sized box can fully swallow a vest box. The higher
    scoring entry of an overlapping pair is always the one kept.
    """
    if boxes.size <= 1:
        return boxes, scores, class_ids

    keep = np.ones(len(boxes), dtype=bool)
    for cid in np.unique(class_ids):
        idx = np.where(class_ids == cid)[0]
        idx = idx[np.argsort(-scores[idx], kind="stable")]
        for i_pos, i in enumerate(idx):
            if not keep[i]:
                continue
            for j in idx[i_pos + 1:]:
                if not keep[j]:
                    continue
                inter = box_iou_matrix(boxes[i:i + 1], boxes[j:j + 1])[0][0]
                inter_w = max(0.0, min(boxes[i][2], boxes[j][2]) - max(boxes[i][0], boxes[j][0]))
                inter_h = max(0.0, min(boxes[i][3], boxes[j][3]) - max(boxes[i][1], boxes[j][1]))
                inter_area = inter_w * inter_h
                area_i = max(1e-6, (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1]))
                area_j = max(1e-6, (boxes[j][2] - boxes[j][0]) * (boxes[j][3] - boxes[j][1]))
                # Either direction counts: whichever box sits inside the other is the redundant one,
                # and since ``i`` is always the higher scoring of the pair, ``j`` is what gets dropped.
                contained = (inter_area / area_j > containment_threshold) or (
                    inter_area / area_i > containment_threshold
                )
                if inter > 0.85 or contained:
                    keep[j] = False
    return boxes[keep], scores[keep], class_ids[keep]
