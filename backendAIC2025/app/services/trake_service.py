# app/services/trake_service.py
"""TRAKE: chọn video (DP alignment) -> định vị thô từng event -> tinh chỉnh frame gốc
(tùy khả năng đọc video) -> sinh tổ hợp Cartesian để nộp tối đa 100 combo.

Case 1 (đủ video gốc, vd đọc từ USB): tier3_globally_ready() = True -> tinh chỉnh tới
frame gốc trong cửa sổ [f-R, f+R] quanh vị trí thô.
Case 2 (không có video gốc): tự động rơi về độ phân giải keyframe (không tinh chỉnh).
Việc chuyển case là tự động theo cấu hình + sự tồn tại thật của file video, không cần
sửa code khi đổi máy.

Rerank khoảnh khắc trong tầng 3 cũng tự swap tương tự: mặc định dùng thuật toán
(pick_semantic_frame_algorithmic - peak/prominence trên đường cong điểm số, miễn phí);
chỉ gọi Qwen2.5-VL (qwen_rerank_candidates) khi 2+ ứng viên đầu tie sít sao VÀ
TRAKE_QWEN_RERANK_ENABLED=true VÀ QWEN_API_BASE_URL đã cấu hình - có fallback an toàn
về thuật toán nếu Qwen lỗi/timeout.
"""
import base64
import logging
import os
from io import BytesIO
from itertools import product
from math import prod

import faiss
import numpy as np
import torch
from PIL import Image

from ..config import Config

logger = logging.getLogger(__name__)

NEG_INF = float("-inf")

# §10.3.1: ngân sách ứng viên/mỗi event sao cho tích Descartes không vượt quá 100 tổ hợp.
_CANDIDATE_BUDGET = {2: 10, 3: 4, 4: 3, 5: 3, 6: 2}


def candidate_budget(n_events: int) -> int:
    if n_events in _CANDIDATE_BUDGET:
        return _CANDIDATE_BUDGET[n_events]
    return 2 if n_events <= 10 else 1


# ---------------------------------------------------------------------------
# Encode text / ảnh bằng CLIP (leg duy nhất đã sẵn sàng end-to-end trong repo này:
# có preprocess + encode_image + encode_text cùng không gian. BEiT-3 hiện thiếu
# package `beit3/` nên chưa dùng được cho TRAKE — xem README/ghi chú PR).
# ---------------------------------------------------------------------------

def encode_texts(texts, clip_bundle, device="cpu"):
    clip_model, tokenizer, _preprocess = clip_bundle
    clip_model = clip_model.to(device)
    clip_model.eval()
    with torch.inference_mode():
        tokens = tokenizer(texts).to(device)
        emb = clip_model.encode_text(tokens)
    emb = emb.cpu().detach().numpy().astype(np.float32)
    faiss.normalize_L2(emb)
    return emb


def encode_images(pil_images, clip_bundle, device="cpu"):
    clip_model, _tokenizer, preprocess = clip_bundle
    clip_model = clip_model.to(device)
    clip_model.eval()
    batch = torch.stack([preprocess(img) for img in pil_images]).to(device)
    with torch.inference_mode():
        emb = clip_model.encode_image(batch)
    emb = emb.cpu().detach().numpy().astype(np.float32)
    faiss.normalize_L2(emb)
    return emb


# ---------------------------------------------------------------------------
# Tầng 1 — chọn video bằng DP đơn điệu trên top-M ứng viên toàn kho của mỗi event.
# ---------------------------------------------------------------------------

def _dp_align(events_sorted):
    """events_sorted[j] = list[(idx, sim)] của event j, đã sort theo idx tăng dần.
    Trả về (best_cum_score, path idx theo từng event) ép idx tăng dần qua các event.
    """
    n = len(events_sorted)
    layers = [[(idx, sim, None) for idx, sim in events_sorted[0]]]

    for j in range(1, n):
        prev_sorted = sorted(layers[j - 1], key=lambda x: x[0])
        cur_layer = []
        for idx, sim in events_sorted[j]:
            best_prev_cum, best_prev_idx = NEG_INF, None
            for p_idx, p_cum, _ in prev_sorted:
                if p_idx >= idx:
                    break
                if p_cum > best_prev_cum:
                    best_prev_cum, best_prev_idx = p_cum, p_idx
            if best_prev_idx is None:
                continue
            cur_layer.append((idx, sim + best_prev_cum, best_prev_idx))
        layers.append(cur_layer)
        if not cur_layer:
            return NEG_INF, []

    idx_last, best_cum, _ = max(layers[-1], key=lambda x: x[1])
    path = [idx_last]
    cur_idx = idx_last
    for j in range(n - 1, 0, -1):
        entry = next(e for e in layers[j] if e[0] == cur_idx)
        cur_idx = entry[2]
        path.append(cur_idx)
    path.reverse()
    return best_cum, path


