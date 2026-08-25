// Past results are kept in this browser only (no account needed).
const KEY = 'healthai.history.v1'
const MAX = 30

function read() {
    try {
        const raw = window.localStorage.getItem(KEY)
        return raw ? JSON.parse(raw) : []
    } catch {
        return []
    }
}

function write(items) {
    try {
        window.localStorage.setItem(KEY, JSON.stringify(items.slice(0, MAX)))
    } catch {
        /* storage full or blocked: history is a convenience, not critical */
    }
}

export function saveResult(result) {
    const items = read().filter((r) => r.session_id !== result.session_id)
    items.unshift({ ...result, saved_at: new Date().toISOString() })
    write(items)
}

export const listResults = read
export const getResult = (id) => read().find((r) => r.session_id === id) || null
export const removeResult = (id) => write(read().filter((r) => r.session_id !== id))
export const clearResults = () => write([])
