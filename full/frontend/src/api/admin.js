import axios from 'axios';

const API_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ==================== НЕУБИВАЕМЫЙ INTERCEPTOR ====================
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    error ? prom.reject(error) : prom.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  console.log('🚀 Making request to:', config.url, 'with token:', !!token);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    console.log('✅ Response received from:', response.config.url);
    return response;
  },
  async (error) => {
    console.log('❌ Error from:', error.config?.url, 'Status:', error.response?.status);
    const originalRequest = error.config;

    // Если это запрос /me и 401 - сразу на логин
    if (error.response?.status === 401 && originalRequest.url?.includes('/api/admin/auth/me/')) {
      localStorage.removeItem('admin_token');
      localStorage.removeItem('refresh_token');
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Если уже рефрешим — ставим в очередь
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');

        // ИСПРАВЛЕННЫЙ URL - проверьте правильность endpoint
        const refreshResponse = await axios.post(`${API_URL}/api/auth/refresh/`, {
          refresh: refreshToken,
        });

        const { access, refresh: newRefresh } = refreshResponse.data;

        localStorage.setItem('admin_token', access);
        if (newRefresh) localStorage.setItem('refresh_token', newRefresh);

        processQueue(null, access);
        originalRequest.headers.Authorization = `Bearer ${access}`;

        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('admin_token');
        localStorage.removeItem('refresh_token');
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ==================== API ОБЪЕКТЫ ====================

export const authAPI = {
  login: (credentials) => api.post('/api/auth/login/', credentials),
  getMe: () => api.get('/api/admin/auth/me/'),
};

export const adminAPI = {
  getUsers: () => api.get('/api/admin/users/'),
  createUser: (userData) => api.post('/api/admin/users/', userData),
  updateUser: (id, userData) => api.patch(`/api/admin/users/${id}/`, userData),
  deleteUser: (id) => api.delete(`/api/admin/users/${id}/`),
  getStats: () => api.get('/api/admin/stats/'),
};

export const kpiAPI = {
  advancedAnalysis: (data) => api.post('/api/kpi/advanced_analysis/', data),
  advancedAnalysisAlt: (data) => api.post('/api/kpi-analysis/advanced_analysis/', data),
  fullStructuredData: (data) => api.post('/api/kpi-analysis/full_structured_data/', data),
  fullDataTable: (data) => api.post('/api/kpi/full_data_table/', data),
};

export const legacyAPI = {
  getFilterParams: () => api.get('/api/legacy/filter-params/'),
  getCategories: () => api.get('/api/categories/'),
  getAdvertisers: () => api.get('/api/advertisers/'),
  kpiAnalysis: (filters) => api.post('/api/legacy/kpi-analysis/', filters),
};

export const spreadsheetAPI = {
  getSpreadsheets: () => api.get('/api/spreadsheets/'),
  getSheets: () => api.get('/api/sheets/'),
  getCells: () => api.get('/api/cells/'),
  getFormulas: () => api.get('/api/formulas/'),
  getPivotTables: () => api.get('/api/pivot-tables/'),
  getCategories: () => api.get('/api/categories/'),
  getOffers: () => api.get('/api/offers/'),
  getOperators: () => api.get('/api/operators/'),
  getAffiliates: () => api.get('/api/affiliates/'),
  getKpiData: () => api.get('/api/kpi-data/'),
};

export default api;