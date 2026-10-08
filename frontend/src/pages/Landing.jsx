import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import TriageTag from '../components/TriageTag'
import IntakeFields from '../components/IntakeFields'
import { systemAPI } from '../api/client'

const SAMPLES = [
    { text: 'Mild sore throat since yesterday, no fever', age: 24, gender: 'female' },
    { text: 'Fever of 39 C for four days with body aches', age: 31, gender: 'male' },
    { text: 'Chest pain and sweating for the last 20 minutes', age: 58, gender: 'male' },
    { text: 'Itchy rash on my hands after using a new soap', age: 27, gender: 'female' },
]

const pctText = (v) => (v == null ? 'n/a' : `${Math.round(v * 100)}%`)

export default function Landing() {
    const navigate = useNavigate()
    const [form, setForm] = useState({ complaint: '', age: '', gender: '' })
    const [error, setError] = useState('')
    const [evals, setEvals] = useState(null)
    const [status, setStatus] = useState(null)

    useEffect(() => {
        systemAPI.evals().then((r) => setEvals(r.data.reports)).catch(() => setEvals([]))
        systemAPI.status().then((r) => setStatus(r.data)).catch(() => setStatus(null))
    }, [])

    const submit = (e) => {
        e.preventDefault()
        if (form.complaint.trim().length < 3) return setError('Describe what you are feeling in a few words.')
        if (form.age === '' || Number(form.age) < 0 || Number(form.age) > 120) return setError('Enter an age between 0 and 120.')
        navigate('/triage', { state: { ...form, age: Number(form.age), autostart: true } })
    }

    const report = evals?.find((r) => r.pipeline === 'agent') || evals?.find((r) => r.pipeline === 'rules')
    const m = report?.metrics

    return (
        <>
            <section className="hero">
                <div className="wrap hero-grid">
                    <div>
                        <h1>How urgent is it?</h1>
                        <p className="lede">
                            Describe what's wrong in your own words. You'll get one of three levels, the reasons
                            behind it, and where to go.
                        </p>
                        <form className="intake" onSubmit={submit} noValidate>
                            <IntakeFields form={form} setForm={(f) => { setForm(f); setError('') }} large />
                            {error && <p className="error-text" role="alert" style={{ marginTop: 10 }}>{error}</p>}
                            <div className="row" style={{ marginTop: 16 }}>
                                <button className="btn btn-primary" type="submit">Check my symptoms</button>
                                <Link className="btn btn-ghost" to="/?tour=1">Take the app tour</Link>
                                <span className="faint">Takes about a minute. No sign-up.</span>
                            </div>
                        </form>
                        <div className="samples">
                            <span className="faint">Or try an example:</span>
                            <div className="samples-list">
                                {SAMPLES.map((s) => (
                                    <button key={s.text} type="button" className="sample"
                                        onClick={() => { setForm({ complaint: s.text, age: String(s.age), gender: s.gender }); setError('') }}>
                                        {s.text}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                    <aside aria-label="The three levels">
                        <p className="levels-caption">Every check ends with one of three levels.</p>
                        <div className="tag-stack">
                            <TriageTag level="HomeCare" />
                            <TriageTag level="Urgent" />
                            <TriageTag level="Emergency" />
                        </div>
                    </aside>
                </div>
            </section>

            <section className="section">
                <div className="wrap">
                    <div className="section-head">
                        <h2>What happens to your words</h2>
                    </div>
                    <ol className="pipeline">
                        <li>
                            <h3>Safety rules read it first</h3>
                            <p>Fixed rules look for emergency signs such as a stroke, a heart attack or heavy bleeding. No AI is involved, so nothing can talk them out of it.</p>
                        </li>
                        <li>
                            <h3>A few follow-up questions</h3>
                            <p>Up to six quick questions picked for your symptoms: yes or no, a 1 to 10 scale, or how long.</p>
                        </li>
                        <li>
                            <h3>An AI agent works the case</h3>
                            <p>It looks up each symptom, searches a knowledge base of 23 short notes, and re-checks anything worrying before it decides.</p>
                            <div className="tools">
                                <code>lookup_symptom</code><code>search_knowledge</code><code>check_red_flags</code>
                            </div>
                        </li>
                        <li>
                            <h3>A safety check, then your result</h3>
                            <p>The final level is never lower than what the safety rules found. You see the reasons, the sources and care nearby.</p>
                        </li>
                    </ol>
                </div>
            </section>

            <section className="section">
                <div className="wrap">
                    <div className="section-head">
                        <div className="stack" style={{ '--s': '8px' }}>
                            <h2>How well it works</h2>
                            <p className="muted">
                                Every change is tested on 60 written cases, 20 for each level. The number that matters
                                most is missed emergencies: someone who needed help now being told to stay home.
                            </p>
                        </div>
                        <Link to="/evals" className="btn btn-quiet">See every case</Link>
                    </div>
                    {m ? (
                        <>
                            <div className="figures">
                                <div className={`figure ${m.critical_misses === 0 ? 'good' : 'bad'}`}>
                                    <div className="figure-value">{m.critical_misses}</div>
                                    <div className="figure-label">emergencies sent home</div>
                                </div>
                                <div className="figure">
                                    <div className="figure-value">{pctText(m.emergency_recall)}</div>
                                    <div className="figure-label">of emergencies flagged as emergencies</div>
                                </div>
                                <div className="figure">
                                    <div className="figure-value">{pctText(m.accuracy)}</div>
                                    <div className="figure-label">of all cases given the expected level</div>
                                </div>
                                <div className="figure">
                                    <div className="figure-value">{pctText(m.over_triage_rate)}</div>
                                    <div className="figure-label">sent to a higher level than needed</div>
                                </div>
                            </div>
                            <p className="faint" style={{ marginTop: 10 }}>
                                {report.pipeline === 'agent' ? 'AI agent with safety rules' : 'Rule-based pipeline (AI off)'},
                                run {new Date(report.run_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}.
                                Expected levels were written by the project author from public guidance and are not clinically validated.
                            </p>
                        </>
                    ) : (
                        <div className="empty">{evals ? 'No eval results published yet.' : 'Loading eval results…'}</div>
                    )}
                    {status && (
                        <p className="notice" style={{ marginTop: 24 }}>
                            {status.agent_enabled
                                ? <>Running now: the AI agent uses {Object.entries(status.llm_models).map(([p, mdl], i) => `${i ? 'backup ' : ''}${mdl} via ${p === 'groq' ? 'Groq' : 'NVIDIA NIM'}`).join(', ')}.</>
                                : <>Running now: no AI provider is configured on this server, so results come from the rule-based assessment and the safety rules.</>}
                            {' '}Knowledge search: {status.knowledge_base.notes} notes, {status.knowledge_base.mode === 'embeddings' ? 'vector search with embeddings' : 'keyword search'}.
                        </p>
                    )}
                </div>
            </section>
        </>
    )
}
