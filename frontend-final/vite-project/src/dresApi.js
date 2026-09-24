import axios from 'axios'

export const DEFAULT_DRES_URL = import.meta.env.VITE_DRES_BASE_URL || 'https://eventretrieval.one'

const normalizeBaseUrl = (value) => String(value || DEFAULT_DRES_URL).trim().replace(/\/+$/, '')

const dresClient = (baseUrl) => axios.create({
  baseURL: normalizeBaseUrl(baseUrl),
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
})

export const loginToDres = async ({ baseUrl, username, password }) => {
  const response = await dresClient(baseUrl).post('/api/v2/login', { username, password })
  return response.data
}

export const listDresEvaluations = async ({ baseUrl, sessionId }) => {
  const response = await dresClient(baseUrl).get('/api/v2/client/evaluation/list', {
    params: { session: sessionId },
  })
  return Array.isArray(response.data) ? response.data : []
}

export const submitToDres = async ({ baseUrl, evaluationId, sessionId, payload }) => {
  const response = await dresClient(baseUrl).post(
    `/api/v2/submit/${encodeURIComponent(evaluationId)}`,
    payload,
    { params: { session: sessionId } },
  )
  return response.data
}

export const describeDresError = (error) => {
  const data = error?.response?.data
  if (typeof data === 'string' && data.trim()) return data
  if (data?.description) return data.description
  if (data?.message) return data.message
  if (data?.error) return data.error
  return error?.message || 'Không thể kết nối DRES.'
}
