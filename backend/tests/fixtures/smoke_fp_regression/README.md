# Smoke False-Positive Regression Fixtures

## REQUIRED: Real doormat frame

Place the actual doormat frame that triggered the original false-positive here:

```
doormat_fp.jpg     ← the exact frame the ONNX model scored as "SMOKE (41%)"
```

This is the **primary** regression proof. The synthetic tests in
`test_smoke_fp_regression.py` are supplementary edge coverage, but they may
not reproduce the real weave's spatial-frequency statistics closely enough to
be the definitive validation. The real frame pinned here is.

### How to add it

1. Extract the frame from your RTSP recording or evidence clip at the timestamp
   where the alert fired.
2. Save it as `doormat_fp.jpg` (JPEG or PNG, any resolution — the test loads
   it with `cv2.imread`).
3. Re-run: `python -m pytest tests/test_smoke_fp_regression.py -v`

The test `test_real_doormat_frame_vetoed` will auto-skip with a clear message
if the file is absent, so CI will not fail while the frame is pending.

## Optional supplementary negatives

| Filename | Description |
|---|---|
| `carpet_fp.jpg` | Woven carpet (diagonal weave) |
| `gray_tile_fp.jpg` | Gray floor tiles with grout lines |
| `shadow_fp.jpg` | Cast shadow on a light-coloured floor |
| `concrete_wall_fp.jpg` | Concrete/cement wall texture |

## Optional positives (must still detect)

| Filename | Description |
|---|---|
| `thin_smoke_tp.jpg` | Early-stage thin smoke wisp |
| `dense_smoke_tp.jpg` | Dense smoke filling ~30% of frame |
| `backlit_smoke_tp.jpg` | Backlit smoke (slightly brighter than BG) |