def select_video_dp(event_vecs, faiss_index, mongo_collection, top_m=150, top_videos=2):
    """Tầng 1: mỗi event tìm top-M toàn kho (FAISS IndexFlat = brute-force, chính xác
    tuyệt đối trong top-M đó), gom theo video, DP đơn điệu để chọn video khớp nhất.
    Chỉ giữ video xuất hiện đủ trong top-M của TẤT CẢ event (nếu rỗng, gọi lại với
    top_m lớn hơn ở tầng orchestrator).
    """
    query_matrix = np.stack(event_vecs).astype(np.float32)
    sims, ids = faiss_index.search(query_matrix, top_m)

    all_ids = sorted({int(i) for row in ids for i in row if i != -1})
    if not all_ids:
        return []

    docs = mongo_collection.find({"idx": {"$in": all_ids}}, {"_id": 0, "idx": 1, "L": 1, "V": 1})
    id_to_video = {d["idx"]: (d.get("L"), d.get("V")) for d in docs}

    per_video = {}
    n_events = len(event_vecs)
    for j in range(n_events):
        for score, cand_id in zip(sims[j], ids[j]):
            if cand_id == -1:
                continue
            vid = id_to_video.get(int(cand_id))
            if vid is None:
                continue
            per_video.setdefault(vid, {}).setdefault(j, []).append((int(cand_id), float(score)))

    results = []
    for vid, per_event in per_video.items():
        if len(per_event) < n_events:
            continue  # thiếu event -> video này không đủ dữ liệu để DP công bằng
        events_sorted = [sorted(per_event[j], key=lambda p: p[0]) for j in range(n_events)]
        best_score, path = _dp_align(events_sorted)
        if best_score == NEG_INF:
            continue
        results.append({"L": vid[0], "V": vid[1], "score": best_score, "coarse_idx_path": path})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_videos]


def softmax_probs(scores):
    scores = np.array(scores, dtype=np.float64)
    scores = scores - scores.max()
    exp = np.exp(scores)
    return exp / exp.sum()


def allocate_video_slots(video_candidates, total_slots=100, confidence_threshold=0.8):
    """§10.3.1 bẫy 3: không dồn hết slot cho 1 video khi chưa chắc chắn."""
    if not video_candidates:
        return []
    if len(video_candidates) == 1:
        return [(video_candidates[0], total_slots)]

    probs = softmax_probs([v["score"] for v in video_candidates])
    if probs[0] >= confidence_threshold:
        return [(video_candidates[0], total_slots)]

    v1, v2 = video_candidates[0], video_candidates[1]
    share_v2 = probs[1] / (probs[0] + probs[1])
    slot_v2 = max(1, int(round(total_slots * share_v2)))
    slot_v1 = total_slots - slot_v2
    return [(v1, slot_v1), (v2, slot_v2)]


# ---------------------------------------------------------------------------
# Tầng 2 — định vị chính xác từng event trong video đã chọn (không cần Qdrant filter:
# reconstruct thẳng vector từ FAISS flat index cho đúng các keyframe của video đó).
# ---------------------------------------------------------------------------

def locate_events_exact(event_vecs, faiss_index, mongo_collection, L, V, topk=3):
    docs = list(
        mongo_collection.find({"L": L, "V": V}, {"_id": 0, "idx": 1, "frame_id": 1, "fps": 1}).sort("idx", 1)
    )
    if not docs:
        return []

    idxs = np.array([d["idx"] for d in docs], dtype=np.int64)
    vecs = np.stack([faiss_index.reconstruct(int(i)) for i in idxs]).astype(np.float32)

    results = []
    prev_pos = -1
    for ev_vec in event_vecs:
        scores = vecs @ ev_vec
        masked = scores.copy()
        if prev_pos >= 0:
            masked[: prev_pos + 1] = NEG_INF
        valid = np.where(np.isfinite(masked))[0]
        if len(valid) == 0:
            valid = np.arange(len(scores))
            masked = scores
        order = valid[np.argsort(-masked[valid])][:topk]

        cands = [
            {
                "idx": int(idxs[p]),
                "frame_id": docs[p].get("frame_id"),
                "fps": docs[p].get("fps"),
                "score": float(scores[p]),
            }
            for p in order
        ]
        results.append(cands)
        prev_pos = int(order[0])

    return results


