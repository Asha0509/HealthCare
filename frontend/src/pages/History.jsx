import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { triageAPI } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Clock, ChevronRight, AlertTriangle, Activity, Plus } from 'lucide-react'
import toast from 'react-hot-toast'

const LABEL_CONFIG = {
    Emergency: { color: '#ef4444', badge: 'badge-emergency', icon: '🚨' },
    Urgent: { color: '#f59e0b', badge: 'badge-urgent', icon: '⚡' },
    HomeCare: { color: '#10b981', badge: 'badge-homecare', icon: '🏠' },
}

function formatDate(iso) {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function History() {
    const { user } = useAuth()
    const navigate = useNavigate()
    const [sessions, setSessions] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!user) { toast.error('Please log in to view history'); navigate('/login'); return }
        triageAPI.history()
            .then(res => setSessions(res.data.sessions || []))
            .catch(() => toast.error('Failed to load history'))
            .finally(() => setLoading(false))
    }, [user])

    return (
        <div style={{ minHeight: '100vh', paddingTop: 80, paddingBottom: 60 }}>
            <div className="container" style={{ maxWidth: 900 }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                    <div>
                        <h2 style={{ marginBottom: 6 }}>Triage History</h2>
                        <p style={{ fontSize: '0.9rem' }}>Your past assessment sessions</p>
                    </div>
                    <Link to="/triage" className="btn btn-primary">
                        <Plus size={16} /> New Triage
                    </Link>
                </div>

                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
                        <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="glass-card" style={{ padding: 60, textAlign: 'center' }}>
                        <Activity size={48} color="var(--text-muted)" style={{ marginBottom: 16 }} />
                        <h3 style={{ marginBottom: 8 }}>No sessions yet</h3>
                        <p style={{ marginBottom: 24 }}>Start your first triage assessment to see it here.</p>
                        <Link to="/triage" className="btn btn-primary">Start Triage</Link>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                        {sessions.map((s) => {
                            const lc = LABEL_CONFIG[s.triage_label] || {}
                            return (
                                <div key={s.session_id} className="glass-card" style={{
                                    padding: '20px 24px',
                                    display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
                                    transition: 'var(--transition)'
                                }}
                                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.transform = 'translateX(4px)' }}
                                    onMouseLeave={e => { e.currentTarget.style.background = ''; e.currentTarget.style.transform = '' }}>

                                    {/* Urgency icon */}
                                    <div style={{
                                        width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                                        background: `rgba(0,0,0,0.3)`, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        fontSize: '1.4rem', border: `1px solid ${lc.color || 'var(--border-glass)'}33`
                                    }}>
                                        {lc.icon || '❓'}
                                    </div>

                                    {/* Complaint */}
                                    <div style={{ flex: 1, minWidth: 200 }}>
                                        <p style={{
                                            fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: 4,
                                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 360
                                        }}>
                                            {s.chief_complaint || 'Symptom assessment'}
                                        </p>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                            <Clock size={12} color="var(--text-muted)" />
                                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{formatDate(s.started_at)}</span>
                                            <span style={{
                                                fontSize: '0.75rem', color: 'var(--text-muted)',
                                                background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: 999
                                            }}>
                                                {s.status}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Label + confidence */}
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                                        {s.triage_label && (
                                            <span className={`badge ${lc.badge || ''}`}>{s.triage_label}</span>
                                        )}
                                        {s.confidence != null && (
                                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                                {Math.round(s.confidence * 100)}% conf.
                                            </span>
                                        )}
                                        {s.triage_label && (
                                            <Link to={`/result/${s.session_id}`} className="btn btn-ghost"
                                                style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                                                View <ChevronRight size={14} />
                                            </Link>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}

                {/* Disclaimer */}
                <div style={{
                    marginTop: 40, display: 'flex', gap: 10, padding: '14px 18px',
                    background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.12)',
                    borderRadius: 'var(--radius-md)', alignItems: 'flex-start'
                }}>
                    <AlertTriangle size={15} color="var(--urgent)" style={{ flexShrink: 0, marginTop: 1 }} />
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                        Past triage results are for reference only. Always consult a qualified physician for medical advice.
                    </p>
                </div>
            </div>
        </div>
    )
}
