import React from 'react'
import { Link } from 'react-router-dom'
import './HomePage.css'

const HomePage = ({ toggleTheme, theme }) => {
  return (
    <div className="home-page">
      <header className="home-header">
        <div className="header-content">
          <div className="logo-container">
            <div className="logo">
              <div className="logo-icon">📊</div>
              <div className="logo-text">
                <span className="logo-primary">KPI</span>
                <span className="logo-secondary">Анализатор</span>
              </div>
            </div>
            <div className="logo-subtitle">Профессиональная платформа анализа данных</div>
          </div>
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === 'dark' ? '☀️ Светлая тема' : '🌙 Тёмная тема'}
          </button>
        </div>
      </header>

      <div className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            Преобразуйте ваши данные
            <span className="hero-highlight"> в инсайты</span>
          </h1>
          <p className="hero-description">
            Продвинутая платформа аналитики KPI с обработкой данных в реальном времени, 
            интерактивными дашбордами и рекомендациями для оптимизации бизнеса.
          </p>
          <div className="hero-actions">
            <Link to="/analytics" className="cta-button primary">
              <span className="cta-icon">🚀</span>
              Начать анализ
            </Link>
            <Link to="/sheets" className="cta-button secondary">
              Исследовать таблицы
            </Link>
          </div>
        </div>
        <div className="hero-visual">
          <div className="floating-card card-1">
            <div className="card-icon">📈</div>
            <div className="card-text">Аналитика в реальном времени</div>
          </div>
          <div className="floating-card card-2">
            <div className="card-icon">⚡</div>
            <div className="card-text">Быстрая обработка</div>
          </div>
          <div className="floating-card card-3">
            <div className="card-icon">💡</div>
            <div className="card-text">Умные рекомендации</div>
          </div>
        </div>
      </div>

      <div className="stats-section">
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-value">99.9%</div>
            <div className="stat-label">Аптайм</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">50K+</div>
            <div className="stat-label">Точек данных</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">30+</div>
            <div className="stat-label">Метрик KPI</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">⚡</div>
            <div className="stat-label">Реальное время</div>
          </div>
        </div>
      </div>

      <footer className="home-footer">
        <div className="footer-content">
          <div className="footer-logo">
            <div className="logo">
              <div className="logo-icon">📊</div>
              <div className="logo-text">
                <span className="logo-primary">KPI</span>
                <span className="logo-secondary">Анализатор</span>
              </div>
            </div>
          </div>
          <div className="footer-links">
            <Link to="/analytics">Аналитика</Link>
            <Link to="/sheets">Таблицы</Link>
            <Link to="/reports">Отчеты</Link>
            <Link to="/full-data">Полные данные</Link>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; 2025 KPI Анализатор</p>
        </div>
      </footer>
    </div>
  )
}

export default HomePage