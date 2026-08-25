import { useState } from 'react'
import { MapPin, Navigation, Phone } from 'lucide-react'
import { errorMessage, facilitiesAPI } from '../api/client'

const WHAT = { Emergency: 'hospitals', Urgent: 'hospitals and clinics', HomeCare: 'pharmacies and clinics' }

/** Real places near the person, from OpenStreetMap, nearest first. */
export default function Facilities({ urgency }) {
    const [data, setData] = useState(null)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const [place, setPlace] = useState('')

    const load = async (params) => {
        setBusy(true); setError('')
        try {
            const { data } = await facilitiesAPI.nearby({ urgency, ...params })
            setData(data)
        } catch (err) {
            setError(errorMessage(err))
        } finally {
            setBusy(false)
        }
    }

    const useLocation = () => {
        if (!navigator.geolocation) return setError('Your browser cannot share location. Type a city or area instead.')
        setBusy(true); setError('')
        navigator.geolocation.getCurrentPosition(
            (pos) => load({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
            () => { setBusy(false); setError('Location was not shared. Type a city or area instead.') },
            { timeout: 10000, maximumAge: 300000 },
        )
    }

    return (
        <div>
            <p className="muted">Find {WHAT[urgency]} near you.</p>
            <div className="row" style={{ marginTop: 12 }}>
                <button className="btn btn-quiet" type="button" onClick={useLocation} disabled={busy}>
                    <MapPin size={16} aria-hidden="true" /> Use my location
                </button>
                <form className="row" style={{ flexWrap: 'nowrap', flex: '1 1 240px' }}
                    onSubmit={(e) => { e.preventDefault(); if (place.trim().length > 1) load({ place: place.trim() }) }}>
                    <label className="sr-only" htmlFor="place">City or area</label>
                    <input id="place" className="input" placeholder="Or type a city or area" value={place}
                        onChange={(e) => setPlace(e.target.value)} />
                    <button className="btn btn-quiet" type="submit" disabled={busy || place.trim().length < 2}>Search</button>
                </form>
            </div>
            {busy && <p className="faint" style={{ marginTop: 12 }}>Searching OpenStreetMap…</p>}
            {error && <p className="error-text" role="alert" style={{ marginTop: 12 }}>{error}</p>}
            {data && !busy && (
                data.facilities.length ? (
                    <>
                        <ul className="fac" style={{ marginTop: 12 }}>
                            {data.facilities.map((f) => (
                                <li key={f.osm_url}>
                                    <div>
                                        <div className="name">{f.name}</div>
                                        <div className="meta">
                                            {f.kind}{f.emergency_department ? ', has an emergency department' : ''}
                                            {f.address ? `. ${f.address}` : ''}
                                        </div>
                                        {f.phone && <a className="meta" href={`tel:${f.phone}`}><Phone size={12} aria-hidden="true" /> {f.phone}</a>}
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <div className="meta">{f.distance_km} km</div>
                                        <a href={f.directions_url} target="_blank" rel="noreferrer"><Navigation size={13} aria-hidden="true" /> Directions</a>
                                    </div>
                                </li>
                            ))}
                        </ul>
                        <p className="faint" style={{ marginTop: 8 }}>
                            Within {data.radius_km} km{data.center?.label ? ` of ${data.center.label.split(',').slice(0, 2).join(',')}` : ''}.
                            Map data © OpenStreetMap contributors. Call ahead to check opening hours.
                        </p>
                    </>
                ) : <p className="faint" style={{ marginTop: 12 }}>Nothing found within {data.radius_km} km. Try a nearby city.</p>
            )}
        </div>
    )
}
