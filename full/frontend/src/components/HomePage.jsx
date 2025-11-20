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

      <div className="features-section">
        <div className="section-header">
          <h2>Почему выбирают KPI Анализатор?</h2>
          <p>Комплексное решение для аналитики современных бизнесов</p>
        </div>
        
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">📊</div>
            <h3>Интерактивные дашборды</h3>
            <p>Визуализация данных в реальном времени с интерактивными графиками и настраиваемыми виджетами</p>
            <div className="feature-highlight">Живые обновления</div>
          </div>
          
          <div className="feature-card feature-primary">
            <div className="feature-icon">💡</div>
            <h3>Умная аналитика</h3>
            <p>Интеллектуальные рекомендации и прогнозные инсайты на основе продвинутых алгоритмов</p>
            <div className="feature-highlight">Умные инсайты</div>
            <div className="new-badge">НОВОЕ</div>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">⚡</div>
            <h3>Высокая производительность</h3>
            <p>Молниеносная обработка и анализ данных с оптимизированными алгоритмами</p>
            <div className="feature-highlight">Быстро и надежно</div>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">🔒</div>
            <h3>Безопасность и конфиденциальность</h3>
            <p>Безопасность корпоративного уровня со сквозным шифрованием и защитой данных</p>
            <div className="feature-highlight">Защищено</div>
          </div>
        </div>
      </div>

      <div className="navigation-section">
        <div className="section-header">
          <h2>Начать работу</h2>
          <p>Выберите точку старта</p>
        </div>
        
        <div className="navigation-grid">
          <Link to="/analytics" className="nav-card nav-primary">
            <div className="nav-card-content">
              <div className="nav-icon">📈</div>
              <div className="nav-text">
                <h3>Расширенная аналитика</h3>
                <p>Глубокий анализ метрик KPI с умными инсайтами и рекомендациями</p>
              </div>
              <div className="nav-arrow">→</div>
            </div>
            <div className="nav-highlight">Самое популярное</div>
          </Link>

          <Link to="/sheets" className="nav-card">
            <div className="nav-card-content">
              <div className="nav-icon">📊</div>
              <div className="nav-text">
                <h3>Таблицы</h3>
                <p>Создавайте и управляйте интерактивными таблицами с совместной работой в реальном времени</p>
              </div>
              <div className="nav-arrow">→</div>
            </div>
          </Link>

          <Link to="/reports" className="nav-card">
            <div className="nav-card-content">
              <div className="nav-icon">📋</div>
              <div className="nav-text">
                <h3>Отчеты и экспорт</h3>
                <p>Генерируйте комплексные отчеты и экспортируйте данные в нескольких форматах</p>
              </div>
              <div className="nav-arrow">→</div>
            </div>
          </Link>

          <Link to="/full-data" className="nav-card">
            <div className="nav-card-content">
              <div className="nav-icon">📁</div>
              <div className="nav-text">
                <h3>Полный доступ к данным</h3>
                <p>Доступ к полным наборам данных с расширенной фильтрацией и поиском</p>
              </div>
              <div className="nav-arrow">→</div>
            </div>
          </Link>
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
          <p>&copy; 2024 KPI Анализатор. Все права защищены.</p>
        </div>
      </footer>
    </div>
  )
}

export default HomePage