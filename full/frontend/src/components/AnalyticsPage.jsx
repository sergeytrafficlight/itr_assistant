import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'
import './AnalyticsPage.css'

const AnalyticsPage = () => {
  const [advancedData, setAdvancedData] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [globalStats, setGlobalStats] = useState({})
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

  // === ЗАГРУЗКА КАТЕГОРИЙ ===
  const loadCategories = async () => {
    try {
      const res = await axios.get('/api/legacy/filter-params/')
      const cats = res.data.available_filters?.categories || []
      setCategories(cats)
    } catch (err) {
      console.error('Ошибка загрузки категорий:', err)
    }
  }

  // === АНАЛИЗ ===
  const loadAdvancedAnalysis = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await axios.post('/api/kpi/advanced_analysis/', filters)
      if (res.data.success) {
        setAdvancedData(res.data.data || [])
        setRecommendations(res.data.recommendations || [])
        setGlobalStats(res.data.global_stats || {})

        // ГРУППИРОВКА
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
      setError(err.response?.data?.error || 'Сервер недоступен')
      console.error('Ошибка запроса:', err)
    } finally {
      setLoading(false)
    }
  }

  // === ДАННЫЕ ДЛЯ ГРИДА ===
  const getRowData = () => {
    if (!advancedData.length) return []
    const rows = []
    let rowId = 0

    advancedData.forEach(cat => {
      // КАТЕГОРИЯ
      rows.push({
        id: rowId++,
        type: 'category',
        description: cat.description,
        calls_effective: cat.kpi_stat?.calls_group_effective_count || 0,
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
      })

      // ОФФЕРЫ
      cat.offers?.forEach(offer => {
        rows.push({
          id: rowId++,
          type: 'offer',
          description: offer.description,
          offer_name: offer.description,
          offer_id: offer.key,
          calls_effective: offer.kpi_stat?.calls_group_effective_count || 0,
          leads_effective: offer.kpi_stat?.leads_effective_count || 0,
          effective_percent: offer.kpi_stat?.effective_percent || 0,
          effective_rate: offer.kpi_stat?.effective_rate || 0,
          leads_non_trash: offer.lead_container?.leads_non_trash_count || 0,
          leads_approved: offer.lead_container?.leads_approved_count || 0,
          approve_percent_fact: offer.approve_percent_fact || 0,
          leads_buyout: offer.lead_container?.leads_buyout_count || 0,
          buyout_percent_fact: offer.buyout_percent_fact || 0,
        })
      })

      // ОПЕРАТОРЫ
      cat.operators?.forEach(op => {
        rows.push({
          id: rowId++,
          type: 'operator',
          description: op.key,
          operator_name: op.key,
          calls_effective: op.kpi_stat?.calls_group_effective_count || 0,
          leads_effective: op.kpi_stat?.leads_effective_count || 0,
          effective_percent: op.kpi_stat?.effective_percent || 0,
          effective_rate: op.kpi_stat?.effective_rate || 0,
        })
      })

      // АФФИЛИАТЫ
      cat.affiliates?.forEach(aff => {
        rows.push({
          id: rowId++,
          type: 'affiliate',
          description: `Веб #${aff.key}`,
          aff_id: aff.key,
          calls_effective: aff.kpi_stat?.calls_group_effective_count || 0,
          leads_effective: aff.kpi_stat?.leads_effective_count || 0,
          effective_percent: aff.kpi_stat?.effective_percent || 0,
          effective_rate: aff.kpi_stat?.effective_rate || 0,
        })
      })
    })

    return rows
  }

  // === КОЛОНКИ ===
  const columnDefs = [
    { headerName: "Тип", field: "type", rowGroup: filters.group_rows === 'Да', hide: true },
    { headerName: "Описание", field: "description", pinned: 'left', width: 220 },
    { headerName: "Звонки", field: "calls_effective", type: 'numericColumn', width: 110 },
    { headerName: "Лиды", field: "leads_effective", type: 'numericColumn', width: 110 },
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

  // === ЗАГРУЗКА ПРИ МОНТИРОВАНИИ ===
  useEffect(() => {
    const init = async () => {
      await loadCategories()
      await loadAdvancedAnalysis()
    }
    init()
  }, [])

  // === ПЕРЕЗАГРУЗКА ПРИ ИЗМЕНЕНИИ ФИЛЬТРОВ ===
  useEffect(() => {
    const timeout = setTimeout(loadAdvancedAnalysis, 500)
    return () => clearTimeout(timeout)
  }, [filters])

  return (
    <div className="analytics-page">
      <header className="analytics-header">
        <h1>Расширенная аналитика KPI</h1>
        {globalStats.actual_data_overview && (
          <div className="period-info">
            Период: {globalStats.actual_data_overview.period_analyzed} |
            Лиды: {globalStats.actual_data_overview.leads_analyzed} |
            Звонки: {globalStats.actual_data_overview.calls_analyzed} |
            Контейнеры: {globalStats.actual_data_overview.containers_analyzed}
          </div>
        )}
        {/* ДОБАВЛЕНО: ПРОИЗВОДИТЕЛЬНОСТЬ */}
        {globalStats.performance && (
          <div className="performance-info" style={{ marginTop: '8px', fontSize: '0.9em', color: '#555' }}>
            <strong>Производительность:</strong> {globalStats.performance.total_seconds}с |
            Лиды/с: {globalStats.performance.leads_per_second} |
            Звонки/с: {globalStats.performance.calls_per_second} |
            <em>{globalStats.performance.optimization}</em>
          </div>
        )}
      </header>

      <div className="filters-section">
        <h3>Фильтры</h3>
        <div className="filter-row">
          <input type="date" value={filters.date_from} onChange={e => setFilters({...filters, date_from: e.target.value})} />
          <input type="date" value={filters.date_to} onChange={e => setFilters({...filters, date_to: e.target.value})} />
          <select value={filters.category} onChange={e => setFilters({...filters, category: e.target.value})}>
            <option value="">Все категории</option>
            {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
          </select>
          <select value={filters.output} onChange={e => setFilters({...filters, output: e.target.value})}>
            <option value="Все">Все</option>
            <option value="Есть активность">Активные</option>
          </select>
        </div>
        <div className="filter-row">
          <select value={filters.group_rows} onChange={e => setFilters({...filters, group_rows: e.target.value})}>
            <option value="Нет">Без группировки</option>
            <option value="Да">С группировкой</option>
          </select>
          <input type="text" placeholder="Advertiser" value={filters.advertiser} onChange={e => setFilters({...filters, advertiser: e.target.value.toLowerCase()})} />
          <input type="text" placeholder="Оператор" value={filters.operator_name} onChange={e => setFilters({...filters, operator_name: e.target.value.toLowerCase()})} />
          <input type="text" placeholder="ID Оффера" value={filters.offer_id} onChange={e => setFilters({...filters, offer_id: e.target.value})} />
        </div>
        <div className="action-buttons">
          <button onClick={loadAdvancedAnalysis} disabled={loading} className="btn primary">
            {loading ? 'Загрузка...' : 'Анализ'}
          </button>
          <button onClick={exportToCSV} className="btn secondary">CSV</button>
          <button onClick={resetFilters} className="btn secondary">Сброс</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {recommendations.length > 0 && (
        <div className="recommendations-section">
          <h3>Рекомендации</h3>
          <div className="recommendations-grid">
            {recommendations.map((rec, i) => (
              <div key={i} className="recommendation-card">
                <strong>{rec.category}</strong>: {rec.type === 'efficiency' ? 'Эфф.' : 'Аппрув'} {rec.current}% → <span style={{color: 'green'}}>{rec.recommended}%</span>
                {rec.comment && <em> ({rec.comment})</em>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="table-section">
        <h3>Данные ({getRowData().length} строк)</h3>
        {loading ? (
          <div className="loading-indicator">Загрузка...</div>
        ) : getRowData().length === 0 ? (
          <div className="no-data-message">Нет данных</div>
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