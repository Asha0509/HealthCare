import { useCallback, useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { errorMessage, systemAPI } from '../api/client'
import { LEVELS, PATHS, timeAgo } from '../lib/labels'

const WINDOWS = [[24, 'Last 24 hours'], [168, 'Last 7 days']]
const pct = (v) => (v == null ? 'n/a' : `${(v * 100).toFixed(1)}%`)
const ms = (v) => (v == null ? 'n/a' : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`)
const hour = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export default function Ops() {
    const [hours, setHours] = useState(24)
    const [data, setData] = useState(null)
    const [error, setError] = useState('')
    const [updated, setUpdated] = useState(null)

    const load = useCallback(async () => {
        try {
            const [s, ts, calls, runs, st] = await Promise.all([
                systemAPI.metrics(hours), systemAPI.timeseries(hours, hours > 24 ? 360 : 60),
                systemAPI.calls(30), systemAPI.runs(30), systemAPI.status(),
            ])
            setData({ summary: s.data, points: ts.data.points, calls: calls.data.calls, runs: runs.data.runs, status: st.data })
            setUpdated(new Date())
            setError('')
        } catch (err) {
            setError(errorMessage(err))
        }
    }, [hours])

    useEffect(() => {
        load()
        const id = setInterval(load, 20000)
        return () => clearInterval(id)
    }, [load])

    const s = data?.summary
    return (
        <div className="wrap section">
            <div className="section-head">
                <div className="stack" style={{ '--s': '8px' }}>
                    <h1 style={{ fontSize: 'var(--t-2xl)' }}>Ops dashboard</h1>
                    <p className="muted measure">
                        Live numbers from this server: every AI model call and every finished check, with how long it
                        took and whether it fell back. Eval runs are left out. Refreshes every 20 seconds.
                    </p>
                </div>
                <div className="segmented" role="group" aria-label="Time window">
                    {WINDOWS.map(([h, label]) => (
                        <button key={h} type="button" aria-pressed={hours === h} onClick={() => setHours(h)}>{label}</button>
                    ))}
                </div>
            </div>
            {error && <p className="error-text" role="alert">{error}</p>}
            {!data && !error && <p className="faint">Loading…</p>}
            {data && (
                <>
                    <p className="notice" style={{ marginBottom: 20 }}>
                        {data.status.agent_enabled
                            ? `AI providers configured: ${data.status.llm_providers.join(', ')}.`
                            : 'No AI provider is configured, so every check uses the rule-based assessment.'}
                        {' '}Knowledge search: {data.status.knowledge_base.mode}. Counters reset when the server redeploys.
                        {updated && ` Updated ${updated.toLocaleTimeString()}.`}
                    </p>
                    <div className="figures">
                        <div className="figure"><div className="figure-value">{s.triage.runs}</div><div className="figure-label">checks finished</div></div>
                        <div className="figure"><div className="figure-value">{ms(s.triage.latency_ms_p50)}</div><div className="figure-label">median time to a result</div></div>
                        <div className="figure"><div className="figure-value">{pct(s.triage.fallback_rate)}</div><div className="figure-label">checks that fell back to rules</div></div>
                        <div className="figure"><div className="figure-value">{s.triage.escalations}</div><div className="figure-label">raised by a safety rule</div></div>
                        <div className="figure"><div className="figure-value">{s.llm.calls}</div><div className="figure-label">AI model calls</div></div>
                        <div className={`figure ${s.llm.error_rate > 0.05 ? 'bad' : ''}`}><div className="figure-value">{pct(s.llm.error_rate)}</div><div className="figure-label">model call errors</div></div>
                        <div className="figure"><div className="figure-value">{ms(s.llm.latency_ms_p50)} / {ms(s.llm.latency_ms_p95)}</div><div className="figure-label">model call time, median / p95</div></div>
                        <div className="figure"><div className="figure-value">{((s.llm.prompt_tokens + s.llm.completion_tokens) / 1000).toFixed(1)}k</div><div className="figure-label">tokens used</div></div>
                    </div>

                    <div className="result-cols" style={{ marginTop: 32 }}>
                        <section>
                            <h2 style={{ fontSize: 'var(--t-lg)', marginBottom: 12 }}>Model calls over time</h2>
                            {data.points.length ? (
                                <div className="panel" style={{ height: 260 }}>
                                    <ResponsiveContainer>
                                        <BarChart data={data.points}>
                                            <CartesianGrid stroke="#e7edea" vertical={false} />
                                            <XAxis dataKey="ts" tickFormatter={hour} fontSize={12} />
                                            <YAxis allowDecimals={false} fontSize={12} width={32} />
                                            <Tooltip labelFormatter={hour} />
                                            <Bar dataKey="calls" name="Calls" fill="#1F5F55" />
                                            <Bar dataKey="errors" name="Errors" fill="#C0392B" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : <div className="empty">No model calls in this window yet. Run a symptom check to see one.</div>}
                            {data.points.some((p) => p.latency_ms_p50) && (
                                <div className="panel" style={{ height: 200, marginTop: 12 }}>
                                    <ResponsiveContainer>
                                        <LineChart data={data.points}>
                                            <CartesianGrid stroke="#e7edea" vertical={false} />
                                            <XAxis dataKey="ts" tickFormatter={hour} fontSize={12} />
                                            <YAxis fontSize={12} width={44} unit=" ms" />
                                            <Tooltip labelFormatter={hour} />
                                            <Line dataKey="latency_ms_p50" name="Median ms" stroke="#1F5F55" dot={false} strokeWidth={2} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </section>
                        <section>
                            <h2 style={{ fontSize: 'var(--t-lg)', marginBottom: 12 }}>Breakdown</h2>
                            <div className="table-wrap">
                                <table>
                                    <thead><tr><th>Provider</th><th className="num">Calls</th><th className="num">Errors</th><th className="num">Median</th></tr></thead>
                                    <tbody>
                                        {Object.entries(s.llm.by_provider).map(([p, v]) => (
                                            <tr key={p}><td>{p}</td><td className="num">{v.calls}</td><td className="num">{v.errors}</td><td className="num">{ms(v.latency_ms_p50)}</td></tr>
                                        ))}
                                        {!Object.keys(s.llm.by_provider).length && <tr><td colSpan={4} className="faint">No calls yet.</td></tr>}
                                    </tbody>
                                </table>
                            </div>
                            <div className="table-wrap" style={{ marginTop: 12 }}>
                                <table>
                                    <thead><tr><th>Decided by</th><th className="num">Checks</th></tr></thead>
                                    <tbody>
                                        {Object.entries(s.triage.by_decision_path).map(([p, n]) => (
                                            <tr key={p}><td>{PATHS[p] || p}</td><td className="num">{n}</td></tr>
                                        ))}
                                        {!Object.keys(s.triage.by_decision_path).length && <tr><td colSpan={2} className="faint">No checks yet.</td></tr>}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    </div>

                    <section style={{ marginTop: 32 }}>
                        <h2 style={{ fontSize: 'var(--t-lg)', marginBottom: 12 }}>Recent checks</h2>
                        <div className="table-wrap">
                            <table>
                                <thead><tr><th>When</th><th>Level</th><th>Decided by</th><th>Red flags</th><th className="num">Model calls</th><th className="num">Time</th></tr></thead>
                                <tbody>
                                    {data.runs.filter((r) => r.source !== 'eval').map((r, i) => (
                                        <tr key={i}>
                                            <td>{timeAgo(new Date(r.ts * 1000).toISOString())}</td>
                                            <td><span className={`pill ${LEVELS[r.label]?.key}`}>{LEVELS[r.label]?.name}</span>{r.escalated && <div className="faint">raised by rule</div>}</td>
                                            <td>{PATHS[r.decision_path] || r.decision_path}{r.fallback_reason && <div className="faint">{r.fallback_reason.replace(/_/g, ' ')}</div>}</td>
                                            <td className="faint">{r.red_flags.join(', ') || 'none'}</td>
                                            <td className="num">{r.llm_calls}</td>
                                            <td className="num">{ms(r.latency_ms)}</td>
                                        </tr>
                                    ))}
                                    {!data.runs.length && <tr><td colSpan={6} className="faint">No checks yet.</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <section style={{ marginTop: 32 }}>
                        <h2 style={{ fontSize: 'var(--t-lg)', marginBottom: 12 }}>Recent model calls</h2>
                        <div className="table-wrap">
                            <table>
                                <thead><tr><th>When</th><th>For</th><th>Provider</th><th>Status</th><th className="num">Tokens in / out</th><th className="num">Tools</th><th className="num">Time</th></tr></thead>
                                <tbody>
                                    {data.calls.map((c, i) => (
                                        <tr key={i} className={c.status === 'error' ? 'miss' : ''}>
                                            <td>{timeAgo(new Date(c.ts * 1000).toISOString())}</td>
                                            <td>{c.purpose?.replace(/_/g, ' ')}</td>
                                            <td>{c.provider}<div className="faint">{c.model}</div></td>
                                            <td>{c.status}{c.error && <div className="faint">{c.error}</div>}</td>
                                            <td className="num">{c.prompt_tokens ?? '–'} / {c.completion_tokens ?? '–'}</td>
                                            <td className="num">{c.tool_calls}</td>
                                            <td className="num">{ms(c.latency_ms)}</td>
                                        </tr>
                                    ))}
                                    {!data.calls.length && <tr><td colSpan={7} className="faint">No model calls yet.</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </section>
                </>
            )}
        </div>
    )
}
