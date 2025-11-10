import React from 'react'
import { Link } from 'react-router-dom'
import './HomePage.css'

const HomePage = ({ toggleTheme, theme }) => {
  return (
    <div className="home-page">
      <header className="home-header">
        <h1>🚀 KPI Анализатор PRO</h1>
        <p>Полный аналог Google Sheets с расширенной аналитикой KPI</p>
        <button className="theme-toggle" onClick={toggleTheme}>
          {theme === 'dark' ? '☀️' : '🌙'} Тема
        </button>
      </header>

      <div className="navigation-grid">
        <Link to="/sheets" className="nav-card">
          <div className="card-icon">📊</div>
          <h3>Таблицы</h3>
          <p>Редактируйте таблицы с поддержкой формул и фильтрации</p>
        </Link>

        <Link to="/analytics" className="nav-card">
          <div className="card-icon">📈</div>
          <h3>Расширенная аналитика</h3>
          <p>Полный анализ KPI с рекомендациями из Google Script</p>
          <div className="new-badge">NEW</div>
        </Link>

        <Link to="/reports" className="nav-card">
          <div className="card-icon">📋</div>
          <h3>Отчеты</h3>
          <p>Экспорт данных и создание отчетов</p>
        </Link>
      </div>

      <div className="quick-stats">
        <div className="stat-item">
          <span className="stat-value">100%</span>
          <span className="stat-label">Совместимость с Google Sheets</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">30+</span>
          <span className="stat-label">KPI метрик</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">🚀</span>
          <span className="stat-label">Расширенный анализ</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">∞</span>
          <span className="stat-label">Офлайн работа</span>
        </div>
      </div>

      <div className="features-section">
        <h2>✨ Новые возможности</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h4>🤖 Умные рекомендации</h4>
            <p>Автоматические рекомендации по KPI на основе анализа эффективности операторов</p>
          </div>
          <div className="feature-card">
            <h4>📊 Расширенная аналитика</h4>
            <p>Полная логика из Google Apps Script с расчетом эффективности и коррекций</p>
          </div>
          <div className="feature-card">
            <h4>⚡ Сравнение анализов</h4>
            <p>Сравнение простого и расширенного анализа для лучшего понимания данных</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HomePage