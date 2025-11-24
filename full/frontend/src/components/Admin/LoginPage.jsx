import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import './Admin.css'

const LoginPage = () => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  })
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { user, login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (user) {
      navigate('/', { replace: true })
    }
  }, [user, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    console.log('🔄 Attempting login...')
    const result = await login(credentials)

    if (result.success) {
      console.log('✅ Login successful, redirecting...')
      navigate('/', { replace: true })
    } else {
      console.error('❌ Login failed:', result.error)
      setError(result.error)
    }

    setIsLoading(false)
  }

  const handleChange = (e) => {
    setCredentials({
      ...credentials,
      [e.target.name]: e.target.value
    })
  }

  if (user) {
    return <div className="loading">Перенаправление...</div>
  }

  return (
    <div className="admin-login-container">
      <div className="admin-login-form">
        <h1>🚀 KPI Анализатор</h1>
        <h2>Вход в систему</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Логин:</label>
            <input
              type="text"
              id="username"
              name="username"
              value={credentials.username}
              onChange={handleChange}
              required
              disabled={isLoading}
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Пароль:</label>
            <input
              type="password"
              id="password"
              name="password"
              value={credentials.password}
              onChange={handleChange}
              required
              disabled={isLoading}
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="error-message">
              {error}
              <br />
              <small>Проверьте правильность введенных данных</small>
            </div>
          )}

          <button
            type="submit"
            className="btn primary"
            disabled={isLoading}
          >
            {isLoading ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginPage