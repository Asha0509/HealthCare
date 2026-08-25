const SEXES = [['female', 'Female'], ['male', 'Male'], ['other', 'Other']]

/** Complaint + age + sex, shared by the landing hero and the triage page. */
export default function IntakeFields({ form, setForm, large = false }) {
    const set = (k) => (v) => setForm({ ...form, [k]: v })
    return (
        <>
            <div className="field">
                <label htmlFor="complaint">What's wrong?</label>
                <textarea id="complaint" className="textarea" maxLength={1000}
                    style={large ? undefined : { minHeight: 100 }}
                    placeholder="For example: headache and fever since yesterday, worse in the evening"
                    value={form.complaint} onChange={(e) => set('complaint')(e.target.value)} />
            </div>
            <div className="intake-meta">
                <div className="field">
                    <label htmlFor="age">Age</label>
                    <input id="age" className="input" type="number" inputMode="numeric" min={0} max={120}
                        placeholder="Years" value={form.age} onChange={(e) => set('age')(e.target.value)} />
                </div>
                <div className="field">
                    <span className="label" id="sex-label">Sex</span>
                    <div className="choice-row" role="group" aria-labelledby="sex-label">
                        {SEXES.map(([v, label]) => (
                            <button key={v} type="button" className="choice" aria-pressed={form.gender === v}
                                onClick={() => set('gender')(form.gender === v ? '' : v)}>{label}</button>
                        ))}
                    </div>
                </div>
            </div>
            <p className="hint" style={{ marginTop: 6 }}>Under 1 year old? Enter 0.</p>
        </>
    )
}
