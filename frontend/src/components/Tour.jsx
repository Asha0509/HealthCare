import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

// One step per page: what the page is for and what is on it. A step with no
// `to` (the result page only exists after a check) describes it without navigating.
export const STEPS = [
    {
        to: '/',
        title: 'Landing page',
        what: 'Explains in a minute what the tool does and lets you start straight away.',
        has: [
            'A box to describe your symptoms, with age and gender, and four example cases you can click',
            '"What happens to your words": safety rules first, follow-up questions, an AI agent, then a safety check',
            '"How well it works": the headline numbers from the published eval',
        ],
    },
    {
        to: '/triage',
        title: 'Check symptoms',
        what: 'The conversation. You describe the problem and answer a few follow-up questions.',
        has: [
            'Your message and the follow-up questions, one at a time',
            '"Your case so far": the symptoms the system picked up, so you can see how it understood you',
            'Emergency warning signs appear in a red box the moment they are noticed',
        ],
    },
    {
        title: 'The result (after a check)',
        what: 'You land here when the questions are done. It is the only page with advice for your case.',
        has: [
            'One of three levels: Home care, Urgent or Emergency, with what to do next (Emergency says call 112)',
            '"Why this level" in plain sentences and the key factors',
            '"Things a doctor may consider", with a reminder that this is not a diagnosis',
            '"Care near you": find hospitals by location or area',
            'Sources the advice came from, and "How this was decided": every step the safety rules and the AI agent took',
        ],
    },
    {
        to: '/history',
        title: 'Your results',
        what: 'Checks you finished before, saved in this browser only. Nobody else can see them.',
        has: ['Each past check with its level and how long ago it was; click one to reopen it', 'A delete button per result, and Delete all', 'If it is empty, a button to start your first check'],
    },
    {
        to: '/evals',
        title: 'How well it works',
        what: 'The published test: 60 written cases, each with the level a careful clinician would choose.',
        has: [
            'Headline numbers: emergencies caught, exact-level match, under-triage, over-triage, median time',
            '"Where the answers landed": expected level against the level given',
            '"By kind of case" and "Every case": each case with how it was decided and why the label is expected',
        ],
    },
    {
        to: '/ops',
        title: 'Ops dashboard',
        what: 'The audit trail for the AI: every model call and every finished check, as they happen on this server.',
        has: [
            '"Model calls over time" and a breakdown by provider and outcome',
            '"Recent checks" and "Recent model calls": latency, tokens, and whether the system fell back to rules',
            'Switch between the last 24 hours and the last 7 days',
        ],
    },
]

export default function Tour({ open, onClose }) {
    const [i, setI] = useState(0)
    const nav = useNavigate()
    const { pathname } = useLocation()
    const step = STEPS[i]

    useEffect(() => {
        if (open && step.to && pathname !== step.to) nav(step.to)
        // Navigate when the step changes or the tour opens, not on every route change.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, i])

    if (!open) return null
    return (
        <aside className="tour" role="dialog" aria-label="App tour">
            <div className="tour-head">
                <span>App tour · {i + 1} of {STEPS.length}</span>
                <button className="tour-x" onClick={onClose} aria-label="Close tour">×</button>
            </div>
            <h2>{step.title}</h2>
            <p className="tour-what">{step.what}</p>
            <ul>{step.has.map((h) => <li key={h}>{h}</li>)}</ul>
            <div className="tour-nav">
                <button className="btn btn-ghost" disabled={i === 0} onClick={() => setI(i - 1)}>Back</button>
                {i < STEPS.length - 1
                    ? <button className="btn btn-primary" onClick={() => setI(i + 1)}>Next page</button>
                    : <button className="btn btn-primary" onClick={onClose}>Finish</button>}
            </div>
        </aside>
    )
}
