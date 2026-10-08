import { lazy, Suspense, useState } from 'react'
import { Navigate, Route, Routes, useSearchParams } from 'react-router-dom'
import Tour from './components/Tour'
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
    const [params, setParams] = useSearchParams()
    const [tour, setTour] = useState(params.get('tour') === '1')
    const closeTour = () => {
        setTour(false)
        if (params.has('tour')) setParams({}, { replace: true })
    }
    return (
        <div className="app">
            <a className="skip-link" href="#main">Skip to content</a>
            <Navbar onTour={() => setTour(true)} />
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
            <Tour open={tour} onClose={closeTour} />
        </div>
    )
}
