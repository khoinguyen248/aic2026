# Hướng dẫn sử dụng — AIC 2026 Multimodal Search

**Đội:** MLIoT_Newbie
**Mô tả:** Công cụ tìm kiếm video đa phương thức (multimodal) cho cuộc thi AI Challenge 2026. Cho phép tìm kiếm keyframe trong kho video bằng **văn bản (semantic)**, **caption**, **giọng nói (ASR)**, **chữ trên màn hình (OCR)**, **đối tượng giao thông (Objects/detection-segmentation)** và chuỗi sự kiện **TRAKE**, sau đó **nộp bài (submission)** lên hệ thống DRES.

---

## Mục lục
1. [Khởi động & truy cập](#1-khởi-động--truy-cập)
2. [Bố cục màn hình](#2-bố-cục-màn-hình)
3. [Thanh tìm kiếm chính](#3-thanh-tìm-kiếm-chính)
4. [Các chế độ tìm kiếm (Modality chips)](#4-các-chế-độ-tìm-kiếm-modality-chips)
5. [Hybrid — lọc kết quả semantic theo OCR/ASR/Objects](#5-hybrid--lọc-kết-quả-semantic)
6. [Popover "Nâng cao"](#6-popover-nâng-cao)
7. [Sidebar ☰ (Image Search + tiện ích)](#7-sidebar--image-search)
8. [Thẻ kết quả (Result card)](#8-thẻ-kết-quả-result-card)
9. [Video Result Inspector (drawer chi tiết)](#9-video-result-inspector)
10. [Xem ±10 keyframe](#10-xem-10-keyframe)
11. [Nộp bài (Submission)](#11-nộp-bài-submission)
12. [Các bộ dữ liệu (data batch)](#12-các-bộ-dữ-liệu-data-batch)
13. [Mẹo dùng nhanh & xử lý sự cố](#13-mẹo-dùng-nhanh--xử-lý-sự-cố)

---

## 1. Khởi động & truy cập

Hệ thống gồm 4 phần chạy trong Docker Compose:

| Thành phần | Vai trò |
|---|---|
| **frontend** (Vite/React) | Giao diện web |
| **backend-api** (Flask) | Xử lý tìm kiếm — Qdrant + MongoDB |
| **frame-server** (Express) | Phục vụ ảnh keyframe (`/Keyframes`) |
| **Qdrant + MongoDB** | Vector DB (embedding) + metadata (OCR/ASR/detseg) |

**Khởi động toàn bộ:**
```bash
docker compose up -d
```

**Khi chỉ sửa code backend** (ví dụ endpoint hybrid mới):
```bash
docker compose restart backend-api
```

**Khi phát triển giao diện** (nhận thay đổi tức thì, không cần build lại Docker):
```bash
cd frontend-final/vite-project
npm run dev
```
→ Mở **http://localhost:5173**

> ⚠️ **Lưu ý Qdrant:** sau khi khởi động lại, Qdrant nạp lại dữ liệu lớn (~vài phút) và **từ chối kết nối** trong lúc đó. Đừng restart liên tục — chờ tới khi `readyz` trả về 200 là chạy được. Nếu backend báo *"Connection refused"* ngay sau restart, chỉ cần đợi.

---

## 2. Bố cục màn hình

```
┌─────────────────────────────────────────────────────────────┐
│ ▲ AIC 2026 | Multimodal Search        ● Dataset ready   ☰   │  ← Header (cố định)
├─────────────────────────────────────────────────────────────┤
│                  Multimodal Video Search                     │  ← Hero (khi chưa có kết quả)
│         [ 🔍  ô nhập query ...        (Nâng cao) (Tìm kiếm) ] │  ← Thanh tìm kiếm
│      [Visual] [Caption] [ASR] [OCR] [Objects] [TRAKE]        │  ← Modality chips
├─────────────────────────────────────────────────────────────┤
│  ▢ ▢ ▢ ▢    (lưới thẻ kết quả)                                │  ← Result grid
│  ▢ ▢ ▢ ▢                                      [ phân trang ] │
└─────────────────────────────────────────────────────────────┘
```

### Header (thanh trên cùng, luôn cố định)
- **▲ AIC 2026 | Multimodal Search** — logo/tên hệ thống.
- **● Dataset ready · Team MLIoT_Newbie** — đèn xanh báo dữ liệu sẵn sàng.
- **☰ (icon menu)** — mở **Sidebar** tiện ích bên trái (tìm bằng ảnh, tính frame…). Xem [mục 7](#7-sidebar--image-search).

---

## 3. Thanh tìm kiếm chính

Ô nhập lớn ở giữa màn hình:

- **Ô query:** gõ nội dung cần tìm. Placeholder thay đổi theo chế độ:
  - Visual: *"Mô tả cảnh cần tìm (1 câu — dùng TRAKE cho nhiều sự kiện)"*
  - Khác: *"Nhập nội dung OCR / ASR / Caption"*
- **Enter** hoặc nút **Tìm kiếm** để chạy.
- **(Nâng cao)** — nút mở popover cấu hình model / top-K / dịch / submission (xem [mục 6](#6-popover-nâng-cao)).

> 💡 Với **Visual**, chỉ nên nhập **1 câu mô tả 1 cảnh**. Nếu cần **nhiều sự kiện nối tiếp nhau theo thời gian**, dùng **TRAKE** ([mục 4.6](#46-trake--chuỗi-sự-kiện)).

---

## 4. Các chế độ tìm kiếm (Modality chips)

Hàng chip ngay dưới ô tìm kiếm chọn **phương thức**. Chip đang chọn được tô đậm (xanh).

### 4.1. Visual (semantic)
Tìm keyframe theo **ý nghĩa hình ảnh** từ câu mô tả. Đây là chế độ mặc định và mạnh nhất.
- Nhập câu mô tả → **Tìm kiếm**.
- Kết quả xếp theo **độ tương đồng (score)** giảm dần.
- Có thể chọn model embedding trong **Nâng cao** (BEIT3 / JINA / PE / CAPTION).

### 4.2. Caption
Tìm theo **caption** (mô tả văn bản gắn với keyframe) đã lập chỉ mục trong MongoDB.

### 4.3. ASR — giọng nói *(chip có popover)*
Bấm chip **ASR** để mở popover với 2 chế độ:
- **ASR only** — tìm trực tiếp các đoạn có **lời nói** khớp query. Kết quả hiển thị dạng **dải keyframe theo từng đoạn nói**.
- **Hybrid** — xem [mục 5](#5-hybrid--lọc-kết-quả-semantic).

Nhập nội dung lời nói → **Áp dụng**.

### 4.4. OCR — chữ trên màn hình *(chip có popover)*
Bấm chip **OCR** để mở popover với 2 chế độ:
- **OCR only** — tìm trực tiếp keyframe có **chữ hiển thị trên màn hình** khớp query (biển hiệu, phụ đề, tiêu đề…). Kết quả hiển thị dạng **lưới thẻ**.
- **Hybrid** — xem [mục 5](#5-hybrid--lọc-kết-quả-semantic).

Nhập chữ cần tìm → **Áp dụng**.

### 4.5. Objects — đối tượng giao thông *(chip có popover)*
Dành cho **video giao thông nhóm N** (có dữ liệu detection/segmentation, **không có OCR/ASR**). Bấm chip **Objects** để mở popover bộ lọc:

- **Chế độ:** `Standalone` (lọc thuần) hoặc `Hybrid` (lọc trên kết quả semantic).
- **≥ tổng xe (vehicle):** số lượng phương tiện tối thiểu trong khung hình.
- **Danh sách object động:** mỗi dòng chọn **tên đối tượng** (car, truck, bus, person, motorcycle, traffic light…) + **số lượng ≥**. Bấm **Thêm object** để thêm dòng, **✕** để xoá. Nhiều dòng = điều kiện **AND**.
- **Sort** (chỉ Standalone): *nhiều xe* / *đông đúc*.
- **Quan hệ vị trí (tuỳ chọn):** ràng buộc **toạ độ tương đối** giữa các đối tượng: `A [bên trái / phải / trên / dưới / giữa] B (và C)`. Nhiều quan hệ = **AND**. Với quan hệ **giữa (between)** cần chọn thêm đối tượng **C**.
- Bấm **Objects Search** để chạy.
- Chip **Objects** hiển thị **badge số** = số object đang lọc (ví dụ `Objects 2`).

> Ví dụ: "có ≥ 3 `car`, và `person` **bên phải** `motorcycle`".

### 4.6. TRAKE — chuỗi sự kiện
Dùng khi câu hỏi mô tả **nhiều sự kiện xảy ra nối tiếp trong cùng một video**. Chip TRAKE mở **TrakePanel** riêng:
- Nhập **từng sự kiện** (mỗi ô = 1 sự kiện theo thứ tự thời gian).
- Cấu hình **khoảng cách tối đa giữa 2 sự kiện** (`max_event_gap_s`) — mặc định **không giới hạn**.
- Kết quả hiển thị **điểm từng frame**, cho phép **nhích thủ công (nudge)**, xem **dải keyframe toàn video (±10 / tất cả)**.
- Có thể **chọn frame cho từng sự kiện rồi nộp combo** (submission dạng TRAKE — nộp danh sách frame_id).

---

## 5. Hybrid — lọc kết quả semantic

**Hybrid** là điểm mạnh: chạy **semantic trước**, rồi **lọc lại** tập kết quả đó theo OCR / ASR / Objects.

**Luồng:**
```
Query chính (Visual) → Semantic → lấy Top-K frame → lọc theo OCR/ASR/Objects → kết quả cuối
```

**Cách dùng:**
1. Chọn chip **Visual** (hoặc Caption), nhập câu mô tả ở ô chính.
2. Bấm chip **OCR** (hoặc **ASR** / **Objects**) → chọn **Hybrid** → nhập query lọc → **Áp dụng**.
3. Bấm **Tìm kiếm**: hệ thống chạy semantic rồi **giữ lại** những frame khớp thêm điều kiện OCR/ASR/Objects (giữ nguyên thứ tự semantic).

- Khi Hybrid đang bật, chip hiển thị trạng thái, ví dụ **`OCR · Hybrid`**, **`ASR · Hybrid`**.
- Bật **cả OCR lẫn ASR Hybrid** cùng lúc → điều kiện **AND** (frame phải khớp cả hai).
- Nếu đã có kết quả trên màn hình, bấm **Áp dụng** trong popover sẽ **lọc ngay** tập kết quả hiện tại.

> **OCR only / ASR only** = tìm độc lập (standalone). **Hybrid** = lọc chồng lên semantic. Đây là 2 việc khác nhau — đọc kỹ dòng mô tả xám trong popover.

---

## 6. Popover "Nâng cao"

Mở bằng nút **(Nâng cao)** cạnh ô tìm kiếm:

| Mục | Ý nghĩa |
|---|---|
| **Model** | Model embedding cho Visual: `BEIT3`, `JINA`, `PE`, `CAPTION`. |
| **top-K** | Số kết quả lấy về (mặc định 100). |
| **Translate** | Dịch query trước khi tìm (hữu ích khi nhập tiếng Việt cho model tiếng Anh). |
| **Augment** | Mở rộng/tăng cường query. |
| **SUBMISSION TASK** | Loại bài nộp: **KIS** hoặc **QA** (áp dụng khi bấm "Nộp"). |

> ⚠️ **batch2 (S / M / N)** chỉ có trong collection **`jina`**. Nếu tìm các video này, chọn model **JINA**.

---

## 7. Sidebar ☰ (Image Search)

Mở bằng icon **☰** ở Header. Chứa:

- **Tìm bằng ảnh (Image Search):** kéo-thả hoặc chọn ảnh JPG/PNG/WEBP → **Search by image**. Kết quả đổ vào lưới như Visual.
- **Hiển thị Model / Top-K** hiện hành.
- **ASR/OCR search (bản legacy)** với 2 mode *Standalone / Merge into main search*.
- **FrameCalc** — tiện ích tính toán frame ↔ thời gian.

> Bộ lọc **Objects (traffic)** đã được chuyển ra **popover của chip "Objects"** (không còn nằm trong sidebar).

---

## 8. Thẻ kết quả (Result card)

Kết quả hiển thị dạng **lưới thẻ**. Mỗi thẻ:

- **Ảnh keyframe** (lazy-load).
- **Badge score** (góc — độ tương đồng, khi có).
- **Badge thời gian** — `phút m giây s`.
- **Meta** dưới ảnh: `Video · frame_id · thời gian · fps` + link mở video ngoài.
- **Caption / OCR / text** (nếu có).

- **Tag modality gọn** ở đáy thẻ (`Visual`, `Caption`, `OCR`, `Objects`…) để **scan nhanh** frame khớp phương thức nào. Tag Hybrid có viền/màu xanh accent (`OCR·Hy`).

**Hover vào thẻ** hiện 3 nút hành động nhanh:
| Nút | Chức năng |
|---|---|
| 📂 | Xem **±10 keyframe** lân cận ([mục 10](#10-xem-10-keyframe)) |
| ▶ | **Mở video** tại đúng thời điểm |
| ➕ | **Nộp kết quả này** (mở modal submission) |

**Bấm vào thẻ** (không phải nút) → mở **Video Result Inspector** ([mục 9](#9-video-result-inspector)).

### Thanh công cụ kết quả (phía trên lưới)
- **Số kết quả**: `Hiển thị X/Y kết quả`.
- **Chip filter Objects đang áp**: mỗi object đang lọc hiện thành chip `Objects: car ≥3` — bấm **×** để bỏ và **tìm lại** ngay.
- **Bộ lọc L/V**: chọn nhiều bộ L, thu hẹp theo V, hoặc loại trừ L/L_V; tuỳ chọn *Giữ bộ lọc khi tìm kiếm mới*.
- **Sắp xếp**: `Độ liên quan` (mặc định — thứ tự semantic) hoặc `Thời gian` (theo mốc trong video).

**Phân trang:** dưới lưới — chọn số thẻ/trang (12 / 24 / 48 / 96; mặc định 24).

---

## 9. Video Result Inspector

Bấm vào một thẻ để mở panel chi tiết bên phải (**"Chi tiết frame"**, rộng ~448px). Gồm 4 khối:

Thiết kế **thoáng, phẳng** (label + nội dung ngăn bằng đường kẻ mảnh, không đóng khung nặng), màu tiết chế (xanh + xám, Hybrid dùng accent xanh).

### Frame + metadata
- Ảnh frame lớn với **overlay**: thời gian góc trái dưới (`▶ 00:30`), **score** góc phải trên (`0.94`).
- Dòng lớn `L21 · V005`, dòng phụ `Frame 925 · 00:30 · 30 FPS`. (Không còn progress bar — pill score trên ảnh là đủ.)

### Matched by
- **Tag các phương thức đã khớp**: `Visual`, `Caption`, `OCR · Hybrid`, `ASR · Hybrid`, `Objects`… Tag thường màu trung tính, tag **Hybrid** có accent xanh.

> Ghi chú trung thực: hybrid ở backend là **lọc khớp/không khớp** (không có điểm % per-modality). Vì vậy panel **không bịa số "độ khớp"** — thay vào đó **highlight đúng đoạn chữ trùng query** trong OCR/ASR (nền vàng nhạt) để thấy rõ vì sao frame được giữ lại.

### Nội dung (Content)
`Caption` / `OCR` / `ASR` / **Objects** (số lượng từng loại) — chỉ hiện phần **có dữ liệu**. Đoạn OCR/ASR khớp query hybrid được **tô sáng**.

### Actions (phân cấp rõ ràng)
1. **▶ Mở video** — nút chính (xanh, full-width).
2. **Xem ±10 keyframe** — phụ.
3. **➕ Nộp kết quả này** — dạng text (mở modal submission).

---

## 10. Xem ±10 keyframe

Mở từ nút 📂 trên thẻ hoặc "Xem ±10 keyframe" trong Inspector.
- Hiện dải keyframe **±10 quanh frame** đang chọn; nút **toggle** để xem **toàn bộ video**.
- Bấm **submit** ngay trên bất kỳ frame nào trong dải (single) hoặc chọn frame cho **TRAKE combo**.
- Millisecond nộp lấy từ **`frame_stamp`** (timestamp thật), **không** suy từ `frame_id/fps` — quan trọng với video **N** có FPS không cố định (VFR).

> Với video **N** không nằm trong collection semantic (beit3), hệ thống **fallback đọc Mongo** để dựng dải keyframe.

---

## 11. Nộp bài (Submission)

Mở modal bằng nút ➕ (thẻ hoặc Inspector) hoặc combo TRAKE.

- **Loại bài:** KIS / QA / TRAKE (mặc định lấy theo SUBMISSION TASK ở Nâng cao; TRAKE tự nhận khi ở chế độ TRAKE).
- **KIS / QA:** nộp **milliseconds** (mstime). TRAKE: nộp **danh sách frame_id**.
- **Xác nhận:** modal có bước xác nhận (state-controlled) và **banner kết quả** (CORRECT / WRONG) sau khi nộp.

### Lưu ý VIDEO_ID batch2 (rất quan trọng)
- Video batch2 nhóm **N/S/M** dùng đúng id gốc, **KHÔNG thêm chữ "L" phía trước**.
  - ✅ Đúng: `N075` · ❌ Sai: `LN075`.
- Định dạng chấp nhận cả kiểu `K01-V01`, `L21-V01`, `N075-V001`…

### Lưu ý timestamp video N (VFR)
- Video giao thông N có **FPS không cố định**. Vì nộp KIS/QA theo **milliseconds**, hệ thống dùng **`frame_stamp`** trong metadata thay vì suy từ `frame_id/fps`.
- Do đội cắt keyframe **1 giây/frame** (không theo cách cắt 2s/frame của BTC), `frame_stamp` hiện tại là chính xác cho việc nộp.

### ⚠️ An toàn / máy chủ DRES
- Server nộp bài chính thức: **`https://eventretrieval.one`**.
- **KHÔNG** dùng `eventretrieval.oj.io.vn` — tên miền này đã bị chiếm dụng (redirect sang site cờ bạc). Không gửi session/bài lên đó.
- Đăng nhập DRES lấy **sessionid** theo hướng dẫn BTC; giữ bí mật session.

---

## 12. Các bộ dữ liệu (data batch)

| Nhóm | Loại | OCR/ASR | Detection/Seg | Ghi chú |
|---|---|---|---|---|
| **K / L** | Video thường (batch1) | ✅ | – | Có trong nhiều collection embedding |
| **S / M** | Video thường (batch2) | ✅ | – | **Chỉ** trong collection `jina` |
| **N** | Camera giao thông (batch2) | ❌ | ✅ (parquet) | **VFR**; tìm bằng chip **Objects** |

### ⚠️ Điểm kỹ thuật quan trọng: lệch index
- **Qdrant idx** đánh **liên tục toàn cục** từ đầu tới cuối.
- **Mongo idx** (OCR/ASR/detseg) **reset về 0 theo từng nhóm chữ cái** (L bắt đầu 0, sang M lại 0…).
- ⇒ Mọi tra chéo giữa Qdrant và Mongo **phải khớp theo `(video_id, frame_id)`**, **không** dùng `idx`. (Hệ thống đã xử lý sẵn; nêu ở đây để hiểu khi debug.)

### Đường dẫn keyframe
Frame-server phục vụ tại route **`/Keyframes`** và tự dò nhiều biến thể đường dẫn: thư mục theo nhóm, tiền tố `frame_`, độ đệm số (padding), đuôi `.webp/.jpg/.jpeg/.png`. Trong runtime, id keyframe batch2 dạng `N010-V001` (có dấu `-`).

---

## 13. Mẹo dùng nhanh & xử lý sự cố

**Mẹo:**
- Câu mô tả **ngắn gọn, 1 cảnh** cho Visual; **TRAKE** cho chuỗi sự kiện.
- Query tiếng Việt cho model tiếng Anh → bật **Translate**.
- Cần "cảnh X **và** có chữ Y trên màn hình" → Visual + **OCR Hybrid**.
- Cần "cảnh X **và** ai đó nói Y" → Visual + **ASR Hybrid**.
- Video giao thông N → **Objects** (Visual thuần thường yếu với loại này).
- Tăng **top-K** nếu lọc Hybrid trả về quá ít.

**Sự cố thường gặp:**

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Backend "Connection refused" sau restart | Qdrant đang nạp dữ liệu (~vài phút). **Chờ**, đừng restart lại. |
| Không quay lại được Visual sau khi search OCR/ASR đơn lẻ | Đã sửa: chuyển chip về **Visual** rồi Tìm kiếm là được. |
| Frame batch2 không hiện | Đảm bảo frame-server đã chạy/rebuild; resolver xử lý mọi biến thể path. |
| ±10 báo "idx not found" với video N | Đã fallback theo `frame_id` (Qdrant idx ≠ Mongo idx). |
| Nút Submit không phản hồi | Đã sửa (React 19 + antd v5): dùng modal state-controlled. |
| Nộp N bị thêm "L" (LN075) | Đã sửa: batch2 giữ nguyên id, không thêm "L". |
| PowerShell báo lỗi `&&` | PowerShell không hỗ trợ `&&`. Chạy lệnh trên **2 dòng** hoặc dùng `;`. |

---

*Tài liệu này mô tả giao diện hiện hành (chip OCR/ASR/Objects dạng popover, Hybrid semantic→filter, và Video Result Inspector). Cập nhật khi UI thay đổi.*
