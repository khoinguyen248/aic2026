# TRAKE — Bộ query có ground-truth (BTC) hiện có

Tổng hợp **4 query multi-event có đáp án** (video_id + frame_id của từng sự kiện) để đánh giá TRAKE. Đây là toàn bộ GT hiện có từ đề của BTC.

## Tổng quan

| # | Query (chủ đề) | Video (GT) | #Event | Loại nhãn | Gợi ý đa phương thức | GT frames |
|---|---|---|---|---|---|---|
| q1 | Hai đầu bếp nấu lươn | `L26_V069` | 4 | điểm (frame) | thị giác thuần | 5360, 5473, 5631, 6104 |
| q2 | Phố trang trí Tết | `L22_V010` | 4 | **khoảng (range)** | thị giác thuần | 9104–9164 · 9358–9480 · 9609–9669 · 9758–9778 |
| q3 | Cảnh đẹp thiên nhiên VN | `L27_V016` | 4 | điểm | **OCR** ("Cánh gà lắc" ở E3) | 86, 146, 283, 1197 |
| q4 | Cuộc thi đua xe đạp | `L23_V007` | 3 | điểm | **OCR + suy luận số** (số hiệu) | 1626, 2511, 3334 |

- **Tổng: 4 query, 15 sự kiện.** Độ dài chuỗi: 3–4 event. 2 loại nhãn: mốc frame đơn (q1,q3,q4) và khoảng frame (q2).
- Độ khó đa dạng: thị giác cụ thể (q3), hành động trừu tượng (q1 "phết dầu"), mô tả người chi tiết (q2), **đọc chữ/suy luận số** (q4 số hiệu tổng 29, |hiệu| 5 → {12,17}).

---

## Chi tiết từng query

### q1 — `L26_V069` (nấu lươn, 4 event) — GT: 5360, 5473, 5631, 6104
> Cảnh 2 người đầu bếp cùng nấu món lươn.
- E1: người đầu bếp lấy cọ phết dầu ăn lên chảo — **5360**
- E2: người đầu bếp đặt lươn lên chảo nướng — **5473**
- E3: người đầu bếp dùng muôi gỗ ép miếng lươn — **5631**
- E4: miếng lươn đầu tiên được đặt lên dĩa — **6104**

### q2 — `L22_V010` (trang trí Tết, 4 event, nhãn KHOẢNG) — GT ranges
> Khu phố trang trí biểu tượng Tết.
- E1: ngôi sao đỏ viền vàng trong vòng tròn bạc — **9104–9164**
- E2: nữ MC cầm sợi dây có móc nhiều đồ vật — **9358–9480**
- E3: người đàn ông áo đen họa tiết cam giữa áo cầm một đồ vật — **9609–9669**
- E4: chú gấu trúc đồ chơi bụng phát sáng treo lủng lẳng — **9758–9778**

### q3 — `L27_V016` (thiên nhiên VN, 4 event, có OCR) — GT: 86, 146, 283, 1197
> Loạt cảnh đẹp thiên nhiên & con người Việt Nam.
- E1: cậu bé cưỡi trâu dưới nước, vung nước lên — **86**
- E2: người đàn ông đeo đèn pin trên đầu (quai xanh biển), đồng hồ đen, cười, sau lưng là cánh đồng lúa — **146**
- E3: cô gái áo ngoài trắng (mic ở áo đen bên trong) đi giữa chợ ẩm thực, có **xe bán "Cánh gà lắc"** (OCR) — **283**
- E4: vỏ lãi màu xanh da trời chạy trên kênh/sông, trên bờ có đường, một bên là rừng — **1197**

### q4 — `L23_V007` (đua xe đạp, 3 event, OCR + suy luận) — GT: 1626, 2511, 3334
> Cuộc thi đua xe đạp.
- E1: bốn tay đua áo vàng bám sát bốn tay đua áo xanh — **1626**
- E2: cận cảnh hai tay đua áo xanh, **số hiệu hiện rõ** (tổng = 29, |hiệu| = 5 → {12, 17}) — **2511**
- E3: ba tay đua áo trắng-pha-xanh-lá xếp một hàng thẳng, **tay đua cuối hàng vượt qua vạch sang đường đầu tiên** — **3334**

---

## Ghi chú trung thực để hỏi reviewer

- **Quy mô:** mới có **4 query (15 event)** — đủ cho *prototype / sanity check* nhưng **chưa đủ cho experimental validation** (reviewer trước đã yêu cầu **≥30–50 query** để R@K/MRR có ý nghĩa thống kê; với N=4 mỗi query đổi kết quả ±0.25).
- **Chưa có ca "sự kiện lặp lại":** để chứng minh **DP > Greedy** cần query mà cùng một event xuất hiện nhiều lần trong video (ép ràng buộc thứ tự). 4 query hiện tại chưa có ca này ⇒ chưa tách được đóng góp của DP.
- **Có mầm cho multimodal:** q3 (OCR "Cánh gà lắc"), q4 (OCR số hiệu + suy luận) — nhưng mỗi loại chỉ 1 query, chưa đủ để chứng minh OCR/ASR nâng accuracy.
- **Đa dạng độ khó** (tốt): thị giác cụ thể → trừu tượng → đọc-chữ/suy-luận; và 2 kiểu nhãn (điểm & khoảng).

**Câu hỏi nên hỏi reviewer:** *"Với 4 query BTC này (đa dạng độ khó, có cả nhãn điểm lẫn khoảng, có ca OCR/suy luận), chúng tôi nên (a) coi đây là qualitative case study và tự mở rộng bộ query tự gán nhãn lên ~30–50, hay (b) có cách nào khác để báo cáo thuyết phục với số query hạn chế này?"*

*(Bộ query này nằm trong `queries_gt.json`; chạy eval: xem `README.md` / `TRAKE_EVAL_PLAN.md`.)*
