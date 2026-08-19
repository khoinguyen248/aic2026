# Ý tưởng UI verify TRAKE — bản để team góp ý

> File này gom lại ý tưởng làm UI cho phần TRAKE ở **vòng sơ loại** (search tay → điền sheet đáp án),
> để cả team xem và cho ý kiến trước khi code. Chưa phải bản chốt.
> Liên quan: [README_TRAKE.md](README_TRAKE.md) (pipeline TRAKE), mục 10.3 trong `AIC2026_IMPROVEMENT_SPEC (1).md`.

---

## 1. Vấn đề cần giải

TRAKE mỗi câu phải nộp `video_id, frame_1, ..., frame_N` (tối đa 100 tổ hợp). **Không ai muốn gom
frame bằng tay** như năm ngoái (dò video YouTube, tính `time × fps` ra frame). Pipeline `/search/trake`
đã **tự sinh sẵn 100 tổ hợp xếp hạng**, nhưng máy vẫn có thể chọn nhầm frame → **cần xem lại frame
thật để verify thủ công cho chắc** trước khi điền vào sheet.

Mục tiêu UI: **bấm TRAKE Search → hiện danh sách tổ hợp → bấm 1 tổ hợp → hiện đúng các frame đó để
mắt người kiểm.**

---

## 2. Hai loại máy, hai cách verify (quan trọng)

Team có 2 kiểu máy khi chạy, UI phải phục vụ được cả hai trong **cùng một giao diện**:

| | Máy chạy **3 tầng** (có video, vd USB) | Máy chạy **2 tầng** (không có video) |
|---|---|---|
| Frame nộp | frame gốc đã tinh chỉnh (mịn tới từng frame) | frame ở mức keyframe |
| Ảnh để verify | **decode thẳng từ video** đúng frame đó | **ảnh keyframe dày** của mình (đã có trên đĩa) |
| Cách dò chính xác | xem ảnh frame gốc là đủ | link YouTube tại `time = frame_id/fps` + **extension YouTube Milliseconds Timestamp** để tính ms → suy ra frame; kèm viewer ±10 frame |

**Ghi chú năm nay:** tụi mình **tự cắt lại frame (không dùng của BTC) → frame dày & mịn hơn** → kết
quả 2 tầng đã gần/lọt cửa sổ đáp án `<10 frame` hơn hẳn năm ngoái. Nên máy 2 tầng năm nay **không
còn quá thiệt**; 3 tầng vẫn chính xác nhất.

Extension dùng cho máy 2 tầng:
`https://chromewebstore.google.com/detail/youtube-milliseconds-time/bchlendkhiidadpakkfgnpeklmifffcp`

---

## 3. Luồng UI đề xuất

```
[Mode: TRAKE]                     ← dropdown selectAns đã có sẵn trong Jobs.jsx
┌───────────────────────────────────────────────┐
│ Event 1: [vận động viên giậm nhảy...........]  │
│ Event 2: [bay qua xà........................]  │   ← nhập N event (theo thứ tự thời gian)
│ Event 3: [tiếp đất..........................]  │
│ [+ thêm event]            [ TRAKE Search ]     │
├───────────────────────────────────────────────┤
│ Kết quả (tổ hợp đã xếp hạng, tối đa 100):      │
│ #1  L21_V001 → 1000, 1007, 1008, 1025   [xem▸] │   ← bấm 1 tổ hợp
│ #2  L21_V001 → 1000, 1007, 1009, 1025   [xem▸] │
│ #3  L21_V001 → 1000, 1006, 1008, 1025   [xem▸] │
└───────────────────────────────────────────────┘
        │ bấm "xem" tổ hợp #1 → bung ra grid frame để verify
        ▼
   ┌──────────┬──────────┬──────────┬──────────┐
   │ [ảnh]    │ [ảnh]    │ [ảnh]    │ [ảnh]    │
   │ f1000    │ f1007    │ f1008    │ f1025    │
   │ event1   │ event2   │ event3   │ event4   │
   │ 0m40s    │ 0m40s    │ 0m40s    │ 0m41s    │
   │ ▶YouTube │ ▶YouTube │ ▶YouTube │ ▶YouTube │   ← link tại đúng time (cắm extension ms)
   │ ±10      │ ±10      │ ±10      │ ±10      │   ← mở viewer ±10 frame (Infor.jsx)
   └──────────┴──────────┴──────────┴──────────┘
```

