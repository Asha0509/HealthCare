import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { Toaster } from 'react-hot-toast'

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <BrowserRouter>
            <App />
            <Toaster
                position="top-right"
                toastOptions={{
                    style: {
                        background: 'rgba(10,22,40,0.95)',
                        color: '#f1f5f9',
                        border: '1px solid rgba(255,255,255,0.08)',
                        backdropFilter: 'blur(20px)',
                        fontFamily: 'Inter, sans-serif',
                    },
                }}
            />
        </BrowserRouter>
    </React.StrictMode>
)
