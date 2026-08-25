import { useEffect, useRef, useState } from 'react'

/** The right control for each question type, so answers are valid by construction. */
export default function AnswerInput({ question, onSubmit, busy }) {
    const [text, setText] = useState('')
    const [custom, setCustom] = useState(false)
    const ref = useRef(null)
    const type = question.answer_type

    useEffect(() => { setText(''); setCustom(false) }, [question.question_id])
    useEffect(() => { if ((type === 'text' || custom) && ref.current) ref.current.focus() }, [type, custom, question.question_id])

    const send = (value) => { if (!busy && String(value).trim()) onSubmit(String(value).trim()) }

    if (type === 'scale') {
        return (
            <div>
                <div className="scale" role="group" aria-label="1 is mild, 10 is the worst imaginable">
                    {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                        <button key={n} type="button" className="choice" disabled={busy} onClick={() => send(n)}>{n}</button>
                    ))}
                </div>
                <div className="scale-ends"><span>1 mild</span><span>10 worst imaginable</span></div>
            </div>
        )
    }

    const options = question.options || []
    if (options.length && !custom) {
        return (
            <div className="choice-row">
                {options.map((o) => (
                    <button key={o} type="button" className="choice" disabled={busy} onClick={() => send(o)}>{o}</button>
                ))}
                {type === 'duration' && (
                    <button type="button" className="btn btn-text" onClick={() => setCustom(true)}>Type it instead</button>
                )}
            </div>
        )
    }

    return (
        <form className="row" style={{ flexWrap: 'nowrap' }} onSubmit={(e) => { e.preventDefault(); send(text) }}>
            <label className="sr-only" htmlFor="answer">Your answer</label>
            <input id="answer" ref={ref} className="input" value={text} maxLength={500} disabled={busy}
                placeholder={type === 'duration' ? 'For example: 3 days' : 'Type your answer'}
                onChange={(e) => setText(e.target.value)} />
            <button className="btn btn-primary" type="submit" disabled={busy || !text.trim()}>Send</button>
        </form>
    )
}
