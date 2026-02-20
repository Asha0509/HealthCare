import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { triageAPI, hospitalAPI } from '../api/client'
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import {
    AlertTriangle, CheckCircle, Clock, Phone, MapPin,
    Heart, Salad, ArrowLeft, ExternalLink, Info
} from 'lucide-react'

const URGENCY_CONFIG = {
    Emergency: {
        icon: '🚨', label: 'Emergency', color: '#ef4444',
        bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.25)',
        glow: '0 0 40px rgba(239,68,68,0.25)',
        badge: 'badge-emergency',
        message: 'This presentation requires immediate emergency care.',
    },
    Urgent: {
        icon: '⚡', label: 'Urgent', color: '#f59e0b',
        bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)',
        glow: '0 0 40px rgba(245,158,11,0.15)',
        badge: 'badge-urgent',
        message: 'Please seek medical attention within the next few hours.',
    },
    HomeCare: {
        icon: '🏠', label: 'Home Care', color: '#10b981',
        bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.25)',
        glow: '0 0 40px rgba(16,185,129,0.15)',
        badge: 'badge-homecare',
        message: 'You can manage this at home with appropriate care.',
    },
}

const SHAP_COLORS = ['#00d4aa', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444']

function ConfidenceRing({ value, color }) {
    const r = 54, circ = 2 * Math.PI * r
    const offset = circ - (value / 100) * circ
    return (
        <svg width={130} height={130} style={{ transform: 'rotate(-90deg)' }}>
            <circle cx={65} cy={65} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} />
            <circle cx={65} cy={65} r={r} fill="none" stroke={color} strokeWidth={10}
                strokeDasharray={circ} strokeDashoffset={offset}
                strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.4,0,0.2,1)', filter: `drop-shadow(0 0 6px ${color})` }} />
        </svg>
    )
}

