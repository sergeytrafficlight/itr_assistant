import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'
import { useNavigate } from 'react-router-dom'
import './AnalyticsPage.css'

const AnalyticsPage = () => {
  const [advancedData, setAdvancedData] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [performance, setPerformance] = useState({})
  const [categories, setCategories] = useState([])
  const [filters, setFilters] = useState({
    date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    date_to: new Date().toISOString().split('T')[0],
    category: '',
    offer_id: '',
    operator_name: '',
    aff_id: '',
    advertiser: '',
    output: 'Все',
    group_rows: 'Нет'
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const gridRef = useRef()
  const cancelToken = useRef(null)
  const firstRender = useRef(true)
  const filterDebounce = useRef(null)
  const navigate = useNavigate()

  const loadCategories = async () => {
    try {
      const res = await axios.get('/api/legacy/filter-params/')
      const cats = res.data.available_filters?.categories || []
      setCategories(cats)
    } catch (err) {
      console.error('Ошибка загрузки категорий:', err)
    }
  }

  const loadAdvancedAnalysis = useCallback(async () => {
    if (cancelToken.current) cancelToken.current.cancel('Отмена предыдущего запроса')
    cancelToken.current = axios.CancelToken.source()

    setLoading(true)
    setError('')

    try {
      const res = await axios.post('/api/kpi/advanced_analysis/', filters, { cancelToken: cancelToken.current.token })
      if (res.data.success) {
        setAdvancedData(res.data.data || [])
        setRecommendations(res.data.recommendations || [])
        setPerformance(res.data.performance || {})

        if (res.data.groups && gridRef.current?.api) {
          setTimeout(() => {
            res.data.groups.forEach(g => {
              for (let i = g.start; i <= g.end; i++) {
                const node = gridRef.current.api.getRowNode(i.toString())
                if (node) node.setExpanded(true)
              }
            })
          }, 100)
        }
      } else {
        setError(res.data.error || 'Ошибка анализа')
      }
    } catch (err) {
      if (!axios.isCancel(err)) {
        setError(err.response?.data?.error || 'Сервер недоступен')
        console.error('Ошибка запроса:', err)
      }
    } finally {
      setLoading(false)
    }
  }, [filters])

  const getRowData = useCallback(() => {
    if (!advancedData.length) return []
    const rows = []
    let rowId = 0

    advancedData.forEach(cat => {
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
      })

      cat.offers?.forEach(offer => {
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
        })
      })

      cat.operators?.forEach(op => {
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
        })
      })

      cat.affiliates?.forEach(aff => {
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
        })
      })
    })

    return rows
  }, [advancedData])

  const columnDefs = [
    { headerName: "Тип", field: "type", rowGroup: filters.group_rows === 'Да', hide: true },
    { headerName: "Описание", field: "description", pinned: 'left', width: 220 },
    { headerName: "Звонки", field: "calls_effective", type: 'numericColumn', width: 110 },
    { headerName: "Лиды", field: "leads_raw", type: 'numericColumn', width: 110 },
    { headerName: "Продажи", field: "leads_effective", type: 'numericColumn', width: 110 },
    {
      headerName: "% Эфф.",
      field: "effective_percent",
      type: 'numericColumn',
      width: 100,
      valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%',
      cellStyle: p => ({
        color: p.value > 20 ? '#10b981' : p.value > 10 ? '#f59e0b' : '#ef4444',
        fontWeight: 'bold'
      })
    },
    { headerName: "Эфф. факт", field: "effective_rate", type: 'numericColumn', width: 100, valueFormatter: p => p.value?.toFixed(2) || '0.00' },
    { headerName: "Эфф. план", field: "expecting_rate", type: 'numericColumn', width: 100, valueFormatter: p => p.value?.toFixed(2) || '-' },
    { headerName: "Без треша", field: "leads_non_trash", type: 'numericColumn', width: 120 },
    { headerName: "Аппрувы", field: "leads_approved", type: 'numericColumn', width: 110 },
    { headerName: "% Аппрув", field: "approve_percent_fact", type: 'numericColumn', width: 120, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%' },
    { headerName: "План аппрув", field: "approve_rate_plan", type: 'numericColumn', width: 120, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '-' },
    { headerName: "Выкупы", field: "leads_buyout", type: 'numericColumn', width: 110 },
    { headerName: "% Выкуп", field: "buyout_percent_fact", type: 'numericColumn', width: 120, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%' },
    { headerName: "% Треш", field: "trash_percent", type: 'numericColumn', width: 100, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%' },
    { headerName: "% Аппрув от сырых", field: "raw_to_approve_percent", type: 'numericColumn', width: 140, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%' },
    { headerName: "% Выкуп от сырых", field: "raw_to_buyout_percent", type: 'numericColumn', width: 140, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%' },
    { headerName: "% Выкуп от нетреша", field: "non_trash_to_buyout_percent", type: 'numericColumn', width: 150, valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%' },
  ]

  const exportToCSV = () => {
    if (gridRef.current?.api) {
      gridRef.current.api.exportDataAsCsv({
        fileName: `kpi_${filters.date_from}_to_${filters.date_to}`
      })
    }
  }

  const resetFilters = () => {
    setFilters({
      date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      date_to: new Date().toISOString().split('T')[0],
      category: '',
      offer_id: '',
      operator_name: '',
      aff_id: '',
      advertiser: '',
      output: 'Все',
      group_rows: 'Нет'
    })
  }

  useEffect(() => {
    const init = async () => {
      await loadCategories()
      await loadAdvancedAnalysis()
    }
    init()
  }, [loadAdvancedAnalysis])

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    if (filterDebounce.current) clearTimeout(filterDebounce.current)
    filterDebounce.current = setTimeout(() => {
      loadAdvancedAnalysis()
    }, 500)

    return () => clearTimeout(filterDebounce.current)
  }, [filters, loadAdvancedAnalysis])

  return (
    <div className="analytics-page">
      <header className="analytics-header">
        <h1>Расширенная аналитика KPI</h1>
        {performance && (
          <div className="performance-info">
            <strong>Производительность:</strong> {performance.total_seconds}с |
            Лидов: {performance.leads_count} |
            Звонков: {performance.calls_count}
          </div>
        )}
      </header>

      <div className="filters-section">
        <h3>Фильтры</h3>
        <div className="filter-row">
          <div className="filter-group">
            <label>Дата с:</label>
            <input type="date" value={filters.date_from} onChange={e => setFilters({...filters, date_from: e.target.value})} />
          </div>
          <div className="filter-group">
            <label>Дата по:</label>
            <input type="date" value={filters.date_to} onChange={e => setFilters({...filters, date_to: e.target.value})} />
          </div>
          <div className="filter-group">
            <label>Категория:</label>
            <select value={filters.category} onChange={e => setFilters({...filters, category: e.target.value})}>
              <option value="">Все категории</option>
              {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
            </select>
          </div>
          <div className="filter-group">
            <label>Вывод:</label>
            <select value={filters.output} onChange={e => setFilters({...filters, output: e.target.value})}>
              <option value="Все">Все</option>
              <option value="Есть активность">Активные</option>
            </select>
          </div>
        </div>
        <div className="filter-row">
          <div className="filter-group">
            <label>Группировка:</label>
            <select value={filters.group_rows} onChange={e => setFilters({...filters, group_rows: e.target.value})}>
              <option value="Нет">Без группировки</option>
              <option value="Да">С группировкой</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Advertiser:</label>
            <input type="text" placeholder="Advertiser" value={filters.advertiser} onChange={e => setFilters({...filters, advertiser: e.target.value.toLowerCase()})} />
          </div>
          <div className="filter-group">
            <label>Оператор:</label>
            <input type="text" placeholder="Оператор" value={filters.operator_name} onChange={e => setFilters({...filters, operator_name: e.target.value.toLowerCase()})} />
          </div>
          <div className="filter-group">
            <label>ID Оффера:</label>
            <input type="text" placeholder="ID Оффера" value={filters.offer_id} onChange={e => setFilters({...filters, offer_id: e.target.value})} />
          </div>
        </div>
        <div className="action-buttons">
          <button onClick={loadAdvancedAnalysis} disabled={loading} className="btn primary">
            {loading ? '🔄 Загрузка...' : '📊 Анализ'}
          </button>
          <button onClick={exportToCSV} className="btn secondary">📥 CSV</button>
          <button onClick={() => navigate('/full-data')} className="btn secondary">
            📋 Полные данные
          </button>
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
          <div className="no-data-message">Нет данных для отображения</div>
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
                if (params.data.type === 'category') return { backgroundColor: '#f0f8ff', fontWeight: 'bold' }
                if (params.data.type === 'offer') return { backgroundColor: '#f8fff8' }
                return null
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default AnalyticsPage