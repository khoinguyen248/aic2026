// AsrResults.jsx — render standalone ASR search results (matched speech segments -> frame)
import { useState } from 'react'
import { Tag } from 'antd'
import { CiLink } from 'react-icons/ci'
import { frameUrl } from './api'

function SegImage({ L, V, frameId, alt }) {
  const [failed, setFailed] = useState(false)
  const noData = L == null || V == null || frameId == null
  if (noData || failed) {
    return (
      <div style={{ width: 200, height: 112, background: '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12, borderRadius: 6, textAlign: 'center', padding: 4, flexShrink: 0 }}>
        No image<br />(no video on machine)
      </div>
    )
  }
  return (
    <img
      src={frameUrl(L, V, frameId)}
      alt={alt}
      style={{ width: 200, height: 112, objectFit: 'cover', borderRadius: 6, border: '1px solid #eee', flexShrink: 0 }}
      onError={() => setFailed(true)}
    />
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
            <div key={i} style={{ display: 'flex', gap: 14, border: '1px solid #eee', borderRadius: 10, padding: 12, background: '#fff' }}>
              <SegImage L={s.L} V={s.V} frameId={s.frame_start} alt={`asr-${i}`} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>
                  {s.video_id}
                  <span style={{ color: '#aaa', fontWeight: 400, fontSize: 12, marginLeft: 8 }}>
                    {s.t_start != null ? `${s.t_start}s–${s.t_end}s` : ''} · frame {s.frame_start}–{s.frame_end}
                    {s.fps != null ? ` · fps ${s.fps}` : ''}
                  </span>
                  {yt && <a href={yt} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 8 }}><CiLink /></a>}
                </div>
                <div style={{ marginTop: 6, lineHeight: 1.5 }}>{s.text}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}