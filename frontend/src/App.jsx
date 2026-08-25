import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import Landing from './pages/Landing'
import Triage from './pages/Triage'
import Result from './pages/Result'
import History from './pages/History'

// Chart-heavy pages load on demand so the symptom checker stays light.
const Evals = lazy(() => import('./pages/Evals'))
const Ops = lazy(() => import('./pages/Ops'))

export default function App() {
    return (
        <div className="app">
            <a className="skip-link" href="#main">Skip to content</a>
            <Navbar />
            <main id="main">
                <Suspense fallback={<div className="wrap section faint">Loading…</div>}>
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/triage" element={<Triage />} />
                    <Route path="/result/:sessionId" element={<Result />} />
                    <Route path="/history" element={<History />} />
                    <Route path="/evals" element={<Evals />} />
                    <Route path="/ops" element={<Ops />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
                </Suspense>
            </main>
            <Footer />
        </div>
    )
}
