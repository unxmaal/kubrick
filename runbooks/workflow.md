# Workflow: story to approved animatic

Follow these steps in order. Each step writes one document into the project folder and ends with a check. Do not start a step until the previous step's check passes. Commands run from the kubrick repo with `uv run kubrick ...`.

No video is rendered before Eric approves the animatic (step 8). Rendering, the pilot and the edit come after that gate, and their tooling is tracked in kubrick #6.

Shot sizes and camera movements use only the labels in `taxonomy.toml`. Continuity rule ids (`axis-180`, `eyeline-match`, `screen-direction`, `action-phase`, `wardrobe-state`) are defined in `src/kubrick/continuity.py`. The grammar run books in `runbooks/grammar/` (kubrick #3) cite them; until that folder exists, skip the steps that refer to it.

## 0. Set up

1. Make a project folder. Copy the source story into it as `story.md`. Never edit the story.
2. Read the whole story before writing anything.

## 1. Script: `script.fountain`

1. Write the story as a screenplay in Fountain format. Every scene starts with a scene heading on its own line after a blank line: `INT.` or `EXT.`, a place, ` - `, and a time of day. Example: `EXT. SERVICE YARD - NIGHT`.
2. A scene is continuous action in one place at one time. A change of place or time starts a new scene, even inside one paragraph of the story. A place seen only in the distance belongs to the scene it is seen from.
3. Narration is a character cue followed by the lines, for example `NARRATOR (V.O.)`. Keep the story's own words for narration where the story has them.
4. Write action lines as what the camera can see, in present tense. Do not write thoughts, backstory or sounds the audience cannot hear.

Check: every scene in the story appears as a heading, in story order. Read the headings back with `grep -n -E '^(INT|EXT|EST|I/E|\.)' script.fountain`.

## 2. Breakdown: `breakdown.json`

For each scene, list:
- `id` (a short string, "1", "2"...) and `heading`, copied exactly from the script;
- `characters` who appear;
- `sets`;
- `props`: every object the story needs that stays put, each with its `place`. An object a character carries or handles (keys, a torch) goes under that character in `wardrobe` instead, so its state can change from shot to shot;
- `wardrobe`: each character's items and their state, for example `{"GUARD": {"cap": "forward"}}`;
- `wardrobe_changes`: only when a state changes on screen, as `{"shot", "char", "item", "state"}`.

Check: `uv run kubrick validate <project> --until breakdown` prints `ok`. It also checks every breakdown heading against the script.

## 3. Test what the model must hold

For every wardrobe or prop detail the story depends on (an unusual way of wearing something, a prop's exact state), test it before the shot list locks. Generate two stills of it with the local image model (`soh` MCP `image` tool) from different angles. Record each test in the breakdown scene's `model_tests` as `{"detail", "result", "note"}`, where `result` is `held`, `failed` or `untested`. If a detail fails, change the detail now, say why in its `note`, and tell Eric. Settle the spec here, not after paid takes: tsatd's guard cap was specified worn backwards and the model could not hold it across cuts, so the spec changed after three takes.

If no image model is available, record the detail with `result` `untested` and carry on.

## 4. Shot list: `shotlist.json`

For each scene, list its shots in order. Each shot has:
- `id` (scene id plus a letter: "1A", "1B");
- `scale` and `movement` from `taxonomy.toml`;
- `subjects`: the characters visible;
- `duration_s`: long enough for its narration, if any, at a calm reading pace;
- `description`: one frozen pose and one main action, describing only what is in frame;
- `wardrobe`: the state of each visible item, as the breakdown has it at this shot;
- `vo`: the narration heard over this shot, if any.

Cover each scene so the audience always knows where they are: open wide enough to place the action, then move in. When the grammar run books in `runbooks/grammar/` exist, follow their coverage and scale rules and note the rule id beside any shot that departs from them.

Check: `uv run kubrick validate <project> --until shotlist` prints `ok`.

## 5. Floor plan: `floorplan.json`

Draw each scene from above on a plane, in metres, with y pointing up the page.
- `characters`: each character's position `pos: [x, y]`.
- `shots`, keyed by shot id: `camera` with `pos`, `heading` (degrees counter-clockwise from +x, the way the lens points) and `lens_mm`. Add `moving` (each walking character's direction as `[dx, dy]`), `looks` and `gaze` (who looks at whom, and which screen side that is), and `action` (an action's phase at the shot's start and end, from 0 to 1) wherever they apply.

Keep the camera on one side of the line between two characters who face each other, unless you mean to cross it.

Check: `uv run kubrick continuity <project>` prints nothing and exits 0. Each line it prints names a rule id and a shot; fix the floor plan or the shot list until it is clean.

## 6. Storyboard: `storyboard.json` and `panels/`

One panel per shot, in a `panels/` folder, listed in `storyboard.json` as `{"shot", "image", "source"}`:
1. If Eric has sketched the shot, photograph or scan the sketch and use it. Its `source` is `sketch`. Eric's sketches are authoritative.
2. Otherwise generate a still with the local image model. Its `source` is `generated`. Make several candidates and keep the one that matches the shot list and floor plan.
3. If no image model is available, make a text card with `uv run kubrick card <shot id> "<description>" panels/<shot id>.png`. Its `source` is `generated`.

Check: lay the panels out in order and read them yourself. For an image, count the people, check each prop and wardrobe state against the breakdown, and check the framing against the shot's scale. For a text card, check its text against the shot list. Then run `uv run kubrick validate <project>`, which must print `ok`.

## 7. Animatic

Run `uv run kubrick animatic <project> <project>/animatic`. It writes `animatic.otio` (the timeline) and `animatic.mp4` (the render).

Check: the command fails unless the mp4 has exactly as many frames as the timeline. Then watch it yourself and confirm each panel appears for its own shot, in shot-list order.

## 8. Gate: Eric approves the animatic

Send Eric the mp4. Eric watches it and gives notes in plain words; Eric does not use editing software, so never ask Eric to open the timeline.

Apply each note to the documents it concerns (script, shot list, floor plan, panels), rerun the checks from that step onwards, rebuild the animatic, and send it again. Repeat until Eric approves it in words.

Nothing is rendered as video before this approval.
