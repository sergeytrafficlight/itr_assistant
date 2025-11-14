import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { AgGridReact } from 'ag-grid-react'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'

const SheetsPage = () => {
  const [spreadsheets, setSpreadsheets] = useState([])
  const [selectedSheet, setSelectedSheet] = useState(null)
  const [rowData, setRowData] = useState([])
  const [loading, setLoading] = useState(false)
  const [kpiData, setKpiData] = useState(null)
  const [isKpiMode, setIsKpiMode] = useState(false) // ← НОВОЕ: режим KPI
  const gridRef = useRef()

  // === ЗАГРУЗКА ТАБЛИЦ ===
  const loadSpreadsheets = async () => {
    try {
      setLoading(true)
      const res = await axios.get('/api/spreadsheets/')
      setSpreadsheets(res.data)
      if (res.data.length > 0 && res.data[0].sheets.length > 0) {
        await loadSheet(res.data[0].sheets[0].id)
      }
    } catch (err) {
      console.error("Ошибка загрузки таблиц:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSpreadsheets()
  }, [])

  // === ЗАГРУЗКА ЛИСТА ===
  const loadSheet = async (sheetId) => {
    try {
      setLoading(true)
      setIsKpiMode(false)
      const res = await axios.get(`/api/sheets/${sheetId}/`)
      setSelectedSheet(res.data)

      const rows = []
      for (let r = 0; r < 100; r++) {
        const row = { id: r }
        for (let c = 0; c < 26; c++) {
          const cell = res.data.cells?.find(cell => cell.row === r && cell.col === c)
          row[`col${c}`] = cell
            ? (cell.formula ? `=${cell.formula}` : cell.value)
            : ''
        }
        rows.push(row)
      }
      setRowData(rows)
    } catch (err) {
      console.error("Ошибка загрузки листа:", err)
    } finally {
      setLoading(false)
    }
  }

  // === СОХРАНЕНИЕ ЯЧЕЙКИ (ТОЛЬКО ДЛЯ ЛИСТОВ) ===
  const onCellValueChanged = async (params) => {
    if (isKpiMode || !selectedSheet) return

    const col = parseInt(params.column.colId.replace('col', ''))
    const row = params.node.id
    const value = params.newValue || ''

    try {
      const isFormula = value.startsWith('=')
      const formula = isFormula ? value.slice(1) : null
      const cellValue = isFormula ? null : value

      await axios.post(`/api/cells/`, {
        sheet: selectedSheet.id,
        row: row,
        col: col,
        value: cellValue,
        formula: formula
      })

      if (isFormula) {
        const evalRes = await axios.post('/api/formulas/evaluate/', {
          formula: formula,
          sheet_data: { celldata: selectedSheet.cells || [] }
        })
        params.node.setDataValue(params.column.colId, evalRes.data.result)
      }
    } catch (err) {
      console.error("Ошибка сохранения:", err)
      params.node.setDataValue(params.column.colId, params.oldValue)
    }
  }

  // === KPI АНАЛИЗ ===
  const runKPIAnalysis = async () => {
    try {
      setLoading(true)
      setIsKpiMode(true)
      const res = await axios.post('/api/kpi/advanced_analysis/', {
        params: {
          date_from: '2025-01-01',
          date_to: '2025-12-31',
          group_rows: 'Да',
          output: 'Все'
        }
      })
      setKpiData(res.data)
      showKPITab(res.data)
    } catch (err) {
      console.error("KPI анализ ошибка:", err)
      alert('Ошибка KPI-анализа')
    } finally {
      setLoading(false)
    }
  }

  const showKPITab = (data) => {
    const kpiRows = []
    let rowId = 0

    data?.data?.forEach(cat => {
      // Категория
      kpiRows.push({
        id: rowId++,
        type: 'category',
        description: cat.description,
        calls_effective: cat.kpi_stat.calls_group_effective_count,
        leads_effective: cat.kpi_stat.leads_effective_count,
        effective_percent: cat.kpi_stat.effective_percent?.toFixed(1) + '%',
      })

      // Офферы
      cat.offers.forEach(offer => {
        const plan = offer.kpi_current_plan
        kpiRows.push({
          id: rowId++,
          type: 'offer',
          key: offer.key,
          description: offer.description,
          calls_effective: offer.kpi_stat.calls_group_effective_count,
          leads_effective: offer.kpi_stat.leads_effective_count,
          effective_percent: offer.kpi_stat.effective_percent?.toFixed(1) + '%',
          plan_eff: plan?.operator_efficiency,
          plan_approve: plan?.planned_approve,
          correction: offer.corrections?.efficiency || ''
        })
      })
    })

    setRowData(kpiRows)
  }

  // === ГРУППИРОВКА ===
  useEffect(() => {
    if (kpiData?.groups && gridRef.current?.api && isKpiMode) {
      setTimeout(() => {
        kpiData.groups.forEach(g => {
          for (let i = g.start; i <= g.end; i++) {
            const node = gridRef.current.api.getRowNode(i.toString())
            if (node) node.setExpanded(true)
          }
        })
      }, 300)
    }
  }, [kpiData, isKpiMode])

  // === КОЛОНКИ (ЕДИНЫЕ ДЛЯ ЛИСТОВ И KPI) ===
  const columnDefs = isKpiMode
    ? [
        { headerName: 'Тип', field: 'type', rowGroup: true, hide: true },
        { headerName: 'Описание', field: 'description', flex: 2, pinned: 'left' },
        { headerName: 'Звонки', field: 'calls_effective', type: 'numericColumn' },
        { headerName: 'Лиды', field: 'leads_effective', type: 'numericColumn' },
        { headerName: 'Эфф., %', field: 'effective_percent' },
        { headerName: 'План Эфф.', field: 'plan_eff', hide: true },
        { headerName: 'План Аппрув', field: 'plan_approve', hide: true },
        { headerName: 'Коррекция', field: 'correction', cellStyle: { color: 'red' } },
      ]
    : Array.from({ length: 26 }, (_, i) => ({
        headerName: String.fromCharCode(65 + i),
        field: `col${i}`,
        editable: true,
        width: 120,
        cellStyle: { fontFamily: 'Arial, sans-serif', fontSize: '13px' },
        valueFormatter: p => p.value?.startsWith('=') ? p.value : p.value
      }))

  return (
    <div className="sheets-page" style={{ padding: '20px', height: '100vh' }}>
      <div style={{ marginBottom: '20px' }}>
        <h1>Google Sheets + KPI Анализ</h1>

        <div style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
          {!isKpiMode && (
            <select
              onChange={(e) => loadSheet(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', minWidth: '300px' }}
              disabled={loading}
            >
              <option value="">Выберите лист...</option>
              {spreadsheets.map(ss => ss.sheets.map(sheet => (
                <option key={sheet.id} value={sheet.id}>
                  {ss.name} → {sheet.name}
                </option>
              )))}
            </select>
          )}

          <button
            onClick={runKPIAnalysis}
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            KPI Анализ
          </button>

          {loading && <span>Загрузка...</span>}
        </div>
      </div>

      <div className="ag-theme-quartz" style={{ height: 'calc(100vh - 180px)', width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          columnDefs={columnDefs}
          rowData={rowData}
          defaultColDef={{ resizable: true, sortable: true, filter: true }}
          onCellValueChanged={isKpiMode ? null : onCellValueChanged}
          groupDisplayType="multipleColumns"
          animateRows={true}
          overlayNoRowsTemplate="Нет данных"
        />
      </div>

      {/* РЕКОМЕНДАЦИИ */}
      {kpiData?.recommendations?.length > 0 && (
        <div style={{ marginTop: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '8px' }}>
          <h3>Рекомендации</h3>
          {kpiData.recommendations.map((r, i) => (
            <div key={i} style={{ margin: '8px 0', padding: '8px', background: 'white', borderRadius: '4px' }}>
              <strong>{r.category}</strong>: {r.type === 'efficiency' ? 'Эфф.' : 'Аппрув'}{' '}
              {r.current}% → <span style={{ color: 'green' }}>{r.recommended}%</span>
              {' '} <em>({r.comment})</em>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default SheetsPage