---

## 4. Điểm kỹ thuật mấu chốt: hiện ảnh frame thế nào

UI hiện tại chỉ serve **file keyframe tĩnh** qua `http://localhost:8080/keyframes/...`
([server.js](backend-framesAIC2025/server.js)) → **chỉ hiện được keyframe có sẵn trên đĩa**. Nhưng
frame tier-3 (vd `1007`) nằm **giữa 2 keyframe → không có file ảnh** → không hiện qua cách này.

**Giải pháp: 1 endpoint ảnh thống nhất** `GET /search/frame?video_id=..&frame_id=..`:
1. Nếu `frame_id` **trùng 1 keyframe** (tra Mongo) → trả ảnh keyframe dày của mình (nhanh — dùng cho
   máy 2 tầng).
2. Nếu **không** (frame tier-3 tinh chỉnh) → **decode thẳng từ video** bằng OpenCV (dùng cho máy 3 tầng).

→ Cùng một UI, tự thích ứng có video hay không, không phải làm 2 phiên bản.

---

## 5. Cần chỉnh nhẹ ở backend

- **Enrich `/search/trake`**: trả kèm `fps` và `video_url` của video đã chọn (đã query Mongo rồi, chỉ
  carry thêm 2 field) → để UI tính `time = frame_id/fps` dựng link YouTube + viewer ±10.
- **Thêm `/search/frame`** như mục 4 (dùng lại `resolve_video_path()` + `VIDEO_ROOT` đã có trong
  `trake_service.py`).

---

## 6. Tái dùng được gì từ UI hiện tại (để nhẹ nhất)

- **Link YouTube tại timestamp** `&t=${time}s` — đã có ở [Jobs.jsx](frontend-final/vite-project/src/Jobs.jsx)
  và [Infor.jsx](frontend-final/vite-project/src/Infor.jsx). Chính là chỗ cắm extension ms.
- **Viewer ±10 frame** — [Infor.jsx](frontend-final/vite-project/src/Infor.jsx) sẵn sàng, chỉ cần gọi lại.
- **Gating theo mode** — `selectAns == "trake"` đã có ở [Jobs.jsx](frontend-final/vite-project/src/Jobs.jsx).
- **Kiểu grid ảnh** — bê pattern `gridTemplateColumns: repeat(N,1fr)` + `<img>` từ Infor.jsx.

---

## 7. Khối lượng code dự kiến

| Phần | Việc |
|---|---|
| Backend | Enrich `/search/trake` (thêm `fps`, `video_url`) + endpoint `/search/frame` |
| Frontend | 1 component panel TRAKE: nhập N event → list tổ hợp → bấm tổ hợp bung grid frame (reuse link YouTube + ±10) |
| Không đụng | luồng KIS/QA giữ nguyên |

---

## 8. Cần chốt với team

1. Panel TRAKE: **nối thẳng vào [Jobs.jsx](frontend-final/vite-project/src/Jobs.jsx)** (hiện khi chọn
   mode TRAKE) hay **tab/trang riêng**?
2. Bung frame khi bấm tổ hợp: **inline** (ngay dưới dòng tổ hợp) hay **modal overlay** (kiểu Infor.jsx)?
3. Có cần nút "copy tổ hợp" để dán nhanh vào sheet không, hay chỉ xem verify là đủ?
4. Máy 2 tầng: hiện luôn ảnh keyframe dày, hay chỉ cần link YouTube + viewer ±10?

---

## 9. Lưu ý phải sửa

- [server.js](backend-framesAIC2025/server.js) đang **hard-code** path keyframe `C:/Users/PC/Downloads/...`
  (máy người khác) → phải sửa về folder frame dày của mình thì ảnh keyframe mới load.
