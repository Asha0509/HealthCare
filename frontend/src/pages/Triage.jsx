import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import IntakeFields from '../components/IntakeFields'
import AnswerInput from '../components/AnswerInput'
import { errorMessage, triageAPI } from '../api/client'
import { saveResult } from '../lib/history'
import { prettySymptom } from '../lib/labels'

function Thinking({ label }) {
    return <span className="thinking" aria-live="polite"><i /><i /><i /> <span style={{ marginLeft: 6 }}>{label}</span></span>
}

export default function Triage() {
    const location = useLocation()
    const navigate = useNavigate()
    const preset = location.state || {}
    const [form, setForm] = useState({ complaint: preset.complaint || '', age: preset.age ?? '', gender: preset.gender || '' })
    const [formError, setFormError] = useState('')
    const [state, setState] = useState(null)            // last TriageSessionState
    const [thread, setThread] = useState([])            // {who, text, kind}
    const [answers, setAnswers] = useState([])          // {q, a}
    const [busy, setBusy] = useState(false)
    const [busyLabel, setBusyLabel] = useState('')
    const [answerError, setAnswerError] = useState('')
    const started = useRef(false)
    const endRef = useRef(null)

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [thread, busy])

    const push = (...msgs) => setThread((t) => [...t, ...msgs])

    const finish = async (sessionId, message) => {
        if (message) push({ who: 'bot', kind: 'warn', text: message })
        setBusyLabel('Putting your result together')
        setBusy(true)
        try {
            const { data } = await triageAPI.result(sessionId)
            saveResult(data)
            navigate(`/result/${sessionId}`, { state: { result: data } })
        } catch (err) {
            setBusy(false)
            push({ who: 'bot', kind: 'warn', text: `Couldn't load your result: ${errorMessage(err)}` })
        }
    }

    const handleState = async (data) => {
        setState(data)
        if (data.status === 'completed') return finish(data.session_id, data.message)
        if (data.current_question) push({ who: 'bot', text: data.current_question.question_text })
    }

    const start = async (f) => {
        if (f.complaint.trim().length < 3) return setFormError('Describe what you are feeling in a few words.')
        if (f.age === '' || Number(f.age) < 0 || Number(f.age) > 120) return setFormError('Enter an age between 0 and 120.')
        setFormError('')
        setThread([{ who: 'me', text: f.complaint.trim() }])
        setAnswers([])
        setBusy(true)
        setBusyLabel('Reading your symptoms')
        try {
            const { data } = await triageAPI.start({
                chief_complaint: f.complaint.trim(),
                patient_age: Number(f.age),
                patient_gender: f.gender || undefined,
            })
            if (data.extracted_symptoms?.length && data.status === 'active') {
                push({ who: 'bot', text: `I picked up: ${data.extracted_symptoms.map(prettySymptom).join(', ')}. A few quick questions.` })
            }
            setBusy(false)
            await handleState(data)
        } catch (err) {
            setBusy(false)
            setThread([])
            setFormError(errorMessage(err))
        }
    }

    useEffect(() => {
        if (preset.autostart && !started.current) {
            started.current = true
            window.history.replaceState({}, '')
            start(form)
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const answer = async (value) => {
        const q = state.current_question
        setAnswerError('')
        setBusy(true)
        setBusyLabel('Thinking')
        try {
            const { data } = await triageAPI.answer({ session_id: state.session_id, question_id: q.question_id, answer: value })
            push({ who: 'me', text: value })
            setAnswers((a) => [...a, { q: q.question_text, a: value }])
            setBusy(false)
            await handleState(data)
        } catch (err) {
            setBusy(false)
            setAnswerError(errorMessage(err))
        }
    }

    const reset = () => { setState(null); setThread([]); setAnswers([]); setAnswerError(''); setFormError('') }

    const active = state?.status === 'active'
    const progress = state ? state.progress_percent : 0

    return (
        <div className="wrap">
            <div className="triage-grid">
                <section aria-labelledby="triage-title">
                    <h1 id="triage-title" style={{ fontSize: 'var(--t-2xl)' }}>Check your symptoms</h1>
                    {!state && !busy && (
                        <form className="stack" style={{ marginTop: 20 }} onSubmit={(e) => { e.preventDefault(); start(form) }} noValidate>
                            <IntakeFields form={form} setForm={(f) => { setForm(f); setFormError('') }} />
                            {formError && <p className="error-text" role="alert">{formError}</p>}
                            <div><button className="btn btn-primary" type="submit">Start</button></div>
                        </form>
                    )}

                    {(state || busy) && (
                        <>
                            <div className="progress" style={{ marginTop: 16 }} role="progressbar" aria-valuenow={progress}
                                aria-valuemin={0} aria-valuemax={100} aria-label="Progress"><span style={{ width: `${Math.max(progress, 4)}%` }} /></div>
                            <div className="thread" aria-live="polite">
                                {thread.map((m, i) => (
                                    <div key={i} className={`msg ${m.kind === 'warn' ? 'warn' : m.who}`}>{m.text}</div>
                                ))}
                                {busy && <div className="msg bot"><Thinking label={busyLabel} /></div>}
                                <div ref={endRef} />
                            </div>
                            {active && !busy && state.current_question && (
                                <div className="answer-box">
                                    <p className="answer-q sr-only">{state.current_question.question_text}</p>
                                    <AnswerInput question={state.current_question} onSubmit={answer} busy={busy} />
                                    {answerError && <p className="error-text" role="alert" style={{ marginTop: 10 }}>{answerError}</p>}
                                </div>
                            )}
                        </>
                    )}
                </section>

                <aside className="case-panel panel" aria-label="Your case so far">
                    <h2>Your case so far</h2>
                    {!state ? (
                        <p className="faint">Your symptoms and answers will appear here as you go.</p>
                    ) : (
                        <div className="stack" style={{ '--s': '14px' }}>
                            <div>
                                <p className="faint">Symptoms picked up</p>
                                <div className="chips" style={{ marginTop: 6 }}>
                                    {state.extracted_symptoms?.length
                                        ? state.extracted_symptoms.map((s) => <span key={s} className="pill">{prettySymptom(s)}</span>)
                                        : <span className="faint">None yet</span>}
                                </div>
                            </div>
                            {answers.length > 0 && (
                                <ul className="case-list">
                                    {answers.map((x, i) => <li key={i}><span className="q">{x.q}</span><span>{x.a}</span></li>)}
                                </ul>
                            )}
                            <button className="btn btn-quiet btn-sm" type="button" onClick={reset} disabled={busy}>Start over</button>
                        </div>
                    )}
                </aside>
            </div>
        </div>
    )
}
