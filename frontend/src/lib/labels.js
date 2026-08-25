export const LEVELS = {
    HomeCare: { key: 'home', name: 'Home care', short: 'Manage at home', meaning: 'Rest, self-care and keep an eye on it.' },
    Urgent: { key: 'urgent', name: 'Urgent', short: 'See a doctor today', meaning: 'Get checked within about 24 hours.' },
    Emergency: { key: 'emergency', name: 'Emergency', short: 'Get help now', meaning: 'Call 112 or go to an emergency department.' },
}

export const PATHS = {
    agent: 'AI agent, checked by safety rules',
    rules: 'Rule-based assessment (AI not used)',
    red_flag: 'Safety rule',
}

export const FALLBACK_REASONS = {
    no_llm_provider: 'No AI provider is configured on this server, so the rule-based assessment was used.',
    agent_failed: "The AI agent didn't return an answer in time, so the rule-based assessment was used.",
    llm_disabled: 'AI was switched off for this request.',
}

export const prettySymptom = (s) => s.replace(/_/g, ' ')

export function timeAgo(iso) {
    const t = new Date(iso).getTime()
    const s = Math.max(0, (Date.now() - t) / 1000)
    if (s < 60) return 'just now'
    if (s < 3600) return `${Math.floor(s / 60)} min ago`
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
