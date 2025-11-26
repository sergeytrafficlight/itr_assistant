import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import Select from 'react-select';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';
import { useNavigate } from 'react-router-dom';
import api, { legacyAPI, kpiAPI, authAPI } from '../api/admin';
import './AnalyticsPage.css';

const AnalyticsPage = () => {
  const [advancedData, setAdvancedData] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [performance, setPerformance] = useState({});
  const [categories, setCategories] = useState([]);
  const [advertisers, setAdvertisers] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [user, setUser] = useState(null);

  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedAdvertisers, setSelectedAdvertisers] = useState([]);

  const [filters, setFilters] = useState({
    date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    date_to: new Date().toISOString().split('T')[0],
    output: 'Все',
    group_rows: 'Нет'
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const gridRef = useRef();
  const abortControllerRef = useRef(null);
  const navigate = useNavigate();

  // Проверка прав администратора
  const checkAdminRights = async () => {
    try {
      const res = await authAPI.getMe();
      if (res.data && res.data.is_staff) {
        setIsAdmin(true);
        setUser(res.data);
      }
    } catch (err) {
      console.log('Пользователь не является администратором');
      setIsAdmin(false);
    }
  };

  // Загрузка всех справочников (только категории и advertisers)
  const loadAllDictionaries = async () => {
    try {
      const [categoriesRes, advertisersRes] = await Promise.all([
        legacyAPI.getCategories(),
        legacyAPI.getAdvertisers()
      ]);

      setCategories(categoriesRes.data || []);
      setAdvertisers(advertisersRes.data || []);

    } catch (err) {
      console.error('Ошибка загрузки справочников:', err);
    }
  };

  // ОСНОВНАЯ ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ - ВЫЗЫВАЕТСЯ ТОЛЬКО ПО КНОПКЕ
  const loadAdvancedAnalysis = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort('Отмена предыдущего запроса');
    }

    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError('');

    try {
      // ФОРМИРОВАНИЕ ФИЛЬТРОВ
      const requestFilters = {
        date_from: filters.date_from,
        date_to: filters.date_to,
        category: selectedCategories.length > 0 ? selectedCategories.map(cat => cat.value) : [],
        advertiser: selectedAdvertisers.length > 0 ? selectedAdvertisers.map(adv => adv.value) : [],
        output: filters.output,
        group_rows: filters.group_rows
      };

      console.log('Отправляемые фильтры:', requestFilters);

      const res = await kpiAPI.advancedAnalysis(requestFilters, {
        signal: abortControllerRef.current.signal
      });

      if (res.data.success) {
        setAdvancedData(res.data.data || []);
        setRecommendations(res.data.recommendations || []);
        setPerformance(res.data.performance || {});

        if (res.data.groups && gridRef.current?.api) {
          setTimeout(() => {
            res.data.groups.forEach(g => {
              for (let i = g.start; i <= g.end; i++) {
                const node = gridRef.current.api.getRowNode(i.toString());
                if (node) node.setExpanded(true);
              }
            });
          }, 100);
        }
      } else {
        setError(res.data.error || 'Ошибка анализа');
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.response?.data?.error || 'Сервер недоступен');
        console.error('Ошибка запроса:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort('Компонент размонтирован');
      }
    };
  }, []);

  // ИНИЦИАЛИЗАЦИЯ - ТОЛЬКО ЗАГРУЗКА СПРАВОЧНИКОВ, НЕ ДАННЫХ
  useEffect(() => {
    const init = async () => {
      await checkAdminRights();
      await loadAllDictionaries();
      // НЕ ВЫЗЫВАЕМ loadAdvancedAnalysis здесь - данные грузятся только по кнопке
    };
    init();
  }, []);

  // УДАЛЕН useEffect который автоматически запускал запросы при изменении фильтров

  const getRowData = useCallback(() => {
    if (!advancedData.length) return [];
    const rows = [];
    let rowId = 0;

    advancedData.forEach(cat => {
      // ФИЛЬТРАЦИЯ ПО ВЫВОДУ (только фронтендная)
      if (filters.output === 'Есть активность') {
        const hasCalls = cat.kpi_stat?.calls_group_effective_count > 0;
        const hasLeads = cat.lead_container?.leads_non_trash_count > 0;
        if (!hasCalls && !hasLeads) return;
      }

      // ФИЛЬТРАЦИЯ ПО КАТЕГОРИЯМ
      if (selectedCategories.length > 0 && !selectedCategories.find(c => c.value === cat.description)) return;

      rows.push({
        id: rowId++,
        type: 'category',
        description: cat.description,
        calls_effective: cat.kpi_stat?.calls_group_effective_count || 0,
        leads_raw: cat.lead_container?.leads_raw_count || 0,
        leads_effective: cat.kpi_stat?.leads_effective_count || 0,
        effective_percent: cat.kpi_stat?.effective_percent || 0,
        effective_rate: cat.kpi_stat?.effective_rate || 0,
        expecting_rate: cat.kpi_stat?.expecting_effective_rate || 0,
        leads_non_trash: cat.lead_container?.leads_non_trash_count || 0,
        leads_approved: cat.lead_container?.leads_approved_count || 0,
        approve_percent_fact: cat.approve_percent_fact || 0,
        approve_rate_plan: cat.approve_rate_plan || 0,
        leads_buyout: cat.lead_container?.leads_buyout_count || 0,
        buyout_percent_fact: cat.buyout_percent_fact || 0,
        trash_percent: cat.trash_percent || 0,
        raw_to_approve_percent: cat.raw_to_approve_percent || 0,
        raw_to_buyout_percent: cat.raw_to_buyout_percent || 0,
        non_trash_to_buyout_percent: cat.non_trash_to_buyout_percent || 0,
      });

      // ДОБАВЛЯЕМ ОФФЕРЫ
      cat.offers?.forEach(offer => {
        if (filters.output === 'Есть активность') {
          const hasCalls = offer.kpi_stat?.calls_group_effective_count > 0;
          const hasLeads = offer.lead_container?.leads_non_trash_count > 0;
          if (!hasCalls && !hasLeads) return;
        }

        rows.push({
          id: rowId++,
          type: 'offer',
          description: offer.description,
          offer_name: offer.description,
          offer_id: offer.key,
          calls_effective: offer.kpi_stat?.calls_group_effective_count || 0,
          leads_raw: offer.lead_container?.leads_raw_count || 0,
          leads_effective: offer.kpi_stat?.leads_effective_count || 0,
          effective_percent: offer.kpi_stat?.effective_percent || 0,
          effective_rate: offer.kpi_stat?.effective_rate || 0,
          leads_non_trash: offer.lead_container?.leads_non_trash_count || 0,
          leads_approved: offer.lead_container?.leads_approved_count || 0,
          approve_percent_fact: offer.approve_percent_fact || 0,
          leads_buyout: offer.lead_container?.leads_buyout_count || 0,
          buyout_percent_fact: offer.buyout_percent_fact || 0,
          trash_percent: offer.trash_percent || 0,
          raw_to_approve_percent: offer.raw_to_approve_percent || 0,
          raw_to_buyout_percent: offer.raw_to_buyout_percent || 0,
          non_trash_to_buyout_percent: offer.non_trash_to_buyout_percent || 0,
        });
      });

      // ДОБАВЛЯЕМ ОПЕРАТОРОВ
      cat.operators?.forEach(op => {
        if (filters.output === 'Есть активность') {
          const hasCalls = op.kpi_stat?.calls_group_effective_count > 0;
          const hasLeads = op.lead_container?.leads_non_trash_count > 0;
          if (!hasCalls && !hasLeads) return;
        }

        rows.push({
          id: rowId++,
          type: 'operator',
          description: op.key,
          operator_name: op.key,
          calls_effective: op.kpi_stat?.calls_group_effective_count || 0,
          leads_raw: op.lead_container?.leads_raw_count || 0,
          leads_effective: op.kpi_stat?.leads_effective_count || 0,
          effective_percent: op.kpi_stat?.effective_percent || 0,
          effective_rate: op.kpi_stat?.effective_rate || 0,
          leads_non_trash: op.lead_container?.leads_non_trash_count || 0,
          leads_approved: op.lead_container?.leads_approved_count || 0,
          approve_percent_fact: op.approve_percent_fact || 0,
          leads_buyout: op.lead_container?.leads_buyout_count || 0,
          buyout_percent_fact: op.buyout_percent_fact || 0,
          trash_percent: op.trash_percent || 0,
          raw_to_approve_percent: op.raw_to_approve_percent || 0,
          raw_to_buyout_percent: op.raw_to_buyout_percent || 0,
          non_trash_to_buyout_percent: op.non_trash_to_buyout_percent || 0,
        });
      });

      // ДОБАВЛЯЕМ АФФИЛИАТОВ
      cat.affiliates?.forEach(aff => {
        if (filters.output === 'Есть активность') {
          const hasCalls = aff.kpi_stat?.calls_group_effective_count > 0;
          const hasLeads = aff.lead_container?.leads_non_trash_count > 0;
          if (!hasCalls && !hasLeads) return;
        }

        rows.push({
          id: rowId++,
          type: 'affiliate',
          description: `Веб #${aff.key}`,
          aff_id: aff.key,
          calls_effective: aff.kpi_stat?.calls_group_effective_count || 0,
          leads_raw: aff.lead_container?.leads_raw_count || 0,
          leads_effective: aff.kpi_stat?.leads_effective_count || 0,
          effective_percent: aff.kpi_stat?.effective_percent || 0,
          effective_rate: aff.kpi_stat?.effective_rate || 0,
          leads_non_trash: aff.lead_container?.leads_non_trash_count || 0,
          leads_approved: aff.lead_container?.leads_approved_count || 0,
          approve_percent_fact: aff.approve_percent_fact || 0,
          leads_buyout: aff.lead_container?.leads_buyout_count || 0,
          buyout_percent_fact: aff.buyout_percent_fact || 0,
          trash_percent: aff.trash_percent || 0,
          raw_to_approve_percent: aff.raw_to_approve_percent || 0,
          raw_to_buyout_percent: aff.raw_to_buyout_percent || 0,
          non_trash_to_buyout_percent: aff.non_trash_to_buyout_percent || 0,
        });
      });
    });
    return rows;
  }, [advancedData, filters.output, selectedCategories]);

  const columnDefs = [
    { headerName: "Тип", field: "type", rowGroup: filters.group_rows === 'Да', hide: true },
    { headerName: "Описание", field: "description", pinned: 'left', width: 220 },
    { headerName: "Звонки", field: "calls_effective", type: 'numericColumn', width: 110 },
    { headerName: "Лиды", field: "leads_raw", type: 'numericColumn', width: 110 },
    { headerName: "Продажи", field: "leads_effective", type: 'numericColumn', width: 110 },
    { headerName: "% Эфф.", field: "effective_percent", type: 'numericColumn', width: 100,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%',
      cellStyle: p => ({ color: p.value > 20 ? '#10b981' : p.value > 10 ? '#f59e0b' : '#ef4444', fontWeight: 'bold' })
    },
    { headerName: "Эфф. факт", field: "effective_rate", type: 'numericColumn', width: 100,
      valueFormatter: p => p.value?.toFixed(2) || '0.00'
    },
    { headerName: "Эфф. план", field: "expecting_rate", type: 'numericColumn', width: 100,
      valueFormatter: p => p.value?.toFixed(2) || '-'
    },
    { headerName: "Без треша", field: "leads_non_trash", type: 'numericColumn', width: 120 },
    { headerName: "Аппрувы", field: "leads_approved", type: 'numericColumn', width: 110 },
    { headerName: "% Аппрув", field: "approve_percent_fact", type: 'numericColumn', width: 120,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
    },
    { headerName: "План аппрув", field: "approve_rate_plan", type: 'numericColumn', width: 120,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '-'
    },
    { headerName: "Выкупы", field: "leads_buyout", type: 'numericColumn', width: 110 },
    { headerName: "% Выкуп", field: "buyout_percent_fact", type: 'numericColumn', width: 120,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
    },
    { headerName: "% Треш", field: "trash_percent", type: 'numericColumn', width: 100,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
    },
    { headerName: "% Аппрув от сырых", field: "raw_to_approve_percent", type: 'numericColumn', width: 140,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
    },
    { headerName: "% Выкуп от сырых", field: "raw_to_buyout_percent", type: 'numericColumn', width: 140,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
    },
    { headerName: "% Выкуп от нетреша", field: "non_trash_to_buyout_percent", type: 'numericColumn', width: 150,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
    },
  ];

  const exportToCSV = () => {
    if (gridRef.current?.api) {
      gridRef.current.api.exportDataAsCsv({
        fileName: `kpi_${filters.date_from}_to_${filters.date_to}`
      });
    }
  };

  const resetFilters = () => {
    setFilters({
      date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      date_to: new Date().toISOString().split('T')[0],
      output: 'Все',
      group_rows: 'Нет'
    });
    setSelectedCategories([]);
    setSelectedAdvertisers([]);
    // Очищаем данные при сбросе фильтров
    setAdvancedData([]);
    setRecommendations([]);
    setPerformance({});
  };

  const customStyles = {
    control: (base) => ({
      ...base,
      minHeight: '40px',
      border: '1px solid #ddd',
      boxShadow: 'none',
      '&:hover': {
        border: '1px solid #28a745'
      }
    }),
    menu: (base) => ({
      ...base,
      zIndex: 9999
    }),
    multiValue: (base) => ({
      ...base,
      backgroundColor: '#d4edda',
      color: '#155724',
      border: '1px solid #c3e6cb'
    }),
    multiValueLabel: (base) => ({
      ...base,
      color: '#155724',
      fontWeight: '500'
    }),
    multiValueRemove: (base) => ({
      ...base,
      color: '#155724',
      '&:hover': {
        backgroundColor: '#f5c6cb',
        color: '#721c24'
      }
    }),
    option: (base, state) => ({
      ...base,
      backgroundColor: state.isSelected
        ? '#28a745'
        : state.isFocused
          ? '#e8f5e8'
          : base.backgroundColor,
      color: state.isSelected
        ? 'white'
        : state.isFocused
          ? '#155724'
          : base.color,
    }),
    indicatorsContainer: (base) => ({
      ...base,
      color: '#6c757d'
    }),
    indicatorSeparator: (base) => ({
      ...base,
      backgroundColor: '#ddd'
    }),
    dropdownIndicator: (base) => ({
      ...base,
      color: '#6c757d',
      '&:hover': {
        color: '#28a745'
      }
    }),
    clearIndicator: (base) => ({
      ...base,
      color: '#6c757d',
      '&:hover': {
        color: '#dc3545'
      }
    }),
    placeholder: (base) => ({
      ...base,
      color: '#6c757d'
    })
  };

  // Подготовка опций для селектов (только категории и advertisers)
  const categoryOptions = categories.map(cat => ({ value: cat, label: cat }));
  const advertiserOptions = advertisers.map(adv => ({ value: adv, label: adv }));

  return (
    <div className="analytics-page">
      <header className="analytics-header">
        <div className="header-top">
          <h1>Расширенная аналитика KPI</h1>
          <div className="header-actions">
            {isAdmin && (
              <button
                onClick={() => navigate('/admin')}
                className="btn admin-btn"
                title="Админ панель"
              >
                ⚙️ Админка
              </button>
            )}
            {user && (
              <div className="user-info">
                <span className="username">{user.username}</span>
                {user.is_staff && <span className="admin-badge">👑</span>}
              </div>
            )}
          </div>
        </div>
        {performance && Object.keys(performance).length > 0 && (
          <div className="performance-info">
            <strong>Производительность:</strong> {performance.total_seconds}с | Лидов: {performance.leads_count} | Звонков: {performance.calls_count}
          </div>
        )}
      </header>

      <div className="filters-section">
        <h3>Фильтры</h3>

        {/* Первая строка фильтров */}
        <div className="filter-row">
          <div className="filter-group">
            <label>Дата с:</label>
            <input
              type="date"
              value={filters.date_from}
              onChange={e => setFilters({...filters, date_from: e.target.value})}
            />
          </div>
          <div className="filter-group">
            <label>Дата по:</label>
            <input
              type="date"
              value={filters.date_to}
              onChange={e => setFilters({...filters, date_to: e.target.value})}
            />
          </div>
          <div className="filter-group">
            <label>Вывод:</label>
            <select value={filters.output} onChange={e => setFilters({...filters, output: e.target.value})}>
              <option value="Все">Все</option>
              <option value="Есть активность">Активные</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Группировка:</label>
            <select value={filters.group_rows} onChange={e => setFilters({...filters, group_rows: e.target.value})}>
              <option value="Нет">Без группировки</option>
              <option value="Да">С группировкой</option>
            </select>
          </div>
        </div>

        {/* Вторая строка фильтров - только категории и advertisers */}
        <div className="filter-row">
          <div className="filter-group wide">
            <label>Категории:</label>
            <Select
              isMulti
              options={categoryOptions}
              value={selectedCategories}
              onChange={setSelectedCategories}
              placeholder="Выберите категории..."
              styles={customStyles}
              className="react-select-container"
              classNamePrefix="react-select"
            />
          </div>
          <div className="filter-group wide">
            <label>Advertisers:</label>
            <Select
              isMulti
              options={advertiserOptions}
              value={selectedAdvertisers}
              onChange={setSelectedAdvertisers}
              placeholder="Выберите advertisers..."
              styles={customStyles}
              className="react-select-container"
              classNamePrefix="react-select"
            />
          </div>
        </div>

        <div className="action-buttons">
          <button onClick={loadAdvancedAnalysis} disabled={loading} className="btn primary">
            {loading ? '🔄 Загрузка...' : '📊 Анализ'}
          </button>
          <button onClick={exportToCSV} disabled={advancedData.length === 0} className="btn secondary">📥 CSV</button>
          <button onClick={() => navigate('/full-data')} className="btn secondary">📋 Полные данные</button>
          <button onClick={resetFilters} className="btn secondary">🔄 Сброс</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {recommendations.length > 0 && (
        <div className="recommendations-section">
          <h3>💡 Рекомендации</h3>
          <div className="recommendations-grid">
            {recommendations.map((rec, i) => (
              <div key={i} className={`recommendation-card ${rec.priority}`}>
                <div className="rec-header">
                  <span className="rec-icon">{rec.icon}</span>
                  <span className="rec-type">{rec.type}</span>
                  <span className="rec-category">{rec.category}</span>
                </div>
                <div className="rec-values">
                  <span className="current">{rec.current}</span>
                  <span className="arrow">→</span>
                  <span className="recommended">{rec.recommended}</span>
                  <span className="difference">{rec.difference}</span>
                </div>
                {rec.comment && <div className="rec-comment">{rec.comment}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="table-section">
        <h3>📈 Данные ({getRowData().length} строк)</h3>
        {loading ? (
          <div className="loading-indicator">Загрузка данных...</div>
        ) : getRowData().length === 0 ? (
          <div className="no-data-message">
            {advancedData.length === 0 ? 'Нажмите "Анализ" для загрузки данных' : 'Нет данных для отображения'}
          </div>
        ) : (
          <div className="ag-theme-quartz" style={{ height: 600, width: '100%' }}>
            <AgGridReact
              ref={gridRef}
              rowData={getRowData()}
              columnDefs={columnDefs}
              defaultColDef={{ resizable: true, sortable: true, filter: true }}
              groupDisplayType="multipleColumns"
              animateRows={true}
              pagination={true}
              paginationPageSize={50}
              paginationPageSizeSelector={[20, 50, 100]}
              getRowStyle={params => {
                if (params.data.type === 'category') return { backgroundColor: '#f0f8ff', fontWeight: 'bold' };
                if (params.data.type === 'offer') return { backgroundColor: '#f8fff8' };
                return null;
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalyticsPage;