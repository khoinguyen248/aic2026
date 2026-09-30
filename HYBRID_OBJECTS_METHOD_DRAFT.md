# Method (draft) — Hybrid OCR/ASR Filtering & Object (Spatial-Relation) Retrieval

> Bản nháp phần **Method** cho hai cơ chế: (A) **Hybrid late-fusion filtering** kết hợp truy hồi hình ảnh với bằng chứng văn bản OCR/ASR; (B) **Object retrieval** theo số lượng đối tượng và **quan hệ vị trí không gian** cho video giao thông. Bám sát cài đặt: `hybrid_controller.py` (`ocr_filter`, `asr_filter`), `traffic_controller.py` (`traffic_search`), và các helper Atlas Search trong `mongo_search.py`.

---

## A. Hybrid OCR/ASR — Late-Fusion Filtering

### A.1. Động cơ

Truy hồi thị giác thuần (ANN trên embedding) mạnh về ngữ nghĩa hình ảnh nhưng "mù" với **chữ hiển thị trên màn hình (OCR)** và **lời nói (ASR)**. Ngược lại, tìm kiếm văn bản thuần bỏ qua nội dung hình ảnh. **Hybrid** kết hợp hai nguồn theo kiểu **lọc kết hợp muộn (late-fusion filtering)**: giữ nguyên xếp hạng thị giác, chỉ **thu hẹp** về những khung hình đồng thời có bằng chứng văn bản khớp truy vấn phụ.

### A.2. Phát biểu

Cho truy vấn thị giác $q_v$ và (tuỳ chọn) truy vấn OCR $q_o$, ASR $q_a$. Bước 1 cho tập ứng viên xếp hạng theo tương đồng cosine:

$$
\mathcal{C} = \mathrm{ANN}_\phi(q_v, K) = \big[(v_1,f_1), \dots, (v_K,f_K)\big], \quad s(v_1,f_1)\ge\dots\ge s(v_K,f_K).
$$

Định nghĩa tập khung hình khớp văn bản (cùng bộ so khớp với tìm kiếm standalone):

$$
\mathcal{M}_{\text{ocr}}(q_o) = \{(v,f): f \in \mathrm{OCR}_{\text{search}}(q_o, v)\}, \qquad
\mathcal{M}_{\text{asr}}(q_a) = \{(v,f): \exists\,(v,s,e)\in \mathrm{ASR}_{\text{seg}}(q_a,v),\ s\le f\le e\}.
$$

Kết quả hybrid là **giao** (bảo toàn thứ tự của $\mathcal{C}$):

$$
\mathcal{R} = \big[\, c \in \mathcal{C} \ :\ (q_o=\varnothing \lor c\in\mathcal{M}_{\text{ocr}}) \ \land\ (q_a=\varnothing \lor c\in\mathcal{M}_{\text{asr}}) \,\big].
$$

Bật đồng thời OCR và ASR ⇒ điều kiện **AND**. Đây là **lọc**, không rerank — thứ hạng thị giác của Qdrant được giữ nguyên.

### A.3. Nguyên tắc nhất quán so khớp (điểm quan trọng)

$\mathrm{OCR}_{\text{search}}$ và $\mathrm{ASR}_{\text{seg}}$ **phải dùng đúng bộ so khớp** như tìm kiếm standalone (Atlas Search + fuzzy), **scoped theo từng video ứng viên** để hiệu quả:

- `ocr_frame_ids_in_video(q, v)`: Atlas `ocr_search` (fuzzy) → top-toàn-kho rồi `$match video_id=v` → tập `frame_id` khớp trong $v$.
- `asr_ranges_in_video(q, v)`: Atlas `asr_search` (fuzzy) → các khoảng $(s,e)$ khớp trong $v$.

> **Bài học kỹ thuật (nên nêu trong paper/limitations).** Ở phiên bản đầu, filter dùng **khớp chuỗi con nguyên cụm** (`regex(q)`) — chặt hơn nhiều so với fuzzy full-text của bước standalone, khiến $\mathcal{M}=\varnothing$ ngay cả khi văn bản thật sự liên quan (ví dụ truy vấn *"truyền thống trồng trầu"* không xuất hiện **nguyên văn** trong bất kỳ đoạn ASR nào ⇒ hybrid rỗng). Sửa bằng cách **đồng nhất bộ so khớp** giữa filter và search: hybrid trở thành *"giao giữa top-K thị giác và kết quả tìm kiếm văn bản"*, đảm bảo $\mathcal{R}\subseteq(\mathcal{C}\cap\text{standalone}(q))$.

### A.4. Thuật toán