export default function Result() {
    const { sessionId } = useParams()
    const [result, setResult] = useState(null)
    const [hospitals, setHospitals] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        const load = async () => {
            try {
                const { data } = await triageAPI.result(sessionId)
                setResult(data)
                
                // Get user location for hospital recommendations
                let lat = null, lon = null
                try {
                    const position = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            enableHighAccuracy: false,
                            timeout: 5000,
                            maximumAge: 300000 // 5 minutes cache
                        })
                    })
                    lat = position.coords.latitude
                    lon = position.coords.longitude
                } catch (geoError) {
                    console.log('Location not available, using default')
                }
                
                // Fetch hospitals with location
                const topSymptom = data.diseases_considered?.[0]?.split('_')[0]
                const hRes = await hospitalAPI.nearby(data.triage_label, topSymptom, lat, lon)
                setHospitals(hRes.data.hospitals || [])
            } catch (e) {
                setError(e.response?.data?.detail || 'Failed to load result.')
            } finally { setLoading(false) }
        }
        load()
    }, [sessionId])

    if (loading) return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 20, paddingTop: 64 }}>
            <div className="spinner" style={{ width: 48, height: 48, borderWidth: 4 }} />
            <p>Generating your triage result...</p>
        </div>
    )

    if (error) return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, paddingTop: 80 }}>
            <div className="glass-card" style={{ padding: 40, maxWidth: 500, textAlign: 'center' }}>
                <AlertTriangle size={40} color="var(--urgent)" style={{ marginBottom: 16 }} />
                <h3>Couldn't load result</h3>
                <p style={{ marginTop: 8, fontSize: '0.9rem' }}>{error}</p>
                <Link to="/triage" className="btn btn-primary" style={{ marginTop: 24 }}>Start New Triage</Link>
            </div>
        </div>
    )

    if (!result) return null

    const cfg = URGENCY_CONFIG[result.triage_label] || URGENCY_CONFIG.HomeCare
    const conf = Math.round((result.confidence || 0.7) * 100)

    // SHAP chart data
    const shapData = (result.shap_features || []).map((f, i) => ({
        name: f.human_label || f.feature,
        value: Math.abs(f.contribution) * 100,
        direction: f.direction,
        color: f.direction === 'increases_risk' ? SHAP_COLORS[i % SHAP_COLORS.length] : '#475569',
    })).slice(0, 5)

    // Probability chart
    const probData = Object.entries(result.probabilities || {}).map(([k, v]) => ({
        name: k, value: Math.round(v * 100),
        color: URGENCY_CONFIG[k]?.color || '#475569'
    }))

    return (
        <div style={{ minHeight: '100vh', paddingTop: 80, paddingBottom: 80 }}>
            <div className="container">
                <Link to="/triage" className="btn btn-ghost" style={{ marginBottom: 24 }}>
                    <ArrowLeft size={16} /> New Triage
                </Link>

                {/* ── Crisis Banner ── */}
                {result.crisis_response && (
                    <div style={{
                        background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                        borderRadius: 'var(--radius-lg)', padding: '20px 24px', marginBottom: 24,
                        display: 'flex', gap: 16, alignItems: 'flex-start'
                    }}>
                        <Heart size={22} color="#ef4444" style={{ flexShrink: 0, marginTop: 2 }} />
                        <div>
                            <strong style={{ color: '#ef4444' }}>You are not alone. Help is available right now.</strong>
                            <p style={{ marginTop: 6, fontSize: '0.88rem', lineHeight: 1.7 }}>
                                iCall India: <strong style={{ color: 'var(--text-primary)' }}>9152987821</strong> &nbsp;|&nbsp;
                                Vandrevala Foundation: <strong style={{ color: 'var(--text-primary)' }}>1860-2662-345</strong> (24/7)
                            </p>
                        </div>
                    </div>
                )}

                {/* ── Main Result Card ── */}
                <div className="glass-card" style={{
                    padding: '40px', marginBottom: 24,
                    background: cfg.bg, borderColor: cfg.border, boxShadow: cfg.glow
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 24 }}>
                        <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                                <span style={{ fontSize: '2.5rem' }}>{cfg.icon}</span>
                                <div>
                                    <span className={`badge ${cfg.badge}`} style={{ fontSize: '0.85rem', marginBottom: 4 }}>
                                        {cfg.label}
                                    </span>
                                    <p style={{ fontSize: '0.88rem', marginTop: 4, color: cfg.color }}>{cfg.message}</p>
                                </div>
                            </div>

                            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)', padding: '16px 20px', marginTop: 16 }}>
                                <p style={{ fontSize: '0.9rem', lineHeight: 1.8, color: 'var(--text-primary)' }}>
                                    {result.explanation_text}
                                </p>
                            </div>

                            <div style={{
                                marginTop: 20, padding: '14px 18px',
                                background: 'rgba(255,255,255,0.04)', borderRadius: 'var(--radius-md)',
                                border: '1px solid var(--border-glass)', fontSize: '0.9rem', lineHeight: 1.7
                            }}>
                                <strong style={{ color: cfg.color }}>Recommended Action: </strong>
                                {result.recommended_action}
                            </div>

                            {result.red_flag_triggered && (
                                <div style={{
                                    marginTop: 16, display: 'flex', gap: 10, alignItems: 'center',
                                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                                    borderRadius: 'var(--radius-md)', padding: '10px 16px'
                                }}>
                                    <AlertTriangle size={16} color="#ef4444" />
                                    <span style={{ fontSize: '0.82rem', color: '#ef4444' }}>
                                        Red-flag rule triggered: {result.red_flag_reason}
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Confidence ring */}
                        <div style={{ textAlign: 'center', flexShrink: 0 }}>
                            <div style={{ position: 'relative', display: 'inline-block' }}>
                                <ConfidenceRing value={conf} color={cfg.color} />
                                <div style={{
                                    position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
                                    textAlign: 'center'
                                }}>
                                    <div style={{ fontSize: '1.6rem', fontWeight: 800 }}>{conf}%</div>
                                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>confidence</div>
                                </div>
                            </div>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>AI Confidence</p>
                        </div>
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 20 }}>
                    {/* ── SHAP Explainability ── */}
                    {shapData.length > 0 && (
                        <div className="glass-card" style={{ padding: 28 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                                <Info size={18} color="var(--accent-teal)" />
                                <h3 style={{ fontSize: '1rem' }}>Why this result?</h3>
                            </div>
                            <p style={{ fontSize: '0.82rem', marginBottom: 20, color: 'var(--text-muted)' }}>
                                Top factors that influenced your triage decision (SHAP attribution)
                            </p>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={shapData} layout="vertical" margin={{ left: 0, right: 20 }}>
                                    <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                                    <YAxis type="category" dataKey="name" width={130}
                                        tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'rgba(10,22,40,0.95)', border: '1px solid rgba(255,255,255,0.08)',
                                            borderRadius: 8, fontSize: '0.8rem'
                                        }}
                                        formatter={(v) => [`${v.toFixed(1)}%`, 'Influence']} />
                                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                                        {shapData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {/* ── Probability Distribution ── */}
                    {probData.length > 0 && (
                        <div className="glass-card" style={{ padding: 28 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                                <h3 style={{ fontSize: '1rem' }}>Probability Distribution</h3>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                                {probData.map(({ name, value, color }) => (
                                    <div key={name}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                                            <span style={{ fontSize: '0.85rem', color }}>{name}</span>
                                            <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>{value}%</span>
                                        </div>
                                        <div className="progress-bar">
                                            <div className="progress-fill" style={{ width: `${value}%`, background: color }} />
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Diseases considered */}
                            {result.diseases_considered?.length > 0 && (
                                <div style={{ marginTop: 24 }}>
                                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 10 }}>Conditions considered:</p>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                        {result.diseases_considered.map(d => (
                                            <span key={d} className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                                                {d.replace(/_/g, ' ')}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ── Remedies ── */}
                    {result.remedies?.length > 0 && (
                        <div className="glass-card" style={{ padding: 28 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                                <Heart size={18} color="var(--homecare)" />
                                <h3 style={{ fontSize: '1rem' }}>Home Remedy Tips</h3>
                            </div>
                            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {result.remedies.map((r, i) => (
                                    <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: '0.88rem' }}>
                                        <CheckCircle size={15} color="var(--homecare)" style={{ flexShrink: 0, marginTop: 2 }} />
                                        <span style={{ color: 'var(--text-secondary)' }}>{r}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* ── Nutrition ── */}
                    {result.nutrition_tips?.length > 0 && (
                        <div className="glass-card" style={{ padding: 28 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                                <Salad size={18} color="var(--accent-teal)" />
                                <h3 style={{ fontSize: '1rem' }}>Nutrition Recommendations</h3>
                            </div>
                            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {result.nutrition_tips.map((n, i) => (
                                    <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: '0.88rem' }}>
                                        <span style={{ color: 'var(--accent-teal)', flexShrink: 0 }}>🥗</span>
                                        <span style={{ color: 'var(--text-secondary)' }}>{n}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* ── Hospital Recommendations ── */}
                    {hospitals.length > 0 && (
                        <div className="glass-card" style={{ padding: 28, gridColumn: '1 / -1' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                                <MapPin size={18} color={cfg.color} />
                                <h3 style={{ fontSize: '1rem' }}>Recommended Healthcare Facilities</h3>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
                                {hospitals.map((h, i) => (
                                    <div key={i} style={{
                                        background: 'rgba(255,255,255,0.03)',
                                        border: '1px solid var(--border-glass)', borderRadius: 'var(--radius-md)', padding: 20
                                    }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                                            <strong style={{ fontSize: '0.9rem', lineHeight: 1.4 }}>{h.name}</strong>
                                            <span className={`badge ${h.type === 'emergency' ? 'badge-emergency' : h.type === 'specialist' ? 'badge-urgent' : 'badge-homecare'}`}
                                                style={{ fontSize: '0.65rem', flexShrink: 0, marginLeft: 8 }}>
                                                {h.type}
                                            </span>
                                        </div>
                                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 12 }}>{h.address}</p>
                                        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                                            {h.phone && (
                                                <a href={`tel:${h.phone}`} className="btn btn-ghost"
                                                    style={{ padding: '4px 10px', fontSize: '0.78rem' }}>
                                                    <Phone size={12} /> {h.phone}
                                                </a>
                                            )}
                                            {h.maps_url && (
                                                <a href={h.maps_url} target="_blank" rel="noopener noreferrer"
                                                    className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.78rem' }}>
                                                    <ExternalLink size={12} /> Directions
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Disclaimer */}
                <div style={{
                    marginTop: 32, padding: '16px 20px',
                    background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.15)',
                    borderRadius: 'var(--radius-md)', display: 'flex', gap: 12, alignItems: 'flex-start'
                }}>
                    <AlertTriangle size={16} color="var(--urgent)" style={{ flexShrink: 0, marginTop: 2 }} />
                    <p style={{ fontSize: '0.8rem', lineHeight: 1.7, color: 'var(--text-muted)' }}>
                        This result is generated by an AI clinical decision support tool and is <strong>not a substitute</strong> for professional medical advice.
                        Always consult a qualified physician for diagnosis and treatment.
                    </p>
                </div>
            </div>
        </div>
    )
}
