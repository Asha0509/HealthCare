import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Activity, User, Mail, Lock } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Register() {
    const [form, setForm] = useState({ full_name: '', email: '', password: '', age: '', gender: '' })
    const { register, loading } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        const payload = { ...form, age: form.age ? parseInt(form.age) : null }
        const res = await register(payload)
        if (res.ok) { toast.success('Account created! Start your triage now.'); navigate('/triage') }
        else toast.error(res.message)
    }

    const F = ({ label, type = 'text', field, placeholder, icon: Icon, extra }) => (
        <div>
            <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>{label}</label>
            <div style={{ position: 'relative' }}>
                {Icon && <Icon size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', zIndex: 1 }} />}
                <input className="input-field" type={type} placeholder={placeholder}
                    style={{ paddingLeft: Icon ? 40 : 16 }} value={form[field]}
                    onChange={e => setForm({ ...form, [field]: e.target.value })} {...extra} />
            </div>
        </div>
    )

    return (
        <div style={{
            minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: '80px 24px'
        }}>
            <div className="glass-card" style={{ width: '100%', maxWidth: 460, padding: 40 }}>
                <div style={{ textAlign: 'center', marginBottom: 32 }}>
                    <div style={{
                        width: 52, height: 52, borderRadius: 14, margin: '0 auto 16px',
                        background: 'linear-gradient(135deg, #00d4aa, #8b5cf6)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 0 24px rgba(139,92,246,0.3)'
                    }}>
                        <Activity size={26} color="white" />
                    </div>
                    <h2 style={{ fontSize: '1.5rem' }}>Create Account</h2>
                    <p style={{ marginTop: 6, fontSize: '0.88rem' }}>Join HealthAI — free forever</p>
                </div>

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <F label="Full Name" field="full_name" placeholder="Dr. Jane Smith" icon={User} extra={{ required: true }} />
                    <F label="Email" type="email" field="email" placeholder="you@example.com" icon={Mail} extra={{ required: true }} />
                    <F label="Password" type="password" field="password" placeholder="Min. 6 characters" icon={Lock} extra={{ required: true, minLength: 6 }} />

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <div>
                            <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>Age <span style={{ color: 'var(--text-muted)' }}>(optional)</span></label>
                            <input className="input-field" type="number" placeholder="e.g. 35" min="0" max="120"
                                value={form.age} onChange={e => setForm({ ...form, age: e.target.value })} />
                        </div>
                        <div>
                            <label style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>Gender <span style={{ color: 'var(--text-muted)' }}>(optional)</span></label>
                            <select className="input-field" value={form.gender} onChange={e => setForm({ ...form, gender: e.target.value })}
                                style={{ appearance: 'none' }}>
                                <option value="">Select</option>
                                <option value="male">Male</option>
                                <option value="female">Female</option>
                                <option value="other">Other</option>
                                <option value="prefer_not_to_say">Prefer not to say</option>
                            </select>
                        </div>
                    </div>

                    <button className="btn btn-primary" type="submit" disabled={loading}
                        style={{ width: '100%', justifyContent: 'center', marginTop: 8, padding: '14px' }}>
                        {loading ? <><span className="spinner" />Creating account...</> : 'Create Account'}
                    </button>
                </form>

                <p style={{ textAlign: 'center', marginTop: 24, fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                    Already have an account?{' '}
                    <Link to="/login" style={{ color: 'var(--accent-teal)', textDecoration: 'none', fontWeight: 600 }}>Sign in</Link>
                </p>
            </div>
        </div>
    )
}
