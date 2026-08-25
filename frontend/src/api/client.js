import axios from 'axios'

// Empty in dev (Vite proxies /api); set VITE_API_URL for a deployed backend.
const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || '', timeout: 60000 })

/** Turn any request failure into a sentence a person can act on. */
export function errorMessage(err) {
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
    if (err?.code === 'ECONNABORTED') return 'The server took too long to answer. Please try again.'
    if (!err?.response) return "Can't reach the server. It may be waking up; try again in a few seconds."
    return 'Something went wrong. Please try again.'
}

export const triageAPI = {
    start: (data) => API.post('/api/triage/start', data),
    answer: (data) => API.post('/api/triage/answer', data),
    result: (sessionId) => API.get(`/api/triage/result/${sessionId}`),
    assess: (data) => API.post('/api/triage/assess', data),
}

export const facilitiesAPI = {
    nearby: (params) => API.get('/api/facilities/nearby', { params }),
}

export const systemAPI = {
    status: () => API.get('/api/system/status'),
    metrics: (hours = 168) => API.get('/api/metrics/summary', { params: { hours } }),
    calls: (limit = 40) => API.get('/api/metrics/calls', { params: { limit } }),
    runs: (limit = 40) => API.get('/api/metrics/runs', { params: { limit } }),
    timeseries: (hours = 24, bucket = 60) => API.get('/api/metrics/timeseries', { params: { hours, bucket_minutes: bucket } }),
    evals: () => API.get('/api/evals'),
    evalReport: (name) => API.get(`/api/evals/${name}`),
}

export default API
