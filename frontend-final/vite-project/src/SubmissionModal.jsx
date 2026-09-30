import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Collapse,
  Divider,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  DEFAULT_DRES_URL,
  describeDresError,
  listDresEvaluations,
  loginToDres,
  submitToDres,
} from './dresApi'
import './SubmissionModal.css'

const { Text } = Typography

const STORAGE = {
  baseUrl: 'aic2026.dres.baseUrl',
  evaluationId: 'aic2026.dres.evaluationId',
  sessionId: 'aic2026.dres.sessionId',
}

const TASK_OPTIONS = [
  { value: 'kis', label: 'Textual / Video KIS' },
  { value: 'qa', label: 'Q&A' },
  { value: 'trake', label: 'TRAKE' },
]

const readLocal = (key, fallback = '') => {
  try { return localStorage.getItem(key) || fallback } catch { return fallback }
}

const readSession = (key, fallback = '') => {
  try { return sessionStorage.getItem(key) || fallback } catch { return fallback }
}

const normalizeVideoId = (value) => String(value || '').trim().toUpperCase()

const frameVideoId = (frame) => {
  if (!frame) return ''
  // Ưu tiên video_id gốc (đã đúng, không thêm tiền tố). VD batch2: N075-V001.
  if (frame.video_id) return normalizeVideoId(frame.video_id)
  const lClean = String(frame.L || '').trim()
  const vRaw = String(frame.V || '').replace(/^V/i, '').padStart(3, '0')
  if (!lClean || !vRaw) return ''
  // L đã có tiền tố chữ khác K/L (N/S/M...) -> giữ nguyên, KHÔNG thêm L.
  if (/^[A-Za-z]/.test(lClean) && !/^[KL]\d/i.test(lClean)) {
    return `${lClean.toUpperCase()}-V${vRaw}`
  }
  const lNum = lClean.replace(/^[KL]/i, '').padStart(2, '0')
  return `${Number(lNum) <= 20 ? 'K' : 'L'}${lNum}_V${vRaw}`
}

const initialFrames = (draft) => {
  const source = draft?.frameIds?.length ? draft.frameIds : [draft?.frame_id]
  return source.filter((value) => value !== undefined && value !== null && value !== '')
    .map((value) => String(value))
}

const makePayload = ({ taskType, videoId, timeMs, answer, frameIds }) => {
  if (taskType === 'kis') {
    return { answerSets: [{ answers: [{ mediaItemName: videoId, start: String(timeMs), end: String(timeMs) }] }] }
  }
  if (taskType === 'qa') {
    return { answerSets: [{ answers: [{ text: `QA-${answer.trim()}-${videoId}-${timeMs}` }] }] }
  }
  return { answerSets: [{ answers: [{ text: `TR-${videoId}-${frameIds.join(',')}` }] }] }
}

// Diễn giải phản hồi DRES thành banner dễ đọc (xanh = đúng, đỏ = sai).
const verdictOf = (resp) => {
  if (!resp) return null
  if (resp.error) return { type: 'error', text: '✗ Nộp KHÔNG được nhận (lỗi)', desc: String(resp.error) }
  const s = String(resp.submission ?? '').toUpperCase()
  if (s === 'CORRECT') return { type: 'success', text: '✓ ĐÚNG! (CORRECT)', desc: resp.description }
  if (s === 'WRONG') return { type: 'error', text: '✗ SAI (WRONG) — bị trừ 10 điểm', desc: resp.description }
  if (s === 'INDETERMINATE' || s === 'UNDECIDABLE') return { type: 'warning', text: `Chưa xác định (${s})`, desc: resp.description }
  if (resp.status === true) return { type: 'success', text: '✓ DRES đã nhận bài', desc: resp.description }
  return { type: 'info', text: 'Đã nhận phản hồi từ DRES', desc: resp.description }
}

