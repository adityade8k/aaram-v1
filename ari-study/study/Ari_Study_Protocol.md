# Ari in the shop
## Exploratory robot–phone study · Protocol draft 0.2

Prepared 17 November 2026 for the NYU ITP/IMA shop. This is a reviewable draft, not ethics clearance or permission to recruit. The interface-first, voice-only direction reflects your choices in this conversation. Portability, the running robot backend, equipment availability, and the final recruitment target remain unconfirmed.

## 1. Questions and design

Primary question: How does interacting with this physically present, gesturing robot change how novice shop users seek, interpret, and respond to assistance, compared with the same voice assistant on a phone?

Secondary question: What differences appear when the assistant can consult a background researcher while continuing the conversation, versus having the conversation model search and interpret the sources itself?

Use a mixed exploratory design: interface is within participant; inference architecture is between participants. Each participant tries robot and phone, keeping inference architecture constant. Randomize eligible participants to one of eight cells: four interface/task sequences crossed with background or inline inference. For a tentative sample of 16, this is two participants per cell, eight per inference group. This is a feasibility target, not a power calculation. Do not promise a reliable interface-by-background interaction estimate from this sample.

| Sequence | Block 1 | Block 2 |
| --- | --- | --- |
| 1 | Robot / X | Phone / Y |
| 2 | Phone / X | Robot / Y |
| 3 | Robot / Y | Phone / X |
| 4 | Phone / Y | Robot / X |

Use the supplied randomized allocation list in order of enrollment. Each consecutive block of eight allocations contains every sequence/mode combination once. Keep allocation hidden during eligibility screening. Record withdrawals and actual exposure; never recycle a completed participant's outcome to rebalance a result. Recruit replacements using a documented rule if cells are incomplete.

Counterbalancing distributes order and task differences; it does not erase transfer of shop knowledge or conversational practice. The second task uses new content but the same skills. Treat that transfer as an interpretation limit.

The robot condition includes physical form, gestures, placement, carrying affordances, microphone and speaker characteristics. Call the result a comparison of these two implementations. It cannot identify a pure effect of physical presence independently of all those features.

## 2. Two architectures, both with internet access

The earlier no-lookup OFF condition is superseded. Use explicit mode names: inline (conversation model alone) and background (conversation model plus a separate researcher). Do not relabel legacy OFF recordings as inline: they had different capabilities.

| Property | Inline: conversation model alone | Background: separate researcher |
| --- | --- | --- |
| Interface options | Phone or robot | Phone or robot |
| Voice model and voice | Shared configured HF service and voice | Identical shared HF configuration |
| Base instructions and shop context | Fixed shared snapshot | Identical shared snapshot |
| Web access | Enabled through lookup_information | Enabled through lookup_information |
| Search service and budget | Shared service; up to five source excerpts per request | Same service and result budget |
| Source interpretation | Conversation model reads returned excerpts itself | Separate model interprets excerpts and sends a brief to the conversation model |
| While work is pending | May acknowledge or ask a useful question before a lookup; microphone stays live; any supported interim speech is allowed | Immediate tool acknowledgement frees the voice model for relevant dialogue while research runs |
| Completion | Tool returns actual search results, then the conversation model responds | Brief enters context at a pause and is used when relevant |
| Camera / long-term memory | No visual input or cross-session memory | Same |

Both modes should try to keep the interaction natural. Neither is forced to chatter, stall, or say “please wait.” One useful acknowledgement, known fact or clarification can help; repeated filler should be coded separately. Do not promise that a single response-generation stream can produce new substantive speech while it is internally computing. Test the deployed voice backend's behavior during an unresolved tool call, including interruptions and new user turns.

There is no synthetic inference delay in this pilot. The background mode is the concurrent architecture: one model can converse while the other processes information. Inline means the conversation model handles the lookup and interprets its result in its own turn sequence. It may still process interruptions if the backend supports them. The software does not mute or gate input simply because a lookup is pending.

Background behavior should be a continuing conversation: the voice model asks a useful question or discusses a known part of the project, responds to the student's clarification, and later connects the finding to those latest details. Example: after the student says a joint is loose, a relevant result can become “That loose fit you mentioned could be related to the material removed by the cut.” Do not speak unfinished research as though a result has already arrived.

The handoff waits for no active user speech, no generated response in flight, and a 750 ms quiet window after reported playback/turn activity. The voice model then either integrates the note briefly or calls a no-speech skip action if the question was resolved, the topic changed, or the note adds nothing. This opportunity remains available after intervening clarification turns. The implementation discards results beyond eight newer turns or three minutes at delivery. Log and pilot these thresholds rather than claiming they perfectly detect a natural pause or topic change.