```
# Bước 1 (thị giác)
C ← ANN_φ(q_v, K)                         # [(v,f)] xếp theo cosine giảm dần

# Bước 2 (lọc văn bản) — OCR
if q_o ≠ ∅:
    for v ∈ videos(C):  O[v] ← ocr_frame_ids_in_video(q_o, v)   # Atlas fuzzy, scoped
    C ← [ (v,f) ∈ C : f ∈ O[v] ]

# Bước 2' — ASR
if q_a ≠ ∅:
    for v ∈ videos(C):  Rng[v] ← asr_ranges_in_video(q_a, v)
    C ← [ (v,f) ∈ C : ∃ (s,e)∈Rng[v], s ≤ f ≤ e ]

return C                                   # giữ nguyên thứ tự thị giác
```

Chi phí: $|\text{videos}(\mathcal C)|$ truy vấn Atlas (mỗi truy vấn có $\log$-index), $K$ nhỏ ($\le$ vài trăm) ⇒ độ trễ thêm không đáng kể.

### A.5. Giao diện & luồng người dùng

Chip **OCR/ASR** mở popover: chọn *only* (standalone) hoặc *Hybrid* + nhập query phụ. Khi Hybrid bật, chip hiển thị trạng thái `OCR · Hybrid`. Người dùng gõ truy vấn thị giác ở ô chính → **Tìm kiếm** → hệ thống chạy Bước 1 rồi Bước 2. Trong **Video Result Inspector**, đoạn văn bản trùng truy vấn được **tô sáng** (không hiển thị điểm số suy diễn — xem §A.6).

### A.6. Ghi chú trung thực

- Hybrid là **bộ lọc nhị phân** (khớp/không khớp) chồng lên tương đồng thị giác; **không** có điểm hợp nhất per-modality. Chỉ **cosine thị giác** là số thật; UI tô sáng đoạn khớp thay vì bịa "độ khớp %".
- `*_in_video` dùng chiến lược **global-prelimit ($\le 300$) rồi scope theo video**: nếu các đoạn khớp của một video rơi ngoài top-300 toàn kho (thường với từ khoá phổ biến, câu ngắn), scoped-match có thể **bỏ sót** ⇒ hybrid recall giảm. Câu truy vấn cụ thể/hiếm cho recall tốt hơn.
- Ngữ nghĩa **AND** khiến kết quả rỗng khi tập video thị giác và tập video khớp văn bản **rời nhau** — đúng logic, nhưng cần tăng $K$ hoặc chỉnh truy vấn khi cần.

---

## B. Object Retrieval — Count & Spatial-Relation (video giao thông N)

### B.1. Động cơ & dữ liệu

Video giao thông nhóm N **không có OCR/ASR/caption**, nhưng có **detection/segmentation** cho từng frame. Ta lập chỉ mục `detseg_metadata`:

- `counts` = $\{\text{class}\mapsto n\}$ (đếm đối tượng theo lớp COCO: car, truck, bus, person, motorcycle, "traffic light", …);
- `dets` = danh sách $\{c, x, y\}$ với $c$ = lớp, $(x,y)$ = **toạ độ tâm** hộp (hệ toạ độ ảnh: $x$ tăng sang phải, $y$ tăng xuống dưới);
- `vehicle_count` (tổng phương tiện), `seg_vehicle_ratio` (mật độ chiếm dụng, proxy tắc nghẽn).

Chỉ mục **wildcard** `counts.$**` cho phép lọc theo lớp bất kỳ mà không cần khai báo trước.

### B.2. Vị từ đếm (count predicates)

Người dùng đặt danh sách điều kiện; frame $f$ thoả:

$$
\Phi_{\text{count}}(f) = \bigwedge_i \big[\text{counts}_f(\text{cls}_i) \ge m_i\big] \ \land\ [\text{vehicle\_count}_f \ge \text{mv}] \ \land\ [d_{\min}\le \text{seg\_vehicle\_ratio}_f \le d_{\max}].
$$

Tất cả điều kiện là **AND**. Các thành phần đều đẩy xuống truy vấn Mongo (index), lọc ở tầng DB (`_build_query`).

### B.3. Vị từ quan hệ không gian (spatial relations)

Cho quan hệ $r=(A, \text{rel}, B[, C])$ với $A,B,C$ là các lớp. Gọi $\mathcal{I}_X(f)$ là tập thể hiện (instance) của lớp $X$ trong frame $f$. Quan hệ thoả theo **lượng từ tồn tại (existential)** trên các thể hiện (một cặp thoả là đủ, vì một lớp có thể có nhiều đối tượng):

$$
\begin{aligned}
\text{left}(A,B) &: \exists a\in\mathcal I_A,\, b\in\mathcal I_B:\ a.x < b.x \quad (A\ \text{bên trái}\ B)\\
\text{right}(A,B) &: \exists a,b:\ a.x > b.x\\
\text{above}(A,B) &: \exists a,b:\ a.y < b.y \quad (y\ \text{nhỏ hơn} = \text{cao hơn trong ảnh})\\
\text{below}(A,B) &: \exists a,b:\ a.y > b.y\\
\text{between}(A,B,C) &: \exists a,b,c:\ (b.x < a.x < c.x)\ \lor\ (c.x < a.x < b.x)
\end{aligned}
$$

