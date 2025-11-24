import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import UserManagement from './UserManagement'
import AdminStats from './AdminStats'
import './Admin.css'

const AdminPanel = () => {
  const [activeTab, setActiveTab] = useState('users')
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout();
  }

  return (
    <div className="admin-panel">
      <header className="admin-header">
        <div className="admin-header-content">
          <h1>⚙️ Админ-панель</h1>
          <div className="admin-user-info">
            <span>Администратор: {user?.username}</span>
            <button onClick={handleLogout} className="btn secondary">
              Выйти
            </button>
          </div>
        </div>
      </header>

      <nav className="admin-tabs">
        <button
          className={`tab-button ${activeTab === 'stats' ? 'active' : ''}`}
          onClick={() => setActiveTab('stats')}
        >
          📊 Статистика
        </button>
        <button
          className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          👥 Управление пользователями
        </button>
      </nav>

      <main className="admin-content">
        {activeTab === 'stats' && <AdminStats />}
        {activeTab === 'users' && <UserManagement />}
      </main>
    </div>
  )
}

export default AdminPanel