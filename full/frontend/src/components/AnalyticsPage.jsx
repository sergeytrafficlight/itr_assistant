import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'
import './AnalyticsPage.css'

const AnalyticsPage = () => {
  const [advancedData, setAdvancedData] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [summary, setSummary] = useState({})
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
  const [gridApi, setGridApi] = useState(null)
  const debugFirstRow = () => {
    if (advancedData.length > 1) {
      const firstDataRow = advancedData[1] // Первая строка с данными (после заголовков)
      console.log('=== ДЕБАГ ПЕРВОЙ СТРОКИ ДАННЫХ ===')
      console.log('Полная строка:', firstDataRow)
      console.log('Тип данных по колонкам:')
      firstDataRow.forEach((value, index) => {
        console.log(`Колонка ${index}:`, value, 'тип:', typeof value)
      })

      // Проверяем числовые колонки
      const numericColumns = [6, 7, 8, 10, 11, 14, 18, 19, 20, 21, 22, 27, 28, 29, 30, 34, 36, 38, 40]
      console.log('Числовые значения:')
      numericColumns.forEach(col => {
        const value = firstDataRow[col]
        const numValue = parseFloat(value)
        console.log(`Колонка ${col}:`, value, 'число?:', !isNaN(numValue), 'преобразованное:', numValue)
      })

      // Проверяем обработанные данные
      const processedData = getRowData()
      if (processedData.length > 0) {
        console.log('=== ОБРАБОТАННЫЕ ДАННЫХ ===')
        console.log('Первая обработанная строка:', processedData[0])
        console.log('Колонка 6 (звонки):', processedData[0][6], 'тип:', typeof processedData[0][6])
        console.log('Колонка 7 (лиды):', processedData[0][7], 'тип:', typeof processedData[0][7])
      }
    } else {
      console.log('Нет данных для дебага')
    }
  }
  const loadAdvancedAnalysis = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await axios.post('/api/kpi-advanced/advanced_analysis/', {
        params: filters
      })

      console.log('📊 Ответ от сервера advanced_analysis:', res.data)

      if (res.data.success) {
        setAdvancedData(res.data.data || [])
        setRecommendations(res.data.recommendations || [])
        setSummary(res.data.summary || {})

        if (gridApi) {
          setTimeout(() => {
            gridApi.sizeColumnsToFit()
          }, 100)
        }
      } else {
        setError(res.data.error || 'Ошибка при загрузке данных')
      }
    } catch (err) {
      console.error('❌ Ошибка загрузки расширенного анализа:', err)
      setError(err.response?.data?.error || 'Ошибка соединения с сервером')
      setAdvancedData([])
      setRecommendations([])
      setSummary({})
    } finally {
      setLoading(false)
    }
  }

  const loadGoogleSheetsFormat = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await axios.post('/api/kpi-advanced/google_sheets_format/', {
        params: filters
      })

      console.log('📊 Полный ответ Google Sheets:', res.data)

      if (res.data.success) {
        const sheetsData = res.data.data || []
        console.log('📊 Данные в формате Google Sheets:', {
          totalRows: sheetsData.length,
          firstRow: sheetsData[0],
          secondRow: sheetsData[1],
          isArray: Array.isArray(sheetsData[0])
        })

        setAdvancedData(sheetsData)
        setSummary(res.data.metadata || {})
        setRecommendations([])

        if (gridApi) {
          setTimeout(() => {
            gridApi.sizeColumnsToFit()
          }, 100)
        }

        alert(`Данные подготовлены в формате Google Sheets: ${sheetsData.length} строк, ${res.data.metadata?.columns_count || 42} колонок`)
      }
    } catch (err) {
      console.error('❌ Ошибка формата Google Sheets:', err)
      setError(err.response?.data?.error || 'Ошибка загрузки Google Sheets формата')
    } finally {
      setLoading(false)
    }
  }

  const loadComparison = async () => {
    try {
      const res = await axios.get('/api/kpi-advanced/comparison/', {
        params: {
          date_from: filters.date_from,
          date_to: filters.date_to
        }
      })

      console.log('📊 Сравнение анализов:', res.data)

      const comparison = res.data.comparison || {}
      alert(`Сравнение завершено!\n\n` +
        `Разница в записях: ${comparison.records_count_diff || 0}\n` +
        `Разница в эффективности: ${comparison.efficiency_diff?.toFixed(2) || 0}%`
      )
    } catch (err) {
      console.error('❌ Ошибка сравнения:', err)
      alert('Ошибка при сравнении анализов')
    }
  }

  const onGridReady = (params) => {
    setGridApi(params.api)
  }

  const advancedColumnDefs = [
    {
      headerName: "Тип данных",
      field: "type",
      width: 120,
      cellStyle: { fontWeight: 'bold' },
      filter: 'agTextFilter',
      pinned: 'left'
    },
    {
      headerName: "Категория",
      field: "category_name",
      width: 150,
      filter: 'agTextFilter'
    },
    {
      headerName: "ID Оффер",
      field: "offer_id",
      width: 100,
      type: 'numericColumn',
      filter: 'agNumberFilter'
    },
    {
      headerName: "Оффер",
      field: "offer_name",
      width: 200,
      filter: 'agTextFilter'
    },
    {
      headerName: "ID Вебмастер",
      field: "aff_id",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter'
    },
    {
      headerName: "Оператор",
      field: "operator_name",
      width: 150,
      filter: 'agTextFilter'
    },
    {
      headerName: "Звонки (эфф)",
      field: "calls_count",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toLocaleString() : '0'
    },
    {
      headerName: "Лиды (эфф)",
      field: "leads_count",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toLocaleString() : '0'
    },
    {
      headerName: "% эффект.",
      field: "effective_percent",
      width: 100,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(1) + '%' : '0%',
      cellStyle: params => ({
        color: params.value > 20 ? '#10b981' : params.value > 10 ? '#f59e0b' : '#ef4444',
        fontWeight: 'bold'
      })
    },
    {
      headerName: "Эфф. факт",
      field: "effective_rate",
      width: 100,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(2) : '0.00'
    },
    {
      headerName: "Эфф. план",
      field: "expecting_effective_rate",
      width: 100,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(2) : '-'
    },
    {
      headerName: "Эфф. реком.",
      field: "efficiency_recommendation",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(2) : '-'
    },
    {
      headerName: "Лиды без треша",
      field: "leads_non_trash_count",
      width: 130,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toLocaleString() : '0'
    },
    {
      headerName: "Аппрувы",
      field: "leads_approved_count",
      width: 100,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toLocaleString() : '0'
    },
    {
      headerName: "% аппрува факт",
      field: "approve_percent_fact",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(1) + '%' : '0%'
    },
    {
      headerName: "% аппрува план",
      field: "approve_rate_plan",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(1) + '%' : '-'
    },
    {
      headerName: "Аппрув реком.",
      field: "approve_recommendation",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(1) + '%' : '-'
    },
    {
      headerName: "Выкупы",
      field: "leads_buyout_count",
      width: 100,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toLocaleString() : '0'
    },
    {
      headerName: "% выкупа факт",
      field: "buyout_percent_fact",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(1) + '%' : '0%'
    },
    {
      headerName: "Выкуп реком.",
      field: "buyout_recommendation",
      width: 120,
      type: 'numericColumn',
      filter: 'agNumberFilter',
      valueFormatter: params => params.value ? params.value.toFixed(1) + '%' : '-'
    }
  ]

  const googleSheetsColumnDefs = [
  { headerName: "Тип данных", field: "0", width: 120, pinned: 'left', filter: 'agTextFilter' },
  { headerName: "Категория", field: "1", width: 150, filter: 'agTextFilter' },
  { headerName: "ID Оффер", field: "2", width: 100, filter: 'agTextFilter' },
  { headerName: "Оффер", field: "3", width: 200, filter: 'agTextFilter' },
  { headerName: "ID Вебмастер", field: "4", width: 120, filter: 'agTextFilter' },
  { headerName: "Оператор", field: "5", width: 150, filter: 'agTextFilter' },
  {
    headerName: "Звонки (эфф)",
    field: "6",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0'
  },
  {
    headerName: "Лиды (эфф)",
    field: "7",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0'
  },
  {
    headerName: "% эффект.",
    field: "8",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0%'
  },
  { headerName: "Пусто", field: "9", width: 80 },
  {
    headerName: "Эфф. факт",
    field: "10",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0.00'
  },
  {
    headerName: "Эфф. план",
    field: "11",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Дата обновления", field: "12", width: 120, filter: 'agTextFilter' },
  { headerName: "Тип Плана", field: "13", width: 100, filter: 'agTextFilter' },
  {
    headerName: "Эфф. реком.",
    field: "14",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Дата обновления", field: "15", width: 120, filter: 'agTextFilter' },
  { headerName: "Коррекция", field: "16", width: 120, filter: 'agTextFilter' },
  { headerName: "Пусто", field: "17", width: 80 },
  {
    headerName: "Лиды без треша",
    field: "18",
    width: 130,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0'
  },
  {
    headerName: "Аппрувы",
    field: "19",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0'
  },
  {
    headerName: "% аппрува факт",
    field: "20",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0%'
  },
  {
    headerName: "% аппрува план",
    field: "21",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  {
    headerName: "Аппрув реком.",
    field: "22",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Дата обновления", field: "23", width: 120, filter: 'agTextFilter' },
  { headerName: "Коррекция", field: "24", width: 120, filter: 'agTextFilter' },
  { headerName: "Пусто", field: "25", width: 80 },
  {
    headerName: "% выкупа",
    field: "26",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0%'
  },
  {
    headerName: "Выкупы",
    field: "27",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0'
  },
  {
    headerName: "% выкупа факт",
    field: "28",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '0%'
  },
  {
    headerName: "% выкупа план",
    field: "29",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  {
    headerName: "Выкуп реком.",
    field: "30",
    width: 120,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Дата обновления", field: "31", width: 120, filter: 'agTextFilter' },
  { headerName: "Коррекция", field: "32", width: 120, filter: 'agTextFilter' },
  { headerName: "[СВОД]", field: "33", width: 80, filter: 'agTextFilter' },
  {
    headerName: "Эфф. Рек.",
    field: "34",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Коррекция?", field: "35", width: 100, filter: 'agTextFilter' },
  {
    headerName: "Апп. Рек.",
    field: "36",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Коррекция?", field: "37", width: 100, filter: 'agTextFilter' },
  {
    headerName: "Чек Рек.",
    field: "38",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Коррекция?", field: "39", width: 100, filter: 'agTextFilter' },
  {
    headerName: "Выкуп. Рек.",
    field: "40",
    width: 100,
    filter: 'agNumberFilter',
    type: 'numericColumn',
    valueFormatter: params => params.value !== undefined && params.value !== null && params.value !== '' ? params.value : '-'
  },
  { headerName: "Коррекция?", field: "41", width: 100, filter: 'agTextFilter' },
  { headerName: "Ссылка", field: "42", width: 120, filter: 'agTextFilter' }
]

  const getColumnDefs = () => {
    console.log('📊 Определение колонок, тип данных:', advancedData.length > 0 ? (Array.isArray(advancedData[0]) ? 'Google Sheets' : 'Обычный') : 'Пусто')

    if (advancedData.length > 0 && Array.isArray(advancedData[0])) {
      console.log('📊 Используем Google Sheets колонки')
      return googleSheetsColumnDefs
    }

    console.log('📊 Используем обычные колонки')
    return advancedColumnDefs
  }

 const getRowData = () => {
  console.log('📊 advancedData:', advancedData)

  // Если данные в формате Google Sheets (двумерный массив)
  if (advancedData.length > 0 && Array.isArray(advancedData[0])) {
    console.log('📊 Обработка Google Sheets формата, строк:', advancedData.length)

    // Берем заголовки из первой строки
    const headers = advancedData[0]
    // Берем данные начиная со второй строки
    const dataRows = advancedData.slice(1)

    console.log('📊 Заголовки:', headers)
    console.log('📊 Первая строка данных:', dataRows[0])

    // Преобразуем в массив объектов с правильными полями
    return dataRows.map((row, index) => {
      const rowObj = { id: index }

      // Создаем объект где ключи - это заголовки колонок
      headers.forEach((header, colIndex) => {
        if (header && header.trim() !== '') {
          // Создаем безопасное имя поля
          const fieldName = `col_${colIndex}`
          rowObj[fieldName] = row[colIndex]
        }
      })

      // Также сохраняем оригинальные данные по индексам
      row.forEach((value, colIndex) => {
        rowObj[colIndex] = value
      })

      return rowObj
    })
  }

  // Если данные в обычном формате
  if (advancedData.length > 0 && typeof advancedData[0] === 'object' && !Array.isArray(advancedData[0])) {
    return advancedData.map(item => ({
      ...item,
      hierarchy: item.type === 'Категория' ? [item.category_name] :
                 item.type === 'Оффер' ? [item.category_name, item.offer_name] :
                 item.type === 'Оператор' ? [item.category_name, item.offer_name, item.operator_name] :
                 [item.category_name, item.offer_name, 'Веб', item.aff_id || item.key]
    }))
  }

  console.log('📊 Нет данных для отображения')
  return []
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

  const exportToCSV = () => {
    if (gridApi) {
      gridApi.exportDataAsCsv({
        fileName: `kpi_analysis_${filters.date_from}_${filters.date_to}`,
        processCellCallback: (params) => {
          return params.value || ''
        }
      })
    }
  }

  useEffect(() => {
    loadAdvancedAnalysis()
  }, [])

  return (
    <div className="analytics-page">
      <header className="analytics-header">
        <h1>📈 Расширенная аналитика KPI</h1>
      </header>

      <div className="filters-section">
        <h3>🔧 Фильтры анализа</h3>

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
            <select
              value={filters.output}
              onChange={e => setFilters({...filters, output: e.target.value})}
            >
              <option value="Все">Все данные</option>
              <option value="Есть активность">Только с активностью</option>
              <option value="--">Только активные</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Группировка:</label>
            <select
              value={filters.group_rows}
              onChange={e => setFilters({...filters, group_rows: e.target.value})}
            >
              <option value="Нет">Без группировки</option>
              <option value="Да">С группировкой</option>
            </select>
          </div>
        </div>

        <div className="filter-row">
          <div className="filter-group">
            <label>Категория:</label>
            <input
              type="text"
              placeholder="Все категории"
              value={filters.category}
              onChange={e => setFilters({...filters, category: e.target.value})}
            />
          </div>
          <div className="filter-group">
            <label>Advertiser:</label>
            <input
              type="text"
              placeholder="Все advertisers"
              value={filters.advertiser}
              onChange={e => setFilters({...filters, advertiser: e.target.value.toLowerCase()})}
            />
          </div>
          <div className="filter-group">
            <label>Оператор:</label>
            <input
              type="text"
              placeholder="Все операторы"
              value={filters.operator_name}
              onChange={e => setFilters({...filters, operator_name: e.target.value.toLowerCase()})}
            />
          </div>
          <div className="filter-group">
            <label>ID Оффера:</label>
            <input
              type="text"
              placeholder="Все офферы"
              value={filters.offer_id}
              onChange={e => setFilters({...filters, offer_id: e.target.value})}
            />
          </div>
        </div>

        <div className="action-buttons">
          <button className="btn primary" onClick={loadAdvancedAnalysis} disabled={loading}>
            {loading ? '🔄 Анализ...' : '📊 Запустить анализ'}
          </button>
          <button className="btn secondary" onClick={loadGoogleSheetsFormat} disabled={loading}>
            📋 Google Sheets формат
          </button>
          <button className="btn secondary" onClick={debugFirstRow}>
                🐛    Дебаг данных
          </button>
          <button className="btn secondary" onClick={loadComparison}>
            📊 Сравнить анализы
          </button>
          <button className="btn secondary" onClick={exportToCSV}>
            📄 Экспорт в CSV
          </button>
          <button className="btn secondary" onClick={resetFilters}>
            🗑️ Сбросить фильтры
          </button>
        </div>
      </div>

      {error && (
        <div className="error-message">
          ❌ {error}
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="recommendations-section">
          <h3>💡 Рекомендации по KPI</h3>
          <div className="recommendations-grid">
            {recommendations.map((rec, index) => (
              <div key={index} className="recommendation-card">
                <div className="rec-header">
                  <span className="rec-type">
                    {rec.type === 'efficiency' ? '📈 Эффективность' :
                     rec.type === 'approve_rate' ? '✅ Аппрув' : '💰 Выкуп'}
                  </span>
                  <span className="rec-category">{rec.category}</span>
                </div>
                <div className="rec-values">
                  <span className="current">Текущее: {rec.current_value}</span>
                  <span className="arrow">→</span>
                  <span className="recommended">Реком.: {rec.recommended_value}</span>
                </div>
                {rec.comment && (
                  <div className="rec-comment">{rec.comment}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {summary && Object.keys(summary).length > 0 && (
        <div className="summary-section">
          <h3>📊 Сводная статистика</h3>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-value">{summary.total_categories || 0}</div>
              <div className="stat-label">Категорий</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{summary.total_offers || 0}</div>
              <div className="stat-label">Офферов</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{summary.total_operators || 0}</div>
              <div className="stat-label">Операторов</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{summary.total_effective_calls?.toLocaleString() || 0}</div>
              <div className="stat-label">Эфф. звонков</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{summary.overall_efficiency?.toFixed(1) || 0}%</div>
              <div className="stat-label">Общая эффективность</div>
            </div>
            {summary.records_count && (
              <div className="stat-item">
                <div className="stat-value">{summary.records_count.toLocaleString()}</div>
                <div className="stat-label">Всего записей</div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="table-section">
        <h3>📋 Детальные данные ({getRowData().length} записей)</h3>

        {loading ? (
          <div className="loading-indicator">
            Загрузка данных...
          </div>
        ) : getRowData().length === 0 ? (
          <div className="no-data-message">
            📊 Нет данных для отображения. Запустите анализ с выбранными фильтрами.
            <br />
            <small>Отладочная информация: advancedData.length = {advancedData.length}, тип = {advancedData.length > 0 ? (Array.isArray(advancedData[0]) ? 'массив' : 'объект') : 'пусто'}</small>
          </div>
        ) : (
          <div
            className="ag-theme-quartz"
            style={{
              height: '600px',
              width: '100%',
              marginTop: '15px'
            }}
          >
            <AgGridReact
              rowData={getRowData()}
              columnDefs={getColumnDefs()}
              defaultColDef={{
                resizable: true,
                sortable: true,
                filter: true,
                minWidth: 80,
                flex: 1
              }}
              onGridReady={onGridReady}
              pagination={true}
              paginationPageSize={50}
              paginationPageSizeSelector={[20, 50, 100]}
              suppressFieldDotNotation={true}
              enableCellTextSelection={true}
              ensureDomOrder={true}
              getRowStyle={params => {
                if (params.data && params.data[0] === 'Категория') {
                  return { backgroundColor: '#f0f8ff', fontWeight: 'bold' }
                }
                if (params.data && params.data[0] === 'Оффер') {
                  return { backgroundColor: '#f0fff0' }
                }
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