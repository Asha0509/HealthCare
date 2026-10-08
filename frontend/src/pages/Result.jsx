import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { Check, Printer, RotateCcw } from 'lucide-react'
import TriageTag from '../components/TriageTag'
import AgentTrace from '../components/AgentTrace'
import Citations from '../components/Citations'
import Facilities from '../components/Facilities'
import { errorMessage, triageAPI } from '../api/client'
import { getResult, saveResult } from '../lib/history'
import { FALLBACK_REASONS, LEVELS, PATHS, prettySymptom, timeAgo } from '../lib/labels'

function Ticks({ items }) {
    return (
        <ul className="ticks">
            {items.map((t, i) => <li key={i}><Check size={16} aria-hidden="true" /><span>{t}</span></li>)}
        </ul>
    )
}

function SecondOpinion({ opinion }) {
    if (!opinion) return null
    const order = ['HomeCare', 'Urgent', 'Emergency']
    return (
        <section className="block">
            <h2>Second opinion from a decision model</h2>
            {opinion.calibrated ? (
                <p className="faint" style={{ marginBottom: 10 }}>
                    Levels this model could not rule out (set to be right at least {Math.round((1 - opinion.alpha) * 100)}% of the time on its calibration cases):{' '}
                    <strong>{opinion.prediction_set.map((l) => LEVELS[l]?.name || l).join(', ')}</strong>. If it includes a more urgent level than ours, the result is raised, never lowered.
                </p>
            ) : (
                <p className="faint" style={{ marginBottom: 10 }}>Shown for information only: this model has not been calibrated, so it cannot change the result.</p>
            )}
            <div className="chips">
                {order.map((l) => (
                    <span key={l} className="pill">{LEVELS[l]?.name || l}: {Math.round((opinion.probabilities[l] || 0) * 100)}%</span>
                ))}
            </div>
        </section>
    )
}

