import axios from 'axios'

const API = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
    headers: {
        'Content-Type': 'application/json'
    }
})
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export const search = (data2) => API.post('/search/collection', data2)
export const searchOcr = (data) => API.post('/search/ocr', data)
export const searchAsr = (data) => API.post('/search/asr', data)
export const searchCaption = (data) => API.post('/search/caption', data)
export const searchImage = (data) => API.post('/search/image', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
})
export const searchinfo = (data3) => API.post('/search/infoframes', data3)
export const framesInRange = (data) => API.post('/search/framerange', data)
export const trakeSearch = (data) => API.post('/search/trake', data)
export const asrSearch = (data) => API.post('/search/asr', data)
export const ocrSearch = (data) => API.post('/search/ocr', data)
export const trafficSearch = (data) => API.post('/search/traffic', data)
export const captionSearch = (data) => API.post('/search/caption', data)
// Hybrid: lọc lại tập frame semantic (Top-K) theo OCR / ASR query
export const ocrFilter = (data) => API.post('/search/ocr_filter', data)
export const asrFilter = (data) => API.post('/search/asr_filter', data)
// Lấy đầy đủ metadata (caption/OCR/ASR/objects) của 1 frame cho panel chi tiết
export const frameDetail = (data) => API.post('/search/frame_detail', data)
// URL ảnh 1 frame gốc để verify (decode từ video ở backend; lỗi/404 nếu máy không có video)
export const frameUrl = (L, V, frameId) =>
    `${API_BASE}/search/frame?L=${encodeURIComponent(L)}&V=${encodeURIComponent(V)}&frame_id=${frameId}`
/*
export const signup = (data) => API.post('/account/signup', data)
export const signin = (data1 ) => API.post(`/account/signin`, data1)
export const getInfors = (email) => API.get(`/account/profile?email=${email}`)
export const jobs = () => API.get('/jobs/alljobs')
export const updateJobs = (data4) => API.post('/jobs/updateJobs', data4)
export const addEmployee = (data5) => API.post('/employees/addemployee', data5)


export const getAlluser = () => API.get('/teachers')
export const getAlljobs = () => API.get('/positions')
export const addjobs = (data) => API.post('/positions', data)
export const addteacher = (data2) => API.post('/teachers', data2)
*/
