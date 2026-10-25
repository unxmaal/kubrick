"""Continuity computed from a scene's floor plan and shot list. Rule ids are the list #3's run books cite.

Floor plan: a top-down plane, y up. A camera has a position and a heading (degrees counter-clockwise
from +x); screen right is the heading turned 90 degrees clockwise."""

import math

from kubrick.cuts import Knob

RULES = {
    "axis-180": "Consecutive shots covering the same pair keep the camera on one side of the line between them.",
    "eyeline-match": "A gaze declared in the shot list points to the screen side the floor plan puts its target on.",
    "screen-direction": "A moving subject keeps its screen direction across cuts unless a neutral shot intervenes.",
    "action-phase": "An action continued across a cut does not run backwards.",
    "wardrobe-state": "Every declared wardrobe or prop state matches the breakdown's state for that shot.",
}
NEUTRAL = Knob(0.3, (0.2, 0.3, 0.4))  # |cos| between movement and screen-right below this is head-on or away
ACTION_OVERLAP = Knob(0.1, (0.0, 0.1, 0.2))  # phase an editor may repeat across a cut for a smooth match


def _right(cam: dict) -> tuple[float, float]:
    h = math.radians(cam["heading"])
    return math.sin(h), -math.cos(h)


def _screen_x(cam: dict, v) -> float:
    rx, ry = _right(cam)
    return v[0] * rx + v[1] * ry


def _side(scene: dict, pair: tuple[str, str], cam: dict) -> int:
    (px, py), (qx, qy) = (scene["characters"][n]["pos"] for n in pair)
    cx, cy = cam["pos"]
    cross = (qx - px) * (cy - py) - (qy - py) * (cx - px)
    return (cross > 0) - (cross < 0)


def _axis(scene: dict) -> list[dict]:
    out, shots = [], scene["shots"]
    for prev, cur in zip(shots, shots[1:]):
        for pair in _pairs(prev) & _pairs(cur):
            if _side(scene, pair, prev["camera"]) * _side(scene, pair, cur["camera"]) < 0:
                out.append({"rule": "axis-180", "shot": cur["id"], "previous": prev["id"],
                            "detail": f"camera crosses the {pair[0]}-{pair[1]} line"})
    return out


def _pairs(shot: dict) -> set[tuple[str, str]]:
    s = sorted(shot.get("subjects", []))
    return {(a, b) for i, a in enumerate(s) for b in s[i + 1:]}


def _eyeline(scene: dict) -> list[dict]:
    out = []
    for shot in scene["shots"]:
        for who, side in shot.get("gaze", {}).items():
            target = shot.get("looks", {}).get(who)
            if target is None:
                continue
            (ax, ay), (bx, by) = scene["characters"][who]["pos"], scene["characters"][target]["pos"]
            computed = "right" if _screen_x(shot["camera"], (bx - ax, by - ay)) > 0 else "left"
            if computed != side:
                out.append({"rule": "eyeline-match", "shot": shot["id"],
                            "detail": f"{who} declared looking {side} at {target}; the floor plan puts {target} {computed}"})
    return out


def screen_direction(cam: dict, v) -> str:
    """Where movement `v` reads on screen from `cam`: left, right, or neutral (head-on or tail-away).
    The checker and the prompt hand-off both use this, so they cannot disagree."""
    norm = math.hypot(*v) or 1.0
    x = _screen_x(cam, v) / norm
    if abs(x) < NEUTRAL.default:
        return "neutral"
    return "right" if x > 0 else "left"


def _direction(scene: dict) -> list[dict]:
    out, last = [], {}  # subject -> (shot id, direction) of its latest non-neutral appearance
    for shot in scene["shots"]:
        for who, v in shot.get("moving", {}).items():
            if who not in shot.get("subjects", []):
                continue
            d = screen_direction(shot["camera"], v)
            if d == "neutral":
                last.pop(who, None)  # a head-on or tail-away shot resets the direction
                continue
            if who in last and last[who][1] != d:
                out.append({"rule": "screen-direction", "shot": shot["id"], "previous": last[who][0],
                            "detail": f"{who} moves {last[who][1]} then {d}"})
            last[who] = (shot["id"], d)
    return out


def _action(scene: dict) -> list[dict]:
    out, shots = [], scene["shots"]
    for prev, cur in zip(shots, shots[1:]):
        for name, (start, _) in cur.get("action", {}).items():
            if name in prev.get("action", {}) and start < prev["action"][name][1] - ACTION_OVERLAP.default:
                out.append({"rule": "action-phase", "shot": cur["id"], "previous": prev["id"],
                            "detail": f"{name} restarts at {start} after reaching {prev['action'][name][1]}"})
    return out


def _wardrobe(scene: dict) -> list[dict]:
    out = []
    state = {who: dict(items) for who, items in scene.get("wardrobe", {}).items()}
    changes = {}
    for ch in scene.get("wardrobe_changes", []):
        changes.setdefault(ch["shot"], []).append(ch)
    for shot in scene["shots"]:
        for ch in changes.get(shot["id"], []):
            state.setdefault(ch["char"], {})[ch["item"]] = ch["state"]
        for who, items in shot.get("wardrobe", {}).items():
            for item, value in items.items():
                want = state.get(who, {}).get(item)
                if want != value:
                    out.append({"rule": "wardrobe-state", "shot": shot["id"],
                                "detail": f"{who}'s {item} is {value}; the breakdown says {want}"})
    return out


def check(scene: dict) -> list[dict]:
    """Every violation in the scene, each naming its rule id and shot."""
    return _axis(scene) + _eyeline(scene) + _direction(scene) + _action(scene) + _wardrobe(scene)
