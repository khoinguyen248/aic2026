import axios from 'axios'

const API = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
    headers: {
        'Content-Type': 'application/json'
    }
})
const ANS = axios.create({
    baseURL: 'https://eventretrieval.oj.io.vn',
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
export const captionSearch = (data) => API.post('/search/caption', data)
// URL ảnh 1 frame gốc để verify (decode từ video ở backend; lỗi/404 nếu máy không có video)
export const frameUrl = (L, V, frameId) =>
    `${API_BASE}/search/frame?L=${encodeURIComponent(L)}&V=${encodeURIComponent(V)}&frame_id=${frameId}`
export const answer = (data4) => ANS.post('/api/v2/submit/06236d7d-368e-44ac-a388-c955cb374a7d?session=t5c14CtTasq641UNhGKBsQIHz_FBGo5I', data4)

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
