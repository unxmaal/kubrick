# Shot scale

Rules for choosing how big each shot is and how scale changes across cuts. Scale labels are the ones in `taxonomy.toml`, in ladder order ECU, CU, MCU, MS, MLS, LS, ELS; FS and INS are off the ladder.

Measured rules are recomputed with `uv run kubrick rules check <id> --labels <folder>`, where the folder holds CineScale's per-film label files by director (Savardi, Kovacs, Signoroni and Benini 2021, CC BY 4.0, Mendeley DOI 10.17632/th46h4vdwd.1). The statistic is compared with a null that reorders each film's own shots and merges equal neighbours, as the labels do. A rule holds when Scorsese, the deriving director, and at least two of the other five directors beat that null in most of their films.

## one-step-scale-cuts
- kind: measured
- decision: When cutting between two shots on the ladder, prefer the next size up or down. A jump of two or more sizes is a deliberate effect, used for a jolt or a reveal, not the default.
- applies when: Consecutive shots in the shot list both sit on the ladder.
- check: In the shot list, most consecutive on-ladder pairs differ by one step; each larger jump has a reason in its shot description.
- counterexample: A sudden cut from an extreme long shot to a close-up of a face, to shock or to isolate a character, is common and effective when meant.
- data check: kubrick rules check one-step-scale-cuts
- result: holds in every film of all six directors, 114 of 114 films above the null (Scorsese 0.585 against 0.500; Bergman 0.697 against 0.549; Tarr 0.889 against 0.668).
- sources:
  - CineScale per-second human scale labels, 123 films by six directors (Savardi et al. 2021), measured here with the merged reordering null.
  - Smith 2012, Projections 6(1), author PDF p. 6: two shots of one subject need a clearly different size or a viewpoint change of about 30 degrees, or the cut reads as a jump; the literature sets a minimum change, and no readable source sets a one-step maximum.

## wide-then-closer
- kind: refuted
- decision: Do not use "after a long shot, cut closer" as a shot-to-shot rule. In the measured films it is no more common than any reordering of the same shots would make it.
- applies when: Deciding the shot that follows an LS or ELS.
- check: Choose the next shot's size by the scene's needs and by scene-opens-wide, not by this claim.
- counterexample: A slow widening from a face to the whole room after a wide shot is as normal as moving in.
- data check: kubrick rules check wide-then-closer
- result: does not hold; 25 of 113 films beat the null, and the observed share (0.93 to 0.98) sits at or below it (0.95 to 0.99). After an ELS nothing is wider, which is most of the apparent effect.
- sources:
  - CineScale per-second human scale labels, 123 films by six directors (Savardi et al. 2021), measured here with the merged reordering null.
  - Cutting 2016, Psychonomic Bulletin and Review 23(6), Study 6 discussion: the moving-in pattern is a scene-level arc, which is what scene-opens-wide states; it is not a claim about every cut.

## scene-opens-wide
- kind: practice
- decision: Open a scene on a shot wide enough to show where the action is, move in on faces as the scene develops, and widen again when characters move to a new part of the space or as the scene closes.
- applies when: The first shots of every scene, and any shot after characters change position.
- check: Each scene's first shot in the shot list is MLS, LS or ELS, or its description says why the scene opens close.
- counterexample: A scene that opens on a close detail to withhold where we are, then reveals it, is a deliberate exception.
- sources:
  - Cutting 2016, Psychonomic Bulletin and Review 23(6), Study 6 discussion: across about 3,200 hand-coded scenes, scenes start on longer shots, move in toward faces and often widen again before the next scene; scale is the strongest cue for a scene change.
  - Smith 2012, Projections 6(1), author PDF p. 6: a scene typically begins with an establishing shot and moves gradually closer, cutting back wider when characters move.
