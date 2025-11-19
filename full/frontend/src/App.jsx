import React, { useState, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import HomePage from './components/HomePage'
import SheetsPage from './components/SheetsPage'
import AnalyticsPage from './components/AnalyticsPage'
import ReportsPage from './components/ReportsPage'
import FullDataPage from './components/FullDataPage' // Импортируйте компонент
import './App.css'

function App() {
  const [theme, setTheme] = useState('dark')
  const location = useLocation()

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'dark'
    setTheme(savedTheme)
    document.documentElement.setAttribute('data-theme', savedTheme)
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  const isHomePage = location.pathname === '/'

  return (
    <div className="app">
      {!isHomePage && (
        <nav className="navbar">
          <div className="nav-brand">
            <Link to="/">🚀 KPI Анализатор PRO</Link>
          </div>
          <div className="nav-links">
            <Link to="/sheets" className={location.pathname === '/sheets' ? 'active' : ''}>
              📊 Таблицы
            </Link>
            <Link to="/analytics" className={location.pathname === '/analytics' ? 'active' : ''}>
              📈 Расширенная аналитика
            </Link>
            <Link to="/reports" className={location.pathname === '/reports' ? 'active' : ''}>
              📋 Отчеты
            </Link>
            {/* Добавьте ссылку в навигацию если нужно */}
            <Link to="/full-data" className={location.pathname === '/full-data' ? 'active' : ''}>
              📋 Полные данные
            </Link>
          </div>
          <div className="nav-actions">
            <button className="btn secondary" onClick={toggleTheme}>
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
          </div>
        </nav>
      )}

      <main className={isHomePage ? '' : 'main-content'}>
        <Routes>
          <Route path="/" element={<HomePage toggleTheme={toggleTheme} theme={theme} />} />
          <Route path="/sheets" element={<SheetsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/reports" element={<ReportsPage toggleTheme={toggleTheme} theme={theme} />} />
          {/* Добавьте этот маршрут */}
          <Route path="/full-data" element={<FullDataPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App