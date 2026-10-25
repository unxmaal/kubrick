# Continuity across cuts

Rules the continuity checker (`src/kubrick/continuity.py`) enforces, run as `uv run kubrick continuity <project>` at step 5 of `runbooks/workflow.md`. Each rule says which checker rule it is in `enforces`.

A caution from the research: viewers miss most continuity slips in finished films. That does not make these rules optional here. A generative model drifts far more than a film crew does, and its drift is cheap to prevent on paper and expensive to fix after rendering.

## axis-180
- kind: practice
- decision: When two characters face each other, keep the camera on one side of the line between them for every shot of the pair. Cross through a shot along the line, or declare the cross in the floor plan as the shot's `crosses_line` with its reason: a camera move across the line seen on screen, or a deliberate cross.
- applies when: Consecutive shots show the same two characters.
- check: `kubrick continuity` prints no axis-180 line for the scene.
- counterexample: A deliberate cross to mark a turn in a confrontation, shown so the viewer can follow it.
- enforces: axis-180
- sources:
  - Smith 2012, Projections 6(1), author PDF pp. 6-7 and 25-26: states the rule and cites eye-tracking work in which viewers often fail to notice a crossing; what matters is that each character appears where the viewer expects on screen.
  - Kachkovski, Vasilyev, Kuk, Kingstone and Street 2017, author manuscript, Experiments 1-3, pp. 10-20: viewers trained in the rule spotted 42 percent of violations; untrained viewers called violating cuts confusing 8 percent of the time against 6 percent for normal cuts, and liked both kinds of video equally.

## eyeline-match
- kind: practice
- decision: In shot and reverse shot, each character looks toward the screen side where the other character is, as the floor plan places them. Write the gaze in the shot list only when it agrees with the floor plan.
- applies when: A shot shows one character looking at another who is off screen or in another shot.
- check: `kubrick continuity` prints no eyeline-match line.
- counterexample: A character who looks away from the other on purpose, to avoid them, is not an error; leave `gaze` out for that shot.
- enforces: eyeline-match
- sources:
  - Smith 2012, Projections 6(1), author PDF pp. 25-26: before the cut, viewers shift attention toward where the other character should appear; a mismatched eyeline sends their search the wrong way.
  - Kachkovski et al. 2017, author manuscript p. 5: staying on one side keeps each character's gaze pointing the same way on screen. This source states the rule; it does not test it.

## screen-direction
- kind: practice
- decision: A subject moving across the frame keeps moving the same way on screen in the next shot of that movement. To change direction, cut through a shot where the subject comes straight at the camera or goes straight away.
- applies when: A subject is moving in consecutive shots.
- check: `kubrick continuity` prints no screen-direction line.
- counterexample: A character who turns round on screen and walks back the other way has changed direction in the story, not across a cut.
- enforces: screen-direction
- sources:
  - Smith 2012, Projections 6(1), author PDF pp. 21-22: on a matched exit and entrance, attention follows the subject across the cut; reversing the direction breaks that.
  - Magliano and Zacks 2011, Cognitive Science 35(8), section 1.1: keeping to one side of the action keeps motion flowing the same way across shots, and crossing flips it.
  - No readable source tests the head-on or tail-away reset; it is the conventional remedy and is recorded here as untested.

## action-phase
- kind: practice
- decision: When one action continues across a cut, the second shot picks it up where the first left it, or a little before. It never starts noticeably earlier, so the action does not appear to run backwards.
- applies when: The same action (standing, opening a door) spans two shots.
- check: `kubrick continuity` prints no action-phase line; the floor plan gives the action's phase at each shot's start and end.
- counterexample: An action replayed on purpose, shown again from a new angle for emphasis.
- enforces: action-phase
- sources:
  - Smith 2012, Projections 6(1), author PDF pp. 23-24: a match-on-action cut works when the action carries on at the same place on screen, and many such cuts go unnoticed.
  - Magliano and Zacks 2011, Cognitive Science 35(8), Study 1, section 2.2: cuts that break the action drove viewers' sense of a new event far more strongly than continuity cuts did; continuous action is what lets viewers bridge a cut.
  - No readable source quantifies how much overlap is tolerated; the checker's tolerance is a registered setting, not a finding.

## wardrobe-state
- kind: practice
- decision: Every worn or carried item keeps the state the breakdown gives it in every shot, until the breakdown records a change. Test unusual states against the model before the shot list locks (workflow step 3).
- applies when: A character with listed wardrobe is on screen.
- check: `kubrick continuity` prints no wardrobe-state line, and each shot's prompt fields carry the breakdown's states.
- counterexample: A change the story shows on screen, recorded in the breakdown's `wardrobe_changes`.
- enforces: wardrobe-state
- sources:
  - Smith 2012, Projections 6(1), author PDF p. 13: in a study it cites, viewers caught on average 2 of 9 planted continuity errors, mostly those near faces.
  - Simons 2000, Visual Cognition 7, pp. 1 and 5: most viewers missed an actor being swapped across a cut; a change goes unseen unless the changed item is attended.
