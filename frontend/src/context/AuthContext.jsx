import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const [user, setUser] = useState(() => {
        try { return JSON.parse(localStorage.getItem('user')) } catch { return null }
    })
    const [loading, setLoading] = useState(false)

    const login = async (email, password) => {
        setLoading(true)
        try {
            const { data } = await authAPI.login({ email, password })
            localStorage.setItem('token', data.access_token)
            const userObj = { id: data.user_id, name: data.full_name, email }
            localStorage.setItem('user', JSON.stringify(userObj))
            setUser(userObj)
            return { ok: true }
        } catch (err) {
            return { ok: false, message: err.response?.data?.detail || 'Login failed' }
        } finally { setLoading(false) }
    }

    const register = async (formData) => {
        setLoading(true)
        try {
            const { data } = await authAPI.register(formData)
            localStorage.setItem('token', data.access_token)
            const userObj = { id: data.user_id, name: data.full_name, email: formData.email }
            localStorage.setItem('user', JSON.stringify(userObj))
            setUser(userObj)
            return { ok: true }
        } catch (err) {
            return { ok: false, message: err.response?.data?.detail || 'Registration failed' }
        } finally { setLoading(false) }
    }

    const logout = () => {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        setUser(null)
    }

    return (
        <AuthContext.Provider value={{ user, login, register, logout, loading }}>
            {children}
        </AuthContext.Provider>
    )
}

export const useAuth = () => useContext(AuthContext)