This comparison changes the number of reasoning models, the form in which evidence reaches the voice model, and scheduling. It does not isolate latency alone or guarantee identical answers. To isolate scheduling later, use the same researcher/content in both conditions and change only whether the conversational turn waits for it. That would be a separate study.

Use the same search provider, result count, source scope, language and restrictions in both modes. The current bridge uses one shared Brave Search adapter returning bounded excerpts, not full page contents. Background synthesis has no additional browsing tools. This introduces a search-service credential in both modes and a Claude credential only in background mode; there is no silent fallback when either is missing. Different query wording and changing web results can still create content differences, so retain queries and sources.

## 3. Recruitment and prerequisites

Proposed eligibility: adults enrolled in ITP/IMA who have not independently operated the specific shop laser. Record prior use of lasers elsewhere, formal shop training, design software familiarity, voice-assistant frequency, robot experience, language preference, and relevant access needs. Do not assume lack of confidence equals lack of skill. Confirm whether adults-only recruitment and an English-language pilot fit the intended population.

Recruit independently of grades and access to shop resources. A participant can stop, skip a question, or ask staff at any time. If a researcher teaches or supervises candidates, arrange recruitment/consent to reduce perceived obligation and discuss this relationship with the advisor.

Before involving students, obtain the advisor's determination of applicable NYU human-subject review, training and consent requirements. Ask explicitly whether feasibility sessions with students are covered. NYU guidance directs researchers to determine review requirements before human-subject research begins; this document does not classify the project as exempt. [NYU ethics and research guidance](https://guides.nyu.edu/tests/ethics).

Before recruitment, named shop staff must review both task packs, the shared shop-context snapshot, the evaluation rubric and the intervention rule. The app currently includes a copy of your repository's shop document. Its details are not independently certified current. Keep all machines idle, with no participant job submission, material loading, focusing, laser settings changes or machine activation.

## 4. Materials and exact task briefs

Provide each task as a paper brief, a design preview, a simplified layer/object list, two labeled material samples or photo cards, a small planning worksheet, and access to the same neutral shop resource station. The printed cards included with this package are drafts for staff review. They are not cut files or material approvals.

### Task X: exhibition sign

Participant brief: “You are preparing a small exhibition sign with cut lettering and an engraved detail. Use the supplied design and material candidates to make a plan you could take to shop staff. Work out what is ready, what you would change, and what you still need to check. Ask the assistant any questions that help. Stop at preparation; do not operate the laser.”

Draft pack: a 120 × 80 mm rectangular sign; one cut contour plus its duplicate; editable text; one engraved symbol. Material A is an identified acrylic sample with a source record and approval still pending. Material B is a visually similar scrap with unknown identity. Optional concept prompt in the project brief: “The sign will eventually fit in a slot. Explain why a drawn width might not produce the fit you expect.” This is a project requirement, not a required spoken question.

### Task Y: project labels

Participant brief: “You are preparing a set of project labels with a cut outline and an engraved symbol. Use the supplied design and material candidates to make a plan you could take to shop staff. Work out what is ready, what you would change, and what you still need to check. Ask the assistant any questions that help. Stop at preparation; do not operate the laser.”

Draft pack: a set of labels occupying a 120 × 80 mm area; one duplicated cut contour; editable text; one engraved symbol. Material C is an identified acrylic sample with a source record and approval still pending. Material D is a visually similar scrap with unknown identity. Parallel concept prompt: “A label will eventually fit into a holder. Explain why a drawn width might not produce the fit you expect.”

Both tasks intentionally require the same kinds of preparation: distinguish known versus unverified material, inspect the supplied object list for duplication/editable text, separate cutting from engraving, explain fit uncertainty, and articulate what staff must verify. The layouts and project goals differ. Use equal text length, information density, number of faults and available time. Test and revise task difficulty before freezing the protocol. Repeated concepts create transfer; record it rather than claiming the tasks eliminate it.

The concept prompt creates an opportunity for lookups in either mode, but the conversation model may already know enough or the student may never ask about it. Do not force a tool call to manufacture the manipulation. Log whether research actually happened. If it rarely happens, revise the tasks during feasibility, then freeze them before the main pilot.

### Staff-reviewed completion rubric

Score each dimension separately as 0 = absent/incorrect, 1 = partly identified or prompted, 2 = independently identified with an appropriate next step. Retain evidence and whether staff/researcher intervened. Avoid presenting the sum as a validated ability score.

