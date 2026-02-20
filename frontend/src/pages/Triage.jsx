import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { triageAPI } from '../api/client'
import { Send, Mic, AlertTriangle, Activity, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'

const URGENCY_COLORS = { Emergency: '#ef4444', Urgent: '#f59e0b', HomeCare: '#10b981' }

function ChatBubble({ role, text, isQuestion, options, onOption }) {
    const isAI = role === 'ai'
    return (
        <div style={{ display: 'flex', justifyContent: isAI ? 'flex-start' : 'flex-end', marginBottom: 16 }}>
            {isAI && (
                <div style={{
                    width: 32, height: 32, borderRadius: '50%', flexShrink: 0, marginRight: 10, marginTop: 4,
                    background: 'linear-gradient(135deg, #00d4aa, #3b82f6)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <Activity size={16} color="white" />
                </div>
            )}
            <div style={{ maxWidth: '72%' }}>
                <div style={{
                    padding: '12px 16px', borderRadius: isAI ? '4px 16px 16px 16px' : '16px 4px 16px 16px',
                    background: isAI ? 'rgba(255,255,255,0.06)' : 'linear-gradient(135deg, #00d4aa22, #3b82f622)',
                    border: `1px solid ${isAI ? 'rgba(255,255,255,0.08)' : 'rgba(0,212,170,0.2)'}`,
                    fontSize: '0.9rem', lineHeight: 1.6, color: 'var(--text-primary)',
                }}>
                    {text}
                </div>
                {options && options.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
                        {options.map(opt => (
                            <button key={opt} onClick={() => onOption(opt)} className="btn btn-secondary"
                                style={{ padding: '6px 14px', fontSize: '0.82rem' }}>{opt}</button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}

export default function Triage() {
    const [phase, setPhase] = useState('demographics')  // demographics | intake | questioning | done
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [sessionId, setSessionId] = useState(null)
    const [currentQuestion, setCurrentQuestion] = useState(null)
    const [progress, setProgress] = useState(0)
    const [symptoms, setSymptoms] = useState([])
    const [patientAge, setPatientAge] = useState('')
    const [patientGender, setPatientGender] = useState('')
    const [language, setLanguage] = useState('en')
    const [listening, setListening] = useState(false)
    const chatRef = useRef(null)
    const navigate = useNavigate()

    useEffect(() => {
        chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: 'smooth' })
    }, [messages])

    const addMessage = (role, text, extra = {}) => {
        setMessages(prev => [...prev, { role, text, ...extra }])
    }

    const handleDemographicsSubmit = () => {
        if (!patientAge || !patientGender) {
            toast.error('Please enter your age and select your gender')
            return
        }
        setPhase('intake')
        addMessage('ai', "Hello! I'm HealthAI, your clinical triage assistant. Please describe your symptoms — what are you experiencing today?")
    }

    const startVoice = () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
        if (!SpeechRecognition) { toast.error('Voice input not supported in this browser'); return }
        const rec = new SpeechRecognition()
        rec.lang = language === 'hi' ? 'hi-IN' : 'en-IN'
        rec.onstart = () => setListening(true)
        rec.onend = () => setListening(false)
        rec.onresult = (e) => setInput(e.results[0][0].transcript)
        rec.start()
    }

    const handleStart = async (text) => {
        if (!text.trim()) return
        addMessage('user', text)
        setInput('')
        setLoading(true)
        addMessage('ai', '🔍 Analyzing your symptoms...')

        try {
            const { data } = await triageAPI.start({
                chief_complaint: text,
                patient_age: patientAge ? parseInt(patientAge) : null,
                patient_gender: patientGender || null,
                language,
            })

            setMessages(prev => prev.filter(m => m.text !== '🔍 Analyzing your symptoms...'))
            setSessionId(data.session_id)
            setSymptoms(data.extracted_symptoms || [])
            setProgress(data.progress_percent || 0)

            if (data.status === 'completed') {
                addMessage('ai', data.message || 'Assessment complete. Fetching your result...')
                setTimeout(() => navigate(`/result/${data.session_id}`), 1500)
                return
            }

            if (data.extracted_symptoms?.length > 0) {
                addMessage('ai', `I've identified: ${data.extracted_symptoms.map(s => s.replace(/_/g, ' ')).join(', ')}. Let me ask a few targeted questions.`)
            }

            if (data.current_question) {
                setCurrentQuestion(data.current_question)
                setPhase('questioning')
                addMessage('ai', data.current_question.question_text, {
                    options: data.current_question.options,
                    questionId: data.current_question.question_id,
                    answerType: data.current_question.answer_type,
                })
            }
        } catch (err) {
            setMessages(prev => prev.filter(m => m.text !== '🔍 Analyzing your symptoms...'))
            const msg = err.response?.data?.detail || 'Failed to start triage. Please check your connection.'
            addMessage('ai', `⚠️ ${msg}`)
            toast.error(msg)
        } finally {
            setLoading(false)
        }
    }

    const handleAnswer = async (answer) => {
        if (!sessionId || !currentQuestion) return
        addMessage('user', answer)
        setInput('')
        setLoading(true)

        try {
            const { data } = await triageAPI.answer({
                session_id: sessionId,
                question_id: currentQuestion.question_id,
                answer,
            })

            setProgress(data.progress_percent || 0)

            if (data.status === 'completed') {
                addMessage('ai', '✅ Assessment complete! Preparing your personalized triage result...')
                setTimeout(() => navigate(`/result/${sessionId}`), 1800)
                setPhase('done')
                return
            }

            if (data.current_question) {
                setCurrentQuestion(data.current_question)
                addMessage('ai', data.current_question.question_text, {
                    options: data.current_question.options,
                    questionId: data.current_question.question_id,
                    answerType: data.current_question.answer_type,
                })
            }
        } catch (err) {
            toast.error('Failed to submit answer. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    const handleSend = () => {
        const text = input.trim()
        if (!text || loading) return
        if (phase === 'intake') handleStart(text)
        else if (phase === 'questioning') handleAnswer(text)
    }

    return (
        <div style={{ minHeight: '100vh', paddingTop: 64, display: 'flex', flexDirection: 'column' }}>
            {/* Header */}
            <div style={{
                background: 'rgba(5,13,26,0.9)', borderBottom: '1px solid var(--border-glass)',
                padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
            }}>
                <div>
                    <h3 style={{ fontSize: '1rem', marginBottom: 2 }}>Clinical Triage Assessment</h3>
                    {symptoms.length > 0 && (
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                            {symptoms.slice(0, 4).map(s => (
                                <span key={s} className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                                    {s.replace(/_/g, ' ')}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    {/* Language toggle */}
                    <div style={{ display: 'flex', gap: 4 }}>
                        {['en', 'hi'].map(lang => (
                            <button key={lang} onClick={() => setLanguage(lang)}
                                style={{
                                    padding: '4px 12px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.8rem',
                                    background: language === lang ? 'var(--accent-teal)' : 'var(--bg-glass)',
                                    color: language === lang ? '#000' : 'var(--text-secondary)'
                                }}>
                                {lang === 'en' ? 'EN' : 'हि'}
                            </button>
                        ))}
                    </div>
                    {/* Progress */}
                    <div style={{ width: 120 }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4, textAlign: 'right' }}>
                            {progress}% complete
                        </div>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${progress}%` }} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Demographics Screen - collect age and gender first */}
            {phase === 'demographics' && (
                <div style={{
                    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '24px'
                }}>
                    <div style={{
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid var(--border-glass)',
                        borderRadius: 16, padding: '32px 40px', maxWidth: 420, width: '100%',
                        textAlign: 'center'
                    }}>
                        <div style={{
                            width: 60, height: 60, borderRadius: '50%', margin: '0 auto 20px',
                            background: 'linear-gradient(135deg, #00d4aa, #3b82f6)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                            <Activity size={28} color="white" />
                        </div>
                        <h2 style={{ fontSize: '1.3rem', marginBottom: 8 }}>Welcome to HealthAI</h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginBottom: 24 }}>
                            Please provide some basic information to help us assess your symptoms accurately.
                        </p>
                        
                        <div style={{ textAlign: 'left', marginBottom: 20 }}>
                            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                Age *
                            </label>
                            <input 
                                className="input-field" 
                                type="number" 
                                placeholder="Enter your age" 
                                min="0" 
                                max="120"
                                value={patientAge} 
                                onChange={e => setPatientAge(e.target.value)}
                                style={{ width: '100%', padding: '12px 16px', fontSize: '0.95rem' }} 
                            />
                        </div>

                        <div style={{ textAlign: 'left', marginBottom: 28 }}>
                            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                Gender *
                            </label>
                            <div style={{ display: 'flex', gap: 10 }}>
                                {['male', 'female', 'other'].map(g => (
                                    <button 
                                        key={g}
                                        onClick={() => setPatientGender(g)}
                                        style={{
                                            flex: 1, padding: '12px 8px', borderRadius: 10,
                                            border: patientGender === g ? '2px solid var(--accent-teal)' : '1px solid var(--border-glass)',
                                            background: patientGender === g ? 'rgba(0,212,170,0.12)' : 'var(--bg-glass)',
                                            color: patientGender === g ? 'var(--accent-teal)' : 'var(--text-secondary)',
                                            cursor: 'pointer', fontSize: '0.9rem', textTransform: 'capitalize',
                                            transition: 'all 0.2s'
                                        }}
                                    >
                                        {g}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <button 
                            onClick={handleDemographicsSubmit}
                            className="btn btn-primary"
                            style={{ width: '100%', padding: '14px 24px', fontSize: '1rem', borderRadius: 12 }}
                        >
                            Start Assessment <ChevronRight size={18} style={{ marginLeft: 8 }} />
                        </button>
                    </div>
                </div>
            )}

            {/* Patient Info (intake phase - compact header display) */}
            {phase === 'intake' && patientAge && patientGender && (
                <div style={{
                    background: 'rgba(0,212,170,0.04)', borderBottom: '1px solid var(--border-glass)',
                    padding: '10px 24px', display: 'flex', gap: 16, alignItems: 'center', fontSize: '0.82rem'
                }}>
                    <span style={{ color: 'var(--text-muted)' }}>Patient:</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{patientAge} years, {patientGender}</span>
                </div>
            )}

            {/* Chat area - only show after demographics */}
            {phase !== 'demographics' && (
                <div ref={chatRef} style={{
                    flex: 1, overflowY: 'auto', padding: '24px',
                    maxWidth: 800, width: '100%', margin: '0 auto', paddingBottom: 120
                }}>
                    {messages.map((msg, i) => (
                        <ChatBubble key={i} role={msg.role} text={msg.text}
                            options={msg.options}
                            onOption={(opt) => handleAnswer(opt)} />
                    ))}
                    {loading && (
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '8px 0' }}>
                            <div style={{
                                width: 32, height: 32, borderRadius: '50%',
                                background: 'linear-gradient(135deg, #00d4aa, #3b82f6)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}>
                                <Activity size={16} color="white" />
                            </div>
                            <div style={{ display: 'flex', gap: 4 }}>
                                {[0, 1, 2].map(i => (
                                    <div key={i} style={{
                                        width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-teal)',
                                        animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`
                                    }} />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Input bar */}
            {phase !== 'done' && phase !== 'demographics' && (
                <div style={{
                    position: 'fixed', bottom: 0, left: 0, right: 0,
                    background: 'rgba(5,13,26,0.95)', borderTop: '1px solid var(--border-glass)',
                    padding: '16px 24px', backdropFilter: 'blur(20px)'
                }}>
                    <div style={{ maxWidth: 800, margin: '0 auto', display: 'flex', gap: 12, alignItems: 'flex-end' }}>
                        <div style={{ flex: 1, position: 'relative' }}>
                            <textarea className="input-field" rows={1}
                                placeholder={phase === 'intake'
                                    ? "Describe your symptoms... (e.g., 'I have chest pain and sweating for 2 hours')"
                                    : "Type your answer or choose an option above..."}
                                value={input} onChange={e => setInput(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                                style={{ resize: 'none', paddingRight: 12, minHeight: 48, maxHeight: 120 }} />
                        </div>

                        <button onClick={startVoice} className="btn btn-secondary"
                            disabled={loading}
                            style={{
                                padding: '12px', borderRadius: 12, flexShrink: 0,
                                background: listening ? 'rgba(239,68,68,0.15)' : undefined,
                                border: listening ? '1px solid rgba(239,68,68,0.3)' : undefined
                            }}>
                            <Mic size={18} color={listening ? '#ef4444' : undefined} />
                        </button>

                        <button onClick={handleSend} className="btn btn-primary" disabled={loading || !input.trim()}
                            style={{ padding: '12px 20px', borderRadius: 12, flexShrink: 0 }}>
                            <Send size={18} />
                        </button>
                    </div>
                    <p style={{ textAlign: 'center', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 8 }}>
                        Not a substitute for professional medical advice. In emergency, call 112.
                    </p>
                </div>
            )}
        </div>
    )
}
