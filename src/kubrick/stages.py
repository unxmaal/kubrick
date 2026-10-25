"""The documents each pre-production stage hands to the next, their schemas, and the joins between them."""

import json
import re
from pathlib import Path

import jsonschema

from kubrick import continuity, taxonomy

DOCS = ("script.fountain", "breakdown.json", "shotlist.json", "floorplan.json", "storyboard.json")
POINT = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}
STATE = {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": {"type": "string"}}}


def schemas() -> dict[str, dict]:
    shot = {"type": "object", "required": ["id", "scale", "movement", "subjects", "duration_s", "description"],
            "properties": {"id": {"type": "string"}, "scale": {"enum": taxonomy.labels("scale")},
                           "movement": {"enum": taxonomy.labels("movement")},
                           "subjects": {"type": "array", "items": {"type": "string"}},
                           "duration_s": {"type": "number", "exclusiveMinimum": 0},
                           "description": {"type": "string", "minLength": 1}, "wardrobe": STATE,
                           "vo": {"type": "string"}}}
    camera = {"type": "object", "required": ["pos", "heading", "lens_mm"],
              "properties": {"pos": POINT, "heading": {"type": "number"}, "lens_mm": {"type": "number"}}}
    return {
        "breakdown.json": {"type": "object", "required": ["scenes"], "properties": {"scenes": {
            "type": "array", "minItems": 1, "items": {
                "type": "object", "required": ["id", "heading", "characters", "sets", "props", "wardrobe"],
                "properties": {"id": {"type": "string"}, "heading": {"type": "string"},
                               "characters": {"type": "array", "items": {"type": "string"}},
                               "sets": {"type": "array", "items": {"type": "string"}},
                               "props": {"type": "object", "additionalProperties": {
                                   "type": "object", "required": ["place"]}},
                               "wardrobe": STATE,
                               "wardrobe_changes": {"type": "array", "items": {
                                   "type": "object", "required": ["shot", "char", "item", "state"]}}}}}}},
        "shotlist.json": {"type": "object", "required": ["scenes"], "properties": {"scenes": {
            "type": "array", "minItems": 1, "items": {
                "type": "object", "required": ["id", "shots"],
                "properties": {"id": {"type": "string"}, "shots": {"type": "array", "minItems": 1, "items": shot}}}}}},
        "floorplan.json": {"type": "object", "required": ["scenes"], "properties": {"scenes": {
            "type": "array", "minItems": 1, "items": {
                "type": "object", "required": ["id", "characters", "shots"],
                "properties": {"id": {"type": "string"},
                               "characters": {"type": "object", "additionalProperties": {
                                   "type": "object", "required": ["pos"], "properties": {"pos": POINT}}},
                               "shots": {"type": "object", "additionalProperties": {
                                   "type": "object", "required": ["camera"], "properties": {"camera": camera}}}}}}}},
        "storyboard.json": {"type": "object", "required": ["panels"], "properties": {"panels": {
            "type": "array", "minItems": 1, "items": {
                "type": "object", "required": ["shot", "image", "source"],
                "properties": {"shot": {"type": "string"}, "image": {"type": "string"},
                               "source": {"enum": ["generated", "sketch"]}}}}}},
    }


HEADING = re.compile(r"^(?:(?:INT|EXT|EST|INT\./EXT|INT/EXT|I/E)[. ].+|\.(?!\.)\S.*)$", re.IGNORECASE)


def scene_headings(fountain: str) -> list[str]:
    """Scene headings per the Fountain spec: a line starting INT, EXT, EST, INT./EXT, INT/EXT or I/E, or a
    forced heading starting with one '.', preceded by a blank line."""
    out, prev_blank = [], True
    for line in fountain.splitlines():
        s = line.strip()
        if prev_blank and s and HEADING.match(s):
            out.append(s[1:].strip() if s.startswith(".") else s)
        prev_blank = not s
    return out


def load_project(root: Path) -> dict:
    root = Path(root)
    p = {"root": root}
    for name in DOCS:
        path = root / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            p[name] = text if name.endswith(".fountain") else json.loads(text)
    return p


def validate_project(root: Path) -> list[str]:
    """Every problem in the stage documents: schema, then the joins between documents."""
    p, errors = load_project(root), []
    for name in DOCS:
        if name not in p:
            errors.append(f"{name}: missing")
    sound = {n for n in DOCS if n in p}  # documents whose schema holds; each join runs only on sound inputs
    for name, schema in schemas().items():
        if name in p:
            for e in jsonschema.Draft202012Validator(schema).iter_errors(p[name]):
                errors.append(f"{name}: {'/'.join(map(str, e.absolute_path)) or '(top)'}: {e.message}")
                sound.discard(name)
    if "storyboard.json" in p:
        for panel in p["storyboard.json"].get("panels", []) if isinstance(p["storyboard.json"], dict) else []:
            if isinstance(panel, dict) and isinstance(panel.get("image"), str) \
                    and not (p["root"] / panel["image"]).is_file():
                errors.append(f"storyboard.json: {panel['image']} does not exist")
    if not set(DOCS) <= sound:
        return errors
    headings = set(scene_headings(p["script.fountain"]))
    breakdown = {s["id"]: s for s in p["breakdown.json"]["scenes"]}
    plans = {s["id"]: s for s in p["floorplan.json"]["scenes"]}
    for s in breakdown.values():
        if s["heading"] not in headings:
            errors.append(f"breakdown.json: scene {s['id']} heading {s['heading']} is not in the script")
    shot_ids = set()
    for scene in p["shotlist.json"]["scenes"]:
        if scene["id"] not in breakdown:
            errors.append(f"shotlist.json: scene {scene['id']} is not in the breakdown")
        plan = plans.get(scene["id"])
        if plan is None:
            errors.append(f"floorplan.json: no scene {scene['id']}")
            continue
        for shot in scene["shots"]:
            shot_ids.add(shot["id"])
            if shot["id"] not in plan["shots"]:
                errors.append(f"floorplan.json: scene {scene['id']} has no shot {shot['id']}")
            for who in shot["subjects"]:
                if who not in plan["characters"]:
                    errors.append(f"floorplan.json: scene {scene['id']} does not place {who} (shot {shot['id']})")
    for panel in p["storyboard.json"]["panels"]:
        if panel["shot"] not in shot_ids:
            errors.append(f"storyboard.json: panel for unknown shot {panel['shot']}")
    return errors


def assemble(p: dict, scene_id: str) -> dict:
    """The continuity checker's view of one scene, joined from breakdown, shot list and floor plan."""
    breakdown = next(s for s in p["breakdown.json"]["scenes"] if s["id"] == scene_id)
    plan = next(s for s in p["floorplan.json"]["scenes"] if s["id"] == scene_id)
    shotlist = next(s for s in p["shotlist.json"]["scenes"] if s["id"] == scene_id)
    shots = []
    for shot in shotlist["shots"]:
        geo = plan["shots"][shot["id"]]
        shots.append({"id": shot["id"], "subjects": shot["subjects"], "wardrobe": shot.get("wardrobe", {}),
                      **{k: geo[k] for k in ("camera", "moving", "looks", "gaze", "action") if k in geo}})
    return {"id": scene_id, "characters": plan["characters"], "wardrobe": breakdown["wardrobe"],
            "wardrobe_changes": breakdown.get("wardrobe_changes", []), "shots": shots}


def prompt_fields(p: dict, scene_id: str, shot_id: str) -> dict:
    """What a shot's image and video prompts must carry from the documents, computed, never retyped."""
    scene = assemble(p, scene_id)
    shot = next(s for s in scene["shots"] if s["id"] == shot_id)
    state = {who: dict(items) for who, items in scene["wardrobe"].items()}
    for ch in scene["wardrobe_changes"]:
        if [s["id"] for s in scene["shots"]].index(ch["shot"]) <= [s["id"] for s in scene["shots"]].index(shot_id):
            state.setdefault(ch["char"], {})[ch["item"]] = ch["state"]
    return {"screen_direction": {who: continuity.screen_direction(shot["camera"], v)
                                 for who, v in shot.get("moving", {}).items() if who in shot["subjects"]},
            "wardrobe": {who: state.get(who, {}) for who in shot["subjects"]}}
