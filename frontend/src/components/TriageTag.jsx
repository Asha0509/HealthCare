import { LEVELS } from '../lib/labels'

/** A triage tag: the punched card used in emergency triage, one colour per level. */
export default function TriageTag({ level, hero = false, children }) {
    const info = LEVELS[level] || LEVELS.Urgent
    return (
        <div className={`tag ${info.key} ${hero ? 'tag-hero' : ''}`}>
            <div className="tag-name">{hero ? info.name : `${info.name}: ${info.short.toLowerCase()}`}</div>
            {children ?? <div className="tag-sub">{info.meaning}</div>}
        </div>
    )
}