# ---------------------------------------------------------------------------
# Tầng 3 — tinh chỉnh trên frame gốc (chỉ chạy khi có video thật, ±R frame quanh
# vị trí thô, decode bằng OpenCV seek trực tiếp, không đọc cả video).
# ---------------------------------------------------------------------------

def tier3_globally_ready():
    if not Config.TRAKE_TIER3_ENABLED:
        return False, "TRAKE_TIER3_ENABLED=false -> case 2 (không tinh chỉnh)"
    if not Config.VIDEO_ROOT or not os.path.isdir(Config.VIDEO_ROOT):
        return False, f"VIDEO_ROOT không tồn tại (USB chưa gắn?): {Config.VIDEO_ROOT!r}"
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False, "opencv-python (cv2) chưa được cài trong môi trường này"
    return True, "tier 3 sẵn sàng"


def resolve_video_path(L, V, mongo_collection):
    root = Config.VIDEO_ROOT
    if not root or not os.path.isdir(root):
        return None

    sample = mongo_collection.find_one({"L": L, "V": V}, {"_id": 0, "video_url": 1}) or {}
    video_url = sample.get("video_url") or ""

    candidates = []
    if video_url and not video_url.startswith(("http://", "https://")):
        candidates.append(os.path.join(root, video_url))
        candidates.append(os.path.join(root, os.path.basename(video_url)))
    candidates += [
        os.path.join(root, f"L{L}_V{V}.mp4"),
        os.path.join(root, f"{L}_{V}.mp4"),
        os.path.join(root, str(L), f"{V}.mp4"),
        os.path.join(root, str(L), f"V{V}.mp4"),
    ]

    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def pick_semantic_frame_algorithmic(frame_ids, scores, topk):
    """Rerank thuật toán, không cần model rời: thay vì chỉ argmax điểm cosine, ưu tiên
    frame nào là ĐỈNH RÕ RỆT (prominence cao) trên đường cong điểm số theo thời gian —
    tách được "khoảnh khắc" khỏi 1 dải phẳng nhiều frame gần giống hệt nhau mà cosine
    không phân biệt nổi. Nếu thiếu scipy hoặc không tìm được đỉnh nào, rơi về argmax
    thường (hành vi y hệt bản cũ trước khi có hàm này -> không bao giờ tệ hơn)."""
    scores = np.asarray(scores, dtype=np.float64)

    if len(scores) >= 3:
        try:
            from scipy.signal import find_peaks

            peaks, props = find_peaks(scores, prominence=0)
            if len(peaks) > 0:
                ranked_peaks = sorted(
                    zip(peaks.tolist(), props["prominences"].tolist()),
                    key=lambda p: (-p[1], -scores[p[0]]),
                )
                ranked_idx = [p[0] for p in ranked_peaks]
                remaining = [i for i in np.argsort(-scores).tolist() if i not in ranked_idx]
                ranked_idx = (ranked_idx + remaining)[:topk]
                return [(int(frame_ids[i]), float(scores[i])) for i in ranked_idx]
        except ImportError:
            pass

    order = np.argsort(-scores)[:topk]
    return [(int(frame_ids[i]), float(scores[i])) for i in order]


def qwen_rerank_ready():
    if not Config.TRAKE_QWEN_RERANK_ENABLED:
        return False, "TRAKE_QWEN_RERANK_ENABLED=false -> chỉ dùng thuật toán (peak detection)"
    if not Config.QWEN_API_BASE_URL:
        return False, "QWEN_API_BASE_URL chưa cấu hình -> chỉ dùng thuật toán"
    return True, "Qwen rerank sẵn sàng"


