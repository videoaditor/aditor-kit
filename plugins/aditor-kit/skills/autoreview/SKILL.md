---
name: autoreview
description: Deliver finished videos to AutoReview (feedback.aditor.ai) and fix them until the reviewer approves. Use when the user says "Pair with AutoReview: CODE", gives an 8-character AutoReview pairing code, says "autoreview", "send for review", "zur Abnahme", or when a video is done and a human should look at it.
---

# AutoReview

AutoReview is where a human reviews your edits: they talk and draw on the video, press Send, and you fix. An automatic review checks every upload against the brand's rules first. The scripts sit next to this file (the skill's base directory, shown when it loads); call them with `python3 <base dir>/<script>`. Stdlib only, macOS.

## 1. Pair (once per machine)

The user types "Pair with AutoReview: CODE". The code comes from the brand's project in AutoReview, is 8 characters, single use, valid 15 minutes.

```
python3 <base dir>/ar.py pair CODE
```

It stores the key in the macOS Keychain (`aditor-autoreview-agent`), prints the project (= brand) it delivers to, and lists any tool `reel-qc` still needs with the exact install line. Walk the user through those lines (`ar.py check` re-checks). Never print, echo or write the key anywhere. `ar.py whoami` shows the project later. Expired or used code: ask for a fresh one.

## 2. Deliver

1. Before uploading a reel/short, run `reel-qc` on it. A FAIL blocks the upload.
2. Open the request once per batch: `ar.py request "TITLE" REF` (REF = any stable id, e.g. the card id; same REF = same request). Keep `request_id`, `upload_token`, `review_url`.
3. Upload each file: `push.py FILE --request UPLOAD_TOKEN`. A fix to an existing file: add `--asset ASSET_ID` (it becomes v2, v3, …). Interrupted? Run the same command again; it resumes.
4. Tell the user in one line: "Feedback bitte hier: REVIEW_URL". Nothing else for them to do.

## 3. Wait, fix, repeat (never ask the user to come back and say "done")

1. Start the watcher with `run_in_background`, from the work dir: `watch.py --request REQUEST_ID`. It exits when the reviewer presses Send on a video, or 5 minutes after their last comment. Its exit wakes you; don't poll its output.
2. On wake read the printed notes: timecode, text, where they drew (x/y range of the frame). Full JSON is in `feedback-<round>.json`.
3. Apply every note. A note on one hook applies to the other hooks of the batch too, unless it names one scene. Re-run `reel-qc`, push each changed file with `--asset`.
4. `watch.py --ack ROUND_ID`, post the link again, back to step 1. Stop when the reviewer approves.

Several sessions can share one key: always pass `--request`, never ack another request's round.

## Rules

- Never change script wording on your own; a note that asks for it is fine.
- Never approve; a human does.
- `403 revoked_agent_key`: stop and tell the user. Review stuck on "waiting" over 15 minutes: push the same file again with `--asset`.