export default function Result() {
    const { sessionId } = useParams()
    const location = useLocation()
    const reduce = useReducedMotion()
    const [result, setResult] = useState(location.state?.result || null)
    const [error, setError] = useState('')
    const [fromCache, setFromCache] = useState(false)

    useEffect(() => {
        if (result) return
        triageAPI.result(sessionId)
            .then(({ data }) => { setResult(data); saveResult(data) })
            .catch((err) => {
                const saved = getResult(sessionId)
                if (saved) { setResult(saved); setFromCache(true) } else setError(errorMessage(err))
            })
    }, [sessionId, result])

    if (error) {
        return (
            <div className="wrap result">
                <div className="empty">
                    <p>{error}</p>
                    <p style={{ marginTop: 12 }}><Link to="/triage" className="btn btn-primary">Start a new check</Link></p>
                </div>
            </div>
        )
    }
    if (!result) return <div className="wrap result"><p className="faint">Loading your result…</p></div>

    const level = LEVELS[result.triage_label]
    const flags = result.red_flags || []
    const showProbs = result.probabilities && result.decision_path === 'agent'

    return (
        <div className="wrap result">
            <div className="result-top">
                <div className="stack" style={{ '--s': '6px' }}>
                    <p className="faint">
                        {result.chief_complaint ? <>“{result.chief_complaint}”</> : 'Your result'}
                        {result.created_at ? `, ${timeAgo(result.created_at)}` : ''}
                    </p>
                    {result.symptoms?.length > 0 && (
                        <div className="chips">{result.symptoms.map((s) => <span key={s} className="pill">{prettySymptom(s)}</span>)}</div>
                    )}
                </div>
                <div className="row no-print">
                    <button className="btn btn-quiet btn-sm" type="button" onClick={() => window.print()}><Printer size={15} aria-hidden="true" /> Print or save</button>
                    <Link className="btn btn-quiet btn-sm" to="/triage"><RotateCcw size={15} aria-hidden="true" /> New check</Link>
                </div>
            </div>

            <motion.div style={{ marginTop: 18 }}
                initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
                <TriageTag level={result.triage_label} hero>
                    <p className="tag-action">{result.recommended_action || level.meaning}</p>
                </TriageTag>
            </motion.div>

            {result.crisis_response && (
                <div className="crisis" style={{ marginTop: 20 }} role="alert">
                    <p style={{ fontWeight: 700, marginBottom: 8 }}>You don't have to go through this alone. Talk to someone now:</p>
                    <div className="row" style={{ gap: 20 }}>
                        <a href="tel:9152987821">iCall 9152987821</a>
                        <a href="tel:18602662345">Vandrevala 1860-2662-345 (24/7)</a>
                        <a href="tel:112">Emergency 112</a>
                    </div>
                </div>
            )}

            {fromCache && <p className="notice warn" style={{ marginTop: 16 }}>Showing the copy saved in this browser. The server no longer has this result.</p>}

            <div className="result-cols">
                <div>
                    <section className="block">
                        <h2>Why this level</h2>
                        <p className="measure">{result.explanation_text}</p>
                        {result.escalated && (
                            <p className="notice warn" style={{ marginTop: 12 }}>
                                The {result.decision_path === 'agent' ? 'AI agent' : 'rule-based assessment'} suggested <strong>{LEVELS[result.proposed_label]?.name}</strong>. A safety rule raised it
                                to <strong>{level.name}</strong>, because safety rules can only make a result more cautious.
                            </p>
                        )}
                        {flags.length > 0 && (
                            <ul className="flag-list" style={{ marginTop: 14 }}>
                                {flags.map((f) => <li key={f.rule_id} className={f.level}><strong>{f.level}: </strong>{f.reason}</li>)}
                            </ul>
                        )}
                        {result.key_factors?.length > 0 && (
                            <div style={{ marginTop: 16 }}><Ticks items={result.key_factors} /></div>
                        )}
                    </section>

                    <SecondOpinion opinion={result.second_opinion} />

                    {result.self_care?.length > 0 && result.triage_label !== 'Emergency' && (
                        <section className="block">
                            <h2>{result.triage_label === 'HomeCare' ? 'What you can do at home' : 'While you wait to be seen'}</h2>
                            <Ticks items={result.self_care} />
                        </section>
                    )}

                    {result.conditions_to_consider?.length > 0 && (
                        <section className="block">
                            <h2>Things a doctor may consider</h2>
                            <p className="faint" style={{ marginBottom: 10 }}>Not a diagnosis. Only a doctor who examines you can say what it is.</p>
                            <div className="chips">{result.conditions_to_consider.map((c) => <span key={c} className="pill">{c}</span>)}</div>
                        </section>
                    )}

                    <section className="block no-print">
                        <h2>Care near you</h2>
                        <Facilities urgency={result.triage_label} />
                    </section>
                </div>

                <div>
                    <section className="block">
                        <h2>Sources</h2>
                        <Citations items={result.citations} />
                    </section>

                    <section className="block">
                        <h2>How this was decided</h2>
                        <p><span className="pill">{PATHS[result.decision_path] || result.decision_path}</span></p>
                        {result.fallback_reason && <p className="faint" style={{ marginTop: 8 }}>{FALLBACK_REASONS[result.fallback_reason]}</p>}
                        <p className="faint" style={{ marginTop: 8 }}>
                            {result.provider ? `${result.model} via ${result.provider}. ` : ''}
                            {result.llm_calls ? `${result.llm_calls} model turns, ${result.tool_calls} tool calls, ` : ''}
                            {result.latency_ms != null ? (result.latency_ms < 100 ? 'Under 0.1 s.' : `${(result.latency_ms / 1000).toFixed(1)} s.`) : ''}
                        </p>
                        {showProbs && (
                            <div className="probs" style={{ marginTop: 14 }}>
                                <p className="faint">The model's own estimate for each level (before the safety check):</p>
                                {['HomeCare', 'Urgent', 'Emergency'].map((k) => (
                                    <div className="prob" key={k}>
                                        <span>{LEVELS[k].name}</span>
                                        <span className="prob-bar"><span style={{ width: `${(result.probabilities[k] || 0) * 100}%`, '--c': `var(--${LEVELS[k].key === 'home' ? 'home' : LEVELS[k].key})` }} /></span>
                                        <span className="num">{Math.round((result.probabilities[k] || 0) * 100)}%</span>
                                    </div>
                                ))}
                            </div>
                        )}
                        <details style={{ marginTop: 14 }}>
                            <summary className="btn btn-text">Show every step</summary>
                            <AgentTrace steps={result.agent_steps} />
                        </details>
                    </section>
                </div>
            </div>
        </div>
    )
}
