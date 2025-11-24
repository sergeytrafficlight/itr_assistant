import React, { useState, useEffect } from 'react'
import { adminAPI } from '../../api/admin'
import { useAuth } from '../../contexts/AuthContext'

const AdminStats = () => {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { user, isAppInitialized } = useAuth()

  useEffect(() => {
    let isMounted = true
    let retryCount = 0
    const maxRetries = 3

    const loadStats = async () => {
      if (isAppInitialized && user && isMounted) {
        try {
          setLoading(true)
          setError('')
          console.log('🔄 Loading admin stats...')
          const response = await adminAPI.getStats()
          if (isMounted) {
            console.log('✅ Stats loaded successfully')
            setStats(response.data)
          }
        } catch (err) {
          console.error('❌ Error loading stats:', err)
          if (isMounted) {
            setError('Ошибка загрузки статистики')
            setStats(null)

            // Retry logic
            if (retryCount < maxRetries) {
              retryCount++
              console.log(`🔄 Retrying stats load (${retryCount}/${maxRetries})...`)
              setTimeout(loadStats, 1000 * retryCount)
            }
          }
        } finally {
          if (isMounted) {
            setLoading(false)
          }
        }
      }
    }

    loadStats()

    return () => {
      isMounted = false
    }
  }, [user, isAppInitialized])

  if (loading) return <div className="loading">Загрузка статистики...</div>
  if (error) return <div className="error-message">{error}</div>
  if (!stats) return <div className="error-message">Не удалось загрузить статистику</div>

  return (
    <div className="admin-stats">
      <h2>Статистика системы</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.total_users}</div>
          <div className="stat-label">Всего пользователей</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.active_users}</div>
          <div className="stat-label">Активных пользователей</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.inactive_users}</div>
          <div className="stat-label">Неактивных пользователей</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.new_users_today}</div>
          <div className="stat-label">Новых сегодня</div>
        </div>
      </div>
    </div>
  )
}

export default AdminStats