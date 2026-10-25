# Cutting: where to cut and how long to hold

Rules for choosing cut points and shot lengths. A source marked `secondary` reports a book we have not read; the rule names the book it reports. The books are not read at all: a rule is settled by two independent retrievable sources or by our own data, and an LLM summary is never a source. Provisional rules rest on one source and name what would confirm them.

Thompson's handout numbers its own fifteen items; Dmytryk's book has seven rules (Jeppsen; SDSU TFM 327), so the handout is cited by item.

## cut-priorities
- kind: practice
- decision: When a cut cannot satisfy everything, give up the lower concerns first. In order of importance: the emotion of the moment, the story, rhythm, where the viewer is looking, the two-dimensional screen plane, the three-dimensional space.
- applies when: Choosing between candidate cut points in the edit, or between shots in the shot list.
- check: Each shot-list note that trades one concern for another names the higher concern it keeps.
- counterexample: A deliberate spatial disorientation, where breaking the space is the emotion.
- sources:
  - secondary: UT Austin RTF 318 course wiki, Murch's Rule of Six (2012), on Murch, In the Blink of an Eye: the six criteria in order, with emotion weighted above the other five together.
  - Smith 2012, Projections 6(1), author PDF: cites the same ordering from Murch when discussing which continuity cues viewers rely on.

## cut-on-attention-shift
- kind: practice
- decision: Cut at the moment the viewer's attention moves: the start of a movement, a turn of the head or eyes, a new line or sound. On an exit, cut as the eyes leave the frame and bring the next shot in just before they re-enter.
- applies when: Choosing the frame for a cut within or between shots of continuous action.
- check: Each cut in the shot list sits at an action start, a look, a line or a sound.
- counterexample: Cutting after a striking image has landed, rather than on the action, when the image is the point.
- sources:
  - Smith 2012, Projections 6(1), author PDF pp. 23-24: a match-on-action cut placed at the start of a movement keeps continuity, by eye-tracking evidence.
  - secondary: Thompson, course handout Edward Dmytryk's Rules of Editing, on Dmytryk, On Film Editing (1984): cut on exits as the eyes leave the frame, and on a look a few frames after the eyes settle.

## hold-until-better
- kind: practice
- decision: Stay on a shot until another shot serves the scene better. Save close-ups for when the emotion rises; an unneeded close-up weakens the ones that follow.
- applies when: Deciding shot lengths and when to go close.
- check: Close shots in the shot list cluster at the scene's emotional peak, and no shot is cut short without a reason.
- counterexample: Fast cutting used on purpose for confusion or panic.
- sources:
  - secondary: Thompson, course handout, on Dmytryk, On Film Editing (1984), item 5: an unneeded close-up weakens later ones.
  - Bordwell 2007, Intensified continuity revisited (davidbordwell.net): Lubitsch keeps close shots for the climax; average shot lengths of two to four seconds make dialogue coverage redundant.

## dialogue-cut-on-reaction
- kind: practice
- decision: In dialogue, cut to the listener when they react, a few frames after the reaction begins, not at the end of the speaker's line. Do not give every line its own shot.
- applies when: Two or more characters talk.
- check: In the shot list, cuts in dialogue fall on reactions or mid-line, and some lines play over the listener.
- counterexample: A line whose delivery is the point stays on the speaker to its end.
- sources:
  - secondary: Thompson, course handout, on Dmytryk, On Film Editing (1984), items 10-11: the meaning of a sentence lands before it ends, so the listener reacts early; cut on the reaction.
  - secondary: UT Austin RTF 318 course wiki, Dragnet: System of Editing, on the cut-to-each-speaker style: it reads as shallow; cut before or after the line ends.
  - Bordwell 2007, Intensified continuity revisited: a shot for every line is redundant.

## blink-cut
- kind: provisional
- decision: Cut a frame or two before a performer blinks while in character, not during the blink. The blink marks a thought landing; the cut follows the thought.
- applies when: Cutting away from a close shot of a performer.
- check: In the edit, cut points out of close shots sit just before a blink.
- counterexample: The rhythm of the scene demands the cut elsewhere.
- confirm: A study that ties editors' cut points to performers' blinks. Viewer evidence so far does not: Nakano et al. 2009 found viewers' blinks cluster at low-attention moments, not at cuts, and Smith and Martin-Portugues Santacreu 2016 found missed cuts did not coincide with viewers' blinks.
- sources:
  - Hullfish 2020, Art of the Cut with Walter Murch, ProVideo Coalition: Murch puts the cut a frame or two before the blink; on the blink looks twitchy.
  - Radiolab 2009, Blink, transcript: Murch noticed his cuts on The Conversation falling during the actor's blinks. Both sources are Murch himself, so they count as one.

