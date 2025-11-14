import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { saveAs } from 'file-saver'
import * as XLSX from 'xlsx'
import './ReportsPage.css'

const ReportsPage = ({ toggleTheme, theme }) => {
  const [filters, setFilters] = useState(() => {
    const saved = localStorage.getItem('kpi_filters')
    return saved
      ? JSON.parse(saved)
      : {
          date_from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          date_to: new Date().toISOString().split('T')[0],
          category: '',
          advertiser: '',
          output: 'Все',
          offer_id: '',
          operator_name: '',
          aff_id: '',
          group_rows: 'Нет'
        }
  })

  const [reportData, setReportData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    localStorage.setItem('kpi_filters', JSON.stringify(filters))
  }, [filters])

  // === 1. ЗАГРУЗКА KPI ДАННЫХ ===
  const loadKPIAnalysis = async () => {
    setLoading(true)
    try {
      const res = await axios.post('/api/kpi/advanced_analysis/', {
        params: {
          ...filters,
          group_rows: filters.group_rows || 'Нет'
        }
      })

      if (res.data.success) {
        setReportData(res.data)
      } else {
        alert('Ошибка: ' + (res.data.error || 'Неизвестная ошибка'))
      }
    } catch (err) {
      console.error('Ошибка загрузки KPI:', err)
      alert('Ошибка сервера')
    } finally {
      setLoading(false)
    }
  }

  // === 2. ЭКСПОРТ В EXCEL ===
  const exportToExcel = () => {
    if (!reportData?.google_sheets_data?.length) {
      return alert('Нет данных для экспорта')
    }

    const ws = XLSX.utils.aoa_to_sheet(reportData.google_sheets_data)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'KPI Анализ')

    const buffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
    saveAs(
      new Blob([buffer]),
      `kpi_${filters.date_from}_to_${filters.date_to}.xlsx`
    )
  }

  // === 3. ЕЖЕДНЕВНЫЙ ОТЧЁТ (Legacy) ===
  const generateDailyReport = async () => {
    setLoading(true)
    try {
      const res = await axios.post('/api/legacy/kpi-analysis/', {
        params: filters  // ← ИСПРАВЛЕНО: { params: filters }
      })

      if (res.data.success) {
        alert('Ежедневный отчёт готов! Данные отправлены в Google Sheets.')
      } else {
        alert('Ошибка: ' + (res.data.error || ''))
      }
    } catch (err) {
      console.error('Ошибка отправки отчёта:', err)
      alert('Ошибка сервера')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="reports-page">
      <h2>Отчёты KPI</h2>

      {/* === ФИЛЬТРЫ === */}
      <div className="filters">
        <div>
          <label>С:</label>
          <input
            type="date"
            value={filters.date_from}
            onChange={e => setFilters({ ...filters, date_from: e.target.value })}
          />
        </div>
        <div>
          <label>По:</label>
          <input
            type="date"
            value={filters.date_to}
            onChange={e => setFilters({ ...filters, date_to: e.target.value })}
          />
        </div>
        <div>
          <label>Группировка:</label>
          <select
            value={filters.group_rows}
            onChange={e => setFilters({ ...filters, group_rows: e.target.value })}
          >
            <option value="Нет">Нет</option>
            <option value="Да">Да</option>
          </select>
        </div>
        <div>
          <label>Вывод:</label>
          <select
            value={filters.output}
            onChange={e => setFilters({ ...filters, output: e.target.value })}
          >
            <option value="Все">Все</option>
            <option value="Есть активность">Есть активность</option>
            <option value="--">Только активные</option>
          </select>
        </div>
      </div>

      {/* === КНОПКИ === */}
      <div className="actions">
        <button onClick={loadKPIAnalysis} disabled={loading}>
          {loading ? 'Загрузка...' : 'Загрузить KPI'}
        </button>
        <button
          onClick={exportToExcel}
          disabled={!reportData?.google_sheets_data || loading}
          className="primary"
        >
          Экспорт Excel
        </button>
        <button
          onClick={generateDailyReport}
          disabled={loading}
          className="secondary"
        >
          Ежедневный отчёт
        </button>
      </div>

      {/* === СВОДКА === */}
      {reportData?.summary && (
        <div className="summary">
          <h3>Сводка</h3>
          <p>Категорий: <strong>{reportData.summary.total_categories}</strong></p>
          <p>Офферов: <strong>{reportData.summary.total_offers}</strong></p>
          <p>Звонков: <strong>{reportData.summary.total_effective_calls?.toLocaleString()}</strong></p>
          <p>Лидов: <strong>{reportData.summary.total_effective_leads?.toLocaleString()}</strong></p>
          <p>Эфф.: <strong>{reportData.summary.overall_efficiency}%</strong></p>
        </div>
      )}

      {/* === РЕКОМЕНДАЦИИ === */}
      {reportData?.recommendations?.length > 0 && (
        <div className="recommendations">
          <h3>Рекомендации</h3>
          {reportData.recommendations.map((r, i) => (
            <div key={i} className="rec-item">
              <strong>{r.category}</strong>: {r.type === 'efficiency' ? 'Эфф.' : 'Аппрув'}{' '}
              {r.current}% → <span style={{ color: 'green' }}>{r.recommended}%</span>
              <em style={{ marginLeft: '8px' }}>({r.comment})</em>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ReportsPage