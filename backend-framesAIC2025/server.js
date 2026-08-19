import express from "express";
import path from "path";

const app = express();
const port = Number(process.env.PORT || 8080);
const keyframesPath = path.resolve(
  process.env.KEYFRAMES_PATH || path.join(process.cwd(), "keyframes"),
);

app.get("/health", (_request, response) => {
  response.type("text").send("ok\n");
});

app.use("/Keyframes", express.static(keyframesPath));

app.listen(port, "0.0.0.0", () => {
  console.log(`Keyframes server listening on port ${port}`);
  console.log(`Serving files from ${keyframesPath}`);
});
