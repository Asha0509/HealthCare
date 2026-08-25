import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { clearResults, listResults, removeResult } from '../lib/history'
import { LEVELS, timeAgo } from '../lib/labels'

export default function History() {
    const [items, setItems] = useState(listResults())

    return (
        <div className="wrap narrow section">
            <div className="section-head">
                <div className="stack" style={{ '--s': '8px' }}>
                    <h1 style={{ fontSize: 'var(--t-2xl)' }}>Your results</h1>
                    <p className="muted">Saved in this browser only. Nobody else can see them, and clearing your browser data removes them.</p>
                </div>
                {items.length > 0 && (
                    <button className="btn btn-quiet btn-sm" type="button"
                        onClick={() => { if (window.confirm('Delete all saved results from this browser?')) { clearResults(); setItems([]) } }}>
                        Delete all
                    </button>
                )}
            </div>
            {items.length === 0 ? (
                <div className="empty">
                    <p>No results yet. Each check you finish is saved here.</p>
                    <p style={{ marginTop: 14 }}><Link to="/triage" className="btn btn-primary">Check your symptoms</Link></p>
                </div>
            ) : (
                <ul className="fac">
                    {items.map((r) => (
                        <li key={r.session_id}>
                            <div>
                                <Link to={`/result/${r.session_id}`} state={{ result: r }} className="name">
                                    {r.chief_complaint || 'Symptom check'}
                                </Link>
                                <div className="meta row" style={{ gap: 8, marginTop: 4 }}>
                                    <span className={`pill ${LEVELS[r.triage_label]?.key}`}>
                                        <span className={`dot ${LEVELS[r.triage_label]?.key}`} />{LEVELS[r.triage_label]?.name}
                                    </span>
                                    <span>{timeAgo(r.saved_at || r.created_at)}</span>
                                </div>
                            </div>
                            <button className="btn btn-text" type="button" aria-label="Delete this result"
                                onClick={() => { removeResult(r.session_id); setItems(listResults()) }}>
                                <Trash2 size={16} aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}
