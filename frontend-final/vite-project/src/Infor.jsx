import React, { useEffect, useState } from 'react'
import './Infor.css'
import { Button } from 'antd'
import { searchinfo } from './api';
import { CiLink } from "react-icons/ci";


const Infor = ({ setModalFlag, selectedFrame }) => {
  const idChecked = selectedFrame.idx

  // Lấy 10 trước và 10 sau
const fetchInfo = async () => {
console.log(selectedFrame)
const response = await searchinfo(selectedFrame)
const frames = response.data.results
console.log(frames)
setFrames(frames)
}

const [frames, setFrames] = useState([])

useEffect(()=> {
fetchInfo()
}, [idChecked])
  return (
    <div className="overlay">
      <div className="content">
        <Button
          style={{ alignSelf: "flex-end" }}
          onClick={() => setModalFlag(false)}
        >
          Close
        </Button>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)", // 5 cột => 2 hàng = 20 frame
            gap: "10px",
            marginTop: "20px"
          }}
        >
          {frames.map((f, i) => {
            let pathVal = f.path || "";
            const imageUrl = pathVal.startsWith("http")
              ? pathVal
              : `http://localhost:8080/${pathVal.replace(/^\/+/, "")}`;
              console.log("f.idx:", f.idx, "typeof:", typeof f.idx);
              const time = f.frame_stamp
   return (
    <>
    <div style={{display:'flex', flexDirection:'column', }}>
       <img
                key={i}
                src={imageUrl}
                alt={`frame-${f.frame_id}`}
style={{
        width: "180px",
        height: "100px",
        objectFit: "cover",
                     border: Number(f.idx) === Number(idChecked) ? "3px solid red" : "none"

      }}                
              />
              <div style={{display:'flex', alignItems:'center'}}>
                <p>{`${parseInt(f.L) <= 20 ? "K" : "L"}: ${f.L}${f.V ? " - V: " + f.V : ""} - ${f.
frame_id}`}</p>
<a href={`${f.video_url}&t=${time}s`} target="_blank" 
  rel="noopener noreferrer"><CiLink/></a>
              </div>
              
    </div>
    
    </>
             
            );
          })}
        </div>
      </div>
    </div>
  )
}

export default Infor
