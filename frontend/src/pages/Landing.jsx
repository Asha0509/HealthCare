import { Link } from 'react-router-dom'
import { Activity, Shield, Brain, Zap, Heart, ChevronRight, AlertTriangle, Database, Layers, BarChart3 } from 'lucide-react'

// Dataset & Model Statistics
const DATASET_STATS = {
    samples: '246,945',
    symptoms: '377',
    diseases: '721',
    accuracy: '82.67%',
    modelType: 'Random Forest',
    trainingDate: 'Feb 2026'
}

const FEATURES = [
    { icon: Brain, title: 'Medical NLP Engine', desc: 'Extracts symptoms, severity, and duration from natural language with clinical-grade accuracy.' },
    { icon: Zap, title: 'Adaptive Questioning', desc: 'Dynamically follows up with the right questions based on your symptoms using Bayesian inference.' },
    { icon: Shield, title: 'Safety Guardrails', desc: 'Hard-coded red-flag rules instantly escalate life-threatening presentations to Emergency.' },
    { icon: Activity, title: 'Explainable AI', desc: 'Every triage result comes with plain-English reasoning backed by SHAP feature attribution.' },
    { icon: Heart, title: 'Remedy & Nutrition', desc: 'Holistic home care recommendations tailored to your specific symptom profile.' },
    { icon: AlertTriangle, title: 'Crisis Support', desc: 'Detects self-harm signals and connects you instantly with crisis hotline resources.' },
]

const STEPS = [
    { num: '01', title: 'Describe Symptoms', desc: 'Type what you feel in your own words — or use voice input.' },
    { num: '02', title: 'Answer Follow-ups', desc: 'Our AI asks targeted questions to build a complete clinical picture.' },
    { num: '03', title: 'Get Triage Result', desc: 'Receive an explainable Emergency, Urgent, or Home Care recommendation instantly.' },
]