| Dimension | Observable evidence |
| --- | --- |
| Material uncertainty | Differentiates identified material from unknown scrap and seeks staff approval |
| File preparation | Notices the duplicate contour and editable text in the supplied object list |
| Cut versus engrave | Communicates which design features should cut versus engrave |
| Limits and verification | Distinguishes an assistant explanation from local authorization or a verified setting |
| Readiness plan | Explains a feasible next step and remaining questions for staff |

Do not score obedience to the assistant as correctness. The reference is the staff-reviewed rubric. Do not treat confidence, speed, or more questions as proof of learning.

## 5. Matched procedure and controls

| Control | Implementation |
| --- | --- |
| Voice / language | Same selected voice, language and provider settings; record values |
| Model versions | Record actual deployed backend/model versions; a shared endpoint alone does not prove fixed weights |
| Instructions | Match shared assistant and shop text; record SHA-256 hashes and every interface-specific addition |
| Information access | Same shared search service and result budget in both modes; the additional researcher exists only in background mode |
| Memory | Fresh provider session for every block; no long-term memory or previous participant transcript |
| Sensory access | No camera, image upload, visual understanding or vision-based tracking in either condition |
| Robot behavior | Fixed speech-reactive movement policy; record enabled gestures and actual behavior |
| Audio | Same room/route; comfortable, roughly matched volume; record distances, noise, recognition failures and interruptions |
| Phone surface | Voice controls only during the block; no transcript, sources, research status, or animated robot face |
| Robot surface | Keep the researcher control screen away from the participant; no extra visible transcript or research dashboard |
| Timing | Equal practice, task limits, facilitator prompts and staff availability |
| Network | Same network where feasible; record disconnects, not simply signal strength |
| Observer | Fixed script and intervention policy; do not coach one interface more than the other |

Some gesture tools alter what the voice model chooses to do. Prefer automatic speech-reactive movement without extra model-visible movement calls for the initial comparison. If you retain model-selected gestures, document those additional tools and interpret that difference as part of the robot condition.

The revised package includes a separate robot audio client that connects to the same backend as the phone. It does not use the old robot app's saved tools or researcher toggle. Do not run both robot conversation applications simultaneously. Confirm the effective mode and lookup tool on a fresh session, and do not silently switch modes after a missing credential.

The revised phone and robot clients share one backend, so a given inference mode receives the same session configuration by construction. Their audio capture, playback and motion paths still differ. Real-device equivalence is not yet validated. Complete the checks in the engineering README before collecting paired study data.

### Movement

Portability is unconfirmed. If the robot is untethered and remains connected, include one identical short route from the workstation to the materials area during each block. Let the participant choose whether/how to carry or place the device. Observe that choice; do not instruct them to cradle the robot or hold the phone in a particular pose.

If the robot needs a cable or cannot maintain a connection, run both conditions at matched stationary locations for this pilot. Document that portability was not tested. Do not turn a cable limitation into a difference in task access without reporting it.

## 6. Forty-minute session script

| Minutes | Activity |
| --- | --- |
| 0–5 | Consent, participant code, baseline experience and access needs |
| 5–8 | Neutral practice, about 90 seconds per interface; no laser task content; practice order follows block order |
| 8–17 | First assigned task/interface; include movement if feasible |
| 17–20 | Ratings, brief task-plan explanation, no teaching feedback |
| 20–22 | Reset conversation, reset physical task materials, switch interface |
| 22–31 | Second assigned task/interface |
| 31–34 | Same ratings and brief plan explanation |
| 34–40 | Comparative interview and debrief; staff correct unresolved unsafe misunderstandings |

Introduction: “We are studying different ways of getting assistance in the shop. We are evaluating the system, not your skill. You can ask questions in your own words, interrupt, or say you do not understand. Neither assistant can see you or the materials. Its answers are not permission to use a machine. You may ask staff or stop at any time.”

Practice: ask the participant to describe a harmless everyday project, ask a follow-up and try an interruption. Do not demonstrate ideal laser questions. Use the same practice opportunity for both devices and reset afterward.

Task instruction: read only the relevant participant brief. Do not list the hidden faults or tell participants what to ask. At the fixed midpoint, say the same thing in both blocks only if needed: “You can use the assistant however you think would help.” Record that prompt. If the participant is silent, allow silence before prompting.

Staff intervene immediately if someone attempts machine operation or a physical risk appears. Record the trigger and intervention. An assistant error alone may be discussed at debrief if nobody acts on it; staff decide the boundary in advance. A task ends when the participant says their plan is ready, at nine minutes, or on withdrawal/interruption. Record which.

For a disconnect, mark it, stop the block and export its partial record. Do not splice an unmarked fresh model session into the same block. At feasibility stage decide a fixed restart/exclusion rule, such as one restart after a documented equipment failure, with both attempts retained. Do not decide exclusions based on whether outcomes look favorable.

