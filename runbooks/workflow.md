# Workflow: story to approved animatic

Follow these steps in order. Each step writes one document into the project folder and ends with a check. Do not start a step until the previous step's check passes. Commands run from the kubrick repo with `uv run kubrick ...`; `<project>` is the project folder's absolute path.

No video is rendered before Eric approves the animatic (step 8). Rendering, the pilot and the edit come after that gate, and their tooling is tracked in kubrick #6.

Shot sizes and camera movements use only the labels in `taxonomy.toml`. Continuity rule ids (`axis-180`, `eyeline-match`, `screen-direction`, `action-phase`, `wardrobe-state`) are defined in `src/kubrick/continuity.py`. The grammar run books in `runbooks/grammar/` cite them.

## 0. Set up

1. Make a project folder. Copy the source story into it as `story.md`. Never edit the story.
2. Read the whole story before writing anything.

## 1. Script: `script.fountain`

1. Write the story as a screenplay in Fountain format. Every scene starts with a scene heading on its own line after a blank line: `INT.` or `EXT.`, a place, ` - `, and a time of day. Example: `EXT. SERVICE YARD - NIGHT`.
2. A scene is continuous action in one place at one time. A change of place or time starts a new scene, even inside one paragraph of the story. "Time" means a particular occasion: "every night" and "the night it changed" are two scenes even in the same place, and their headings must differ (name the occasion or the part of the place). A place seen only in the distance belongs to the scene it is seen from.
3. Narration is a character cue followed by the lines, for example `NARRATOR (V.O.)`. Keep the story's own words for narration where the story has them.
4. Write action lines as what the camera can see, in present tense. Do not write thoughts, backstory or sounds the audience cannot hear.

Check: every scene in the story appears as a heading, in story order. Read the headings back with `grep -n -E '^(INT|EXT|EST|I/E|\.)' script.fountain`.

## 2. Breakdown: `breakdown.json`

For each scene, list:
- `id` (a short string, "1", "2"...) and `heading`, copied exactly from the script;
- `characters` who appear;
- `sets`;
- `props`: every object the story needs that stays put, each with its `place`. An object a character wears or carries on the body (a cap, keys, a torch) goes under that character in `wardrobe` instead, so its state can change from shot to shot. Things a character only uses where they lie (a ledger on a desk) stay props. When the story does not say where a carried object is, choose and write the choice in the scene's `model_tests` note or the shot description;
- `wardrobe`: each character's items and their state, for example `{"GUARD": {"cap": "forward"}}`;
- `wardrobe_changes`: only when a state changes on screen, as `{"shot", "char", "item", "state"}`.

Check: `uv run kubrick validate <project> --until breakdown` prints `ok`. It also checks every breakdown heading against the script.

## 3. Test what the model must hold

For every wardrobe or prop detail the story depends on (an unusual way of wearing something, a prop's exact state), test it before the shot list locks. Generate two stills of it with the local image model (`soh` MCP `image` tool) from different angles, and name the angles in the test's `note`. Record each test in the breakdown scene's `model_tests` as `{"detail", "result", "note"}`, where `result` is `held`, `failed` or `untested`; `note` is required for `held` and `failed` and optional for `untested`. If a detail fails, change the detail now, say why in its `note`, and tell Eric. Settle the spec here, not after paid takes: tsatd's guard cap was specified worn backwards and the model could not hold it across cuts, so the spec changed after three takes.

If no image model is available, record the detail with `result` `untested` and carry on.

## 4. Shot list: `shotlist.json`

For each scene, list its shots in order. Each shot has:
- `id` (scene id plus a letter: "1A", "1B");
- `scale` and `movement` from `taxonomy.toml`;
- `subjects`: the characters visible;
- `duration_s`: long enough for its narration at 2.5 words per second, plus half a second, or the time its action needs, whichever is longer;
- `description`: one frozen pose and one main action, describing only what is in frame;
- `wardrobe`: the state of each visible item, as the breakdown has it at this shot;
- `vo`: the narration heard over this shot, if any.

Follow `runbooks/grammar/scale.md`: open each scene wide enough to place the action (`scene-opens-wide`), and prefer cuts to the neighbouring size (`one-step-scale-cuts`). Note the rule id in the description of any shot that departs from a rule on purpose. Then `runbooks/grammar/cutting.md` and `camera.md`: let narration run across picture cuts and bridge scenes with J and L cuts (`picture-leads-sound`), skip time that carries nothing (`elide-time`), use a dissolve only for a change of time or place (`scene-transitions`), alternate simultaneous strands (`cross-cutting`), and cover groups by sub-group (`group-coverage`).

Check: `uv run kubrick validate <project> --until shotlist` prints `ok`.

## 5. Floor plan: `floorplan.json`

Draw each scene from above on a plane, in metres, with y pointing up the page.
- `characters`: each character's position `pos: [x, y]`.
- `shots`, keyed by shot id: `camera` with `pos`, `heading` (degrees counter-clockwise from +x, the way the lens points) and `lens_mm`. Add `moving` (each walking character's direction as `[dx, dy]`), `looks` and `gaze` (who looks at whom, and which screen side that is), and `action` (an action's phase at the shot's start and end, from 0 to 1) wherever they apply.

Keep the camera on one side of the line between two characters who face each other, unless you mean to cross it; then give that shot `crosses_line` with the reason (see `grammar/continuity.md`, axis-180). With a single character the axis check has nothing to compare; screen direction and wardrobe still apply.

Check: `uv run kubrick continuity <project>` prints nothing and exits 0. Each line it prints names a rule id and a shot; fix the floor plan or the shot list until it is clean.

## 6. Storyboard: `storyboard.json` and `panels/`

One panel per shot, in a `panels/` folder, listed in `storyboard.json` as `{"shot", "image", "source"}`:
1. If Eric has sketched the shot, photograph or scan the sketch and use it. Its `source` is `sketch`. Eric's sketches are authoritative.
2. Otherwise generate a still with the local image model. Its `source` is `generated`. Make several candidates and keep the one that matches the shot list and floor plan.
3. If no image model is available, make a text card with `uv run kubrick card <shot id> "<description>" panels/<shot id>.png`. Its `source` is `card`.

Check: lay the panels out in order and read them yourself. For an image, count the people, check each prop and wardrobe state against the breakdown, and check the framing against the shot's scale. For a text card, check its text against the shot list. Then run `uv run kubrick validate <project>`, which must print `ok`.

## 7. Animatic

Run `uv run kubrick animatic <project> <project>/animatic`. It writes `animatic.otio` (the timeline) and `animatic.mp4` (the render).

Check: the command fails unless the mp4 has exactly as many frames as the timeline. Then confirm each panel appears for its own shot, in shot-list order: a person watches it; an agent extracts the first and last frame of each shot's span with ffmpeg and compares them with that shot's panel.

## 8. Gate: Eric approves the animatic

Send Eric the mp4. Eric watches it and gives notes in plain words; Eric does not use editing software, so never ask Eric to open the timeline.

Apply each note to the documents it concerns (script, shot list, floor plan, panels), rerun the checks from that step onwards, rebuild the animatic, and send it again. Repeat until Eric approves it in words.

Nothing is rendered as video before this approval.
