import { useEffect, useMemo, useState } from 'react'
import { errorMessage, systemAPI } from '../api/client'
import { LEVELS } from '../lib/labels'

const ORDER = ['HomeCare', 'Urgent', 'Emergency']
const RANK = { HomeCare: 0, Urgent: 1, Emergency: 2 }
const PIPELINE_NAME = { agent: 'AI agent + safety rules', rules: 'Rules only (AI off)' }
const pct = (v) => (v == null ? 'n/a' : `${Math.round(v * 100)}%`)

function Matrix({ confusion }) {
    return (
        <div className="matrix" role="table" aria-label="Expected level (rows) against the level given (columns)">
            <div className="h" role="columnheader">Expected ↓ / Given →</div>
            {ORDER.map((p) => <div key={p} className="h" role="columnheader">{LEVELS[p].name}</div>)}
            {ORDER.map((e) => (
                <div key={e} style={{ display: 'contents' }} role="row">
                    <div className="h" role="rowheader">{LEVELS[e].name}</div>
                    {ORDER.map((p) => {
                        const cls = e === p ? 'diag' : RANK[p] < RANK[e] ? 'under' : 'over'
                        return <div key={p} className={confusion[e][p] ? cls : ''} role="cell">{confusion[e][p]}</div>
                    })}
                </div>
            ))}
        </div>
    )
}

export default function Evals() {
    const [reports, setReports] = useState(null)
    const [name, setName] = useState(null)
    const [report, setReport] = useState(null)
    const [error, setError] = useState('')
    const [onlyWrong, setOnlyWrong] = useState(false)

    useEffect(() => {
        systemAPI.evals().then(({ data }) => {
            setReports(data.reports)
            const pick = data.reports.find((r) => r.pipeline === 'agent') || data.reports[0]
            if (pick) setName(pick.name)
        }).catch((err) => setError(errorMessage(err)))
    }, [])

    useEffect(() => {
        if (!name) return
        setReport(null)
        systemAPI.evalReport(name).then(({ data }) => setReport(data)).catch((err) => setError(errorMessage(err)))
    }, [name])

    const rows = useMemo(() => (report?.results || []).filter((r) => !onlyWrong || r.predicted !== r.expected), [report, onlyWrong])
    const m = report?.metrics

    return (
        <div className="wrap section">
            <div className="section-head">
                <div className="stack" style={{ '--s': '8px' }}>
                    <h1 style={{ fontSize: 'var(--t-2xl)' }}>How well it works</h1>
                    <p className="muted measure">
                        Each case is a short description with the level a careful clinician would likely choose. The
                        system runs every case through the same API you use. Cases tagged “judgement” are worded
                        without textbook keywords, so they test reasoning rather than the safety rules.
                    </p>
                </div>
                {reports?.length > 1 && (
                    <div className="segmented" role="group" aria-label="Pipeline">
                        {reports.map((r) => (
                            <button key={r.name} type="button" aria-pressed={r.name === name} onClick={() => setName(r.name)}>
                                {PIPELINE_NAME[r.pipeline] || r.name}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {error && <p className="error-text">{error}</p>}
            {reports && reports.length === 0 && <div className="empty">No eval results have been published yet.</div>}
            {!report && !error && reports?.length !== 0 && <p className="faint">Loading…</p>}

            {m && (
                <>
                    <div className="figures">
                        <div className={`figure ${m.critical_misses ? 'bad' : 'good'}`}>
                            <div className="figure-value">{m.critical_misses}</div>
                            <div className="figure-label">emergencies told to stay home</div>
                        </div>
                        <div className="figure"><div className="figure-value">{pct(m.emergency_recall)}</div><div className="figure-label">emergencies caught</div></div>
                        <div className="figure"><div className="figure-value">{pct(m.accuracy)}</div><div className="figure-label">exact level ({m.cases} cases)</div></div>
                        <div className="figure"><div className="figure-value">{pct(m.under_triage_rate)}</div><div className="figure-label">under-triaged (too low)</div></div>
                        <div className="figure"><div className="figure-value">{pct(m.over_triage_rate)}</div><div className="figure-label">over-triaged (too cautious)</div></div>
                        <div className="figure"><div className="figure-value">{m.latency_ms_p50 != null ? `${(m.latency_ms_p50 / 1000).toFixed(1)} s` : 'n/a'}</div><div className="figure-label">median time per case</div></div>
                    </div>
                    <p className="faint" style={{ marginTop: 10 }}>
                        {PIPELINE_NAME[report.pipeline]}{report.providers?.length ? ` using ${report.providers.join(', ')}` : ''}.
                        Run {new Date(report.run_at).toLocaleString()} against {report.target}. {report.label_note}
                    </p>
                    {report.gate_failures?.length > 0 && (
                        <p className="notice warn" style={{ marginTop: 12 }}>Safety gate not met: {report.gate_failures.join('; ')}.</p>
                    )}

                    <div className="result-cols" style={{ marginTop: 36 }}>
                        <section>
                            <h2 style={{ fontSize: 'var(--t-lg)', marginBottom: 12 }}>Where the answers landed</h2>
                            <Matrix confusion={m.confusion} />
                            <p className="faint" style={{ marginTop: 8 }}>Green: correct. Red: lower than expected (the dangerous direction). Amber: more cautious than needed.</p>
                        </section>
                        <section>
                            <h2 style={{ fontSize: 'var(--t-lg)', marginBottom: 12 }}>By kind of case</h2>
                            <div className="table-wrap">
                                <table>
                                    <thead><tr><th>Kind</th><th className="num">Cases</th><th className="num">Correct</th></tr></thead>
                                    <tbody>
                                        {Object.entries(m.by_tag).map(([t, v]) => (
                                            <tr key={t}><td>{t.replace(/_/g, ' ')}</td><td className="num">{v.cases}</td><td className="num">{pct(v.accuracy)}</td></tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    </div>

                    <section style={{ marginTop: 36 }}>
                        <div className="section-head" style={{ marginBottom: 12 }}>
                            <h2 style={{ fontSize: 'var(--t-lg)' }}>Every case</h2>
                            <label className="row" style={{ gap: 8 }}>
                                <input type="checkbox" checked={onlyWrong} onChange={(e) => setOnlyWrong(e.target.checked)} /> Only show misses
                            </label>
                        </div>
                        <div className="table-wrap">
                            <table>
                                <thead><tr><th>Case</th><th>Expected</th><th>Given</th><th>How</th><th>Why this label</th></tr></thead>
                                <tbody>
                                    {rows.map((r) => {
                                        const miss = r.predicted !== r.expected
                                        const dangerous = miss && RANK[r.predicted] < RANK[r.expected]
                                        return (
                                            <tr key={r.id} className={dangerous ? 'miss' : ''}>
                                                <td>{r.complaint}<div className="faint">{r.id}, {r.tag.replace(/_/g, ' ')}</div></td>
                                                <td><span className={`pill ${LEVELS[r.expected].key}`}>{LEVELS[r.expected].name}</span></td>
                                                <td>{r.predicted
                                                    ? <span className={`pill ${LEVELS[r.predicted].key}`}>{LEVELS[r.predicted].name}{miss ? ' ✕' : ''}</span>
                                                    : <span className="error-text">error</span>}
                                                    {r.escalated && <div className="faint">raised by a safety rule</div>}
                                                </td>
                                                <td className="faint">{r.decision_path?.replace('_', ' ')}</td>
                                                <td className="faint">{r.rationale}</td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </section>
                </>
            )}
        </div>
    )
}
