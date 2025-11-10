import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { saveAs } from 'file-saver'
import * as XLSX from 'xlsx'
import './ReportsPage.css'

const ReportsPage = ({ toggleTheme, theme }) => {
  const [exportData, setExportData] = useState([])
  const [filters, setFilters] = useState(() => {
    const saved = localStorage.getItem('kpi_filters')
    return saved ? JSON.parse(saved) : {
      date_from: new Date(Date.now() - 30*24*60*60*1000).toISOString().split('T')[0],
      date_to: new Date().toISOString().split('T')[0],
      category: '', advertiser: '', output: 'Все', offer_id: '', operator_name: '', aff_id: ''
    }
  })

  useEffect(() => {
    localStorage.setItem('kpi_filters', JSON.stringify(filters))
  }, [filters])

  const loadExportData = async () => {
    try {
      const response = await axios.post('/api/kpi-advanced/google_sheets_format/', filters)
      if (response.data.success) {
        setExportData(response.data.data || [])
      }
    } catch (error) {
      console.error('Error:', error)
    }
  }

  const exportToExcel = () => {
    if (exportData.length === 0) return alert('Нет данных')
    const ws = XLSX.utils.json_to_sheet(exportData)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'KPI Анализ')
    const buffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
    saveAs(new Blob([buffer]), `kpi_${filters.date_from}_${filters.date_to}.xlsx`)
  }

  const generateDailyReport = async () => {
    const res = await axios.post('/api/kpi-advanced/advanced_analysis/', filters)
    if (res.data.success) {
      alert('Отчет готов!')
    }
  }

  return (
    <div className="reports-page">
      <h2>Отчеты KPI</h2>
      <div className="filters">
        <input type="date" value={filters.date_from} onChange={e => setFilters({...filters, date_from: e.target.value})} />
        <input type="date" value={filters.date_to} onChange={e => setFilters({...filters, date_to: e.target.value})} />
        <button onClick={loadExportData}>Загрузить</button>
      </div>
      <button className="btn primary" onClick={exportToExcel}>Экспорт Excel</button>
      <button className="btn secondary" onClick={generateDailyReport}>Ежедневный отчет</button>
    </div>
  )
}

export default ReportsPage