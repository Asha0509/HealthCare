import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Activity, Mail, Lock, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Login() {
    const [form, setForm] = useState({ email: '', password: '' })
    const [showPwd, setShowPwd] = useState(false)
    const { login, loading } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        const res = await login(form.email, form.password)
        if (res.ok) { toast.success('Welcome back!'); navigate('/triage') }
        else toast.error(res.message)
    }

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
            paddingTop: 64, padding: '80px 24px'
        }}>
            <div className="glass-card" style={{ width: '100%', maxWidth: 420, padding: 40 }}>
                {/* Logo */}
                <div style={{ textAlign: 'center', marginBottom: 32 }}>
                    <div style={{
                        width: 52, height: 52, borderRadius: 14, margin: '0 auto 16px',
                        background: 'linear-gradient(135deg, #00d4aa, #3b82f6)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 0 24px rgba(0,212,170,0.4)'
                    }}>
                        <Activity size={26} color="white" />
                    </div>
                    <h2 style={{ fontSize: '1.5rem' }}>Welcome back</h2>
                    <p style={{ marginTop: 6, fontSize: '0.88rem' }}>Sign in to your HealthAI account</p>
                </div>

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div>
                        <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>Email</label>
                        <div style={{ position: 'relative' }}>
                            <Mail size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                            <input className="input-field" type="email" placeholder="you@example.com"
                                style={{ paddingLeft: 40 }} value={form.email}
                                onChange={e => setForm({ ...form, email: e.target.value })} required />
                        </div>
                    </div>

                    <div>
                        <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>Password</label>
                        <div style={{ position: 'relative' }}>
                            <Lock size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                            <input className="input-field" type={showPwd ? 'text' : 'password'} placeholder="••••••••"
                                style={{ paddingLeft: 40, paddingRight: 40 }} value={form.password}
                                onChange={e => setForm({ ...form, password: e.target.value })} required />
                            <button type="button" onClick={() => setShowPwd(!showPwd)}
                                style={{
                                    position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)',
                                    background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)'
                                }}>
                                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </div>

                    <button className="btn btn-primary" type="submit" disabled={loading}
                        style={{ width: '100%', justifyContent: 'center', marginTop: 8, padding: '14px' }}>
                        {loading ? <><span className="spinner" />Signing in...</> : 'Sign In'}
                    </button>
                </form>

                <p style={{ textAlign: 'center', marginTop: 24, fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                    Don't have an account?{' '}
                    <Link to="/register" style={{ color: 'var(--accent-teal)', textDecoration: 'none', fontWeight: 600 }}>
                        Sign up free
                    </Link>
                </p>
            </div>
        </div>
    )
}