## 7. Observations and measurements

Primary output: a within-person comparison of interaction episodes, supported by logs and interviews. Counts and ratings describe those episodes; they do not define a winner.

| Code | Operational definition | Keep distinct from |
| --- | --- | --- |
| Information request | A new question asking for a fact, explanation or resource | Repeated ASR repair |
| Clarification | A request to explain or disambiguate prior assistance | New topic |
| Confusion disclosure | Explicitly says they do not know, understand, or feel sure | Observer-inferred discomfort |
| Follow-up | Builds on the previous answer in the same topic | Exact repetition after a failure |
| Repair | Repeats, rephrases or corrects after a recognition/understanding failure | Voluntary elaboration |
| Interruption | Participant begins during assistant playback; note successful stop | Mere overlap from delayed playback |
| Verification | Checks advice against staff, supplied material or another allowed source | Verbal agreement |
| Uptake | Incorporates advice into their stated plan | Correctness or actual machine action |
| Embodied orientation | Looks, points, turns, places or carries the device | Claimed visual understanding |
| Assumed capability | Words/actions indicating the assistant is expected to see or know context | Researcher speculation without evidence |
| Staff escalation | Participant or assistant directs an unresolved issue to staff | Automatic evidence of failure |
| Research episode | Request → interim talk/silence → result/failure → possible use | Every question in a session |

Report questions, repairs and interruptions both as raw counts and per minute of usable task time; speech failures can inflate all three. Code who initiated each clarification. Retain negative cases, such as the robot discouraging disclosure or the phone inviting more social behavior.

Timing definitions:

- User end of speech → first audio received by the bridge: transport/model proxy, not audible response time.
- Browser receipt of the speech-stop event → scheduled first playback: a browser-side estimate, not measured acoustic onset.
- Lookup request → search ready: shared search-service latency.
- Search ready → research ready: additional background-model processing time, present only in background mode.
- Research ready → context injection: delivery delay, including the configured quiet window; injection is not evidence of spoken use.
- Research follow-up requested → integrated / skipped / interrupted: code whether the finding connects to the latest user details, repeats an old question, or forces an unwanted topic return.
- Lookup request → first useful answer actually spoken: manually code from consented recordings/transcript with playback context.
- Annotate quiet time, useful acknowledgements, relevant clarifications, repetitive filler, interruptions and abandonment during a lookup separately. An early “I’ll check” is first speech, not the first useful answer. Do not collapse them into one “engagement” number.

The app labels server and browser clocks and uses relative time within each. Do not subtract timestamps across clocks without synchronization. Browser audio scheduling and base latency are recorded; physical speaker onset needs an external recording. Robot logs need equivalent event definitions. Capture one agreed sync marker if aligning system logs with a consented observer recording.

Post-condition ratings, 1 strongly disagree to 7 strongly agree; allow skipped responses:

1. I could understand the assistance.
2. I felt comfortable saying I was confused.
3. It took effort to keep the conversation going.
4. I could tell when the assistant was uncertain.
5. I knew when I needed to check with staff.
6. I felt that I was interacting with a socially present partner.

These are study-specific exploratory items, not a validated composite scale. Report separately; do not reverse-score and sum them into “trust” or “usability.” Ask “What led you to that rating?” for one especially informative response if time permits, using the same opportunity in both blocks.

## 8. Comparative interview

Use neutral order and ask for concrete moments rather than abstract preferences.

1. “Walk me through one moment when the way you asked for help changed between the two devices.”
2. “Was there anything you asked one assistant that you would not have asked the other? What made the difference?”
3. “What did you think each assistant could notice or understand about the situation? What gave you that impression?”
4. “How did you decide which advice to use, check, or take to staff? Tell me about an example.”
5. “What happened for you during pauses, interruptions or corrections? Did any specific moment stand out?”
6. “How did holding, placing or moving the device affect what you did? What would you change about either setup?”

If movement was omitted, replace question 6 with placement and orientation. For either mode, after open answers ask: “What did the assistant do while it was finding information? Was that helpful, distracting or neither? Tell me about a specific moment.” Do not tell participants that continuing conversation is the intended success behavior.

Debrief: explain the assigned background mode, identify the two factors, correct any unresolved preparation misconceptions with staff and reiterate that this was not laser training or certification.

## 9. Analysis plan

Create one row per participant per interface with mode, sequence, task, actual block duration, prior experience, technical failures, rubric dimensions, six ratings and coded event counts. Keep an episode table with timestamps and evidence excerpts. Missing data stays missing; do not code it as zero.

