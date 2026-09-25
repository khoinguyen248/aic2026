import React, { useEffect, useState } from 'react'
import './Infor.css'
import { Button, Tag } from 'antd'
import { searchinfo } from './api';
import { CiLink } from "react-icons/ci";

// Từ 1 frame doc -> draft để nộp (video_id + frame_id + thời gian ms).
const frameDraft = (f) => {
  const t = Number(f.frame_stamp)
  const mstime = Number.isFinite(t)
    ? Math.floor(t * 1000)
    : (f.fps ? Math.floor((Number(f.frame_id) / Number(f.fps)) * 1000) : 0)
  return { video_id: f.video_id, L: f.L, V: f.V, frame_id: f.frame_id, fps: f.fps, mstime }
}

const Infor = ({ setModalFlag, selectedFrame, onSubmitSingle, trakeEvents, onSubmitCombo }) => {
  // Lấy 10 trước và 10 sau. TRAKE truyền frame_id (không có idx) -> vẫn chạy.
  const hasKey = (v) => v !== undefined && v !== null && String(v) !== ''

  const [frames, setFrames] = useState([])
  const [targetIdx, setTargetIdx] = useState(null)
  const [error, setError] = useState('')
  const [showAll, setShowAll] = useState(false) // false = ±10 (mặc định), true = toàn bộ video
  const [picks, setPicks] = useState([])         // TRAKE: frame đã chọn theo thứ tự event

  const isTrake = Number(trakeEvents) >= 2
  const close = () => setModalFlag(false)

  useEffect(() => {
    if (!hasKey(selectedFrame?.idx) && !hasKey(selectedFrame?.frame_id)) {
      setFrames([])
      return
    }
    let cancelled = false
    const fetchInfo = async () => {
      try {
        setError('')
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

  const pickFrame = (f) => setPicks((prev) => (prev.length >= trakeEvents ? prev : [...prev, f]))
  const undoPick = () => setPicks((prev) => prev.slice(0, -1))
  const submitCombo = () => {
    if (picks.length < 2) return
    onSubmitCombo?.(picks.map((p) => Number(p.frame_id)))
    close()
  }
  const submitSingle = (f) => {
    onSubmitSingle?.(frameDraft(f))
    close()
  }

  return (
    <div className="overlay">
      <div className="content">
        <Button style={{ alignSelf: "flex-end" }} onClick={close}>Close</Button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '8px 0', flexWrap: 'wrap' }}>
          <Button size="small" type={showAll ? 'default' : 'primary'} onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Chỉ ±10' : 'Xem toàn bộ video'}
          </Button>
          <span style={{ fontWeight: 600 }}>
            {frames.length > 0 ? `${frames.length} keyframe ${showAll ? '(toàn bộ)' : '(±10)'} · viền đỏ = frame gốc` : ''}
          </span>
        </div>

        {/* TRAKE: thanh chọn combo theo event */}
        {isTrake && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 10px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600 }}>Chọn frame theo thứ tự event ({picks.length}/{trakeEvents}):</span>
            {picks.map((p, i) => (
              <Tag key={i} color="blue">E{i + 1}: {p.frame_id}</Tag>
            ))}
            <Button size="small" onClick={undoPick} disabled={!picks.length}>Hoàn tác</Button>
            <Button size="small" type="primary" danger onClick={submitCombo} disabled={picks.length < 2}>
              Nộp combo ({picks.length})
            </Button>
          </div>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: "10px",
            marginTop: "8px"
          }}
        >
          {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
          {frames.map((f, i) => {
            const pathVal = f.path || "";
            const imageUrl = pathVal.startsWith("http") ? pathVal : `/frames/${pathVal.replace(/^\/+/, "")}`;
            const time = f.frame_stamp;
            const isTarget = Number(f.idx) === Number(targetIdx);
            return (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <img
                  id={isTarget ? 'infor-target' : undefined}
                  src={imageUrl}
                  alt={`frame-${f.frame_id}`}
                  loading="lazy"
                  style={{
                    width: "180px", height: "100px", objectFit: "cover",
                    border: isTarget ? "3px solid red" : "1px solid #eee",
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <p style={{ margin: 0, fontSize: 13 }}>
                    {`${parseInt(f.L) <= 20 ? "K" : "L"}: ${f.L}${f.V ? " - V: " + f.V : ""} - ${f.frame_id}`}
                  </p>
                  <a href={`${f.video_url}&t=${time}s`} target="_blank" rel="noopener noreferrer"><CiLink /></a>
                </div>
                {/* Nút nộp/chọn frame này (khác frame viền đỏ vẫn nộp được) */}
                {isTrake ? (
                  <Button
                    size="small"
                    onClick={() => pickFrame(f)}
                    disabled={picks.length >= trakeEvents}
                  >
                    Chọn E{Math.min(picks.length + 1, trakeEvents)}
                  </Button>
                ) : onSubmitSingle ? (
                  <Button size="small" type="primary" onClick={() => submitSingle(f)}>
                    Nộp frame này
                  </Button>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  )
}

export default Infor
