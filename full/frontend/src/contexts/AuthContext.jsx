import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/admin';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAppInitialized, setIsAppInitialized] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('admin_token');

      // Если токена нет — сразу инициализируем приложение (не ждём)
      if (!token) {
        setUser(null);
        setIsLoading(false);
        setIsAppInitialized(true);
        return;
      }

      try {
        console.log('🔄 Checking auth with token...');
        const res = await authAPI.getMe();
        console.log('✅ Auth check successful, user:', res.data);
        setUser(res.data);
      } catch (err) {
        console.warn('❌ Auth check failed:', err);
        // Interceptor должен обработать рефреш/редирект
        setUser(null);
      } finally {
        setIsLoading(false);
        setIsAppInitialized(true);
      }
    };

    checkAuth();
  }, []);

  const login = async (credentials) => {
    try {
      console.log('🔄 Attempting login...');
      const res = await authAPI.login(credentials);

      const { access, refresh } = res.data;

      localStorage.setItem('admin_token', access);
      if (refresh) {
        localStorage.setItem('refresh_token', refresh);
      }

      // Делаем /me, чтобы точно знать, кто мы
      const meRes = await authAPI.getMe();
      setUser(meRes.data);

      console.log('✅ Login successful');
      return { success: true };
    } catch (err) {
      console.error('❌ Login failed:', err);
      return {
        success: false,
        error: err.response?.data?.detail || 'Неверный логин или пароль'
      };
    }
  };

  const logout = () => {
    console.log('🚪 Logging out...');
    localStorage.removeItem('admin_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    // Используем хард-редирект для надежности
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAppInitialized,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);