# Camera: coverage and movement

Rules for where cameras go in a scene and when they move. Movement labels are those in `taxonomy.toml`. A source marked `secondary` reports a book we have not read; the rule names the book it reports. The books are not read at all: a rule is settled by two independent retrievable sources or by our own data, and an LLM summary is never a source.

## triangle-coverage
- kind: practice
- decision: Cover a dialogue scene from one side of the line between the speakers, with an establishing shot first, then external (over the shoulder) and internal (single) positions on that side, and a close shot for each actor, since anyone may become the subject. Re-establish when the situation changes.
- applies when: Two or more characters talk in one place.
- check: The floor plan's cameras for the scene sit on one side of each speaking pair's line, and the shot list holds an establishing shot and a close shot per speaker.
- counterexample: A single long take that moves among the speakers.
- sources:
  - secondary: He, Cohen and Salesin 1996, The Virtual Cinematographer, SIGGRAPH, on Arijon, Grammar of the Film Language, fig. 4.11: the external, internal and apex positions on one side of the line.
  - secondary: Li and Xiao 2005, An Interactive Camera Planning System for Automatic Cinematographer, MMM, on Arijon: one close shot per actor, because any actor may become the subject.
  - Smith 2012, Projections 6(1), author PDF p. 6: a master-to-closer progression and the 30 degree change between shots of one subject.

## group-coverage
- kind: practice
- decision: With three people, alternate the shot pair that fits who is addressing whom, and bring back the group shot now and then. With four or more, split the group into pairs or threes and cover each sub-group; open and close on a master and return to it when the talk runs long. Draw the line of action through the middle of each sub-group.
- applies when: Three or more characters talk in one place.
- check: The shot list for such a scene opens on a group shot, covers sub-groups rather than every person at once, and returns to the group at least once per exchange.
- counterexample: A scene centred on one silent character, held on them.
- sources:
  - secondary: He, Cohen and Salesin 1996, The Virtual Cinematographer, SIGGRAPH, section 2.3 and fig. 3, on Arijon, Grammar of the Film Language, fig. 6.29: the three-actor alternation and the returning group shot.
  - Li and Xiao 2005, An Interactive Camera Planning System for Automatic Cinematographer, sections 3.1-3.2: over-four talk split into sub-groups of two or three, with a master that opens, closes and re-establishes.
  - secondary: Evin, Hamalainen and Guckelsberger 2022, Cine-AI, arXiv 2208.05701, section 2.1, on Arijon: the line of action for several characters runs through the midpoints of their positions.

## motivated-movement
- kind: practice
- decision: Move the camera only when the scene motivates it: to follow a moving subject, or to reveal something. A move with no motive makes the camera itself noticeable; use one only on purpose.
- applies when: Choosing a shot's `movement` other than `static`.
- check: Every moving shot's description names what the move follows or reveals.
- counterexample: A deliberately unmotivated drift to unsettle the viewer.
- sources:
  - Lightman 1946, American Cinematographer, March, p. 82: movement for its own sake misuses the technique.
  - Nashville State Community College, Moving the Camera, LibreTexts course text: motivated moves follow action or reveal information.

## actor-leads-move
- kind: provisional
- decision: The actor starts moving and the camera follows; the camera settles just before the actor stops.
- applies when: A camera move follows a moving subject.
- check: In the shot description, the move begins after the subject's movement and ends before it.
- counterexample: A camera that anticipates the action to build tension.
- confirm: A second retrievable source, independent of He et al., on the camera following an actor's move.
- sources:
  - secondary: He, Cohen and Salesin 1996, The Virtual Cinematographer, on Arijon and others: the heuristics it encodes for following a subject.

## push-as-eye
- kind: practice
- decision: A push in or pull back can stand in for cutting to a closer or wider shot, as the audience's own attention moving. A cut does the same faster; choose the move when the change should be felt gradually.
- applies when: A shot list would otherwise cut straight in or out on the same subject.
- check: Such a move is marked `push` or `pull` with what it moves toward.
- counterexample: A cut is cleaner when the change of size should feel sudden.
- sources:
  - Lightman 1946, American Cinematographer, March, p. 82.
  - A Practical Manual of Screen Playwriting 1952 (World Publishing), p. 115, via the Media History Digital Library: a cut to a close-up shows what a dolly-in shows, and faster.


## staging-in-depth
- kind: provisional
- decision: Shift the viewer's attention within one shot by staging: hold a main and a secondary centre of interest in foreground and background, and let a figure walk forward, or step aside to reveal another, to take over the scene without a cut.
- applies when: A scene where a cut would break a mood or a relationship the frame should hold.
- check: A shot that replaces cuts names its zones and who moves between them in its description.
- counterexample: Fast exchanges where each line needs its own emphasis.
- confirm: A source independent of Bordwell, such as Barr 1963, CinemaScope: Before and After, Film Quarterly, which Bordwell follows.
- sources:
  - Bordwell 2008, Gradation of emphasis, starring Glenn Ford, davidbordwell.net: depth staging holds primary and secondary centres of interest; a figure coming forward takes over the scene.
  - Bordwell 2010, Nordisk and the Tableau Aesthetic, davidbordwell.net, section 2D and 3D: emphasis moves between zones by bringing a player forward or by blocking and revealing.

## camera-height-progression
- kind: practice
- decision: Plan the camera's height across a film as a progression that serves what the film is about. For a story that closes in on its characters, start above eye level, come down to it, and end below it, so the ceiling enters the frame; longer lenses as it goes tighten the space further.
- applies when: Setting heights and lenses in the floor plan for a whole film, not shot by shot.
- check: The floor plan's camera heights (or the shot descriptions) follow a stated plan for the film.
- counterexample: A film whose point is a constant, detached view.
- sources:
  - secondary: Mikulec, 12 Angry Men at 69, Cinephilia & Beyond, on Lumet, Making Movies, section on 12 Angry Men: the lens plot toward longer lenses and the camera dropping from above to below eye level.
  - secondary: Snider 2017, 10 Deliberate Facts About 12 Angry Men, Mental Floss, on Lumet, Making Movies: the three camera heights and the ceiling coming into view. It does not cover lenses, so the lens half rests on the first source.
