// TrakePanel.jsx — enter N events -> /search/trake -> combo list -> click to verify frames
import { useState } from 'react'
import { Input, Button, Spin, Tag } from 'antd'
import { IoIosAddCircle } from 'react-icons/io'
import { CiLink } from 'react-icons/ci'
import { trakeSearch, frameUrl } from './api'

const fmtTime = (frameId, fps) => {
  if (!fps || fps <= 0) return ''
  const s = frameId / fps
  const m = Math.floor(s / 60)
  return `${m}m${Math.round(s - 60 * m)}s`
}

// One frame image cell: try decoding from video; on error (Case 2 / no video) -> placeholder
function FrameCell({ L, V, frameId, fps, videoUrl, eventIdx }) {
  const [failed, setFailed] = useState(false)
  const t = fps ? Math.floor(frameId / fps) : null
  const yt = videoUrl ? `${videoUrl}${videoUrl.includes('?') ? '&' : '?'}t=${t}s` : null
  return (
    <div style={{ width: 150 }}>
      {failed ? (
        <div style={{ width: 150, height: 90, background: '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12, borderRadius: 6, textAlign: 'center', padding: 4 }}>
          No image<br />(2-tier machine)
        </div>
      ) : (
        <img
          src={frameUrl(L, V, frameId)}
          alt={`frame ${frameId}`}
          style={{ width: 150, height: 90, objectFit: 'cover', borderRadius: 6, border: '1px solid #eee' }}
          onError={() => setFailed(true)}
        />
      )}
      <div style={{ fontSize: 12, color: '#888' }}>Event {eventIdx + 1}</div>
      <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace' }}>
        frame {frameId}
        {yt && (
          <a href={yt} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 6 }}><CiLink /></a>
        )}
      </div>
      <div style={{ fontSize: 12, color: '#aaa' }}>{fmtTime(frameId, fps)}</div>
    </div>
  )
}

export default function TrakePanel({ language = false, device = 'cpu' }) {
  const [events, setEvents] = useState(['', ''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [openKey, setOpenKey] = useState(null) // `${vi}-${ci}`

  const setEvent = (i, val) => setEvents(prev => prev.map((e, idx) => (idx === i ? val : e)))
  const addEvent = () => setEvents(prev => [...prev, ''])
  const removeEvent = (i) => setEvents(prev => (prev.length <= 2 ? prev : prev.filter((_, idx) => idx !== i)))

  const runSearch = async () => {
    const evs = events.map(e => e.trim()).filter(Boolean)
    if (evs.length < 2) { setError('Need at least 2 events (in chronological order)'); return }
    setError(''); setLoading(true); setResult(null); setOpenKey(null)
    try {
      const resp = await trakeSearch({ events: evs, language, device })
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
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{ width: 62, color: '#666', fontSize: 13 }}>Event {i + 1}</span>
          <Input
            value={ev}
            placeholder={`describe moment ${i + 1}`}
            onChange={(e) => setEvent(i, e.target.value)}
            onPressEnter={runSearch}
          />
          <Button type="text" danger disabled={events.length <= 2} onClick={() => removeEvent(i)}>✕</Button>
        </div>
      ))}

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <Button icon={<IoIosAddCircle />} onClick={addEvent}>Add event</Button>
        <Button type="primary" loading={loading} onClick={runSearch}>TRAKE search</Button>
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
                            frameId={fid}
                            fps={vid.fps}
                            videoUrl={vid.video_url}
                            eventIdx={ei}
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
    </div>
  )
}
