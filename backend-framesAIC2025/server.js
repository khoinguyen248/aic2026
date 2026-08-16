import express from "express";
import path from "path";

const app = express();

// đường dẫn tuyệt đối tới folder keyframes
const keyframesPath = path.join("C:/Users/PC/Downloads/Downloads/keyframes");
// serve static folder
app.use("/keyframes", express.static(keyframesPath));

app.listen(8080, () => {
  console.log("Keyframes server running at http://localhost:8080/keyframes");
});