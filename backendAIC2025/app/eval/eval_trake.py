"""Eval harness cho TRAKE — chạy ma trận ablation (Run 1-6), tính metric, xuất .md/.csv.

CHẠY (in-process, trong container backend vì cần SearchEngine + Qdrant + model):
    docker compose exec backend-api python -m app.eval.eval_trake \
        --queries app/eval/queries_gt.json --out app/eval/out --runs all

Thư mục app/ được mount vào container -> sửa file này chỉ cần chạy lại, KHỎI rebuild.
Ground-truth (GT) lấy từ đáp án công khai AIC (xem app/eval/README.md để biết định dạng + converter).

Metric (khớp §1 tài liệu "Đánh giá Thuật toán TRAKE"):
  - Xếp hạng/độ phủ: Recall@K, SuccessRate@K, MRR, mAP (giả định 1 target/query).
  - Thứ tự & sai lệch thời gian: Kendall tau, Spearman rho, MATE (giây), Frame-tolerance hit T@delta.
  - Vận hành: latency end-to-end + breakdown (encode/tier1/tier2/tier3/qwen/combos), throughput.
Accuracy CẦN GT; nếu query không có GT -> chỉ tính vận hành/behavioral.
"""
import argparse
import csv
import json
import os
import statistics
import time

from ..config import Config
from ..services import trake_service


# --------------------------------------------------------------------------- #
# Ma trận ablation: mỗi Run = (override Config) + cờ đặc biệt.
# tier3 (Run4/5/6) chỉ thật sự chạy khi có VIDEO_ROOT + video trên máy; nếu không -> tự về case2.
# qwen (Run6) chỉ chạy khi TRAKE_QWEN_RERANK_ENABLED + có GPU/model; nếu không -> tự về thuật toán.
# --------------------------------------------------------------------------- #
RUNS = {
    "run1_greedy":  {"desc": "Baseline: ANN/event + ghép tham lam (No DP, No Refine)",
                     "greedy": True, "use_ocr_asr": False},
    "run2_dp":      {"desc": "Tier1+2 DP (keyframe-only, no multimodal)",
                     "cfg": {"TRAKE_TIER3_ENABLED": False, "TRAKE_QWEN_RERANK_ENABLED": False},
                     "use_ocr_asr": False},
    "run3_mm":      {"desc": "+Multimodal (OCR/ASR soft-boost + injection)",
                     "cfg": {"TRAKE_TIER3_ENABLED": False, "TRAKE_QWEN_RERANK_ENABLED": False},
                     "use_ocr_asr": True},
    "run4_tier3_argmax": {"desc": "+Tier3 decode + rerank ARGMAX",
                     "cfg": {"TRAKE_TIER3_ENABLED": True, "TRAKE_RERANK_MODE": "argmax",
                             "TRAKE_QWEN_RERANK_ENABLED": False},
                     "use_ocr_asr": True},
    "run5_tier3_peak": {"desc": "+Tier3 decode + rerank PEAK prominence",
                     "cfg": {"TRAKE_TIER3_ENABLED": True, "TRAKE_RERANK_MODE": "peak",
                             "TRAKE_QWEN_RERANK_ENABLED": False},
                     "use_ocr_asr": True},
    "run6_full":    {"desc": "Full TRAKE: Tier3 peak + Qwen tie-break có điều kiện",
                     "cfg": {"TRAKE_TIER3_ENABLED": True, "TRAKE_RERANK_MODE": "peak",
                             "TRAKE_QWEN_RERANK_ENABLED": True},
                     "use_ocr_asr": True},
}
RUN_ORDER = list(RUNS.keys())
DEFAULT_KS = [1, 5, 10, 100]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def norm_vid(v):
    """So khớp video_id bất kể separator: 'L27_V012' == 'L27-V012' == 'l27v012'."""
    return str(v or "").strip().upper().replace("-", "").replace("_", "")


def translate_events(events, language):
    """Dịch vi->en nếu language=True (mô phỏng trake_controller). Lỗi/thiếu package -> giữ nguyên."""
    if not language:
        return events
    try:
        from deep_translator import GoogleTranslator
        return [GoogleTranslator(source="vi", target="en").translate(e) if e and e.strip() else e
                for e in events]
    except Exception:
        return events


