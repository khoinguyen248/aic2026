// TrakePanel.jsx — enter N events -> /search/trake -> combo list -> click to verify frames
import { useState } from 'react'
import { Input, InputNumber, Button, Spin, Tag } from 'antd'
import { IoIosAddCircle } from 'react-icons/io'
import { CiLink } from 'react-icons/ci'
import { FaFolderOpen } from 'react-icons/fa'
import { trakeSearch, frameUrl } from './api'
import Infor from './Infor'

const fmtTime = (frameId, fps) => {
  if (!fps || fps <= 0) return ''
  const s = frameId / fps
  const m = Math.floor(s / 60)
  return `${m}m${Math.round(s - 60 * m)}s`
}

// One frame image cell.
// Case 2: có path keyframe -> hiện ảnh keyframe (/frames/<path>). Case 1: decode frame gốc từ video.
function FrameCell({ L, V, videoId, frameId, fps, videoUrl, eventIdx, path, onOpenInfo }) {
  const [failed, setFailed] = useState(false)
  const t = fps ? Math.floor(frameId / fps) : null
  const yt = videoUrl ? `${videoUrl}${videoUrl.includes('?') ? '&' : '?'}t=${t}s` : null
  const src = path ? `/frames/${String(path).replace(/^\/+/, '')}` : frameUrl(L, V, frameId)
  return (
    <div style={{ width: 150 }}>
      {failed ? (
        <div style={{ width: 150, height: 90, background: '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12, borderRadius: 6, textAlign: 'center', padding: 4 }}>
          No image<br />(frame unavailable)
        </div>
      ) : (
        <img
          src={src}
          alt={`frame ${frameId}`}
          style={{ width: 150, height: 90, objectFit: 'cover', borderRadius: 6, border: '1px solid #eee' }}
          onError={() => setFailed(true)}
        />
      )}
      <div style={{ fontSize: 12, color: '#888' }}>Event {eventIdx + 1}</div>
      <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: 6 }}>
        frame {frameId}
        {yt && (
          <a href={yt} target="_blank" rel="noopener noreferrer"><CiLink /></a>
        )}
        {/* Xem 10 frame trước + 10 frame sau của frame này */}
        <FaFolderOpen
          title="Xem ±10 frame"
          style={{ cursor: 'pointer', color: '#1677ff' }}
          onClick={() => onOpenInfo({ L, V, video_id: videoId, frame_id: frameId })}
        />
      </div>
      <div style={{ fontSize: 12, color: '#aaa' }}>{fmtTime(frameId, fps)}</div>
    </div>
  )
}

