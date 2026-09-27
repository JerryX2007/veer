# SideOut — Volleyball VOD Analyzer PRD

Sep 27, 2026 · @Jerry

SideOut (working name) turns an uploaded volleyball match video into a box score, a clickable event log and per-player highlight reels, processed on the user's own machine in a fraction of match length.

## Problem & opportunity

Stat-keeping from match video is either a person tapping every contact live, or a cloud service that returns results hours later; nobody gives a coach or player fast, private, reviewable stats with one-click jumps to the moment.

- **Manual apps** such as [SoloStats 123](https://play.google.com/store/apps/details?id=com.rotate123.solostats123&hl=en_US) are exact but need a dedicated person watching the screen instead of the match.
- **Human breakdown services** such as [QwikCut](https://www.qwikcut.com/volleyball/) offer 12- or 24-hour turnaround.
- **AI video services** already exist and set the bar: they upload footage to the cloud and bill per match or per season.

| Tool | How it works | Turnaround | What SideOut does differently |
| --- | --- | --- | --- |
| [Hudl Assist / Balltime](https://smashvision.ai/blog/best-volleyball-stats-apps) | Cloud AI; Hudl acquired Balltime | Not stated | Local processing, no upload |
| [SportsVisio](https://www.sportsvisio.com/sport/volleyball) | Cloud AI, per-player reels and stat clips | Usually within 24 h | Minutes, not a day |
| [Tavo](https://www.tavosports.com/) | Cloud AI, clips by player or skill | Not stated | Describe-a-player targeting |
| [SmashVision](https://smashvision.ai/blog/best-volleyball-stats-apps) | Phone behind the court, near-live detection | Seconds (live) | Works on any existing VOD |

The opening: a lightweight app that analyzes an existing VOD on the user's own machine, lets them point at one player by describing them, and puts every stat one click from the exact frame, with a fast way to fix the model's mistakes.

## Users

v1 serves two primary users, the coach and the player; the scout is served by the same event log and gets deeper tools in v1.1.

| User | Job to be done | What matters most |
| --- | --- | --- |
| Club or high-school coach (primary) | "Give me a box score I trust, and let me verify it in under 10 minutes." | Stat accuracy, review queue, CSV export |
| Player or parent (primary) | "Find every kill and dig by #7 and cut me a 60–90 s recruiting reel." | Player targeting, highlight reel, shareable timestamps |
| Analyst or scout (secondary) | "Show me where their outside hitter attacks and who they serve at." | Filterable event log, per-player breakdowns |

All three share one habit: they watch footage in short bursts and jump around. Every number the app shows must therefore link to the exact moment it came from.

## Goals, non-goals and v1 scope

v1 is indoor 6v6 match footage from a fixed camera, analyzed locally, producing a reviewable box score, clickable event log and highlight reels.

**Goals (v1)**

1. Automatic box score: kills, attack errors, attack attempts, hitting %, aces, service errors, reception errors, digs, solo and assisted blocks, assists, points.
2. Every event, stat cell and highlight is a clickable timestamp that seeks the in-app player to that moment.
3. Track one player chosen by text description or by clicking them in the video, and filter stats and highlights to that player.
4. Highlight list and exportable MP4 reel, for one player or for the whole match.
5. Speed: first rally timestamps within 2 minutes of upload; full results in at most a quarter of match length on the reference GPU laptop.
6. Runs locally and offline on a consumer laptop; footage never leaves the machine unless the user exports it.

**Non-goals (v1)**

- Live, in-match analysis.
- Face recognition, or naming people without a roster the user supplies.
- Labeling anyone's race, ethnicity or other protected attribute (appearance words in a description are matching cues only; see Privacy).
- Recognizing the same player across different videos (v2, opt-in).
- Rotation and lineup tracking, pass ratings 0–3, beach 2v2 (all v1.1).
- Broadcast footage with camera cuts (best effort: rallies and timestamps only).

## Supported footage

"Any video" is the promise, but accuracy depends on the camera, so the app grades each upload into a tier and tells the user up front what they will get.

| Tier | Footage | v1 output |
| --- | --- | --- |
| A — full | Tripod, elevated about 2 m or more behind an end line or in a corner; whole court and net in frame; 720p or better; 25 fps or better | Full stats, player tracking, highlights |
| B — partial | Fixed sideline camera, or handheld with mild pan and zoom | Rallies, touches, highlights; stats marked lower confidence; far-side in/out calls may be missing |
| C — rallies only | Broadcast with camera cuts and replays | Rally timestamps and highlights; stats best effort; replays detected and skipped |
| D — unsupported | Close-up phone following one player, court not visible, or below 480p | Pre-flight explains why and what to change next time |

**Pre-flight check.** Before full processing, the app samples about 20 frames (target under 15 s) to find court lines and the net, estimate the tier, and flag variable frame rate, low resolution or a moving camera. The user sees the tier and can proceed anyway. The upload screen also shows a one-line recording tip: tripod, elevated, behind the end line, whole court in frame.

## User flow

The user can start watching and clicking timestamps while the rest of the match is still processing.

1. **Upload.** Drag in a video file (MP4, MOV, MKV; up to 3 h and 10 GB). Optionally add team names and a roster (jersey number to name).
2. **Pre-flight.** The app shows the footage tier and what the user will get; the user confirms.
3. **Processing.** A progress bar per stage; rallies appear in the event log as each one is processed.
4. **Watch and jump.** The viewer plays the match; the event log and timeline markers seek to any serve, kill, dig or block in one click.
5. **Pick a player (optional).** Type a description ("#12, white shoes, braids, tallest on the black team") or click the player in the frame; confirm from the top 3 candidates. Stats, events and highlights filter to that player.
6. **Review.** Work down the "Needs review" queue of low-confidence events; each fix updates the box score instantly.
7. **Export.** Download the highlight reel (MP4), the box score (CSV) and the event log (CSV or JSON), or copy a timestamp list to paste into a message.

## Requirements — upload, processing and viewer

The viewer is the product's spine: every stat, event and highlight resolves to a moment in it, and a click gets there in under 300 ms.

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| F1.1 | Import MP4, MOV, MKV, WebM (H.264, HEVC, VP9, AV1), up to 3 h and 10 GB | A 2 h iPhone HEVC file imports without error |
| F1.2 | Build a playback proxy: 720p H.264, constant frame rate, keyframe every 1 s, fast-start; all analysis runs on and refers to the proxy | Proxy duration equals source within 1 frame; variable-frame-rate sources become constant |
| F1.3 | Resume after quitting: processing restarts from the last finished stage and chunk | Killing the app mid-run loses at most one chunk of work |
| F2.1 | Progressive results: rally list first, then events rally by rally | First rally timestamps within 2 min of upload (1 h Tier A match, reference hardware) |
| F2.2 | Per-stage progress with ETA; cancel; process a chosen range only (for example set 3) | Range run processes only frames inside the range plus 5 s padding |
| F2.3 | Viewer stays usable while processing runs in the background | Playback never stalls because of processing |
| F3.1 | Player controls: play and pause, 0.25×–2×, frame step, fullscreen | Frame step moves exactly one proxy frame |
| F3.2 | Timeline with rally bands and colored markers per event type; hover shows the label; click seeks | Markers stay aligned with the playhead at every zoom level |
| F3.3 | Event log rows such as "12:41 · Kill · #7 Lee · Set 2, rally 18 · 91%"; click seeks to event time minus a 3 s pre-roll and plays | Seek finishes in 300 ms or less; the event frame lands within 1 frame of the stored time |
| F3.4 | Filter the log by event type, team, player, set and confidence | Filters combine; counts update with the filter |
| F3.5 | Keyboard: space, ←/→ for 5 s, comma and period for frame step, \[ and \] for previous or next event, N for next review item | All shortcuts listed in a ? overlay |
| F3.6 | Overlay toggle: box around the tracked player and the ball trail, synced per frame | Overlay drifts no more than 1 frame from video |
| F3.7 | Deep link to a moment (?t=761.4) and "copy timestamp list" as plain text | Pasted list is readable in a text message |
| F3.8 | Every box-score cell is clickable and filters the log to the events behind that number | Clicking "Kills: 14" shows exactly 14 events |

## Requirements — stats and definitions

Every stat is computed from the event log and nothing else, so editing one event updates every number that depends on it; the definitions below follow common US box-score conventions and live in one module.

```latex
\text{Hitting \%} = \frac{K - E}{TA}
```

Shown to three decimals (.312); shown as a dash when TA is 0. Points = K + SA + BS + 0.5 × BA. Total blocks = BS + 0.5 × BA.

| Stat | Counted when | How the pipeline decides |
| --- | --- | --- |
| Attack attempt (TA) | A player sends the ball over with an attack contact (spike, tip, roll shot) meant to score; free balls and overpasses do not count | Touch classified as attack, followed by the ball crossing the net or meeting a block |
| Kill (K) | An attack leads directly to a point: lands in, or a defender touches it but cannot keep it in play | Attacking team wins the rally with no further contact of its own after the attack |
| Attack error (E) | Attack lands out, goes into the net and is not recovered, hits the antenna, or is blocked straight down for a point | Landing point outside the court on the court map, net contact, or a stuff block, then rally lost |
| Ace (SA) | A serve leads directly to a point: lands in untouched, or the receiver cannot keep it in play | Rally ends inside the serve's flight or after one failed receive contact |
| Service error (SE) | Serve goes into the net or out | Serve trajectory ends at the net or outside the court; foot faults are not detected in v1 |
| Reception error (RE) | Charged to the receiver who touched an ace; an untouched ace is charged to the team | Nearest player at the failed receive contact |
| Dig (DIG) | First contact on an attacked ball (not a serve) that keeps it in play; block touches never count | Touch after an opponent attack, followed by another contact by the same team |
| Solo block (BS) | One blocker blocks the ball straight to the floor for a point | One player at the net in contact window, rally won |
| Block assist (BA) | Two or three blockers share a point-scoring block; each gets one | Several players in the block, rally won |
| Assist (A) | The set immediately before a kill | Contact before the kill, same team, classified as set |

A block touch that does not end the rally is not one of the team's three contacts and earns no stat. v1.1 adds pass ratings 0–3, per-set rates and a switch for other scoring conventions.

## Requirements — tracking one player from a description

The app does not search raw video for a person; it builds a gallery of every player it tracked, ranks that gallery against the description, and the user confirms with one click.

1. **Gallery.** Each tracked identity gets its sharpest front and back crops, a jersey number with confidence, team, a libero flag (contrasting jersey), dominant colors of top, shorts, shoes, socks, knee pads and sleeves, and a height estimate.
2. **Parse the description.** A rule-based parser pulls out jersey number, team color, item-and-color pairs ("white shoes"), height words ("tallest", "6'2") and position words ("libero", "setter"). The whole sentence is also scored against each player's crops by a small local vision-language model, which covers hairstyle and anything the parser misses.
3. **Rank.** A legible jersey number dominates. Without one, the score blends attribute matches with image-text similarity.
4. **Confirm.** The top 3 appear with crops and reasons ("#12 read in 41 frames · white shoes · tallest on team"). The user picks one, taps "Not them" for the next 3, or pauses and clicks the player in the frame instead.
5. **Pin and filter.** The confirmed identity can be named; stats, events and highlights filter to it.
6. **Fix identities.** "Same player" merges two identities; "split here" cuts a track at the playhead when the tracker swapped two players.

**Height** from a single camera is coarse. The net (2.43 m men, 2.24 m women) serves as a vertical reference, and the estimate is a weak cue; "tallest on the black team" works better than an exact number.

**Appearance words**, including hair and skin tone, are used only to score the match. The app never outputs a race or ethnicity label and keeps no description after matching unless the user saves the player.

| ID | Acceptance criterion (Tier A footage) |
| --- | --- |
| F5.1 | Correct player in the top 3 for at least 95% of descriptions that include a jersey number legible in the video |
| F5.2 | Correct player in the top 3 for at least 75% of descriptions without a number |
| F5.3 | Click-to-pick selects the player under the cursor in one click |
| F5.4 | Merge and split update stats in under 1 s |

## Requirements — highlights and reel export

A highlight list is the event log ranked by how worth watching each moment is; the reel is that list played as a playlist in the app, then rendered to one MP4 on request.

**Ranking.** Stuff blocks, aces and kills rank highest, then digs that lead to a won point, then long rallies. Harder attacks (ball speed from the trajectory) rank higher. Events below the confidence threshold stay out of automatic reels until reviewed.

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| F6.1 | Highlight list for one player or the whole match, sorted by time or rank; each row seeks the viewer | Same seek behaviour as F3.3 |
| F6.2 | Clip window: 2.5 s before the key contact to 1.5 s after the rally ends; adjustable; overlapping clips merge | No clip cuts off the key contact |
| F6.3 | Concise defaults: player reel 90 s or less, match reel 3 min or less; user can set a length or choose event types ("kills and digs only") | Reel length within 5 s of the target |
| F6.4 | Preview the reel as an in-app playlist without rendering; reorder or drop clips | Preview starts in under 1 s |
| F6.5 | Export MP4 (H.264, source resolution up to 1080p) with optional spotlight ring on the player at clip start and caption ("Kill · Set 2") | File plays in the default players on Windows, macOS, iOS and Android |
| F6.6 | Export speed | A 90 s reel renders in 60 s or less on reference hardware |
| F6.7 | Copy or save the highlight list as plain text timestamps | One line per clip: time, event, player, set |

v1.1 adds a 9:16 vertical reel that follows the chosen player, for social posts.

## Requirements — review, correction and export

The model will be wrong sometimes, so the app makes wrong calls fast to find and fix: a coach should verify a full Tier A match in 10 minutes or less.

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| F7.1 | Every event has a confidence; events under the threshold (default 0.7) enter a "Needs review" queue, ordered by stat impact (kills, errors, aces, blocks first) | Queue holds 15% or fewer of events on Tier A footage |
| F7.2 | Review mode loops each queued clip with its proposed label; one key each to accept, change type, change player (type a jersey number), change outcome, or delete | Median review time 10 min or less per match |
| F7.3 | Add a missed event at the playhead | New event appears in the log and box score immediately |
| F7.4 | Edits recompute stats in under 200 ms, are marked "edited", support undo and redo, and keep the model's original output | Undo restores the exact prior box score |
| F7.5 | Opt-in: save corrections as labeled examples for local model improvement | Nothing leaves the machine |
| F8.1 | Export box score CSV (per player, per set and match) and event log CSV or JSON, with timestamps | Re-importing the JSON rebuilds the same box score |
| F8.2 | Save and reopen a project file holding the proxy path, events, identities and edits | Reopened project matches the saved state exactly |

## Technical approach

A staged computer-vision pipeline runs locally: cheap stages find the rallies, heavy models run only inside them, and ball and player tracks meet where touches are attributed.

&#91;embedded content: analysis pipeline · 11 stages, one fork\]

Ball and player tracking run in parallel on the same rally windows; the dashed line is the proxy video, which the viewer plays so every timestamp matches exactly.

| Stage | Approach | Candidate models and libraries | License |
| --- | --- | --- | --- |
| Decode, proxy, clips | Hardware decode; 720p constant-frame-rate proxy; clip cutting and reel render | FFmpeg, PyAV | LGPL build; confirm the H.264 encoder's terms |
| Court map | Detect court line intersections, fit a homography with RANSAC; re-fit if the camera moves | Small keypoint model, OpenCV | Own weights; Apache 2.0 |
| Rally segmentation | Classify low-fps frames as serve, play or no-play; whistle detector on audio | Small image classifier; the open-source [volleyball\_analytics](https://github.com/masouduut94/volleyball_analytics) project uses VideoMAE for the same three states | Own weights |
| Ball tracking | Heatmap model on 3 consecutive frames, then trajectory smoothing, gap filling and bounce detection | [VballNet](https://github.com/asigatchov/vball-net) (TrackNetV4-based, 288×512 input, ONNX export) | MIT |
| Player tracking | Person detector every 2nd–3rd frame, multi-object tracker, team by jersey-color clustering | [RF-DETR](https://blog.roboflow.com/rf-detr-is-free-to-use-commercially/) or D-FINE; ByteTrack via supervision | Apache 2.0; MIT |
| Identity | Re-ID embeddings to stitch tracks across rallies; jersey number read as legibility filter, pose-guided torso crop, PARSeq, then a vote over the track | [Koshkina & Elder pipeline](https://github.com/mkoshkina/jersey-number-pipeline) pattern; OSNet; RTMPose | Check each repo; weights fine-tuned in-house |
| Touches and actions | Touch = sharp change in ball direction near a player; a temporal model over pose and ball path labels serve, receive, set, attack, block, dig, free ball; rally rules correct the sequence | Own model; pretraining on the [VNL-STES](https://hoangqnguyen.github.io/stes/) benchmark (serve, receive, set, spike, block, score) | Own weights; VNL data sourced with Volleyball World's permission, so check terms before commercial use |
| Rally outcome | Ball end point on the court map (in or out), net or block contact, which side won | Rules | — |
| Description matching | Parse structured attributes; score free text against player crops | SigLIP-family image-text model in ONNX | Apache 2.0 |

**Rally grammar.** Volleyball's rules make a strong error-corrector: at most 3 contacts per side, a block touch does not count as one, possession flips when the ball crosses the net, and every rally starts with a serve. Decoding the classifier's output under these rules fixes many single-touch mistakes.

**Runtime.** Inference runs on ONNX Runtime (CUDA, DirectML or CoreML) so the shipped app carries no PyTorch; PyTorch is used only for training. The [Ultralytics YOLO](https://blog.roboflow.com/roboflow-vs-ultralytics/) family is avoided because its AGPL-3.0 license would require open-sourcing the app or buying an enterprise license.

**App shell.** React + TypeScript front end with a native HTML5 video element and a canvas overlay synced by requestVideoFrameCallback; a local FastAPI server and job runner in Python; SQLite for projects, events and jobs; Parquet for per-frame tracks. v1 ships as a desktop app (Tauri shell with the Python engine as a sidecar).

## Performance budget

"Lightweight" means a 1 h match is fully analyzed in 15 minutes on a gaming-class laptop, the app runs offline in 4 GB of memory, and the install stays under 1.5 GB; these are targets to confirm in the M0 spike.

| Metric | Reference GPU laptop (8 GB NVIDIA, RTX 4060 class) | Apple Silicon (M2+, 16 GB) or CPU-only 8-core |
| --- | --- | --- |
| Full results, 1 h 1080p30 Tier A match | 15 min or less | 45 min or less |
| First rally timestamps | 2 min or less | 4 min or less |
| Seek from any timestamp | 300 ms or less | 300 ms or less |
| Peak memory | 4 GB or less | 4 GB or less |
| Install size, models included | 1.5 GB or less (weights 500 MB or less) | Same |
| 90 s reel export | 60 s or less | 120 s or less |

**How the pipeline gets there**

1. **Skip dead time.** Rally segmentation scans at 2–5 fps; heavy stages see only rally windows plus 2 s padding, since the ball is in play for only part of a match.
2. **Right frame rate per job.** Ball at full frame rate (touch timing needs it); players at 10–15 fps with interpolation; jersey OCR on at most about 20 legible crops per track; description matching on the gallery, never on video.
3. **Right resolution per job.** Person detection at 640 px, ball model at 288×512, OCR crops cut from the full-resolution frame.
4. **Decode once.** Hardware decode into a shared frame buffer that every stage reads; batched inference.
5. **Lean runtime.** ONNX Runtime with FP16 on GPU and INT8-quantized models on CPU; no PyTorch in the shipped app.
6. **Parallel chunks.** Each rally is an independent work unit in a process pool, and results stream to the viewer as chunks finish.
7. **Cheap clips.** Plain clips are cut without re-encoding where keyframes allow; reels with overlays use the hardware encoder.

## Data model and invariants

Six entities in SQLite, per-frame tracks in Parquet, and one rule above all: the event log is the only source of truth.

| Entity | Key fields | Notes |
| --- | --- | --- |
| Video | id, source path, proxy path, fps, duration, resolution, tier, content hash, status | One per project |
| Rally | id, video, set number, rally number, start and end time, serving team, winning team | From segmentation and outcome stages |
| Identity | id, video, team, jersey number and confidence, libero flag, display name, attributes (colors, height rank), gallery crops | One per real player per video |
| Track | id, identity, frame range; per-frame box and court position in Parquet | Raw tracker output, re-linkable by merge and split |
| Event | id, rally, time (s), frame, type, player, team, outcome, court x and y, confidence, source (model or user), model version, superseded by | Every stat and highlight points here |
| Reel | id, ordered event ids, clip windows, render settings | Rendered on demand |

**Invariants**

1. Stats are always computed from events; any cache is invalidated on edit.
2. Times are seconds on the proxy timeline plus a frame index; the viewer plays the proxy, so the two never disagree.
3. Analytics use court coordinates in meters (18 × 9 m court, net at the 9 m line); pixels appear only in tracks and overlays.
4. Model output is never overwritten; a user edit writes a new event that supersedes the old one, which is what makes undo and "show original" free.
5. Team is assigned by jersey color, never by court side, because teams switch ends every set.
6. Each stage's output is keyed by video hash, stage and model version, so reruns are cached and interrupted jobs resume.

## Accuracy targets and measurement

v1 ships when these targets hold on 10 held-out, hand-coded Tier A matches; M0's first job is to measure where the baseline actually sits.

**Evaluation set.** 20 Tier A matches from varied gyms, jersey colors and levels (14U club to college), split 10 for development and 10 held out, plus 5 Tier B and 5 Tier C matches for tier reporting. Each contact is hand-coded (time, player, type, outcome) using the app's own review mode. A predicted touch matches a coded one when it is within 0.2 s and on the same team.

| Measure | v1 target (Tier A, held out) |
| --- | --- |
| Rally detection | Recall 98%+, start and end within 1 s |
| Touch detection, all contacts | Recall 90%+ |
| Touch type (serve, receive, set, attack, block, dig, free ball) | 90%+ correct on detected touches |
| Player attribution, numbers legible | 90%+ correct |
| Serve outcome (ace, error, in play) | 95%+ correct |
| Attack outcome (kill, error, in play) | 90%+ correct |
| Digs and blocks | F1 of 0.85+ each |
| Box score | Hitting % within .050 for 90% of player-matches with 10+ attempts; kills, aces, blocks within 1 for 90% of player-matches |
| Review load | 15% or fewer of events flagged |

An `eval` command runs the pipeline over the set and writes a per-metric report. CI blocks a merge that drops any metric by more than 2 points.

## Privacy and responsible design

Much of this footage shows minors, so v1 keeps everything on the user's machine and identifies players only within one video, by what they wear and do.

- **Local by default.** Video, crops, tracks and events never leave the machine; no account is needed; telemetry is opt-in and never includes frames.
- **No face recognition.** Identity comes from jersey number, clothing, position and motion. Recognizing a player across videos waits for v2, as an explicit opt-in.
- **No protected-attribute labels.** Appearance words in a description, skin tone and hair included, only score the match; the app never outputs race or ethnicity. Men's or women's net height is a match setting the user picks, not something inferred about a person.
- **Fairness check.** The evaluation set reports player-matching accuracy by jersey color, lighting and skin tone, and gaps are fixed before release.
- **Ephemeral descriptions.** Description text is processed in memory and not logged.
- **Sharing notice.** The first reel export reminds the user to get consent before sharing clips of other players, especially minors.
- **Real deletion.** "Delete project" removes the proxy, crops, tracks, events and any saved corrections.

## Milestones

The build order front-loads the viewer so the app is useful (clickable rally timestamps) before any stat model is finished, and every phase ends at a gate measured on the evaluation set.

&#91;embedded content: roadmap · 5 phases, 5 gates\]

M1 alone already beats scrubbing through a 2-hour VOD; M2 unlocks the player reel even before stats are reliable. A phase does not start until the previous gate passes, or the gap is written down as a known risk.

## Risks and mitigations

The biggest risks are the ball and the footage: a small, fast ball on unpredictable video decides whether touches, and so every stat, are found.

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Ball lost against busy backgrounds or at the far end, so touches are missed | High | 3-frame heatmap model, physics-based gap filling, rally-grammar decoding, camera guidance at upload |
| Footage varies far more than the eval set | High | Tier grading and pre-flight; fall back to rallies-only mode instead of wrong stats |
| Identity switches when players cluster at the net or both teams wear similar colors | High | Re-ID plus jersey vote per track; merge and split tools; optional roster import |
| Training data scarce or restricted | High | Review mode doubles as a labeling tool: the model proposes, people correct, corrections become labels; check every dataset license before training shipped weights |
| Stats disagree with a coach's scorebook on judgment calls (dig or not, kill after a touch) | Medium | One definitions module shown in-app; fast edits; scoring-convention switch in v1.1 |
| License contamination (AGPL model, GPL encoder) | Medium | Apache and MIT models only; LGPL FFmpeg build; license allowlist check in CI |
| Too slow on low-end laptops | Medium | Fast model variants, INT8 on CPU, process-a-range option; optional cloud processing later |
| Libero swaps and side switches confuse team logic | Medium | Team by jersey color; libero detected by contrasting jersey |
| Reels of minors shared without consent | Medium | Local-only storage, no auto-upload, sharing notice on first export |

## Open questions

The first two answers change the architecture; the rest change scope.

- [ ] Desktop app with local processing (this PRD's assumption) or a web app with cloud GPUs?
- [ ] Commercial product or personal or open-source project? This decides whether AGPL-licensed models are an option.
- [ ] Must CPU-only laptops be supported in v1, or is a GPU or Apple Silicon machine acceptable?
- [ ] Indoor only for v1, or is beach 2v2 needed sooner?
- [ ] Roster import at upload (number to name), or name players afterward?
- [ ] Track the score in v1 (scoreboard reading or rally winners), so highlights can favour set and match points?
- [ ] Default scoring convention: US high-school and college box score, or FIVB?
- [ ] Team size and target date, to turn the milestones into a schedule.

## Sources

- [SportsVisio — volleyball](https://www.sportsvisio.com/sport/volleyball)
- [SmashVision — Best volleyball stats apps in 2026](https://smashvision.ai/blog/best-volleyball-stats-apps)
- [Tavo](https://www.tavosports.com/)
- [QwikCut — volleyball](https://www.qwikcut.com/volleyball/)
- [SoloStats 123 on Google Play](https://play.google.com/store/apps/details?id=com.rotate123.solostats123&hl=en_US)
- [VballNet (GitHub)](https://github.com/asigatchov/vball-net)
- [Fast volleyball tracking inference (GitHub)](https://github.com/asigatchov/fast-volleyball-tracking-inference)
- [RF-DETR is free to use commercially (Roboflow)](https://blog.roboflow.com/rf-detr-is-free-to-use-commercially/)
- [Roboflow vs. Ultralytics licensing](https://blog.roboflow.com/roboflow-vs-ultralytics/)
- [Jersey number pipeline, Koshkina & Elder (GitHub)](https://github.com/mkoshkina/jersey-number-pipeline)
- [VNL-STES volleyball event-spotting dataset](https://hoangqnguyen.github.io/stes/)
- [volleyball\_analytics (GitHub)](https://github.com/masouduut94/volleyball_analytics)
