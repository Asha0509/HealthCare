import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Activity, Clock, LogOut, Menu, X } from 'lucide-react'
import { useState } from 'react'

export default function Navbar() {
    const { user, logout } = useAuth()
    const navigate = useNavigate()
    const [menuOpen, setMenuOpen] = useState(false)

    const handleLogout = () => { logout(); navigate('/') }

    return (
        <nav style={{
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
            background: 'rgba(5,13,26,0.85)',
            backdropFilter: 'blur(20px)',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            padding: '0 24px',
            height: '64px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
            {/* Logo */}
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
                <div style={{
                    width: 36, height: 36, borderRadius: 10,
                    background: 'linear-gradient(135deg, #00d4aa, #3b82f6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 0 16px rgba(0,212,170,0.4)',
                }}>
                    <Activity size={20} color="white" strokeWidth={2.5} />
                </div>
                <span style={{ fontWeight: 800, fontSize: '1.1rem', letterSpacing: '-0.02em' }}>
                    Health<span className="gradient-text">AI</span>
                </span>
            </Link>

            {/* Desktop Nav */}
            <div className="hide-mobile" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Link to="/triage" className="btn btn-ghost" style={{ fontSize: '0.85rem' }}>
                    Start Triage
                </Link>
                {user && (
                    <Link to="/history" className="btn btn-ghost" style={{ fontSize: '0.85rem' }}>
                        <Clock size={15} /> History
                    </Link>
                )}
                {user ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                            {user.name}
                        </span>
                        <button className="btn btn-secondary" onClick={handleLogout}
                            style={{ padding: '8px 16px', fontSize: '0.8rem' }}>
                            <LogOut size={14} /> Logout
                        </button>
                    </div>
                ) : (
                    <div style={{ display: 'flex', gap: 8 }}>
                        <Link to="/login" className="btn btn-secondary" style={{ padding: '8px 20px', fontSize: '0.85rem' }}>Login</Link>
                        <Link to="/register" className="btn btn-primary" style={{ padding: '8px 20px', fontSize: '0.85rem' }}>Sign Up</Link>
                    </div>
                )}
            </div>

            {/* Mobile toggle */}
            <button className="btn btn-ghost" style={{ display: 'none' }}
                onClick={() => setMenuOpen(!menuOpen)}>
                {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
        </nav>
    )
}
