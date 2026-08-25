import { Link } from 'react-router-dom'

export default function Footer() {
    return (
        <footer className="footer">
            <div className="wrap">
                <p className="measure">
                    HealthAI is a portfolio project, not a medical device. It can be wrong. If you are worried about
                    your health, see a doctor. In an emergency, call 112.
                </p>
                <nav aria-label="Footer">
                    <Link to="/triage">Check symptoms</Link>
                    <Link to="/evals">How well it works</Link>
                    <Link to="/ops">Ops dashboard</Link>
                    <a href="https://github.com/Asha0509/HealthCare" target="_blank" rel="noreferrer">Source code</a>
                </nav>
            </div>
        </footer>
    )
}
