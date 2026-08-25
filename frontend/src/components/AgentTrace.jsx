const KIND_LABEL = { rule: 'Safety rule', llm: 'AI model', tool: 'Tool', note: 'Note' }

const NAMES = {
    red_flag_rules: 'Checked emergency red flags',
    rules_assessment: 'Rule-based assessment',
    safety_merge: 'Safety check on the final level',
    chat: 'Model turn',
    lookup_symptom: 'Looked up a symptom',
    search_knowledge: 'Searched the knowledge base',
    check_red_flags: 'Re-checked text for red flags',
    submit_assessment: 'Submitted its assessment',
    parsed_json_reply: 'Read a plain-text answer',
    no_submission: 'No assessment returned',
    agent_error: 'Agent error',
}

function args(a) {
    if (!a || !Object.keys(a).length) return null
    const shown = Object.fromEntries(Object.entries(a).filter(([k]) => !['explanation', 'self_care', 'key_factors', 'conditions_to_consider', 'probabilities', 'recommended_action'].includes(k)))
    return <code>{JSON.stringify(shown)}</code>
}

/** Step-by-step record of how the result was produced. */
export default function AgentTrace({ steps }) {
    if (!steps?.length) return null
    return (
        <ol className="trace">
            {steps.map((s, i) => (
                <li key={i} className={s.kind}>
                    <div><span className="step-name">{NAMES[s.name] || s.name}</span>{' '}
                        <span className="step-meta">
                            {KIND_LABEL[s.kind]}{s.provider ? `, ${s.model} via ${s.provider}` : ''}{s.ms != null ? `, ${s.ms} ms` : ''}
                        </span>
                    </div>
                    {args(s.args)}
                    {s.summary && <div className="step-sum">{s.summary}</div>}
                    {s.failovers?.length > 0 && <div className="step-meta">Failed first: {s.failovers.join('; ')}</div>}
                </li>
            ))}
        </ol>
    )
}
