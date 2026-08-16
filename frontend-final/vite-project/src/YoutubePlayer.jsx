import React from "react";
import "./Infor.css";
import { Button } from "antd";

export default function YoutubePlayer({ url, close }) {
  const embedUrl = getYouTubeEmbedUrl(url);

  return (
    <div className="overlay" style={{ zIndex: 9999 }}>
      <div className="content" style={{ width: "840px", height: "660px" }}>
        {embedUrl ? (
          <>
          <Button
              style={{ alignSelf: "flex-end" }}
              onClick={() => close(false)}
            >
              Close
            </Button>
          <iframe
  width="100%"
  height="100%"
  src={embedUrl + "&autoplay=1&controls=1"}
  title="YouTube video player"
  frameBorder="0"
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowFullScreen
></iframe></>
        
        ) : (
          <>
            <Button
              style={{ alignSelf: "flex-end" }}
              onClick={() => close(false)}
            >
              Close
            </Button>
            <div
              style={{
                width: "100%",
                height: "100%",
                background: "#000",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "18px",
                borderRadius: "8px",
              }}
            >
              ⚠️ Không thể phát video với URL này
            </div></>


        )}
      </div>
    </div>
  );
}


function getYouTubeEmbedUrl(url) {
  const regExp =
    /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);
  if (match && match[2].length === 11) {
    const videoId = match[2];

    // Lấy query params (t, start)
    const urlObj = new URL(url);
    let startTime = 0;

    if (urlObj.searchParams.get("t")) {
      // YouTube cho "t=242s" hoặc "t=242"
      const t = urlObj.searchParams.get("t");
      startTime = parseInt(t.replace("s", ""), 10);
    }

    if (urlObj.searchParams.get("start")) {
      startTime = parseInt(urlObj.searchParams.get("start"), 10);
    }

    return `https://www.youtube.com/embed/${videoId}${
      startTime ? `?start=${startTime}` : ""
    }`;
  }
  return null;
}