def kendall_tau(a, b):
    """Kendall tau-a giữa 2 chuỗi cùng độ dài (O(n^2), không cần scipy)."""
    n = len(a)
    if n < 2:
        return None
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
    denom = n * (n - 1) / 2
    return (conc - disc) / denom if denom else None


def spearman_rho(a, b):
    """Spearman rho qua thứ hạng (đơn giản, giả định không trùng nhiều)."""
    n = len(a)
    if n < 2:
        return None
    def ranks(x):
        order = sorted(range(n), key=lambda i: x[i])
        r = [0] * n
        for rank, idx in enumerate(order):
            r[idx] = rank
        return r
    ra, rb = ranks(a), ranks(b)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - (6 * d2) / (n * (n * n - 1))


def combo_correct(pred_frames, gt_frames, tol):
    """Combo đúng nếu cùng độ dài và mỗi frame lệch <= tol so với GT (theo vị trí sự kiện)."""
    if len(pred_frames) != len(gt_frames):
        return False
    return all(abs(int(p) - int(g)) <= tol for p, g in zip(pred_frames, gt_frames))


# --------------------------------------------------------------------------- #
# Greedy baseline (Run 1): ANN/event, chọn video được nhiều event nhất, top-1/event, KHÔNG ràng buộc thứ tự.
# --------------------------------------------------------------------------- #
def run_greedy(events_text, engine, model, top_m, max_combos):
    t0 = time.perf_counter()
    t_enc = time.perf_counter()
    vecs = trake_service.encode_events(events_text, engine, model)
    enc = time.perf_counter() - t_enc

    t_s = time.perf_counter()
    by_video = {}  # vid -> {j: [(fid, score)]}
    meta = {}
    for j, v in enumerate(vecs):
        if v is None:
            continue
        for h in trake_service._qdrant_query(engine, model, v, top_m):
            vid, fid = h.get("video_id"), h.get("frame_id")
            if vid is None or fid is None:
                continue
            by_video.setdefault(vid, {}).setdefault(j, []).append((int(fid), float(h["score"])))
            meta.setdefault(vid, h)
    if not by_video:
        return {"ok": False, "submissions": [], "timings": {"total": time.perf_counter() - t0}}
    # chọn video: nhiều event nhất, tie-break tổng điểm top-1/event
    def vscore(vid):
        evs = by_video[vid]
        return (len(evs), sum(max(s for _, s in evs[j]) for j in evs))
    best = max(by_video, key=vscore)
    evs = by_video[best]
    combo = [max(evs[j], key=lambda t: t[1])[0] if j in evs else -1
             for j in range(len(vecs))]
    tier1 = time.perf_counter() - t_s
    return {
        "ok": True, "mode": "greedy", "tier": 0,
        "submissions": [{"video_id": best, "frame_ids": combo}],
        "video_candidates": [{"video_id": best}],
        "per_video": [{"video_id": best, "fps": meta.get(best, {}).get("fps")}],
        "qwen_rerank_used_events": 0,
        "timings": {"encode": round(enc, 4), "tier1": round(tier1, 4),
                    "tier2": 0.0, "tier3": 0.0, "qwen": 0.0, "combos": 0.0,
                    "total": round(time.perf_counter() - t0, 4)},
    }


# --------------------------------------------------------------------------- #
# Config override context
# --------------------------------------------------------------------------- #
class override_cfg:
    def __init__(self, cfg):
        self.cfg = cfg or {}
        self.saved = {}

    def __enter__(self):
        for k, v in self.cfg.items():
            self.saved[k] = getattr(Config, k, None)
            setattr(Config, k, v)

    def __exit__(self, *a):
        for k, v in self.saved.items():
            setattr(Config, k, v)


