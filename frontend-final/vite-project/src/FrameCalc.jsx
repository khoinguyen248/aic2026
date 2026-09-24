// FrameCalc.jsx — frame tool for long-segment KIS: enter fps + start/end
// (seconds "mm:ss"/"s" or frame) -> auto-computes the MIDDLE frame to submit. No manual seconds×fps.
import { useState } from 'react'
import { Input, InputNumber, Radio, Button, message } from 'antd'

// "6:31" / "1:06:31" / "391.4" -> seconds (float). Invalid -> null.
function parseTime(s) {
  s = String(s ?? '').trim()
  if (!s) return null
  if (s.includes(':')) {
    const parts = s.split(':').map((x) => Number(x))
    if (parts.some((x) => Number.isNaN(x))) return null
    return parts.reduce((acc, p) => acc * 60 + p, 0)
  }
  const n = parseFloat(s)
  return Number.isNaN(n) ? null : n
}

const fmtTime = (sec) => {
  if (sec == null || !isFinite(sec)) return ''
  const m = Math.floor(sec / 60)
  const s = sec - 60 * m
  return `${m}m${s.toFixed(1)}s`
}

export default function FrameCalc() {
  const [fps, setFps] = useState(25)
  const [unit, setUnit] = useState('sec') // 'sec' | 'frame'
  const [startVal, setStartVal] = useState('')
  const [endVal, setEndVal] = useState('')

  // Convert one input -> frame (by unit + fps).
  const toFrame = (v) => {
    if (unit === 'frame') {
      const n = parseInt(v, 10)
      return Number.isNaN(n) ? null : n
    }
    const sec = parseTime(v)
    return sec == null || !fps ? null : Math.round(sec * fps)
  }

  const sF = toFrame(startVal)
  const eF = toFrame(endVal)
  const midFrame =
    sF != null && eF != null ? Math.round((sF + eF) / 2) : sF != null ? sF : null
  const midSec = midFrame != null && fps ? midFrame / fps : null

  const copy = async (val) => {
    try {
      await navigator.clipboard.writeText(String(val))
      message.success(`Copied ${val}`)
    } catch {
      message.info(`Frame: ${val}`)
    }
  }

  const box = { background: '#fafafa', border: '1px solid #eee', borderRadius: 8, padding: 10 }
  const lbl = { fontSize: 12, color: '#666', minWidth: 42 }
  const row = { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontWeight: 600 }}>Frame calculator — long segment → middle frame</div>
      <div style={box}>
        <div style={row}>
          <span style={lbl}>fps</span>
          <InputNumber value={fps} min={1} step={1} onChange={(v) => setFps(v || 25)} style={{ width: 90 }} />
          <Radio.Group size="small" value={unit} onChange={(e) => setUnit(e.target.value)}>
            <Radio.Button value="sec">sec</Radio.Button>
            <Radio.Button value="frame">frame</Radio.Button>
          </Radio.Group>
        </div>
        <div style={row}>
          <span style={lbl}>start</span>
          <Input
            size="small"
            value={startVal}
            placeholder={unit === 'sec' ? 'mm:ss or seconds' : 'frame number'}
            onChange={(e) => setStartVal(e.target.value)}
          />
          <span style={{ fontSize: 12, color: '#aaa', width: 70 }}>{sF != null ? `f ${sF}` : ''}</span>
        </div>
        <div style={row}>
          <span style={lbl}>end</span>
          <Input
            size="small"
            value={endVal}
            placeholder={unit === 'sec' ? 'mm:ss or seconds (empty = single point)' : 'frame number (empty = single point)'}
            onChange={(e) => setEndVal(e.target.value)}
          />
          <span style={{ fontSize: 12, color: '#aaa', width: 70 }}>{eF != null ? `f ${eF}` : ''}</span>
        </div>

        {midFrame != null ? (
          <div style={{ marginTop: 4, paddingTop: 8, borderTop: '1px dashed #ddd' }}>
            <div style={{ fontSize: 12, color: '#888' }}>
              {eF != null ? 'MIDDLE frame' : 'Frame'} {midSec != null ? `· ${fmtTime(midSec)}` : ''}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
              <span style={{ fontSize: 22, fontWeight: 700, fontFamily: 'monospace', color: '#1677ff' }}>
                {midFrame}
              </span>
              <Button size="small" onClick={() => copy(midFrame)}>Copy</Button>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: '#bbb', marginTop: 4 }}>Enter marks to compute…</div>
        )}
      </div>
      <div style={{ fontSize: 11, color: '#aaa' }}>
        ⚠️ fps must match the actual video (some videos are 30fps even if metadata says 25). Wrong fps → wrong frame.
      </div>
    </div>
  )
}
