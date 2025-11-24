import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ children }) => {
  const { user, isLoading, isAppInitialized } = useAuth();

  // Показываем лоадер только во время первоначальной загрузки
  if (isLoading || !isAppInitialized) {
    return (
      <div className="app-loading">
        <div className="loading">Проверка авторизации...</div>
      </div>
    );
  }

  // Если пользователь не авторизован - редирект на логин
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // Если всё ок - рендерим детей
  return children;
};

export default ProtectedRoute;