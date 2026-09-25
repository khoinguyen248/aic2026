import express from "express";
import path from "path";
import fs from "fs";

const app = express();
const port = Number(process.env.PORT || 8080);
const keyframesPath = path.resolve(
  process.env.KEYFRAMES_PATH || path.join(process.cwd(), "keyframes"),
);

app.get("/health", (_request, response) => {
  response.type("text").send("ok\n");
});

// Ca phổ biến nhất: path trong metadata khớp tuyệt đối tên file trên đĩa.
app.use("/Keyframes", express.static(keyframesPath));

// --- Resolver dự phòng ---
// Các batch dữ liệu (K/L/M/N/S) không đồng nhất tên file: tiền tố "frame_"/"frame-",
// số frame có/không zero-pad, đuôi .jpg/.jpeg/.png/.webp khác nhau dù ảnh thật luôn
// .webp, và đôi khi thừa 1 cấp thư mục trùng tên video do giải nén sai. Chỉ chạy khi
// express.static ở trên không tìm thấy file khớp tuyệt đối.
const EXTENSIONS = new Set(["webp", "jpg", "jpeg", "png"]);
const FRAME_NAME_RE = /^(?:frame[_-])?0*(\d+)\.([A-Za-z0-9]+)$/i;

// Cache danh sách file mỗi thư mục — dữ liệu chỉ đọc trong suốt vòng đời container.
const dirEntryCache = new Map();
const listDir = (dir) => {
  if (dirEntryCache.has(dir)) return dirEntryCache.get(dir);
  let entries = [];
  try {
    entries = fs.readdirSync(dir);
  } catch {
    entries = [];
  }
  dirEntryCache.set(dir, entries);
  return entries;
};

// Chặn path traversal (".." hoặc chứa "/", "\") trên từng segment URL.
const isSafeSegment = (value) =>
  typeof value === "string" &&
  value.length > 0 &&
  value !== "." &&
  value !== ".." &&
  !value.includes("/") &&
  !value.includes("\\");

const findByFrameNumber = (dir, wantedNumber) => {
  for (const entry of listDir(dir)) {
    const match = entry.match(FRAME_NAME_RE);
    if (!match) continue;
    const [, digits, ext] = match;
    if (digits === wantedNumber && EXTENSIONS.has(ext.toLowerCase())) {
      return path.join(dir, entry);
    }
  }
  return null;
};

app.get("/Keyframes/:video/:file", (request, response) => {
  const { video, file } = request.params;
  if (!isSafeSegment(video) || !isSafeSegment(file)) {
    response.status(400).type("text").send("invalid path\n");
    return;
  }

  const match = file.match(FRAME_NAME_RE);
  if (!match) {
    response.status(404).type("text").send("not found\n");
    return;
  }
  const wantedNumber = match[1];

  const videoDir = path.join(keyframesPath, video);
  // Thử đúng thư mục trước, rồi thử lồng thêm 1 cấp trùng tên video (phòng giải nén
  // thừa cấp: Keyframes/<video>/<video>/...).
  const resolved =
    findByFrameNumber(videoDir, wantedNumber) ??
    findByFrameNumber(path.join(videoDir, video), wantedNumber);

  if (!resolved) {
    response.status(404).type("text").send("not found\n");
    return;
  }
  response.sendFile(resolved);
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Keyframes server listening on port ${port}`);
  console.log(`Serving files from ${keyframesPath}`);
});