export default function Landing() {
    return (
        <div style={{ paddingTop: 64 }}>
            {/* ── Hero ── */}
            <section style={{ minHeight: '90vh', display: 'flex', alignItems: 'center', padding: '80px 0' }}>
                <div className="container" style={{ textAlign: 'center' }}>
                    {/* Status badge */}
                    <div style={{
                        display: 'inline-flex', alignItems: 'center', gap: 10,
                        background: 'rgba(0,212,170,0.1)', border: '1px solid rgba(0,212,170,0.2)',
                        borderRadius: 999, padding: '6px 18px', marginBottom: 32
                    }}>
                        <span className="pulse-dot" />
                        <span style={{ fontSize: '0.8rem', color: 'var(--accent-teal)', fontWeight: 600 }}>
                            AI Clinical Triage System — Active
                        </span>
                    </div>

                    <h1 style={{ maxWidth: 900, margin: '0 auto 24px' }}>
                        <span className="gradient-text">AI-Powered</span> Healthcare Triage
                        <br />for the Real World
                    </h1>

                    <p style={{ fontSize: '1.15rem', maxWidth: 640, margin: '0 auto 48px', lineHeight: 1.8 }}>
                        Describe your symptoms. Our clinical AI asks intelligent follow-up questions,
                        analyzes red flags in real-time, and delivers an explainable triage decision —
                        <strong style={{ color: 'var(--text-primary)' }}> Emergency, Urgent, or Home Care</strong>.
                    </p>

                    <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
                        <Link to="/triage" className="btn btn-primary" style={{ padding: '16px 36px', fontSize: '1rem' }}>
                            Start Triage <ChevronRight size={18} />
                        </Link>
                        <Link to="/register" className="btn btn-secondary" style={{ padding: '16px 36px', fontSize: '1rem' }}>
                            Create Account
                        </Link>
                    </div>

                    {/* Floating stats */}
                    <div style={{ display: 'flex', gap: 24, justifyContent: 'center', marginTop: 64, flexWrap: 'wrap' }}>
                        {[
                            { label: 'Training Samples', value: DATASET_STATS.samples },
                            { label: 'Symptom Features', value: DATASET_STATS.symptoms },
                            { label: 'Disease Classes', value: DATASET_STATS.diseases },
                            { label: 'Top-5 Accuracy', value: DATASET_STATS.accuracy },
                        ].map(s => (
                            <div key={s.label} className="glass-card" style={{ padding: '20px 32px', textAlign: 'center', minWidth: 130 }}>
                                <div style={{
                                    fontSize: '1.8rem', fontWeight: 800, background: 'var(--gradient-brand)',
                                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
                                }}>{s.value}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{s.label}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── How it works ── */}
            <section style={{ padding: '100px 0', background: 'rgba(255,255,255,0.01)' }}>
                <div className="container">
                    <div style={{ textAlign: 'center', marginBottom: 64 }}>
                        <h2>How It Works</h2>
                        <p style={{ marginTop: 12 }}>Three steps. Seconds to result.</p>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
                        {STEPS.map((s, i) => (
                            <div key={i} className="glass-card" style={{ padding: 32, position: 'relative', overflow: 'hidden' }}>
                                <div style={{
                                    fontSize: '4rem', fontWeight: 900, position: 'absolute', top: 16, right: 20,
                                    color: 'rgba(255,255,255,0.04)', fontVariantNumeric: 'tabular-nums'
                                }}>{s.num}</div>
                                <div style={{
                                    fontSize: '1.5rem', fontWeight: 800, marginBottom: 12,
                                    background: 'var(--gradient-brand)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
                                }}>
                                    {s.num}
                                </div>
                                <h3 style={{ marginBottom: 10 }}>{s.title}</h3>
                                <p style={{ fontSize: '0.9rem', lineHeight: 1.7 }}>{s.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── Features ── */}
            <section style={{ padding: '100px 0' }}>
                <div className="container">
                    <div style={{ textAlign: 'center', marginBottom: 64 }}>
                        <h2>High-Level Engineering</h2>
                        <p style={{ marginTop: 12 }}>Production-grade AI stack built for real-world healthcare.</p>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
                        {FEATURES.map((f, i) => (
                            <div key={i} className="glass-card" style={{
                                padding: 28,
                                transition: 'transform 0.2s, box-shadow 0.2s',
                                cursor: 'default'
                            }}
                                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 16px 48px rgba(0,0,0,0.4), 0 0 20px rgba(0,212,170,0.1)' }}
                                onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '' }}>
                                <div style={{
                                    width: 44, height: 44, borderRadius: 12,
                                    background: 'var(--accent-teal-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16
                                }}>
                                    <f.icon size={22} color="var(--accent-teal)" />
                                </div>
                                <h3 style={{ marginBottom: 8 }}>{f.title}</h3>
                                <p style={{ fontSize: '0.88rem', lineHeight: 1.7 }}>{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ── Disclaimer ── */}
            <section style={{ padding: '60px 0' }}>
                <div className="container">
                    {/* Dataset & Model Info Banner */}
                    <div className="glass-card" style={{ 
                        padding: 32, 
                        marginBottom: 32, 
                        background: 'linear-gradient(135deg, rgba(0,212,170,0.05) 0%, rgba(59,130,246,0.05) 100%)',
                        border: '1px solid rgba(0,212,170,0.15)'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                            <div style={{
                                width: 40, height: 40, borderRadius: 10,
                                background: 'var(--accent-teal-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}>
                                <Database size={20} color="var(--accent-teal)" />
                            </div>
                            <h3 style={{ margin: 0 }}>Powered by Medical Dataset</h3>
                        </div>
                        
                        <div style={{ 
                            display: 'grid', 
                            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
                            gap: 20 
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Layers size={18} color="var(--accent-teal)" />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Dataset</div>
                                    <div style={{ fontWeight: 600 }}>Augmented Symptoms-Diseases</div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <BarChart3 size={18} color="var(--accent-teal)" />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Model</div>
                                    <div style={{ fontWeight: 600 }}>{DATASET_STATS.modelType} Classifier</div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Brain size={18} color="var(--accent-teal)" />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Training Data</div>
                                    <div style={{ fontWeight: 600 }}>{DATASET_STATS.samples} samples</div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <Activity size={18} color="var(--accent-teal)" />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Prediction Accuracy</div>
                                    <div style={{ fontWeight: 600 }}>{DATASET_STATS.accuracy} (Top-5)</div>
                                </div>
                            </div>
                        </div>
                        
                        <div style={{ 
                            marginTop: 20, 
                            paddingTop: 16, 
                            borderTop: '1px solid rgba(255,255,255,0.06)',
                            fontSize: '0.8rem',
                            color: 'var(--text-muted)'
                        }}>
                            <strong style={{ color: 'var(--text-secondary)' }}>ML Pipeline:</strong> Trained on {DATASET_STATS.symptoms} symptom features across {DATASET_STATS.diseases} disease classes using {DATASET_STATS.modelType} with stratified k-fold validation.
                        </div>
                    </div>
                    
                    <div style={{
                        background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.2)',
                        borderRadius: 'var(--radius-lg)', padding: '24px 32px', display: 'flex', gap: 16, alignItems: 'flex-start'
                    }}>
                        <AlertTriangle size={22} color="var(--urgent)" style={{ flexShrink: 0, marginTop: 2 }} />
                        <div>
                            <strong style={{ color: 'var(--urgent)', fontSize: '0.9rem' }}>Medical Disclaimer</strong>
                            <p style={{ marginTop: 4, fontSize: '0.85rem', lineHeight: 1.7 }}>
                                This system is a clinical decision <em>support</em> tool and is NOT a substitute for professional medical advice,
                                diagnosis, or treatment. Always seek advice from a qualified physician for any medical condition.
                                In an emergency, call <strong style={{ color: 'var(--text-primary)' }}>112</strong> immediately.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Footer ── */}
            <footer style={{ borderTop: '1px solid var(--border-glass)', padding: '32px 0' }}>
                <div className="container flex-between" style={{ flexWrap: 'wrap', gap: 12 }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        © 2025 HealthAI — AI Clinical Triage System
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Built with FastAPI · XGBoost · SciSpacy · React · Trained on 246K+ Medical Records
                    </span>
                </div>
            </footer>
        </div>
    )
}
