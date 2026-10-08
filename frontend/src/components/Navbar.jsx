import { useState } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { useEffect } from 'react'

export function BrandMark() {
    return (
        <svg className="brand-mark" viewBox="0 0 22 28" aria-hidden="true">
            <path d="M5 0h17v28H0V5z" fill="#1F5F55" />
            <circle cx="11" cy="7" r="2.4" fill="#F6F8F7" />
            <path d="M6.5 15.5h9v2.6h-9z M9.7 12.3h2.6v9h-2.6z" fill="#F6F8F7" />
        </svg>
    )
}

const LINKS = [
    ['/triage', 'Check symptoms'],
    ['/history', 'Your results'],
    ['/evals', 'Evals'],
    ['/ops', 'Ops'],
]

export default function Navbar({ onTour }) {
    const [open, setOpen] = useState(false)
    const { pathname } = useLocation()
    useEffect(() => setOpen(false), [pathname])

    return (
        <header>
            <div className="sos">
                <div className="wrap">
                    <span>Someone in danger right now?</span>
                    <a href="tel:112">Call 112</a>
                    <span className="faint" style={{ color: '#c9d4d0' }}>This tool gives guidance, not a diagnosis.</span>
                </div>
            </div>
            <nav className="nav" aria-label="Main">
                <div className="wrap">
                    <Link to="/" className="brand"><BrandMark /> HealthAI</Link>
                    <button className="menu-btn" aria-expanded={open} aria-controls="nav-links"
                        onClick={() => setOpen(!open)} aria-label={open ? 'Close menu' : 'Open menu'}>
                        {open ? <X size={20} /> : <Menu size={20} />}
                    </button>
                    <div id="nav-links" className={`nav-links ${open ? 'open' : ''}`}>
                        {LINKS.map(([to, label]) => (
                            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : '')}>{label}</NavLink>
                        ))}
                        <button className="tour-launch" onClick={() => { setOpen(false); onTour() }}>App tour</button>
                    </div>
                </div>
            </nav>
        </header>
    )
}
