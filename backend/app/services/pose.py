"""Phase 2 (not yet implemented): pose estimation on serve/attack clips.

This only ever runs on short clips that the rally tagger has already cut out
(a few seconds each) — never on a full match — which is what keeps the CV
problem tractable.

Plan:
1. Load a clip with OpenCV, read it frame by frame.
2. Run MediaPipe Pose on each frame to get 33 body landmarks.
3. Smooth the landmark sequence (e.g. a rolling average or a simple Kalman
   filter) to cut down on jitter and dropped-frame noise before computing
   anything from it.
4. Derive metrics from the smoothed sequence, e.g.:
   - jump_height_cm: peak vertical displacement of the hip landmarks
   - arm_angle_deg: shoulder-elbow-wrist angle at the estimated contact frame
5. Persist each metric as a Metric row linked back to the rally, so the
   frontend can chart them over time per outcome type (serve vs attack).

Install when starting this phase: `pip install mediapipe opencv-python`
"""

from typing import Dict


def analyze_clip(clip_path: str) -> Dict[str, float]:
    raise NotImplementedError("Pose estimation lands in phase 2 — see the plan above.")
