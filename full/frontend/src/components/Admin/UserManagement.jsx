import React, { useState, useEffect } from 'react'
import { adminAPI } from '../../api/admin'
import { useAuth } from '../../contexts/AuthContext'

const UserManagement = () => {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    is_active: true
  })
  const { user, isAppInitialized } = useAuth()

  useEffect(() => {
    let isMounted = true

    const loadUsers = async () => {
      if (isAppInitialized && user && isMounted) {
        try {
          setLoading(true)
          setError('')
          console.log('🔄 Loading users...')
          const response = await adminAPI.getUsers()
          if (isMounted) {
            console.log('✅ Users loaded successfully:', response.data.length)
            setUsers(response.data)
          }
        } catch (err) {
          console.error('❌ Error loading users:', err)
          if (isMounted) {
            setError('Ошибка загрузки пользователей: ' + (err.response?.data?.error || err.message))
          }
        } finally {
          if (isMounted) {
            setLoading(false)
          }
        }
      }
    }

    loadUsers()

    return () => {
      isMounted = false
    }
  }, [user, isAppInitialized])

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      setError('')
      setSuccess('')
      console.log('🔄 Creating user...')
      await adminAPI.createUser(formData)
      console.log('✅ User created successfully')

      // Reload users
      const response = await adminAPI.getUsers()
      setUsers(response.data)

      setSuccess('Пользователь успешно создан')
      setShowForm(false)
      setFormData({
        username: '',
        email: '',
        password: '',
        is_active: true
      })

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      console.error('❌ Error creating user:', err)
      setError('Ошибка создания пользователя: ' + (err.response?.data?.error || err.message))
    }
  }

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.type === 'checkbox' ? e.target.checked : e.target.value
    })
  }

  const toggleUserStatus = async (userId, currentStatus) => {
    try {
      setError('')
      console.log(`🔄 Toggling user status for ${userId}...`)
      await adminAPI.updateUser(userId, { is_active: !currentStatus })
      console.log('✅ User status updated successfully')

      // Reload users
      const response = await adminAPI.getUsers()
      setUsers(response.data)
    } catch (err) {
      console.error('❌ Error updating user:', err)
      setError('Ошибка обновления пользователя: ' + (err.response?.data?.error || err.message))
    }
  }

  const deleteUser = async (userId) => {
    if (!window.confirm('Вы уверены, что хотите удалить пользователя?')) {
      return
    }

    try {
      setError('')
      console.log(`🔄 Deleting user ${userId}...`)
      await adminAPI.deleteUser(userId)
      console.log('✅ User deleted successfully')

      // Reload users
      const response = await adminAPI.getUsers()
      setUsers(response.data)
    } catch (err) {
      console.error('❌ Error deleting user:', err)
      setError('Ошибка удаления пользователя: ' + (err.response?.data?.error || err.message))
    }
  }

  if (loading) return <div className="loading">Загрузка пользователей...</div>

  return (
    <div className="user-management">
      <div className="section-header">
        <h2>Управление пользователями</h2>
        <button
          className="btn primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? '✕ Отмена' : '➕ Добавить пользователя'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      {showForm && (
        <form onSubmit={handleSubmit} className="user-form">
          <h3>Добавить нового пользователя</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Логин:</label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
                autoComplete="new-username"
              />
            </div>
            <div className="form-group">
              <label>Email:</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                autoComplete="email"
              />
            </div>
          </div>
          <div className="form-group">
            <label>Пароль:</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              autoComplete="new-password"
            />
          </div>
          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
              />
              Активный пользователь
            </label>
          </div>
          <button type="submit" className="btn primary">
            Создать пользователя
          </button>
        </form>
      )}

      <div className="users-table-container">
        <table className="users-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Логин</th>
              <th>Email</th>
              <th>Статус</th>
              <th>Дата регистрации</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {users.map(userItem => (
              <tr key={userItem.id}>
                <td>{userItem.id}</td>
                <td>{userItem.username}</td>
                <td>{userItem.email}</td>
                <td>
                  <span className={`status-badge ${userItem.is_active ? 'active' : 'inactive'}`}>
                    {userItem.is_active ? 'Активен' : 'Неактивен'}
                  </span>
                </td>
                <td>{new Date(userItem.date_joined).toLocaleDateString('ru-RU')}</td>
                <td className="actions">
                  <button
                    className={`btn small ${userItem.is_active ? 'secondary' : 'primary'}`}
                    onClick={() => toggleUserStatus(userItem.id, userItem.is_active)}
                  >
                    {userItem.is_active ? 'Деактивировать' : 'Активировать'}
                  </button>
                  <button
                    className="btn small danger"
                    onClick={() => deleteUser(userItem.id)}
                    disabled={userItem.id === user?.id} // Нельзя удалить себя
                  >
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && !loading && (
          <div className="no-data">Пользователи не найдены</div>
        )}
      </div>
    </div>
  )
}

export default UserManagement