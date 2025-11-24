import React, { useState, useEffect } from 'react'
import {
  Routes,
  Route,
  Link,
  useLocation,
  Navigate,
} from 'react-router-dom'
import HomePage from './components/HomePage'
import SheetsPage from './components/SheetsPage'
import AnalyticsPage from './components/AnalyticsPage'
import ReportsPage from './components/ReportsPage'
import FullDataPage from './components/FullDataPage'
import AdminPanel from './components/Admin/AdminPanel'
import LoginPage from './components/Admin/LoginPage'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import './App.css'

// Публичный маршрут — только для незалогиненных
const PublicRoute = ({ children }) => {
  const { user, isLoading, isAppInitialized } = useAuth()

  if (isLoading || !isAppInitialized) {
    return <div className="loading">Загрузка...</div>
  }

  return user ? <Navigate to="/" replace /> : children
}

// Основная часть приложения
const AppContent = () => {
  const [theme, setTheme] = useState('dark')
  const location = useLocation()
  const { user, isLoading, isAppInitialized } = useAuth()

  // Загрузка темы из localStorage при монтировании
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
  const isAdminPage = location.pathname.startsWith('/admin')
  const isLoginPage = location.pathname === '/login'

  // Глобальный лоадер, пока идёт проверка авторизации при старте
  if (isLoading || !isAppInitialized) {
    return (
      <div className="app-loading">
        <div className="loading">Инициализация приложения...</div>
      </div>
    )
  }

  return (
    <div className="app">
      {/* Навигация — только для залогиненных и не на главной/логине/админке */}
      {user && !isHomePage && !isAdminPage && !isLoginPage && (
        <nav className="navbar">
          <div className="nav-brand">
            <Link to="/">KPI Анализатор</Link>
          </div>
          <div className="nav-links">
            <Link to="/sheets" className={location.pathname === '/sheets' ? 'active' : ''}>
              Таблицы
            </Link>
            <Link to="/analytics" className={location.pathname === '/analytics' ? 'active' : ''}>
              Расширенная аналитика
            </Link>
            <Link to="/reports" className={location.pathname === '/reports' ? 'active' : ''}>
              Отчеты
            </Link>
            <Link to="/full-data" className={location.pathname === '/full-data' ? 'active' : ''}>
              Полные данные
            </Link>
            <Link to="/admin" className={location.pathname === '/admin' ? 'active' : ''}>
              Админка
            </Link>
          </div>
          <div className="nav-actions">
            <button className="btn secondary" onClick={toggleTheme}>
              {theme === 'dark' ? 'Светлая' : 'Тёмная'}
            </button>
          </div>
        </nav>
      )}

      <main className={isHomePage ? '' : 'main-content'}>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <HomePage toggleTheme={toggleTheme} theme={theme} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/sheets"
            element={
              <ProtectedRoute>
                <SheetsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <AnalyticsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <ReportsPage toggleTheme={toggleTheme} theme={theme} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/full-data"
            element={
              <ProtectedRoute>
                <FullDataPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/*"
            element={
              <ProtectedRoute>
                <AdminPanel />
              </ProtectedRoute>
            }
          />
          <Route
            path="/login"
            element={
              <PublicRoute>
                <LoginPage />
              </PublicRoute>
            }
          />
          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

// Главный компонент
const App = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App