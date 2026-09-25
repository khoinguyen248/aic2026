// videoGroup.js — phân tích video_id thành nhóm + số video.
// Dataset có nhiều chữ nhóm khác nhau (K/L/M/N/S...) và 2 kiểu dấu phân cách:
// "L26_V403" (L, M dùng "_") và "N078-V002" / "S01-V001" (N, S dùng "-").
// Trước đây nhiều chỗ trong code chỉ nhận diện chữ "L"/"K" + dấu "_", nên video
// thuộc nhóm M/N/S bị hiện sai (rơi về video_id thô) hoặc gắn nhầm nhãn K/L.

// Khớp ở đầu chuỗi hoặc ngay sau "/" (vd trong path "Keyframes/N078-V002/000000.webp")
// -> không cần chuỗi đầu vào chỉ chứa mỗi video_id, vẫn tìm được trong path/url.
const VIDEO_ID_RE = /(?:^|\/)([A-Za-z]+)(\d+)[-_]V(\d+)/i;

// Trả về { letter, number, v } từ 1 chuỗi có chứa video_id (video_id, path, url...).
// Không khớp -> null.
export const parseVideoId = (candidate) => {
  const m = String(candidate || '').match(VIDEO_ID_RE);
  if (!m) return null;
  return { letter: m[1].toUpperCase(), number: m[2], v: m[3] };
};

// Nhãn hiển thị cho 1 nhóm: quy ước cũ của dataset gốc là nhóm "L" đánh số <=20
// hiển thị là "K" (dữ liệu chỉ có L21-L30 thật, số 1-20 hiển thị K để khớp tên
// công khai). Các chữ nhóm khác (M/N/S...) hiển thị đúng chữ cái gốc.
export const groupLabel = (letter, number) => {
  const upper = String(letter || 'L').toUpperCase();
  if (upper === 'K' || upper === 'L') {
    return Number(number) <= 20 ? 'K' : 'L';
  }
  return upper;
};
