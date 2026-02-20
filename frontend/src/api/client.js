import axios from 'axios'

const API = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    timeout: 30000,
})

// Attach JWT token
API.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

// Handle 401
API.interceptors.response.use(
    (r) => r,
    (err) => {
        if (err.response?.status === 401) {
            localStorage.removeItem('token')
            localStorage.removeItem('user')
            window.location.href = '/login'
        }
        return Promise.reject(err)
    }
)

export const authAPI = {
    register: (data) => API.post('/api/auth/register', data),
    login: (data) => API.post('/api/auth/login', data),
    me: () => API.get('/api/auth/me'),
}

export const triageAPI = {
    start: (data) => API.post('/api/triage/start', data),
    answer: (data) => API.post('/api/triage/answer', data),
    result: (sessionId) => API.get(`/api/triage/result/${sessionId}`),
    history: () => API.get('/api/triage/history'),
}

export const hospitalAPI = {
    nearby: (urgency, symptom, lat, lon) =>
        API.get('/api/hospitals/nearby', { params: { urgency, symptom, lat, lon } }),
}

export default API