## picture-leads-sound
- kind: practice
- decision: Choose cuts for the picture and let sound run across them. Between scenes, bridge with a split edit: the next scene's sound starts under the last shot (J cut), or the old scene's sound runs on over the new picture (L cut). In voiceover and dialogue, let lines play over the listener or the next image rather than cutting on every line.
- applies when: Cutting a scene with continuous sound, narration or voiceover, and every scene change.
- check: In the animatic, the voiceover track runs across picture cuts, and each scene change says whether it is a straight cut, a J cut or an L cut.
- counterexample: A hard sound cut used on purpose for shock.
- sources:
  - secondary: Thompson, course handout, on Dmytryk, On Film Editing (1984), item 3: cut for the picture; the sound accompanies it.
  - Yale Film Analysis Guide, Sound Bridge: sound that leads into or lingers past a cut links the two scenes.
  - secondary: Kennedy 2011, PremiumBeat (vendor blog; the author teaches editing at Columbia College Chicago), on Murch, In the Blink of an Eye: more L cuts, fewer line-by-line cuts.

## insert-read-time
- kind: practice
- decision: Hold an insert or a point-of-view shot only as long as it takes to read; for text, time it for a slow reader. A repeated insert can be shorter.
- applies when: Inserts, close details and point-of-view shots.
- check: Each insert's `duration_s` in the shot list covers reading it, and no more.
- counterexample: An insert held long to build dread.
- sources:
  - secondary: Thompson, course handout, on Dmytryk, On Film Editing (1984), item 7.
  - Technique of the Photoplay 1916 (Moving Picture World), p. 160, via the Media History Digital Library: time inserts for slow readers; a repeat can be flashed for two or three seconds.


## elide-time
- kind: practice
- decision: Cut out the stretches of an action that carry nothing; the cut lets the story skip time the viewer does not need. A jump cut compresses time openly and reads as a rupture, so use it only when that roughness is wanted.
- applies when: An action or journey is longer on paper than the shot list can hold.
- check: No shot's description covers an action from start to end when only its outcome matters.
- counterexample: Real time held on purpose, to make the viewer wait with a character.
- sources:
  - Smith 2012, Projections 6(1), author PDF: continuity editing removes redundant action and time.
  - Yale Film Analysis Guide, Editing, elliptical editing: jump cuts compress time, and signal a break with mainstream storytelling.
  - SDSU TFM 327 slides 2017, When to Cut!: compressing time is one of the reasons to cut.

## cross-cutting
- kind: practice
- decision: To show two actions in different places as happening at once, alternate between them. The viewer reads the strands as simultaneous and linked; use it for a race against time or to tie two characters together.
- applies when: The story has two or more lines of action at the same time.
- check: Each strand's shots carry the same scene ids in alternation, and the script makes their link clear.
- counterexample: Cutting between strands that do not bear on each other dissolves the tension.
- sources:
  - Bordwell 2017, Wisconsin Film Festival: Cutting to the chase, and away from it, davidbordwell.net: cross-cutting implies rough simultaneity and builds tension in chases and rescues.
  - Columbia Film Language Glossary 2015, Parallel Editing: cutting between related actions in separate places.
  - Yale Film Analysis Guide, Editing: alternating separate, usually simultaneous actions links the characters involved.

## cross-cut-quickens
- kind: provisional
- decision: In a cross-cut race against a deadline, shorten the alternations as the deadline nears.
- applies when: A cross-cut sequence building to a climax.
- check: Shot durations in the cross-cut fall toward its end.
- counterexample: A steady alternation held to keep both strands legible.
- confirm: A second source, independent of Bordwell, on shortening alternations toward a climax.
- sources:
  - Bordwell 2017, Wisconsin Film Festival: Cutting to the chase, davidbordwell.net: long alternating blocks give way to shorter bursts, often driven by a deadline.

## scene-transitions
- kind: practice
- decision: Within a scene, use straight cuts. Between scenes, a straight cut by default; a dissolve when time has passed or the place has changed, or for a dream or memory.
- applies when: Choosing each transition in the shot list (`taxonomy.toml` transitions: cut, dissolve, fade).
- check: Every dissolve in the shot list sits at a scene change or marks a dream or memory.
- counterexample: A dissolve within a scene, used on purpose for a hallucination.
- sources:
  - Columbia Film Language Glossary 2015, Dissolve: in continuity editing the straight cut is the norm within a scene; dissolves mark a change of place or time, a flashback or a dream.
  - Yale Film Analysis Guide, Editing: a dissolve links two scenes or suggests a hallucinatory state.

## fade-and-match
- kind: provisional
- decision: Fade out to end a section or the film. Join two scenes by a graphic match (a shape, colour or movement repeated across the cut) when the link between them is the point.
- applies when: The end of a sequence, and scene changes that should feel connected.
- check: Fades fall only at section ends; a graphic match names the shared element in both shot descriptions.
- counterexample: A fade used inside a sequence to mark a short lapse of time.
- confirm: A second source on fades ending a section, and one on graphic matches beyond Yale.
- sources:
  - Columbia Film Language Glossary 2015, Fade: a fade out and in moves between scenes; a fade to black ends a scene or the film.
  - Yale Film Analysis Guide, Editing, graphic match: shots joined by a strong similarity of shape or colour, smoothing a transition or making a metaphor.
