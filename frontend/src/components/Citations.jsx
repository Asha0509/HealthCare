import { ExternalLink } from 'lucide-react'

/** Knowledge-base passages the result relied on, each linked to further reading. */
export default function Citations({ items }) {
    if (!items?.length) return <p className="faint">No sources were needed for this result.</p>
    return (
        <div>
            {items.map((c) => (
                <details key={c.chunk_id} className="cite">
                    <summary><span>{c.title}: {c.section}</span><span className="faint">Show</span></summary>
                    <p>{c.text}</p>
                    {c.url && (
                        <p><a href={c.url} target="_blank" rel="noreferrer">Read more on MedlinePlus <ExternalLink size={13} aria-hidden="true" /></a></p>
                    )}
                </details>
            ))}
        </div>
    )
}
