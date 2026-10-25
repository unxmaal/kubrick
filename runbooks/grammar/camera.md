# Camera: coverage and movement

Rules for where cameras go in a scene and when they move. Movement labels are those in `taxonomy.toml`. A source marked `secondary` reports a book we have not read.

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

## three-person-coverage
- kind: provisional
- decision: With three people, alternate the over-the-shoulder group shot with the listener's reaction; when two of them talk to each other, alternate their singles; re-establish the group now and then.
- applies when: Three characters talk in one place.
- check: The shot list for such a scene follows that alternation, with a group shot at least once per exchange.
- counterexample: A scene centred on one silent character, held on them.
- confirm: Arijon, Grammar of the Film Language, fig. 6.29, once the book arrives.
- sources:
  - secondary: He, Cohen and Salesin 1996, The Virtual Cinematographer, on Arijon, fig. 6.29.

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
- confirm: Arijon, Grammar of the Film Language, on following movement, once the book arrives.
- sources:
  - secondary: He, Cohen and Salesin 1996, The Virtual Cinematographer, on Arijon and others: the heuristics it encodes for following a subject.

## push-as-eye
- kind: provisional
- decision: A push in or pull back can stand in for cutting to a closer or wider shot, as the audience's own attention moving.
- applies when: A shot list would otherwise cut straight in or out on the same subject.
- check: Such a move is marked `push` or `pull` with what it moves toward.
- counterexample: A cut is cleaner when the change of size should feel sudden.
- confirm: A second readable source on the push in as a substitute for the cut.
- sources:
  - Lightman 1946, American Cinematographer, March, p. 82.
