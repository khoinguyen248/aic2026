# TRAKE verification UI — proposal for team review

> This file collects the UI ideas for the TRAKE part of the **preliminary round** (manual search →
> fill in the answer sheet) so the team can comment before anyone writes code. Not final.
> Related: [README_TRAKE.md](README_TRAKE.md) (the TRAKE pipeline) and §10.3 of
> `AIC2026_IMPROVEMENT_SPEC (1).md`.

---

## 1. The problem

Every TRAKE question requires submitting `video_id, frame_1, ..., frame_N` (up to 100 combinations).
**Nobody wants to collect frames by hand** the way we did last year — scrubbing the YouTube video and
computing `time × fps` to get a frame number. The `/search/trake` pipeline already **produces 100
ranked combinations automatically**, but the machine can still pick the wrong frame, so we **need to
look at the real frames and verify manually** before filling in the sheet.

Goal of the UI: **press TRAKE Search → see the list of combinations → click one → see exactly those
frames for a human to check.**

---

## 2. Two kinds of machine, two ways to verify (important)

Team machines fall into two categories and the UI has to serve both **in one interface**:

| | Machine running **3 tiers** (has the videos, e.g. on USB) | Machine running **2 tiers** (no videos) |
|---|---|---|
| Submitted frame | refined source frame (frame-exact) | keyframe-level frame |
| Image for verification | **decoded straight from the video** at that frame | **our own dense keyframe** image already on disk |
| How to pin it down | looking at the source frame is enough | YouTube link at `time = frame_id/fps` plus the **YouTube Milliseconds Timestamp** extension to convert ms → frame, together with a ±10 frame viewer |

**Note for this year:** we **cut our own frames instead of using the organizers' set → denser and
finer**, so the 2-tier result already lands much closer to the `<10 frame` answer window than last
year. A 2-tier machine is no longer at a serious disadvantage; 3 tiers is still the most accurate.

Extension used on 2-tier machines:
`https://chromewebstore.google.com/detail/youtube-milliseconds-time/bchlendkhiidadpakkfgnpeklmifffcp`

---

## 3. Proposed UI flow

```
[Mode: TRAKE]                     ← the selectAns dropdown already exists in Jobs.jsx
┌───────────────────────────────────────────────┐
│ Event 1: [athlete plants the take-off foot..]  │
│ Event 2: [clears the bar...................]  │   ← enter N events in chronological order
│ Event 3: [lands on the mat.................]  │
│ [+ add event]             [ TRAKE Search ]     │
├───────────────────────────────────────────────┤
│ Results (ranked combinations, up to 100):      │
│ #1  L21_V001 → 1000, 1007, 1008, 1025   [view▸]│   ← click a combination
│ #2  L21_V001 → 1000, 1007, 1009, 1025   [view▸]│
│ #3  L21_V001 → 1000, 1006, 1008, 1025   [view▸]│
└───────────────────────────────────────────────┘
        │ click "view" on #1 → expand a frame grid for verification
        ▼
   ┌──────────┬──────────┬──────────┬──────────┐
   │ [image]  │ [image]  │ [image]  │ [image]  │
   │ f1000    │ f1007    │ f1008    │ f1025    │
   │ event1   │ event2   │ event3   │ event4   │
   │ 0m40s    │ 0m40s    │ 0m40s    │ 0m41s    │
   │ ▶YouTube │ ▶YouTube │ ▶YouTube │ ▶YouTube │   ← link at the exact time (with the ms extension)
   │ ±10      │ ±10      │ ±10      │ ±10      │   ← open the ±10 frame viewer (Infor.jsx)
   └──────────┴──────────┴──────────┴──────────┘
```

---

## 4. The key technical point: how to display a frame

The current UI only serves **static keyframe files** over
`http://localhost:8080/keyframes/...` ([server.js](backend-framesAIC2025/server.js)), so it can only
show keyframes that exist on disk. A tier-3 frame (say `1007`) sits **between two keyframes → no image
file exists** and cannot be shown this way.

**Solution: one unified image endpoint** `GET /search/frame?video_id=..&frame_id=..`:

1. If `frame_id` **matches a keyframe** (looked up in Mongo) → return our dense keyframe image (fast —
   this is the 2-tier path).
2. If it **does not** (a refined tier-3 frame) → **decode it from the video** with OpenCV (the 3-tier
   path).

→ One UI that adapts to whether videos are present, instead of two separate versions.

---

## 5. Small backend changes needed

- **Enrich `/search/trake`**: also return the `fps` and `video_url` of the chosen video (both already
  come from the Mongo query, just carry two more fields) so the UI can compute `time = frame_id/fps`
  for the YouTube link and the ±10 viewer.
- **Add `/search/frame`** as described in §4, reusing `resolve_video_path()` and `VIDEO_ROOT`, which
  already exist in `trake_service.py`.

---

## 6. What can be reused from the current UI

- **YouTube link at a timestamp** `&t=${time}s` — already in
  [Jobs.jsx](frontend-final/vite-project/src/Jobs.jsx) and
  [Infor.jsx](frontend-final/vite-project/src/Infor.jsx). That is where the ms extension plugs in.
- **±10 frame viewer** — [Infor.jsx](frontend-final/vite-project/src/Infor.jsx) is ready, it just needs
  to be called again.
- **Mode gating** — `selectAns == "trake"` already exists in
  [Jobs.jsx](frontend-final/vite-project/src/Jobs.jsx).
- **Image grid styling** — reuse the `gridTemplateColumns: repeat(N,1fr)` + `<img>` pattern from
  Infor.jsx.

---

## 7. Estimated work

| Area | Work |
|---|---|
| Backend | Enrich `/search/trake` (add `fps`, `video_url`) and add the `/search/frame` endpoint |
| Frontend | One TRAKE panel component: enter N events → list combinations → click one to expand the frame grid (reusing the YouTube link and ±10 viewer) |
| Untouched | The KIS/QA flows stay as they are |

---

## 8. Decisions needed from the team

1. TRAKE panel: **wire it straight into [Jobs.jsx](frontend-final/vite-project/src/Jobs.jsx)** (shown
   when TRAKE mode is selected), or give it its own tab/page?
2. Expanding frames on click: **inline** (right under the combination row) or **modal overlay** (like
   Infor.jsx)?
3. Do we want a "copy combination" button for pasting into the sheet, or is visual verification enough?
4. On 2-tier machines: always show the dense keyframe image, or is the YouTube link plus the ±10 viewer
   sufficient?

---

## 9. Known issue to fix

- [server.js](backend-framesAIC2025/server.js) **hard-codes** the keyframe path
  `C:/Users/PC/Downloads/...` (someone else's machine). Point it at your own dense frame folder or the
  keyframe images will not load. In the Docker setup this is already handled: the container serves
  `/data/keyframes`, bind-mounted from `runtime-data/keyframes`.
