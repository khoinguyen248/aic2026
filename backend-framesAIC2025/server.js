import express from "express";
import path from "path";
import fs from "fs";

const app = express();
const port = Number(process.env.PORT || 8080);
const keyframesPath = path.resolve(
  process.env.KEYFRAMES_PATH || path.join(process.cwd(), "keyframes"),
);

// video_id dạng L21_V001 / K01_V001 / N016-V003 / M09_V024 / S01_V001...
const VID_RE = /^[A-Za-z]+\d+[-_]V\d+$/i;

// Resolver linh hoạt: xử lý mọi lệch giữa path yêu cầu và file thật:
//  - thừa thư mục nhóm (Keyframes/N016/N016-V003/...) -> phẳng theo video_id
//  - tên file có/không tiền tố "frame_"
//  - số frame có/không pad 6 số (1541 <-> 001541)
//  - đuôi .jpg/.jpeg/.png/.webp lẫn lộn
const EXTS = ["webp", "jpg", "jpeg", "png"];

function resolveKeyframe(relPath) {
  const clean = decodeURIComponent(String(relPath || "")).replace(/^\/+/, "");
  if (!clean || clean.includes("..")) return null;
  const segs = clean.split("/").filter(Boolean);
  if (!segs.length) return null;

  const tryAbs = [];
  const add = (p) => {
    const abs = path.resolve(keyframesPath, p);
    if (abs.startsWith(keyframesPath)) tryAbs.push(abs);
  };

  add(clean); // path đúng (batch1)

  const vid = segs.find((s) => VID_RE.test(s));
  const m = segs[segs.length - 1].match(/(\d+)/);
  if (vid && m) {
    const num = parseInt(m[1], 10);
    const padded = String(num).padStart(6, "0");
    const names = [padded, `frame_${padded}`, String(num), `frame_${num}`];
    for (const n of names) for (const e of EXTS) add(`${vid}/${n}.${e}`);
  }

  for (const abs of tryAbs) {
    try {
      if (fs.existsSync(abs) && fs.statSync(abs).isFile()) return abs;
    } catch {
      // bỏ qua
    }
  }
  return null;
}

app.get("/health", (_request, response) => {
  response.type("text").send("ok\n");
});

// Ưu tiên resolver linh hoạt; không tìm thấy -> để express.static xử lý (giữ tương thích).
// Dùng app.use (Express 5 không nhận route "/Keyframes/*"); req.path đã là phần sau /Keyframes.
app.use("/Keyframes", (request, response, next) => {
  const abs = resolveKeyframe(request.path);
  if (abs) return response.sendFile(abs);
  return next();
});

app.use("/Keyframes", express.static(keyframesPath));

app.listen(port, "0.0.0.0", () => {
  console.log(`Keyframes server listening on port ${port}`);
  console.log(`Serving files from ${keyframesPath}`);
});