Nhiều quan hệ kết hợp bằng **AND**:

$$
\Phi_{\text{rel}}(f) = \bigwedge_{r} \text{rel}_r\big(f\big).
$$

Điều kiện frame cuối cùng: $\Phi(f) = \Phi_{\text{count}}(f)\ \land\ \Phi_{\text{rel}}(f)$.

**Tối ưu 2 pha:** các lớp xuất hiện trong quan hệ được thêm điều kiện tồn tại `counts.cls ≥ 1` vào truy vấn Mongo để **thu hẹp con trỏ** trước; kiểm tra hình học $\Phi_{\text{rel}}$ (dùng `dets`) chạy ở tầng ứng dụng (`_passes_relations`) trên tập đã thu hẹp.

### B.4. Thuật toán

```
Φ_count ← build_mongo_query(objects, min_vehicle, density)   # đẩy xuống index
add counts.cls ≥ 1 cho mọi cls trong relations               # thu hẹp cursor

# --- Standalone ---
cursor ← detseg.find(Φ_count).sort(vehicle_count | seg_vehicle_ratio, desc)
rows ← []; scanned ← 0
for d in cursor:
    scanned++
    if passes_relations(d.dets, relations): rows.append(d)
    if |rows| ≥ k: break
    if scanned ≥ 8000: break            # trần quét, tránh treo khi lọc hình học
return decorate(rows)                    # join ocr_metadata lấy fps/video_url/idx + path keyframe

# --- Hybrid (kèm frames semantic) ---
pairs ← [(v,f) ∈ frames]
D ← detseg.find(Φ_count ∧ {(v,f) ∈ pairs})       # chỉ trên ứng viên semantic
rows ← [ D[(v,f)] for (v,f) in pairs             # GIỮ THỨ TỰ semantic
         if (v,f) ∈ D and passes_relations(D[(v,f)].dets, relations) ][:k]
```

**Standalone** xếp theo mức độ đông xe (`vehicle_count`) hoặc mật độ (`seg_vehicle_ratio`). **Hybrid** giao với top-K thị giác và **bảo toàn thứ tự thị giác** (giống Hybrid OCR/ASR ở phần A).

### B.5. Ghi chú trung thực

- Quan hệ không gian dựa trên **toạ độ tâm 2D**, **không có độ sâu/ą3D**; "trái/phải/trên/dưới" là so sánh toạ độ tâm trong mặt phẳng ảnh, "dưới" $\equiv$ $y$ lớn hơn (ảnh, gốc trên-trái).
- Lượng từ **tồn tại**: quan hệ đúng nếu **có ít nhất một** cặp thể hiện thoả — không yêu cầu mọi thể hiện thoả (phù hợp truy vấn kiểu "có một người bên phải xe máy").
- **Trần quét 8000** ở standalone khi có ràng buộc hình học: đảm bảo độ trễ ổn định nhưng có thể bỏ sót nếu frame thoả nằm sâu sau ngưỡng sort — nêu rõ khi báo cáo.
- Chất lượng phụ thuộc **chất lượng detector** sinh ra `counts`/`dets` (nguồn parquet); lỗi phát hiện lan truyền vào truy hồi.

---

## C. So sánh & vị trí trong hệ thống

| Chiều | Hybrid OCR/ASR (A) | Object/Spatial (B) |
|---|---|---|
| Nguồn bằng chứng | Văn bản (OCR/ASR) trên Mongo Atlas | Detection/segmentation trên Mongo |
| Kết hợp thị giác | Lọc giao, giữ thứ tự thị giác | Lọc giao (hybrid) / độc lập (standalone) |
| Bộ so khớp | Atlas fuzzy full-text (đồng nhất standalone) | Vị từ đếm + hình học 2D |
| Nhóm dữ liệu | K/L/S/M (có OCR/ASR) | N (giao thông) |
| Điểm số | cosine thị giác (thật); văn bản = nhị phân | cosine (hybrid) hoặc xếp theo mật độ (standalone) |

Cả hai theo cùng triết lý **late-fusion filtering**: ANN thị giác cho ứng viên, ràng buộc phương thức phụ **thu hẹp** mà **không phá vỡ** xếp hạng thị giác — nhất quán với TRAKE (xem `TRAKE_METHOD_DRAFT.md`).

---

## D. TODO khi hoàn thiện paper
- (i) Ablation: visual-only vs +OCR-hybrid vs +ASR-hybrid vs +Objects; đo recall/precision theo ground-truth BTC.
- (ii) Phân tích ảnh hưởng của **global-prelimit** (300) tới recall của hybrid; thử tăng prelimit hoặc scoped-$search.
- (iii) Ví dụ định tính: 1 truy vấn hybrid (ảnh + đoạn OCR/ASR tô sáng) và 1 truy vấn spatial-relation (khung hình + toạ độ đối tượng).
- (iv) Thời gian đáp ứng trung bình từng pha.