def qwen_rerank_candidates(frame_ids, frames_pil, event_text):
    """Gọi Qwen2.5-VL qua endpoint kiểu OpenAI-compatible (vLLM/Ollama tự host, DashScope, ...)
    để phân xử giữa vài frame gần tie theo điểm cosine. Trả None nếu lỗi/timeout bất kỳ ->
    caller PHẢI tự fallback về kết quả thuật toán, không được để trống kết quả vì lỗi mạng."""
    import requests

    try:
        content = [
            {
                "type": "text",
                "text": (
                    f'Trong các ảnh sau (đánh số theo đúng thứ tự thời gian), ảnh nào ĐÚNG khoảnh khắc: '
                    f'"{event_text}"? Chỉ trả về đúng 1 số thứ tự ảnh, không giải thích gì thêm.'
                ),
            }
        ]
        for i, img in enumerate(frames_pil):
            buf = BytesIO()
            img.save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            content.append({"type": "text", "text": f"Ảnh {i + 1}:"})
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        headers = {"Authorization": f"Bearer {Config.QWEN_API_KEY}"} if Config.QWEN_API_KEY else {}
        resp = requests.post(
            f"{Config.QWEN_API_BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": Config.QWEN_MODEL_NAME,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=Config.QWEN_RERANK_TIMEOUT,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            picked = int(digits[:2])
            if 1 <= picked <= len(frame_ids):
                return frame_ids[picked - 1]
    except Exception as e:
        logger.warning("Qwen rerank thất bại (%s) -> fallback thuật toán", e)
    return None


def refine_event_fine(video_path, ev_vec, event_text, coarse_frame_id, prev_fine_frame_id, clip_bundle, device, radius, stride, topk):
    """Trả về (candidates, used_qwen). candidates=None nếu không đọc được video (caller tự
    fallback độ phân giải keyframe)."""
    import cv2

    if coarse_frame_id is None:
        return None, False

    lo = coarse_frame_id - radius
    if prev_fine_frame_id is not None:
        lo = max(lo, prev_fine_frame_id + 1)  # giữ thứ tự thời gian giữa các event
    lo = max(lo, 0)
    hi = coarse_frame_id + radius
    if lo > hi:
        lo = hi

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, False

    cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
    frames, frame_ids = [], []
    cur = lo
    while cur <= hi:
        ok, frame = cap.read()
        if not ok:
            break
        if (cur - lo) % stride == 0:
            frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            frame_ids.append(cur)
        cur += 1
    cap.release()

    if not frames:
        return None, False

    embs = encode_images(frames, clip_bundle, device=device)
    scores = embs @ ev_vec
    ranked = pick_semantic_frame_algorithmic(frame_ids, scores, topk)

    used_qwen = False
    if len(ranked) >= 2 and abs(ranked[0][1] - ranked[1][1]) < Config.TRAKE_RERANK_TIE_MARGIN:
        ready, _reason = qwen_rerank_ready()
        if ready and event_text:
            tie = ranked[: min(len(ranked), 3)]
            tie_ids = [fid for fid, _ in tie]
            tie_frames = [frames[frame_ids.index(fid)] for fid in tie_ids]
            picked = qwen_rerank_candidates(tie_ids, tie_frames, event_text)
            if picked is not None:
                top_score = ranked[0][1]
                ranked = [(picked, top_score)] + [c for c in ranked if c[0] != picked]
                used_qwen = True

    return ranked, used_qwen


# ---------------------------------------------------------------------------
# §10.3.1 — sinh tổ hợp Cartesian từ top-k ứng viên mỗi event, xếp theo tích xác
# suất, lọc NMS thời gian + ràng buộc thứ tự tăng dần.
# ---------------------------------------------------------------------------

def nms_candidates(candidates, min_gap=15):
    """candidates: list[(frame_id, score)] đã sort giảm dần theo score."""
    kept = []
    for frame_id, score in candidates:
        if all(abs(frame_id - kept_id) >= min_gap for kept_id, _ in kept):
            kept.append((frame_id, score))
    return kept


def build_cartesian_submissions(candidates_per_event, max_combos=100, min_gap=15):
    cleaned = []
    for cands in candidates_per_event:
        cands_sorted = sorted(cands, key=lambda c: -c[1])
        cands_sorted = nms_candidates(cands_sorted, min_gap=min_gap)
        if not cands_sorted:
            return []  # event này không có ứng viên nào -> không thể nộp tổ hợp nào
        probs = softmax_probs([c[1] for c in cands_sorted])
        cleaned.append(list(zip([c[0] for c in cands_sorted], probs)))

    weighted_combos = []
    for combo in product(*cleaned):
        frame_ids = [c[0] for c in combo]
        if all(frame_ids[i] < frame_ids[i + 1] for i in range(len(frame_ids) - 1)):
            weight = prod(p for _, p in combo)
            weighted_combos.append((frame_ids, weight))

    weighted_combos.sort(key=lambda x: -x[1])
    return [c[0] for c in weighted_combos[:max_combos]]


# ---------------------------------------------------------------------------
# Orchestrator — chọn case 1/2 tự động theo tier3_globally_ready() + sự tồn tại
# thật của file video cho đúng video đã chọn.
# ---------------------------------------------------------------------------

def run_trake(
    events_text,
    clip_bundle,
    device,
    faiss_index,
    mongo_collection,
    top_m=None,
    top_videos=None,
    max_combos=None,
):
    top_m = top_m or Config.TRAKE_TOP_M
    top_videos = top_videos or Config.TRAKE_TOP_VIDEOS
    max_combos = min(max_combos or Config.TRAKE_MAX_COMBOS, 100)
    tier3_radius = Config.TRAKE_TIER3_RADIUS
    tier3_stride = Config.TRAKE_TIER3_STRIDE
    confidence_threshold = Config.TRAKE_VIDEO_CONFIDENCE_THRESHOLD
    tier3_topk = candidate_budget(len(events_text))

    event_vecs = encode_texts(events_text, clip_bundle, device=device)

    video_candidates, attempt_m = [], top_m
    for _ in range(3):
        video_candidates = select_video_dp(
            event_vecs, faiss_index, mongo_collection, top_m=attempt_m, top_videos=top_videos
        )
        if video_candidates:
            break
        attempt_m *= 3
    if not video_candidates:
        return {
            "ok": False,
            "error": "Không tìm được video khớp đủ tất cả event trong top-M ứng viên (đã thử tới top_m="
            f"{attempt_m}). Thử tăng top_m hoặc kiểm tra lại mô tả event.",
        }

    slots = allocate_video_slots(video_candidates, total_slots=max_combos, confidence_threshold=confidence_threshold)

    ready, reason = tier3_globally_ready()
    qwen_ready, qwen_reason = qwen_rerank_ready()

    per_video = []
    any_tier3 = False
    qwen_used_events_total = 0

    for video, slot_count in slots:
        if slot_count <= 0:
            continue
        L, V = video["L"], video["V"]

        coarse = locate_events_exact(event_vecs, faiss_index, mongo_collection, L, V, topk=tier3_topk)
        if not coarse:
            continue

        video_path = resolve_video_path(L, V, mongo_collection) if ready else None
        use_tier3 = ready and video_path is not None

        candidates_per_event = []
        qwen_used_events = 0
        if use_tier3:
            prev_fine = None
            for ev_vec, ev_text, cands in zip(event_vecs, events_text, coarse):
                fine, used_qwen = refine_event_fine(
                    video_path, ev_vec, ev_text, cands[0]["frame_id"], prev_fine, clip_bundle, device,
                    tier3_radius, tier3_stride, tier3_topk,
                )
                if fine is None:
                    fine = [(c["frame_id"], c["score"]) for c in cands if c.get("frame_id") is not None]
                if used_qwen:
                    qwen_used_events += 1
                candidates_per_event.append(fine)
                if fine:
                    prev_fine = fine[0][0]
            use_tier3 = bool(candidates_per_event) and all(candidates_per_event)
        else:
            for cands in coarse:
                fallback = [(c["frame_id"], c["score"]) for c in cands if c.get("frame_id") is not None]
                if not fallback:
                    fallback = [(c["idx"], c["score"]) for c in cands]  # frame_id thiếu -> nộp idx keyframe
                candidates_per_event.append(fallback)

        any_tier3 = any_tier3 or use_tier3
        qwen_used_events_total += qwen_used_events

        combos = build_cartesian_submissions(candidates_per_event, max_combos=slot_count)
        per_video.append(
            {
                "video_id": f"{L}_{V}",
                "L": L,
                "V": V,
                "video_score": video["score"],
                "tier3_used": use_tier3,
                "qwen_rerank_used_events": qwen_used_events,
                "combos": combos,
            }
        )

    submissions = []
    for r in per_video:
        for combo in r["combos"]:
            submissions.append({"video_id": r["video_id"], "frame_ids": combo})
    submissions = submissions[:max_combos]

    return {
        "ok": True,
        "mode": "case1_full" if any_tier3 else "case2_coarse",
        "tier3_globally_ready": ready,
        "tier3_reason": reason,
        "qwen_rerank_globally_ready": qwen_ready,
        "qwen_rerank_reason": qwen_reason,
        "qwen_rerank_used_events": qwen_used_events_total,
        "video_candidates": [
            {"video_id": f"{v['L']}_{v['V']}", "L": v["L"], "V": v["V"], "score": v["score"]}
            for v in video_candidates
        ],
        "per_video": per_video,
        "submissions": submissions,
    }