export default function SubmissionModal({ open, onClose, draft, defaultTaskType = 'kis' }) {
  const [taskType, setTaskType] = useState(defaultTaskType)
  const [videoId, setVideoId] = useState('')
  const [timeMs, setTimeMs] = useState(0)
  const [answer, setAnswer] = useState('')
  const [frameIds, setFrameIds] = useState([])

  const [baseUrl, setBaseUrl] = useState(() => readLocal(STORAGE.baseUrl, DEFAULT_DRES_URL))
  const [sessionId, setSessionId] = useState(() => readSession(STORAGE.sessionId))
  const [evaluationId, setEvaluationId] = useState(() => readLocal(STORAGE.evaluationId))
  const [evaluations, setEvaluations] = useState([])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [lastResponse, setLastResponse] = useState(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const nextType = draft?.taskType || defaultTaskType || 'kis'
    const nextFrames = initialFrames(draft)
    setTaskType(nextType)
    setVideoId(frameVideoId(draft))
    setTimeMs(Math.max(0, Math.round(Number(draft?.mstime) || 0)))
    setFrameIds(nextFrames.length ? nextFrames : [''])
    setAnswer('')
    setLastResponse(null)
  }, [open, draft, defaultTaskType])

  const cleanFrames = useMemo(
    () => frameIds.map((value) => String(value).trim()).filter(Boolean),
    [frameIds],
  )

  const payload = useMemo(() => makePayload({
    taskType,
    videoId: normalizeVideoId(videoId),
    timeMs: Math.max(0, Math.round(Number(timeMs) || 0)),
    answer,
    frameIds: cleanFrames,
  }), [taskType, videoId, timeMs, answer, cleanFrames])

  const validationError = useMemo(() => {
    if (!baseUrl.trim()) return 'Thiếu địa chỉ DRES.'
    if (!sessionId.trim()) return 'Thiếu sessionId.'
    if (!evaluationId.trim()) return 'Thiếu evaluationID.'
    if (!videoId.trim()) return 'Thiếu VIDEO_ID.'
    if ((taskType === 'kis' || taskType === 'qa') && (!Number.isFinite(Number(timeMs)) || Number(timeMs) < 0)) {
      return 'TIME(ms) phải là số nguyên không âm.'
    }
    if (taskType === 'qa' && !answer.trim()) return 'Q&A cần nội dung trả lời.'
    if (taskType === 'qa' && answer.includes('-')) return 'Câu trả lời Q&A không nên chứa dấu gạch ngang vì đây là ký tự phân cách của định dạng.'
    if (taskType === 'trake' && cleanFrames.length < 2) return 'TRAKE cần ít nhất 2 frame theo đúng thứ tự sự kiện.'
    if (taskType === 'trake' && cleanFrames.some((value) => !/^\d+$/.test(value))) return 'TRAKE chỉ chấp nhận frame ID nguyên không âm.'
    return ''
  }, [answer, baseUrl, cleanFrames, evaluationId, sessionId, taskType, timeMs, videoId])

  const saveConnection = (nextSessionId = sessionId) => {
    localStorage.setItem(STORAGE.baseUrl, baseUrl.trim().replace(/\/+$/, ''))
    localStorage.setItem(STORAGE.evaluationId, evaluationId.trim())
    sessionStorage.setItem(STORAGE.sessionId, nextSessionId.trim())
  }

  const loadEvaluations = async (nextSessionId = sessionId) => {
    if (!nextSessionId.trim()) throw new Error('Thiếu sessionId.')
    const items = await listDresEvaluations({ baseUrl, sessionId: nextSessionId.trim() })
    setEvaluations(items)
    const active = items.find((item) => item.status === 'ACTIVE') || items[0]
    if (active?.id) setEvaluationId(active.id)
    return items
  }

  const handleLogin = async () => {
    if (!username.trim() || !password) {
      message.error('Nhập username và password do ban tổ chức cấp.')
      return
    }
    setConnecting(true)
    try {
      const data = await loginToDres({ baseUrl, username: username.trim(), password })
      const nextSessionId = data?.sessionId || data?.sessionID
      if (!nextSessionId) throw new Error('DRES không trả về sessionId.')
      setSessionId(nextSessionId)
      sessionStorage.setItem(STORAGE.sessionId, nextSessionId)
      setPassword('')
      await loadEvaluations(nextSessionId)
      message.success('Đã đăng nhập và lấy danh sách evaluation.')
    } catch (error) {
      message.error(describeDresError(error))
    } finally {
      setConnecting(false)
    }
  }

  const handleRefreshEvaluations = async () => {
    setConnecting(true)
    try {
      await loadEvaluations()
      saveConnection()
      message.success('Đã cập nhật danh sách evaluation.')
    } catch (error) {
      message.error(describeDresError(error))
    } finally {
      setConnecting(false)
    }
  }

  const doSubmit = async () => {
    setSubmitting(true)
    setLastResponse(null)
    try {
      saveConnection()
      const data = await submitToDres({
        baseUrl,
        evaluationId: evaluationId.trim(),
        sessionId: sessionId.trim(),
        payload,
      })
      setLastResponse(data ?? { ok: true })
      message.success('DRES đã nhận bài nộp.')
    } catch (error) {
      const detail = describeDresError(error)
      setLastResponse({ error: detail })
      message.error(detail)
    } finally {
      setSubmitting(false)
    }
  }

  const confirmSubmit = () => {
    // validationError đã hiển thị qua Alert bên dưới nên chỉ cần chặn.
    if (validationError) return
    // React 19: Modal.confirm static của antd v5 không chạy -> dùng Modal có state.
    setConfirmOpen(true)
  }

  const copyPayload = async () => {
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
    message.success('Đã sao chép JSON.')
  }

  const connectionPanel = (
    <div className="submission-connection">
      <Text type="secondary">Thông tin đăng nhập chỉ dùng trong trình duyệt này; mật khẩu không được lưu.</Text>
      <Input addonBefore="DRES" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
      <div className="submission-grid-two">
        <Input placeholder="Username" value={username} onChange={(event) => setUsername(event.target.value)} />
        <Input.Password placeholder="Password" value={password} onChange={(event) => setPassword(event.target.value)} onPressEnter={handleLogin} />
      </div>
      <Button loading={connecting} onClick={handleLogin}>Đăng nhập và lấy session</Button>
      <Divider plain>hoặc nhập session có sẵn</Divider>
      <Input.Password placeholder="sessionId" value={sessionId} onChange={(event) => setSessionId(event.target.value)} />
      <Space.Compact block>
        <Select
          showSearch
          value={evaluationId || undefined}
          placeholder="Chọn evaluation đang ACTIVE"
          onChange={setEvaluationId}
          options={evaluations.map((item) => ({
            value: item.id,
            label: `${item.name || item.id}${item.status ? ` (${item.status})` : ''}`,
          }))}
          style={{ width: '100%' }}
        />
        <Button loading={connecting} onClick={handleRefreshEvaluations}>Lấy evaluation</Button>
      </Space.Compact>
      <Input placeholder="evaluationID (có thể nhập tay)" value={evaluationId} onChange={(event) => setEvaluationId(event.target.value)} />
    </div>
  )

  return (
    <>
    <Modal
      open={open}
      onCancel={onClose}
      width={760}
      destroyOnHidden
      footer={[
        <Button key="copy" onClick={copyPayload}>Sao chép JSON</Button>,
        <Button key="close" onClick={onClose}>Đóng</Button>,
        <Button key="submit" type="primary" danger loading={submitting} onClick={confirmSubmit}>
          Nộp lên DRES
        </Button>,
      ]}
      title="Nộp bài AI Challenge 2026"
    >
      <div className="submission-modal-body">
        <Alert
          type="warning"
          showIcon
          message="Điểm tính theo lần đúng đầu tiên; mỗi lần sai bị trừ 10 điểm. Video KIS và Textual KIS dùng cùng định dạng nộp."
        />

        <div className="submission-heading-row">
          <div>
            <Text type="secondary">Dạng bài</Text>
            <Select value={taskType} onChange={setTaskType} options={TASK_OPTIONS} className="submission-task-select" />
          </div>
          <Tag color={taskType === 'trake' ? 'purple' : taskType === 'qa' ? 'gold' : 'blue'}>
            {TASK_OPTIONS.find((item) => item.value === taskType)?.label}
          </Tag>
        </div>

        <div className="submission-field">
          <Text strong>VIDEO_ID</Text>
          <Input value={videoId} onChange={(event) => setVideoId(event.target.value)} placeholder="L21_V001" />
        </div>

        {(taskType === 'kis' || taskType === 'qa') && (
          <div className="submission-field">
            <Text strong>TIME (ms)</Text>
            <InputNumber min={0} precision={0} value={timeMs} onChange={(value) => setTimeMs(value ?? 0)} style={{ width: '100%' }} />
            <Text type="secondary">Thời gian của frame trong video gốc, tính bằng millisecond.</Text>
          </div>
        )}

        {taskType === 'qa' && (
          <div className="submission-field">
            <Text strong>ANSWER</Text>
            <Input value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Câu trả lời ngắn, không dùng dấu gạch ngang" />
          </div>
        )}

        {taskType === 'trake' && (
          <div className="submission-field">
            <div className="submission-heading-row">
              <Text strong>FRAME_ID theo thứ tự sự kiện</Text>
              <Button size="small" onClick={() => setFrameIds((current) => [...current, ''])}>Thêm frame</Button>
            </div>
            {frameIds.map((frameId, index) => (
              <Space.Compact block key={index} className="submission-frame-row">
                <Input
                  addonBefore={`Event ${index + 1}`}
                  value={frameId}
                  onChange={(event) => setFrameIds((current) => current.map((value, i) => i === index ? event.target.value : value))}
                  placeholder="Frame ID"
                />
                <Button danger disabled={frameIds.length <= 2} onClick={() => setFrameIds((current) => current.filter((_, i) => i !== index))}>Xóa</Button>
              </Space.Compact>
            ))}
          </div>
        )}

        {validationError && <Alert type="error" showIcon message={validationError} />}

        <Collapse
          items={[{
            key: 'connection',
            label: 'Kết nối DRES và evaluation',
            children: connectionPanel,
          }, {
            key: 'payload',
            label: 'Xem JSON sẽ gửi',
            children: <pre className="submission-json">{JSON.stringify(payload, null, 2)}</pre>,
          }]}
        />

        {lastResponse && (() => {
          const v = verdictOf(lastResponse)
          return (
            <div className="submission-response">
              {v && (
                <Alert
                  type={v.type}
                  showIcon
                  message={<span style={{ fontSize: 16, fontWeight: 700 }}>{v.text}</span>}
                  description={v.desc}
                  style={{ marginBottom: 8 }}
                />
              )}
              <Collapse
                items={[{
                  key: 'raw',
                  label: 'Chi tiết phản hồi (JSON)',
                  children: <pre className="submission-json">{JSON.stringify(lastResponse, null, 2)}</pre>,
                }]}
              />
            </div>
          )
        })()}
      </div>
    </Modal>

    {/* Hộp xác nhận (state-controlled) — thay Modal.confirm static không chạy trên React 19 */}
    <Modal
      open={confirmOpen}
      title="Xác nhận nộp đáp án?"
      okText="Nộp lên DRES"
      cancelText="Kiểm tra lại"
      okButtonProps={{ danger: true }}
      onOk={() => { setConfirmOpen(false); doSubmit() }}
      onCancel={() => setConfirmOpen(false)}
    >
      Mỗi lần nộp sai bị trừ điểm. Hãy kiểm tra VIDEO_ID, thời gian/frame và evaluation đang ACTIVE.
    </Modal>
    </>
  )
}
