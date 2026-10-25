"""Where the frame cuts the body: Apple Vision body pose and face boxes as shot-scale features."""

import cv2
import numpy as np

# joint groups top to bottom; a group is visible if any joint in it is confidently found
GROUPS = {
    "head": ("Nose", "LeftEye", "RightEye", "LeftEar", "RightEar"),
    "neck": ("Neck",),
    "shoulders": ("LeftShoulder", "RightShoulder"),
    "elbows": ("LeftElbow", "RightElbow"),
    "wrists": ("LeftWrist", "RightWrist"),
    "hips": ("LeftHip", "RightHip", "Root"),
    "knees": ("LeftKnee", "RightKnee"),
    "ankles": ("LeftAnkle", "RightAnkle"),
}
MIN_CONFIDENCE = 0.3
N_FEATURES = 5 + len(GROUPS) + 4


def _handler(data):
    import Vision

    return Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)


def features(frame: np.ndarray) -> np.ndarray:
    """Fixed-length vector: people, faces, largest face height and centre, largest person's visible
    joint groups, and that person's joint extent (top, bottom, height, width) as frame fractions."""
    import Foundation
    import Vision

    ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("could not encode frame for Vision")
    handler = _handler(Foundation.NSData.dataWithBytes_length_(jpg.tobytes(), len(jpg)))
    body, face = Vision.VNDetectHumanBodyPoseRequest.alloc().init(), Vision.VNDetectFaceRectanglesRequest.alloc().init()
    # a failed request must not read as "no people in frame"
    done, err = handler.performRequests_error_([body, face], None)
    if not done:
        raise RuntimeError(f"Vision request failed: {err}")
    out = np.zeros(N_FEATURES, np.float32)
    faces = face.results() or []
    people = body.results() or []
    out[0], out[1] = len(people), len(faces)
    if faces:
        f = max(faces, key=lambda r: r.boundingBox().size.height)
        bb = f.boundingBox()
        out[2] = bb.size.height
        out[3] = bb.origin.y + bb.size.height / 2
        out[4] = bb.size.width
    best, best_h = None, -1.0
    for p in people:
        pts = {}
        for group, names in GROUPS.items():
            for n in names:
                key = getattr(Vision, f"VNHumanBodyPoseObservationJointName{n}")
                pt, err = p.recognizedPointForJointName_error_(key, None)
                if pt is not None and pt.confidence() >= MIN_CONFIDENCE:
                    pts.setdefault(group, []).append((pt.location().x, pt.location().y))
        ys = [y for v in pts.values() for _, y in v]
        h = (max(ys) - min(ys)) if ys else 0.0
        if pts and h > best_h:
            best, best_h = pts, h
    if best:
        for i, group in enumerate(GROUPS):
            out[5 + i] = 1.0 if group in best else 0.0
        xs = [x for v in best.values() for x, _ in v]
        ys = [y for v in best.values() for _, y in v]
        j = 5 + len(GROUPS)
        out[j:j + 4] = (max(ys), min(ys), max(ys) - min(ys), max(xs) - min(xs))  # Vision y is bottom-up
    return out
