import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'
import { useNavigate } from 'react-router-dom'
import FormulaEngine from '../utils/FormulaEngine'
import './FullDataPage.css'

const FullDataPage = () => {
  const [structuredData, setStructuredData] = useState([])
  const [rowData, setRowData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({
    date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    date_to: new Date().toISOString().split('T')[0],
    category: '',
    offer_id: '',
    operator_name: '',
    aff_id: '',
    advertiser: '',
    output: 'Все'
  })
  const [categories, setCategories] = useState([])
  const formulaEngine = useRef(new FormulaEngine())
  const gridRef = useRef()
  const navigate = useNavigate()

  // Вспомогательная функция для безопасного деления
  const safeDiv = (a, b) => (b && b !== 0 ? a / b : 0)

  // Загрузка категорий
  const loadCategories = async () => {
    try {
      const res = await axios.get('/api/legacy/filter-params/')
      const cats = res.data.available_filters?.categories || []
      setCategories(cats)
    } catch (err) {
      console.error('Ошибка загрузки категорий:', err)
    }
  }

  // Загрузка структурированных данных
  const loadStructuredData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await axios.post('/api/kpi-analysis/full_structured_data/', filters)
      if (res.data.success) {
        setStructuredData(res.data.data || [])
        // Преобразуем структурированные данные в плоский формат для таблицы
        const flatData = convertToFlatData(res.data.data || [])
        setRowData(flatData)
      } else {
        setError(res.data.error || 'Ошибка загрузки данных')
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Сервер недоступен')
      console.error('Ошибка запроса:', err)
    } finally {
      setLoading(false)
    }
  }, [filters])

  // Преобразование структурированных данных в плоский формат для AG-Grid
  const convertToFlatData = (structuredData) => {
    const flatData = []
    let rowIndex = 0

    structuredData.forEach(category => {
      // Добавляем строку категории
      flatData.push({
        id: rowIndex++,
        level: 0,
        ...createCategoryRow(category)
      })

      // Добавляем офферы
      category.offers?.forEach(offer => {
        flatData.push({
          id: rowIndex++,
          level: 1,
          ...createOfferRow(offer, category)
        })
      })

      // Добавляем операторов
      category.operators?.forEach(operator => {
        flatData.push({
          id: rowIndex++,
          level: 1,
          ...createOperatorRow(operator)
        })
      })

      // Добавляем вебмастеров
      category.affiliates?.forEach(affiliate => {
        flatData.push({
          id: rowIndex++,
          level: 1,
          ...createAffiliateRow(affiliate)
        })
      })
    })

    return flatData
  }

  // Создание строки категории
  const createCategoryRow = (category) => {
    // Вычисляем проценты на клиенте, если их нет в данных
    const approvePercent = category.approve_percent_fact ||
      safeDiv(category.lead_container?.leads_approved_count || 0, category.lead_container?.leads_non_trash_count || 0) * 100

    const buyoutPercent = category.buyout_percent_fact ||
      safeDiv(category.lead_container?.leads_buyout_count || 0, category.lead_container?.leads_approved_count || 0) * 100

    return {
      type: 'Категория',
      description: category.description,

      // Эффективность
      calls_effective: category.kpi_stat?.calls_group_effective_count || 0,
      leads_effective: category.kpi_stat?.leads_effective_count || 0,
      effective_percent: category.kpi_stat?.effective_percent || 0,
      effective_rate_fact: category.kpi_stat?.effective_rate || 0,
      effective_rate_plan: category.kpi_stat?.expecting_effective_rate || 0,
      effective_recommendation: category.recommended_efficiency?.value || null,
      effective_correction_needed: category.kpi_eff_need_correction_str || '',

      // Аппрувы
      leads_non_trash: category.lead_container?.leads_non_trash_count || 0,
      leads_approved: category.lead_container?.leads_approved_count || 0,
      approve_percent_fact: approvePercent,
      approve_percent_plan: category.approve_rate_plan || 0,
      approve_recommendation: category.recommended_approve?.value || null,
      approve_correction_needed: category.kpi_app_need_correction_str || '',

      // Выкупы
      leads_buyout: category.lead_container?.leads_buyout_count || 0,
      buyout_percent: buyoutPercent,
      buyout_percent_fact: buyoutPercent,
      buyout_percent_plan: category.recommended_buyout?.value || null,
      buyout_recommendation: category.recommended_buyout?.value || null,
      buyout_correction_needed: category.kpi_buyout_need_correction_str || '',

      // Сводные рекомендации
      summary_effective_rec: category.recommended_efficiency?.value || null,
      summary_approve_rec: category.recommended_approve?.value || null,
      summary_buyout_rec: category.recommended_buyout?.value || null,
      summary_check_rec: category.recommended_confirmation_price?.value || null,

      // Дополнительные поля
      effective_update_date: category.kpi_current_plan?.operator_efficiency_update_date || '',
      approve_update_date: category.kpi_current_plan?.planned_approve_update_date || '',
      buyout_update_date: category.kpi_current_plan?.planned_buyout_update_date || '',
      plan_type: category.kpi_current_plan?.plan_type || '',

      // Формулы
      formula_efficiency: `=ЭФФЕКТИВНОСТЬ(${category.kpi_stat?.calls_group_effective_count || 0}, ${category.kpi_stat?.leads_effective_count || 0})`,
      formula_approve: `=АППРУВ_ПРОЦЕНТ(${category.lead_container?.leads_approved_count || 0}, ${category.lead_container?.leads_non_trash_count || 0})`,
      formula_buyout: `=ВЫКУП_ПРОЦЕНТ(${category.lead_container?.leads_buyout_count || 0}, ${category.lead_container?.leads_approved_count || 0})`
    }
  }

  // Создание строки оффера
  const createOfferRow = (offer, category) => {
    const kpiPlan = offer.kpi_current_plan || {}

    return {
      type: 'Оффер',
      offer_id: offer.key,
      offer_name: offer.description,
      description: offer.description,
      category: category.description,

      // Эффективность
      calls_effective: offer.kpi_stat?.calls_group_effective_count || 0,
      leads_effective: offer.kpi_stat?.leads_effective_count || 0,
      effective_percent: offer.kpi_stat?.effective_percent || 0,
      effective_rate_fact: offer.kpi_stat?.effective_rate || 0,
      effective_rate_plan: kpiPlan.operator_efficiency || 0,
      effective_recommendation: offer.recommended_efficiency?.value || null,
      effective_correction_needed: offer.kpi_eff_need_correction_str || '',

      // Аппрувы
      leads_non_trash: offer.lead_container?.leads_non_trash_count || 0,
      leads_approved: offer.lead_container?.leads_approved_count || 0,
      approve_percent_fact: calculateApprovePercent(offer),
      approve_percent_plan: kpiPlan.planned_approve || 0,
      approve_recommendation: offer.recommended_approve?.value || null,
      approve_correction_needed: offer.kpi_app_need_correction_str || '',

      // Выкупы
      leads_buyout: offer.lead_container?.leads_buyout_count || 0,
      buyout_percent: calculateBuyoutPercent(offer),
      buyout_percent_fact: calculateBuyoutPercent(offer),
      buyout_percent_plan: kpiPlan.planned_buyout || 0,
      buyout_recommendation: offer.recommended_buyout?.value || null,
      buyout_correction_needed: offer.kpi_buyout_need_correction_str || '',

      // Сводные рекомендации
      summary_effective_rec: offer.recommended_efficiency?.value || null,
      summary_approve_rec: offer.recommended_approve?.value || null,
      summary_buyout_rec: offer.recommended_buyout?.value || null,
      summary_check_rec: offer.recommended_confirmation_price?.value || null,
      summary_effective_corr: offer.kpi_eff_need_correction ? 'Да' : '',
      summary_approve_corr: offer.kpi_app_need_correction ? 'Да' : '',
      summary_buyout_corr: offer.kpi_buyout_need_correction ? 'Да' : '',
      summary_check_corr: offer.kpi_confirmation_price_need_correction ? 'Да' : '',

      // Дополнительные поля
      effective_update_date: kpiPlan.operator_efficiency_update_date || '',
      approve_update_date: kpiPlan.planned_approve_update_date || '',
      buyout_update_date: kpiPlan.planned_buyout_update_date || '',
      plan_type: kpiPlan.plan_type || '',

      // Ссылка
      link: {
        url: `https://admin.crm.itvx.biz/partners/tloffer/${offer.key}/change/`,
        text: offer.key
      },

      // Формулы
      formula_efficiency: `=ЭФФЕКТИВНОСТЬ(${offer.kpi_stat?.calls_group_effective_count || 0}, ${offer.kpi_stat?.leads_effective_count || 0})`,
      formula_approve: `=АППРУВ_ПРОЦЕНТ(${offer.lead_container?.leads_approved_count || 0}, ${offer.lead_container?.leads_non_trash_count || 0})`,
      formula_buyout: `=ВЫКУП_ПРОЦЕНТ(${offer.lead_container?.leads_buyout_count || 0}, ${offer.lead_container?.leads_approved_count || 0})`,
      formula_cr: `=CR(${offer.lead_container?.leads_approved_count || 0}, ${offer.kpi_stat?.calls_group_effective_count || 0})`
    }
  }

  // Создание строки оператора
  const createOperatorRow = (operator) => {
    return {
      type: 'Оператор',
      operator_name: operator.description,
      description: operator.description,

      // Эффективность
      calls_effective: operator.kpi_stat?.calls_group_effective_count || 0,
      leads_effective: operator.kpi_stat?.leads_effective_count || 0,
      effective_percent: operator.kpi_stat?.effective_percent || 0,
      effective_rate_fact: operator.kpi_stat?.effective_rate || 0,

      // Аппрувы
      leads_non_trash: operator.lead_container?.leads_non_trash_count || 0,
      leads_approved: operator.lead_container?.leads_approved_count || 0,
      approve_percent_fact: calculateApprovePercent(operator),

      // Выкупы
      leads_buyout: operator.lead_container?.leads_buyout_count || 0,
      buyout_percent: calculateBuyoutPercent(operator),

      // Формулы
      formula_efficiency: `=ЭФФЕКТИВНОСТЬ(${operator.kpi_stat?.calls_group_effective_count || 0}, ${operator.kpi_stat?.leads_effective_count || 0})`,
      formula_approve: `=АППРУВ_ПРОЦЕНТ(${operator.lead_container?.leads_approved_count || 0}, ${operator.lead_container?.leads_non_trash_count || 0})`,
      formula_buyout: `=ВЫКУП_ПРОЦЕНТ(${operator.lead_container?.leads_buyout_count || 0}, ${operator.lead_container?.leads_approved_count || 0})`
    }
  }

  // Создание строки вебмастера
  const createAffiliateRow = (affiliate) => {
    return {
      type: 'Вебмастер',
      aff_id: affiliate.key,
      description: `Веб #${affiliate.key}`,

      // Эффективность
      calls_effective: affiliate.kpi_stat?.calls_group_effective_count || 0,
      leads_effective: affiliate.kpi_stat?.leads_effective_count || 0,
      effective_percent: affiliate.kpi_stat?.effective_percent || 0,
      effective_rate_fact: affiliate.kpi_stat?.effective_rate || 0,

      // Аппрувы
      leads_non_trash: affiliate.lead_container?.leads_non_trash_count || 0,
      leads_approved: affiliate.lead_container?.leads_approved_count || 0,
      approve_percent_fact: calculateApprovePercent(affiliate),

      // Выкупы
      leads_buyout: affiliate.lead_container?.leads_buyout_count || 0,
      buyout_percent: calculateBuyoutPercent(affiliate),

      // Формулы
      formula_efficiency: `=ЭФФЕКТИВНОСТЬ(${affiliate.kpi_stat?.calls_group_effective_count || 0}, ${affiliate.kpi_stat?.leads_effective_count || 0})`,
      formula_approve: `=АППРУВ_ПРОЦЕНТ(${affiliate.lead_container?.leads_approved_count || 0}, ${affiliate.lead_container?.leads_non_trash_count || 0})`,
      formula_buyout: `=ВЫКУП_ПРОЦЕНТ(${affiliate.lead_container?.leads_buyout_count || 0}, ${affiliate.lead_container?.leads_approved_count || 0})`
    }
  }

  // Вспомогательные функции для расчетов
  const calculateApprovePercent = (item) => {
    const nonTrash = item.lead_container?.leads_non_trash_count || 0
    const approved = item.lead_container?.leads_approved_count || 0
    return safeDiv(approved, nonTrash) * 100
  }

  const calculateBuyoutPercent = (item) => {
    const approved = item.lead_container?.leads_approved_count || 0
    const buyout = item.lead_container?.leads_buyout_count || 0
    return safeDiv(buyout, approved) * 100
  }

  // Колонки для всех данных
  const columnDefs = [
    // Блок 1: Основная информация
    {
      headerName: "Тип данных",
      field: "type",
      width: 120,
      pinned: 'left',
      cellStyle: params => {
        const type = params.value;
        if (type === 'Категория') return { backgroundColor: '#e3f2fd', fontWeight: 'bold' }
        if (type === 'Оффер') return { backgroundColor: '#f3e5f5' }
        if (type === 'Оператор') return { backgroundColor: '#e8f5e8' }
        if (type === 'Вебмастер') return { backgroundColor: '#fff3e0' }
        return null
      }
    },
    { headerName: "ID Оффер", field: "offer_id", width: 100, pinned: 'left' },
    { headerName: "Оффер", field: "offer_name", width: 200, pinned: 'left' },
    { headerName: "ID Вебмастер", field: "aff_id", width: 120 },
    { headerName: "Оператор", field: "operator_name", width: 150 },
    { headerName: "Категория", field: "category", width: 150 },

    // Блок 2: Эффективность
    {
      headerName: "Ко-во звонков (эфф)",
      field: "calls_effective",
      width: 140,
      type: 'numericColumn'
    },
    {
      headerName: "Ко-во продаж (эфф)",
      field: "leads_effective",
      width: 140,
      type: 'numericColumn'
    },
    {
      headerName: "% эффективности",
      field: "effective_percent",
      width: 130,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%',
      cellStyle: params => ({
        color: params.value > 20 ? '#10b981' : params.value > 10 ? '#f59e0b' : '#ef4444'
      })
    },
    { headerName: "", field: "blank1", width: 50 },

    // Блок 3: Эффективность план/факт
    {
      headerName: "Эфф. факт",
      field: "effective_rate_fact",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(2) || '0.00'
    },
    {
      headerName: "Эфф. план",
      field: "effective_rate_plan",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(2) || '-'
    },
    { headerName: "Дата обновления", field: "effective_update_date", width: 120 },
    { headerName: "Тип Плана", field: "plan_type", width: 100 },
    {
      headerName: "Эфф. рекоммендация",
      field: "effective_recommendation",
      width: 140,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(2) || '-'
    },
    {
      headerName: "Требуется коррекция",
      field: "effective_correction_needed",
      width: 140,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },
    { headerName: "", field: "blank2", width: 50 },

    // Блок 4: Аппрувы
    {
      headerName: "Ко-во лидов (без треша)",
      field: "leads_non_trash",
      width: 160,
      type: 'numericColumn'
    },
    {
      headerName: "Ко-во аппрувов",
      field: "leads_approved",
      width: 130,
      type: 'numericColumn'
    },
    {
      headerName: "% аппрува факт",
      field: "approve_percent_fact",
      width: 130,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "% аппрува план",
      field: "approve_percent_plan",
      width: 130,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '-'
    },
    {
      headerName: "% аппрува рекоммендация",
      field: "approve_recommendation",
      width: 160,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '-'
    },
    { headerName: "Дата обновления аппрув", field: "approve_update_date", width: 140 },
    {
      headerName: "Требуется коррекция аппрув",
      field: "approve_correction_needed",
      width: 180,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },
    { headerName: "", field: "blank3", width: 50 },

    // Блок 5: Выкупы
    {
      headerName: "% выкупа",
      field: "buyout_percent",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "Ко-во выкупов",
      field: "leads_buyout",
      width: 120,
      type: 'numericColumn'
    },
    {
      headerName: "% выкупа факт",
      field: "buyout_percent_fact",
      width: 120,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "% выкупа план",
      field: "buyout_percent_plan",
      width: 120,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '-'
    },
    {
      headerName: "% выкупа рекоммендация",
      field: "buyout_recommendation",
      width: 150,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '-'
    },
    { headerName: "Дата обновления выкупа", field: "buyout_update_date", width: 140 },
    {
      headerName: "Требуется коррекция выкупа",
      field: "buyout_correction_needed",
      width: 180,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },

    // Блок 6: Сводные рекомендации
    {
      headerName: "Эфф. Рек.",
      field: "summary_effective_rec",
      width: 100,
      type: 'numericColumn'
    },
    {
      headerName: "Коррекция?",
      field: "summary_effective_corr",
      width: 100,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },
    {
      headerName: "Апп. Рек.",
      field: "summary_approve_rec",
      width: 100,
      type: 'numericColumn'
    },
    {
      headerName: "Коррекция?",
      field: "summary_approve_corr",
      width: 100,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },
    {
      headerName: "Чек Рек.",
      field: "summary_check_rec",
      width: 100,
      type: 'numericColumn'
    },
    {
      headerName: "Коррекция?",
      field: "summary_check_corr",
      width: 100,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },
    {
      headerName: "Выкуп. Рек.",
      field: "summary_buyout_rec",
      width: 100,
      type: 'numericColumn'
    },
    {
      headerName: "Коррекция?",
      field: "summary_buyout_corr",
      width: 100,
      cellStyle: params => params.value ? { color: '#ef4444', fontWeight: 'bold' } : null
    },

    // Блок 7: Формулы
    {
      headerName: "Формула эфф.",
      field: "formula_efficiency",
      width: 200,
      tooltipField: "formula_efficiency"
    },
    {
      headerName: "Формула аппрув",
      field: "formula_approve",
      width: 200,
      tooltipField: "formula_approve"
    },
    {
      headerName: "Формула выкуп",
      field: "formula_buyout",
      width: 200,
      tooltipField: "formula_buyout"
    },

    // Блок 8: Ссылки
    {
      headerName: "Ссылка",
      field: "link",
      width: 120,
      cellRenderer: params => {
        if (!params.value) return null
        return (
          <a
            href={params.value.url}
            target="_blank"
            rel="noopener noreferrer"
            className="offer-link"
          >
            {params.value.text}
          </a>
        )
      }
    }
  ]

  const defaultColDef = {
    resizable: true,
    sortable: true,
    filter: true,
    wrapText: true,
    autoHeight: true,
  }

  useEffect(() => {
    loadCategories()
  }, [])

  useEffect(() => {
    loadStructuredData()
  }, [loadStructuredData])

  const exportToCSV = () => {
    if (gridRef.current?.api) {
      gridRef.current.api.exportDataAsCsv({
        fileName: `full_kpi_data_${filters.date_from}_to_${filters.date_to}`
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
      output: 'Все'
    })
  }

  return (
    <div className="full-data-page">
      <header className="full-data-header">
        <div className="header-top">
          <button onClick={() => navigate('/analytics')} className="btn back-btn">
            ← Назад к аналитике
          </button>
          <h1>Полные данные KPI с формулами</h1>
          <button onClick={exportToCSV} className="btn primary">
            Экспорт в CSV
          </button>
        </div>
      </header>

      <div className="filters-section">
        <h3>Фильтры</h3>
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
            <label>Категория:</label>
            <select
              value={filters.category}
              onChange={e => setFilters({...filters, category: e.target.value})}
            >
              <option value="">Все категории</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="action-buttons">
          <button onClick={loadStructuredData} disabled={loading} className="btn primary">
            {loading ? 'Загрузка...' : 'Обновить'}
          </button>
          <button onClick={resetFilters} className="btn secondary">Сброс</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="table-section">
        <div className="table-header">
          <h3>Полные данные KPI ({rowData.length} строк)</h3>
          <div className="table-info">
            Прокрутите горизонтально для просмотра всех колонок • Цветовые коды:
            <span className="color-code category">Категория</span>
            <span className="color-code offer">Оффер</span>
            <span className="color-code operator">Оператор</span>
            <span className="color-code affiliate">Вебмастер</span>
          </div>
        </div>

        {loading ? (
          <div className="loading-indicator">Загрузка структурированных данных...</div>
        ) : rowData.length === 0 ? (
          <div className="no-data-message">Нет данных</div>
        ) : (
          <div className="ag-theme-quartz full-data-grid" style={{ height: 800, width: '100%' }}>
            <AgGridReact
              ref={gridRef}
              rowData={rowData}
              columnDefs={columnDefs}
              defaultColDef={defaultColDef}
              enableRangeSelection={true}
              enableFillHandle={true}
              animateRows={true}
              pagination={true}
              paginationPageSize={100}
              paginationPageSizeSelector={[50, 100, 200, 500]}
              suppressRowClickSelection={true}
              rowSelection="multiple"
              getRowStyle={params => {
                if (params.data?.type === 'Категория') return { backgroundColor: '#e3f2fd' }
                if (params.data?.type === 'Оффер') return { backgroundColor: '#f3e5f5' }
                if (params.data?.type === 'Оператор') return { backgroundColor: '#e8f5e8' }
                if (params.data?.type === 'Вебмастер') return { backgroundColor: '#fff3e0' }
                return null
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default FullDataPage