export default function TrakePanel({ language = false, model = 'beit3' }) {
  // Mỗi event: { q: mô tả hình ảnh, ocr: chữ trên màn hình, asr: lời nói } — ocr/asr tùy chọn.
  const [events, setEvents] = useState([{ q: '', ocr: '', asr: '' }, { q: '', ocr: '', asr: '' }])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [openKey, setOpenKey] = useState(null) // `${vi}-${ci}`
  const [maxCombos, setMaxCombos] = useState(100) // số tổ hợp hiển thị (trần 500)
  const [topVideos, setTopVideos] = useState(2)   // số video xét ở tầng 1 (nhiều -> nhiều L hơn)
  const [infoFrame, setInfoFrame] = useState(null) // frame đang xem ±10 ({L, V, frame_id}) | null

  const setField = (i, field, val) =>
    setEvents(prev => prev.map((e, idx) => (idx === i ? { ...e, [field]: val } : e)))
  const addEvent = () => setEvents(prev => [...prev, { q: '', ocr: '', asr: '' }])
  const removeEvent = (i) => setEvents(prev => (prev.length <= 2 ? prev : prev.filter((_, idx) => idx !== i)))

  const runSearch = async () => {
    // Event "hợp lệ" = có mô tả hình HOẶC OCR HOẶC ASR (không bắt buộc mô tả hình).
    const picked = events.filter(e => e.q.trim() || (e.ocr || '').trim() || (e.asr || '').trim())
    if (picked.length < 2) { setError('Need ≥2 events (each event: visual description OR OCR OR ASR)'); return }
    const payload = {
      events: picked.map(e => e.q.trim()), language, model,
      max_combos: maxCombos, top_videos: topVideos,
    }
    // OCR/ASR đi song song với events đã lọc (map theo event). Chỉ gửi khi có ít nhất 1 ô.
    const ocr = picked.map(e => (e.ocr || '').trim())
    const asr = picked.map(e => (e.asr || '').trim())
    if (ocr.some(Boolean)) payload.events_ocr = ocr
    if (asr.some(Boolean)) payload.events_asr = asr
    setError(''); setLoading(true); setResult(null); setOpenKey(null)
    try {
      const resp = await trakeSearch(payload)
      if (!resp.data?.ok) { setError(resp.data?.error || 'Search failed'); }
      else setResult(resp.data)
    } catch (err) {
      setError(err?.response?.data?.error || err.message || 'Backend connection error')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ padding: 16, background: '#fff', borderRadius: 10, boxShadow: '0 1px 6px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Tag color="blue">TRAKE</Tag>
        <span style={{ color: '#888', fontSize: 13 }}>Enter events in chronological order</span>
      </div>

      {events.map((ev, i) => (
        <div key={i} style={{ marginBottom: 12, borderLeft: '2px solid #f0f0f0', paddingLeft: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 62, color: '#666', fontSize: 13 }}>Event {i + 1}</span>
            <Input
              value={ev.q}
              placeholder={`visual description for moment ${i + 1} (optional if OCR/ASR given)`}
              onChange={(e) => setField(i, 'q', e.target.value)}
              onPressEnter={runSearch}
            />
            <Button type="text" danger disabled={events.length <= 2} onClick={() => removeEvent(i)}>✕</Button>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 6, marginLeft: 70, marginRight: 40 }}>
            <Input
              size="small"
              addonBefore="OCR"
              value={ev.ocr}
              placeholder="on-screen text (optional)"
              onChange={(e) => setField(i, 'ocr', e.target.value)}
              onPressEnter={runSearch}
            />
            <Input
              size="small"
              addonBefore="ASR"
              value={ev.asr}
              placeholder="spoken words in segment (optional)"
              onChange={(e) => setField(i, 'asr', e.target.value)}
              onPressEnter={runSearch}
            />
          </div>
        </div>
      ))}

      <div style={{ display: 'flex', gap: 8, marginTop: 4, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button icon={<IoIosAddCircle />} onClick={addEvent}>Add event</Button>
        <Button type="primary" loading={loading} onClick={runSearch}>TRAKE search</Button>
        <span style={{ fontSize: 12, color: '#666', marginLeft: 8 }}>combos</span>
        <InputNumber size="small" min={1} max={500} step={50} value={maxCombos}
          onChange={(v) => setMaxCombos(v || 100)} style={{ width: 80 }} />
        <span style={{ fontSize: 12, color: '#666' }}>videos</span>
        <InputNumber size="small" min={1} max={20} value={topVideos}
          onChange={(v) => setTopVideos(v || 2)} style={{ width: 64 }} />
        <span style={{ fontSize: 11, color: '#aaa' }}>(more videos = more variety)</span>
      </div>

      {error && <div style={{ color: '#d4380d', marginTop: 12 }}>{error}</div>}
      {loading && <div style={{ marginTop: 16 }}><Spin /> Searching...</div>}

      {result && (
        <div style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 10, fontSize: 13 }}>
            <Tag color={result.tier === 3 ? 'green' : 'gold'}>
              {result.tier === 3 ? 'Case 1 · 3 tiers' : 'Case 2 · 2 tiers'}
            </Tag>
            <Tag color={result.rerank_method === 'qwen' ? 'purple' : 'default'}>
              rerank: {result.rerank_method === 'qwen' ? 'Qwen2.5-VL' : 'algorithm'}
            </Tag>
            {result.ocr_asr_applied && (
              <Tag color="cyan">OCR/ASR boost · {result.ocr_asr_boosted_frames || 0} hit</Tag>
            )}
            <span style={{ color: '#aaa' }}>
              {result.submissions?.length || 0} combos · {result.tier3_reason}
            </span>
          </div>

          {(result.per_video || []).map((vid, vi) => (
            <div key={vi} style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                {vid.video_id}
                <span style={{ color: '#aaa', fontWeight: 400, fontSize: 12, marginLeft: 8 }}>
                  fps {vid.fps ?? '?'} · score {vid.video_score?.toFixed(2)}
                  {vid.tier3_used ? ' · refined' : ''}
                </span>
              </div>

              {(vid.combos || []).map((combo, ci) => {
                const key = `${vi}-${ci}`
                const open = openKey === key
                return (
                  <div key={ci} style={{ border: '1px solid #eee', borderRadius: 8, marginBottom: 6 }}>
                    <div
                      onClick={() => setOpenKey(open ? null : key)}
                      style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', cursor: 'pointer' }}
                    >
                      <span style={{ color: '#bbb', width: 28, fontSize: 12 }}>#{ci + 1}</span>
                      <span style={{ fontWeight: 600 }}>{vid.video_id}</span>
                      <span style={{ color: '#555', fontFamily: 'monospace' }}>→ {combo.join(', ')}</span>
                      <span style={{ marginLeft: 'auto', color: '#999' }}>{open ? '▾' : '▸'}</span>
                    </div>
                    {open && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, padding: '4px 12px 12px' }}>
                        {combo.map((fid, ei) => (
                          <FrameCell
                            key={ei}
                            L={vid.L}
                            V={vid.V}
                            videoId={vid.video_id}
                            frameId={fid}
                            fps={vid.fps}
                            videoUrl={vid.video_url}
                            eventIdx={ei}
                            path={vid.frame_paths?.[String(fid)]}
                            onOpenInfo={setInfoFrame}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}

      {/* Modal ±10 frame quanh frame được chọn (tái dùng từ search results) */}
      {infoFrame && (
        <Infor
          setModalFlag={() => setInfoFrame(null)}
          selectedFrame={infoFrame}
        />
      )}
    </div>
  )
}