# --------------------------------------------------------------------------- #
# Chạy 1 query dưới 1 Run
# --------------------------------------------------------------------------- #
def eval_query(q, run_key, engine, ks, tol):
    spec = RUNS[run_key]
    events = [str(e or "") for e in q.get("events", [])]
    lang = bool(q.get("language", False))
    model = q.get("model") or "beit3"
    events_text = translate_events(events, lang)
    use_mm = spec.get("use_ocr_asr", False)
    ev_ocr = q.get("events_ocr") if use_mm else None
    ev_asr = q.get("events_asr") if use_mm else None

    top_m = Config.TRAKE_TOP_M
    max_combos = Config.TRAKE_MAX_COMBOS

    if spec.get("greedy"):
        res = run_greedy(events_text, engine, model, top_m, max_combos)
    else:
        with override_cfg(spec.get("cfg")):
            res = trake_service.run_trake(
                events_text=events_text, engine=engine, model=model,
                events_ocr=ev_ocr, events_asr=ev_asr,
                max_event_gap_s=q.get("max_event_gap_s"),
            )

    out = {"ok": bool(res.get("ok")), "timings": res.get("timings", {}),
           "mode": res.get("mode"), "tier": res.get("tier"),
           "qwen_used": res.get("qwen_rerank_used_events", 0),
           "n_submissions": len(res.get("submissions", [])),
           "n_video_cand": len(res.get("video_candidates", []))}

    gt = q.get("gt")
    if not gt:
        out["has_gt"] = False
        return out
    out["has_gt"] = True

    subs = res.get("submissions", [])
    gt_vid = norm_vid(gt.get("video_id"))
    gt_frames = [int(x) for x in gt.get("frame_ids", [])]
    fps = float(gt.get("fps") or (res.get("per_video") or [{}])[0].get("fps") or 25.0)

    # rank của combo đúng đầu tiên
    rank_correct = None
    for i, s in enumerate(subs):
        if norm_vid(s.get("video_id")) == gt_vid and combo_correct(s.get("frame_ids", []), gt_frames, tol):
            rank_correct = i + 1
            break
    out["rank_correct"] = rank_correct
    out["recall_at"] = {k: int(rank_correct is not None and rank_correct <= k) for k in ks}
    out["mrr"] = (1.0 / rank_correct) if rank_correct else 0.0
    out["ap"] = (1.0 / rank_correct) if rank_correct else 0.0  # 1 target/query

    # temporal: combo top-1 của ĐÚNG video (nếu có) để đo sai lệch thời gian
    pred = next((s.get("frame_ids", []) for s in subs if norm_vid(s.get("video_id")) == gt_vid), None)
    if pred and len(pred) == len(gt_frames) and gt_frames:
        diffs = [abs(int(p) - int(g)) for p, g in zip(pred, gt_frames)]
        out["mate_s"] = (sum(diffs) / len(diffs)) / fps if fps else None
        out["thit"] = sum(1 for d in diffs if d <= tol) / len(diffs)
        out["kendall"] = kendall_tau(pred, gt_frames)
        out["spearman"] = spearman_rho(pred, gt_frames)
        out["video_hit"] = 1
    else:
        out["video_hit"] = int(any(norm_vid(s.get("video_id")) == gt_vid for s in subs))
    return out


# --------------------------------------------------------------------------- #
# Tổng hợp + xuất
# --------------------------------------------------------------------------- #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def aggregate(rows, ks):
    gt_rows = [r for r in rows if r.get("has_gt")]
    agg = {"n": len(rows), "n_gt": len(gt_rows)}
    # accuracy
    for k in ks:
        agg[f"R@{k}"] = _mean([r["recall_at"][k] for r in gt_rows]) if gt_rows else None
    agg["MRR"] = _mean([r["mrr"] for r in gt_rows]) if gt_rows else None
    agg["mAP"] = _mean([r["ap"] for r in gt_rows]) if gt_rows else None
    agg["VideoHit"] = _mean([r.get("video_hit", 0) for r in gt_rows]) if gt_rows else None
    # temporal
    agg["MATE_s"] = _mean([r.get("mate_s") for r in gt_rows])
    agg["T@tol"] = _mean([r.get("thit") for r in gt_rows])
    agg["Kendall"] = _mean([r.get("kendall") for r in gt_rows])
    agg["Spearman"] = _mean([r.get("spearman") for r in gt_rows])
    # latency (giây) breakdown
    for key in ["encode", "tier1", "tier2", "tier3", "qwen", "combos", "total"]:
        agg[f"t_{key}"] = _mean([r["timings"].get(key) for r in rows if r.get("timings")])
    tot = agg.get("t_total")
    agg["QPS"] = (1.0 / tot) if tot else None
    # behavioral
    agg["qwen_used"] = _mean([r.get("qwen_used", 0) for r in rows])
    agg["n_subs"] = _mean([r.get("n_submissions", 0) for r in rows])
    return agg


