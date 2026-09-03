// AsrResults.jsx — render standalone ASR search results.
// Mỗi đoạn lời nói có khoảng frame -> hiện luôn các keyframe trong khoảng đó
// (ảnh keyframe đọc từ Qdrant qua /search/framerange, giống OCR/main search).
import { useEffect, useState } from 'react'
import { Tag } from 'antd'
import { CiLink } from 'react-icons/ci'
import { framesInRange } from './api'

const frameSrc = (path) =>
  path
    ? (String(path).startsWith('http') ? String(path) : `/frames/${String(path).replace(/^\/+/, '')}`)
    : null

// 1 keyframe trong strip.
function KeyframeCell({ f, videoUrl }) {
  const [failed, setFailed] = useState(false)
  const src = frameSrc(f.path)
  const t = f.frame_stamp != null ? Math.floor(f.frame_stamp) : null
  const yt = videoUrl && t != null
    ? `${videoUrl}${videoUrl.includes('?') ? '&' : '?'}t=${t}s`
    : null
  return (
    <div style={{ width: 140, flexShrink: 0 }}>
      {src && !failed ? (
        <img
          src={src}
          alt={`frame ${f.frame_id}`}
          style={{ width: 140, height: 80, objectFit: 'cover', borderRadius: 6, border: '1px solid #eee' }}
          onError={() => setFailed(true)}
        />
      ) : (
        <div style={{ width: 140, height: 80, background: '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 11, borderRadius: 6 }}>
          no image
        </div>
      )}
      <div style={{ fontSize: 12, fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: 4 }}>
        {f.frame_id}
        {yt && <a href={yt} target="_blank" rel="noopener noreferrer"><CiLink /></a>}
      </div>
    </div>
  )
}

// Strip keyframe cho 1 đoạn ASR: tự fetch theo khoảng frame.
function SegKeyframes({ videoId, L, V, frameStart, frameEnd }) {
  const [frames, setFrames] = useState(null) // null = loading
  const [truncated, setTruncated] = useState(false)
  const [videoUrl, setVideoUrl] = useState(null)

  useEffect(() => {
    let alive = true
    setFrames(null)
    framesInRange({ video_id: videoId, L, V, frame_start: frameStart, frame_end: frameEnd })
      .then((r) => {
        if (!alive) return
        const res = r.data?.results || []
        setFrames(res)
        setTruncated(Boolean(r.data?.truncated))
        setVideoUrl(res[0]?.video_url || null)
      })
      .catch(() => { if (alive) setFrames([]) })
    return () => { alive = false }
  }, [videoId, L, V, frameStart, frameEnd])

  if (frames === null) return <div style={{ color: '#aaa', fontSize: 12, marginTop: 8 }}>Loading keyframes…</div>
  if (frames.length === 0) return <div style={{ color: '#bbb', fontSize: 12, marginTop: 8 }}>No keyframe in this range</div>

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>
        {frames.length} keyframe{frames.length > 1 ? 's' : ''}
        {truncated ? ' (showing first ' + frames.length + ')' : ''}
      </div>
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
        {frames.map((f, i) => <KeyframeCell key={i} f={f} videoUrl={videoUrl} />)}
      </div>
    </div>
  )
}

export default function AsrResults({ loading, error, results }) {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Tag color="cyan">ASR · spoken content</Tag>
        {!loading && !error && <span style={{ color: '#888' }}>{results?.length || 0} matched segments</span>}
      </div>

      {loading && <div>Searching...</div>}
      {error && <div style={{ color: '#d4380d' }}>{error}</div>}
      {!loading && !error && (results?.length || 0) === 0 && (
        <div style={{ color: '#aaa' }}>No results yet. Enter spoken content in the sidebar and click ASR Search.</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {(results || []).map((s, i) => {
          const t = s.t_start != null ? Math.floor(s.t_start) : null
          const yt = s.video_url && t != null
            ? `${s.video_url}${s.video_url.includes('?') ? '&' : '?'}t=${t}s`
            : null
          return (
            <div key={i} style={{ border: '1px solid #eee', borderRadius: 10, padding: 12, background: '#fff' }}>
              <div style={{ fontWeight: 600 }}>
                {s.video_id}
                <span style={{ color: '#aaa', fontWeight: 400, fontSize: 12, marginLeft: 8 }}>
                  {s.t_start != null ? `${s.t_start}s–${s.t_end}s` : ''} · frame {s.frame_start}–{s.frame_end}
                </span>
                {yt && <a href={yt} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 8 }}><CiLink /></a>}
              </div>
              <div style={{ marginTop: 6, lineHeight: 1.5 }}>{s.text}</div>
              <SegKeyframes
                videoId={s.video_id}
                L={s.L}
                V={s.V}
                frameStart={s.frame_start}
                frameEnd={s.frame_end}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
