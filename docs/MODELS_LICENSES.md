# Models and licences

Everything below runs locally. The service makes no network calls at inference time.

## Shipped in the service (runtime)

| Component | Model / library | Licence | Notes |
|---|---|---|---|
| Object detector | RT-DETRv2-R18 (`PekingU/rtdetr_v2_r18vd`), fine-tuned on our CVAT labels (v2) → `models/detector/detector.onnx` | Apache-2.0 | 12 classes; ONNX Runtime on CPU; int8 quantisation tested and rejected (slower, outputs changed) |
| Crop encoder | DINOv2-small (`facebook/dinov2-small`) | Apache-2.0 | Frozen; ~21 ms per crop on 2 CPU threads |
| Heads | Logistic regression (scikit-learn) on DINOv2 features → `models/heads.joblib` | BSD-3 | Object states, person role, person action |
| Person tracking | ByteTrack (`trackers` 2.6, Roboflow) + `supervision` | Apache-2.0 / MIT | |
| Cash tracking, timeline, rules | own code (`ml/`) | — | |
| Runtime | ONNX Runtime, PyTorch (CPU), OpenCV, transformers | MIT / BSD / Apache-2.0 | |

## Used offline only (pre-labelling, experiments; not shipped)

| Model | Licence | Use |
|---|---|---|
| Grounding DINO base/tiny (IDEA-Research) | Apache-2.0 | Pre-labels for large objects |
| OWLv2 base (Google) | Apache-2.0 | Example-based cash pre-labels (patch embeddings + head trained on X01) |
| Florence-2 base/large (Microsoft) | MIT | Compared, rejected: no confidence scores, invents boxes |
| SigLIP2-base (Google) | Apache-2.0 | Compared with DINOv2 for the crop encoder; slower, not better |
| SAHI | MIT | Sliced-inference test for small objects; no gain |
| DINOv2-base (Meta) | Apache-2.0 | Object states: +0.01–0.07 AUC (mostly across camera angles) but ~4× slower; not shipped, upgrade option |
| RTMPose-s via rtmlib (OpenMMLab / Tau-J) | Apache-2.0 | Wrist features for actions: no gain (0.33 vs 0.34); not shipped |
| Detector v1 (5 reviewed videos) | Apache-2.0 base | Replaced by v2 (all 40 tasks, both camera angles): door mAP on the other angle 0.32 → 0.61, laptop 0.05 → 0.88 |
| CVAT 2.79 | MIT | Annotation tool (local Docker) |

## Rejected because of the licence
- Ultralytics YOLO (v5/v8/11), YOLO-World and YOLOE: AGPL-3.0.
- Qwen2.5-VL-3B: Qwen Research licence (non-commercial).
- DINOv3: custom licence, gated.
- SAM 3: custom SAM Licence, gated. Would be usable offline only; not used.