def fmt(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def write_markdown(path, per_run, ks, meta):
    L = []
    L.append("# Kết quả eval TRAKE\n")
    L.append(f"- Thời điểm: {meta['ts']}")
    L.append(f"- Số query: {meta['n_queries']} (có GT: {meta['n_gt']})")
    L.append(f"- Tolerance khung hình: ±{meta['tol']} frame · K = {ks}")
    L.append(f"- tier3_globally_ready: **{meta['tier3_ready']}** · qwen_globally_ready: **{meta['qwen_ready']}**")
    if not meta["tier3_ready"]:
        L.append("  > ⚠️ Không có VIDEO_ROOT/video -> Run4/5/6 tự về case2 (không tinh chỉnh tầng 3); số accuracy của chúng sẽ ~ Run3.")
    L.append("")

    # Bảng 1: xếp hạng & độ phủ
    L.append("## 1. Xếp hạng & độ phủ tổ hợp")
    hdr = ["Run", "mô tả"] + [f"R@{k}" for k in ks] + ["MRR", "mAP", "VideoHit"]
    L.append("| " + " | ".join(hdr) + " |")
    L.append("|" + "|".join(["---"] * len(hdr)) + "|")
    for rk in RUN_ORDER:
        if rk not in per_run:
            continue
        a = per_run[rk]
        row = [rk, RUNS[rk]["desc"]] + [fmt(a.get(f"R@{k}")) for k in ks] + [fmt(a.get("MRR")), fmt(a.get("mAP")), fmt(a.get("VideoHit"))]
        L.append("| " + " | ".join(row) + " |")
    L.append("")

    # Bảng 2: thứ tự & sai lệch thời gian
    L.append("## 2. Thứ tự & sai lệch thời gian")
    hdr = ["Run", "MATE (s)", f"T@±{meta['tol']}f", "Kendall τ", "Spearman ρ"]
    L.append("| " + " | ".join(hdr) + " |")
    L.append("|" + "|".join(["---"] * len(hdr)) + "|")
    for rk in RUN_ORDER:
        if rk not in per_run:
            continue
        a = per_run[rk]
        L.append("| " + " | ".join([rk, fmt(a.get("MATE_s")), fmt(a.get("T@tol")), fmt(a.get("Kendall")), fmt(a.get("Spearman"))]) + " |")
    L.append("")

    # Bảng 3: hiệu năng vận hành (giây)
    L.append("## 3. Hiệu năng vận hành — latency breakdown (giây, trung bình/query)")
    hdr = ["Run", "encode", "tier1", "tier2", "tier3", "qwen", "combos", "total", "QPS"]
    L.append("| " + " | ".join(hdr) + " |")
    L.append("|" + "|".join(["---"] * len(hdr)) + "|")
    for rk in RUN_ORDER:
        if rk not in per_run:
            continue
        a = per_run[rk]
        L.append("| " + " | ".join([rk] + [fmt(a.get(f"t_{k}")) for k in ["encode", "tier1", "tier2", "tier3", "qwen", "combos", "total"]] + [fmt(a.get("QPS"), 2)]) + " |")
    L.append("")

    L.append("## 4. Behavioral")
    L.append("| Run | #submissions tb | qwen events tb |")
    L.append("|---|---|---|")
    for rk in RUN_ORDER:
        if rk not in per_run:
            continue
        a = per_run[rk]
        L.append(f"| {rk} | {fmt(a.get('n_subs'),1)} | {fmt(a.get('qwen_used'),2)} |")
    L.append("")
    L.append("> Ghi chú: accuracy chỉ tính trên query có GT. Nếu số MATE/Kendall rỗng (-) nghĩa là combo đúng-video có độ dài khác GT hoặc không tìm thấy đúng video.")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def write_csv(path, per_run, ks):
    cols = ["run", "desc"] + [f"R@{k}" for k in ks] + ["MRR", "mAP", "VideoHit",
            "MATE_s", "T@tol", "Kendall", "Spearman",
            "t_encode", "t_tier1", "t_tier2", "t_tier3", "t_qwen", "t_combos", "t_total", "QPS",
            "n_subs", "qwen_used", "n_gt"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for rk in RUN_ORDER:
            if rk not in per_run:
                continue
            a = per_run[rk]
            row = [rk, RUNS[rk]["desc"]] + [a.get(f"R@{k}") for k in ks] + [
                a.get("MRR"), a.get("mAP"), a.get("VideoHit"), a.get("MATE_s"), a.get("T@tol"),
                a.get("Kendall"), a.get("Spearman"), a.get("t_encode"), a.get("t_tier1"),
                a.get("t_tier2"), a.get("t_tier3"), a.get("t_qwen"), a.get("t_combos"),
                a.get("t_total"), a.get("QPS"), a.get("n_subs"), a.get("qwen_used"), a.get("n_gt")]
            w.writerow(row)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Eval harness TRAKE (ablation Run 1-6).")
    ap.add_argument("--queries", required=True, help="JSON list các query (+gt). Xem README.")
    ap.add_argument("--out", default="app/eval/out", help="Thư mục xuất .md/.csv")
    ap.add_argument("--runs", default="all", help="'all' hoặc danh sách ngăn cách dấu phẩy, vd run2_dp,run5_tier3_peak")
    ap.add_argument("--k", default="1,5,10,100", help="Các mốc K cho Recall@K")
    ap.add_argument("--tol-frames", type=int, default=25, help="Cửa sổ dung sai khung hình cho 'đúng'")
    args = ap.parse_args()

    ks = [int(x) for x in args.k.split(",") if x.strip()]
    run_keys = RUN_ORDER if args.runs == "all" else [r.strip() for r in args.runs.split(",") if r.strip() in RUNS]
    os.makedirs(args.out, exist_ok=True)

    with open(args.queries, encoding="utf-8") as f:
        queries = json.load(f)
    print(f"[eval] {len(queries)} query, runs={run_keys}, K={ks}, tol=±{args.tol_frames}f")

    from ..controllers.qdrant_controller import _get_engine
    engine = _get_engine()

    # Warmup: nạp sẵn model để KHÔNG tính thời gian load vào query đầu (tránh lệch latency).
    for m in {(q.get("model") or "beit3") for q in queries}:
        try:
            engine.registry.encode_text("warmup", m)
            print(f"[warmup] model {m} sẵn sàng")
        except Exception as e:
            print(f"[warmup] {m} lỗi: {e}")

    tier3_ready, _ = trake_service.tier3_globally_ready()
    qwen_ready, _ = trake_service.qwen_rerank_ready()

    per_run = {}
    for rk in run_keys:
        print(f"\n[run] {rk} — {RUNS[rk]['desc']}")
        rows = []
        for i, q in enumerate(queries):
            try:
                r = eval_query(q, rk, engine, ks, args.tol_frames)
            except Exception as e:
                print(f"  ! query {i} lỗi: {e}")
                continue
            rows.append(r)
            tag = f"rank={r.get('rank_correct')}" if r.get("has_gt") else "no-gt"
            print(f"  q{i}: ok={r['ok']} {tag} t_total={r['timings'].get('total')}s mode={r.get('mode')}")
        per_run[rk] = aggregate(rows, ks)

    meta = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "n_queries": len(queries),
            "n_gt": sum(1 for q in queries if q.get("gt")), "tol": args.tol_frames,
            "tier3_ready": tier3_ready, "qwen_ready": qwen_ready}
    md, csvp = os.path.join(args.out, "eval_results.md"), os.path.join(args.out, "eval_results.csv")
    write_markdown(md, per_run, ks, meta)
    write_csv(csvp, per_run, ks)
    print(f"\n[done] -> {md}\n        -> {csvp}")


if __name__ == "__main__":
    main()
