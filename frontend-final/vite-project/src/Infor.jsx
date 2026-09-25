import React, { useEffect, useState } from 'react'
import './Infor.css'
import { Button } from 'antd'
import { searchinfo } from './api';
import { CiLink } from "react-icons/ci";


const Infor = ({ setModalFlag, selectedFrame }) => {
  // Lấy 10 trước và 10 sau. TRAKE truyền frame_id (không có idx) -> vẫn chạy.
  const hasKey = (v) => v !== undefined && v !== null && String(v) !== ''

const [frames, setFrames] = useState([])
const [targetIdx, setTargetIdx] = useState(null)
const [error, setError] = useState('')
const [showAll, setShowAll] = useState(false) // false = ±10 (mặc định), true = toàn bộ video

useEffect(() => {
  // Chỉ bỏ qua khi thiếu CẢ idx lẫn frame_id.
  if (!hasKey(selectedFrame?.idx) && !hasKey(selectedFrame?.frame_id)) {
    setFrames([])
    return
  }

  let cancelled = false
  const fetchInfo = async () => {
    try {
      setError('')
      // showAll=false -> ±10 (window:10); showAll=true -> toàn bộ keyframe của video V.
      const response = await searchinfo({ ...selectedFrame, full: showAll, window: 10 })
      if (!cancelled) {
        setFrames(response.data.results || [])
        setTargetIdx(response.data.target_idx ?? selectedFrame?.idx ?? null)
      }
    } catch (requestError) {
      console.error('Unable to load neighbouring frames:', requestError)
      if (!cancelled) {
        setFrames([])
        setError(requestError.response?.data?.error || 'Không thể tải các frame lân cận.')
      }
    }
  }

  fetchInfo()
  return () => { cancelled = true }
}, [selectedFrame, showAll])

// Cuộn tới frame gốc (viền đỏ) sau khi danh sách load xong.
useEffect(() => {
  if (!frames.length) return
  const el = document.getElementById('infor-target')
  if (el) el.scrollIntoView({ block: 'center' })
}, [frames, targetIdx])
  return (
    <div className="overlay">
      <div className="content">
        <Button
          style={{ alignSelf: "flex-end" }}
          onClick={() => setModalFlag(false)}
        >
          Close
        </Button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '8px 0' }}>
          <Button size="small" type={showAll ? 'default' : 'primary'} onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Chỉ ±10' : 'Xem toàn bộ video'}
          </Button>
          <span style={{ fontWeight: 600 }}>
            {frames.length > 0 ? `${frames.length} keyframe ${showAll ? '(toàn bộ)' : '(±10)'} · viền đỏ = frame đang chọn` : ''}
          </span>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)", // 5 cột mỗi hàng
            gap: "10px",
            marginTop: "8px"
          }}
        >
          {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
          {frames.map((f, i) => {
            let pathVal = f.path || "";
            const imageUrl = pathVal.startsWith("http")
              ? pathVal
              : `/frames/${pathVal.replace(/^\/+/, "")}`;
              console.log("f.idx:", f.idx, "typeof:", typeof f.idx);
              const time = f.frame_stamp
   return (
    <>
    <div style={{display:'flex', flexDirection:'column', }}>
       <img
                key={i}
                id={Number(f.idx) === Number(targetIdx) ? 'infor-target' : undefined}
                src={imageUrl}
                alt={`frame-${f.frame_id}`}
                loading="lazy"
style={{
        width: "180px",
        height: "100px",
        objectFit: "cover",
                     border: Number(f.idx) === Number(targetIdx)
                      ? "3px solid red"
                      : "none"

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