Compare phone and robot within each person. Plot paired ratings and event rates, then show individual differences and medians/ranges for the full sample and each inference group. Inspect first-versus-second block and X-versus-Y patterns. With this sample, emphasize variability and cases rather than significance claims. If inferential tests are later planned, specify them and a sample-size rationale before looking at outcome differences.

Keep the assigned inline/background comparison as the primary mode description. Also describe whether each session actually used a lookup and whether the background researcher ran; lookup-exposed episodes are a self-selected subset and cannot establish a causal mode effect. Separate sessions with network or recognition failures in a sensitivity description while retaining their experience in the qualitative analysis.

For qualitative coding, two researchers independently code a small common set spanning both interfaces and modes, discuss definitions and disagreements, then revise the codebook before coding the remainder. For categorical event counts, double-code a preselected portion and report agreement plus how disagreements were resolved. For interpretive themes, retain memos and counterexamples rather than presenting agreement statistics as proof of objectivity. Blind transcript-only coders to interface when feasible; recordings with visible devices cannot be blinded.

Integrate evidence using a participant-by-interface matrix: observed event → system context → participant interpretation. For example, an extra question may be sociability, task interest, uncertainty or an ASR repair. The logs and interview should distinguish those possibilities.

Claims should stay specific to this robot, phone interface, model snapshot, novice sample and tasks. Do not generalize to robots versus all LLMs or claim learning gains from a brief preparation task. Note novelty, small sample, bundled interface differences, learning transfer, model variability and potential researcher effects.

## 10. Consent and data handling

Use participant codes; keep any identity/consent linkage separately in institution-approved storage. The app streams microphone audio to the configured voice service and sends search queries to the shared search provider in both modes. Background mode additionally sends recent transcript text and source excerpts to the research model. Explain the actual providers and their retention arrangements in consent after checking your account settings. Do not promise that providers retain nothing.

The app itself does not save raw audio/video. After consent the phone saves the current block's transcript, event log, ratings and notes in that browser and allows JSON/CSV export. The robot client writes a JSONL event record to the specified output directory; researcher ratings and notes use the supplied forms. Browser storage is not a research archive. Export after each block to the approved study location, verify the file opens, then clear the shared device's browser record. Keep the screen locked when unattended. Select researcher roles, retention duration, withdrawal cutoff and deletion process with the advisor before recruitment.

External audio/video recording requires the approved consent process and a defined capture area; avoid recording bystanders. A phone microphone will still transmit ambient sound while live. Participants can mute or end the session. No study data should be placed in public deployment assets, public repositories or the source-code package.

## 11. Readiness and open decisions

Required before recruitment: staff task/rubric signoff; advisor/ethics determination; successful live phone audio on iPhone and Android; matched robot configuration; a verified inline and background tool trace on both interfaces; confirmed source/voice/model identifiers; no memory or camera leakage; interruption, timeout, disconnect and export checks; and a settled handling rule for technical failures.

Still to decide with your team: where the working backend runs and which voice and shared-search credentials it uses; whether the robot is untethered; the robot gesture policy; who reviews task materials; session room/noise; accessibility accommodations; recruitment pool and compensation; the final sample and time budget; recording method and approved storage/retention. These are unresolved, not assumed capabilities.

Run engineering checks without student research data first. If covered by the appropriate review, use a small feasibility pilot to tune tasks and timing, document changes, then freeze the protocol and begin the main exploratory sample. Keep feasibility data separate if the interface or procedure changes.

## References and provenance

- Local implementation reviewed: Aaram “version 1”, including huggingface_realtime.py, background_reasoning.py, tools/research_question.py, profiles/ari/profile.md, prompts.py, experiment_log.py and both grounding documents. Code capabilities are observations of that checkout, not evidence of a running deployment.
- [NYU: Ethics and research involving human subjects](https://guides.nyu.edu/tests/ethics). Consult the advisor and applicable NYU review office for this project.
- [Netlify Server overview](https://docs.netlify.com/build/server/) and [API reference](https://docs.netlify.com/build/server/api/). Current hosting option with WebSocket support; Early Access availability must be confirmed for your account.
- [Brave Search API documentation](https://api-dashboard.search.brave.com/app/documentation/web-search) and [Reachy Mini SDK reference](https://huggingface.co/docs/reachy_mini/API/reachymini) support the search and robot-adapter implementation.
- [Pollen Robotics conversation app](https://huggingface.co/spaces/pollen-robotics/reachy_mini_conversation_app/blob/main/README.md). Public upstream context; the local modified checkout remains the basis for this phone bridge.

The task designs, rating items and analysis plan above are proposals for this project, not borrowed validated instruments.
