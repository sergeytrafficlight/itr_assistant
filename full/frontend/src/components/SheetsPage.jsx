import React, { useState, useEffect, useRef, useCallback } from 'react'
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
  const [isKpiMode, setIsKpiMode] = useState(false)
  const [kpiFilters, setKpiFilters] = useState({
    date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    date_to: new Date().toISOString().split('T')[0],
    group_rows: 'Да',
    output: 'Все'
  })
  const gridRef = useRef()

  // === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
  const safeDiv = (a, b) => b ? (a / b) * 100 : 0

  const getRowData = useCallback((data) => {
    if (!data || !data.length) return []
    const rows = []
    let rowId = 0

    data.forEach(cat => {
      // Категория
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

      // Офферы
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
          approve_percent_fact: safeDiv(offer.lead_container?.leads_approved_count, offer.lead_container?.leads_non_trash_count),
          leads_buyout: offer.lead_container?.leads_buyout_count || 0,
          buyout_percent_fact: safeDiv(offer.lead_container?.leads_buyout_count, offer.lead_container?.leads_approved_count),
          plan_eff: offer.kpi_current_plan?.operator_efficiency,
          plan_approve: offer.kpi_current_plan?.planned_approve,
          plan_buyout: offer.kpi_current_plan?.planned_buyout,
          recommended_eff: offer.recommended_efficiency,
          recommended_approve: offer.recommended_approve,
          recommended_buyout: offer.recommended_buyout,
          correction_eff: offer.kpi_eff_need_correction ? '⚠️' : '',
          correction_approve: offer.kpi_app_need_correction ? '⚠️' : '',
          correction_buyout: offer.kpi_buyout_need_correction ? '⚠️' : '',
        })
      })

      // Операторы
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

      // Вебмастера
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
  }, [])

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

  // === ЗАГРУЗКА ЛИСТА С ПУСТЫМИ ЯЧЕЙКАМИ ===
  const loadSheet = async (sheetId) => {
    try {
      setLoading(true)
      setIsKpiMode(false)
      const res = await axios.get(`/api/sheets/${sheetId}/`)
      setSelectedSheet(res.data)

      // СОЗДАЕМ ПУСТЫЕ ЯЧЕЙКИ ДЛЯ ПУСТОЙ ТАБЛИЦЫ
      const rows = []
      const ROW_COUNT = 100
      const COL_COUNT = 26

      for (let r = 0; r < ROW_COUNT; r++) {
        const row = { id: r }
        for (let c = 0; c < COL_COUNT; c++) {
          const cellKey = `col${c}`
          const cell = res.data.cells?.find(cell => cell.row === r && cell.col === c)

          if (cell) {
            // Ячейка с данными
            row[cellKey] = cell.formula ? `=${cell.formula}` : cell.value
            row[`${cellKey}_raw`] = cell // Сохраняем сырые данные для формул
            row[`${cellKey}_isFormula`] = !!cell.formula
          } else {
            // ПУСТАЯ ЯЧЕЙКА
            row[cellKey] = ''
            row[`${cellKey}_raw`] = null
            row[`${cellKey}_isFormula`] = false
          }
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

  // === ОБРАБОТКА ФОРМУЛ ===
  const evaluateFormula = async (formula, currentSheetData) => {
    try {
      const evalRes = await axios.post('/api/formulas/evaluate/', {
        formula: formula,
        sheet_data: {
          celldata: currentSheetData || [],
          rows: rowData.length,
          cols: 26
        }
      })
      return evalRes.data.result
    } catch (err) {
      console.error('Ошибка вычисления формулы:', err)
      return '#ERROR'
    }
  }

  // === СОХРАНЕНИЕ ЯЧЕЙКИ С ПОДДЕРЖКОЙ ФОРМУЛ ===
  const onCellValueChanged = async (params) => {
    if (isKpiMode || !selectedSheet) return

    const colId = params.column.colId
    const col = parseInt(colId.replace('col', ''))
    const row = params.node.id
    const newValue = params.newValue || ''

    try {
      const isFormula = newValue.startsWith('=')
      const formula = isFormula ? newValue.slice(1) : null
      const cellValue = isFormula ? null : newValue

      // Сохраняем в базу
      await axios.post('/api/cells/', {
        sheet: selectedSheet.id,
        row: row,
        col: col,
        value: cellValue,
        formula: formula
      })

      // Если это формула - вычисляем и обновляем отображение
      if (isFormula) {
        const result = await evaluateFormula(formula, selectedSheet.cells || [])
        params.node.setDataValue(colId, result)

        // Сохраняем вычисленное значение
        params.node.setDataValue(`${colId}_raw`, {
          row: row,
          col: col,
          value: result,
          formula: formula
        })
      } else {
        // Простое значение
        params.node.setDataValue(`${colId}_raw`, {
          row: row,
          col: col,
          value: cellValue,
          formula: null
        })
      }

      params.node.setDataValue(`${colId}_isFormula`, isFormula)

    } catch (err) {
      console.error("Ошибка сохранения:", err)
      // Откатываем значение в случае ошибки
      params.node.setDataValue(colId, params.oldValue)
    }
  }

  // === KPI АНАЛИЗ С ИСПОЛЬЗОВАНИЕМ OUTPUT_FORMATTER ===
  const runKPIAnalysis = async () => {
    try {
      setLoading(true)
      setIsKpiMode(true)

      const res = await axios.post('/api/kpi/advanced_analysis/', kpiFilters)

      if (res.data.success) {
        setKpiData(res.data)

        // ИСПОЛЬЗУЕМ OUTPUT_FORMATTER ДАННЫЕ
        const formattedData = getRowData(res.data.data)
        setRowData(formattedData)

        // Группировка
        if (res.data.groups && gridRef.current?.api) {
          setTimeout(() => {
            res.data.groups.forEach(g => {
              for (let i = g.start; i <= g.end; i++) {
                const node = gridRef.current.api.getRowNode(i.toString())
                if (node) node.setExpanded(true)
              }
            })
          }, 300)
        }
      } else {
        alert('Ошибка KPI-анализа: ' + (res.data.error || 'Неизвестная ошибка'))
      }
    } catch (err) {
      console.error("KPI анализ ошибка:", err)
      alert('Ошибка KPI-анализа: ' + (err.response?.data?.error || err.message))
    } finally {
      setLoading(false)
    }
  }

  // === КОЛОНКИ ===
  const getColumnDefs = () => {
    if (isKpiMode) {
      return [
        {
          headerName: "Тип",
          field: "type",
          rowGroup: kpiFilters.group_rows === 'Да',
          hide: true
        },
        {
          headerName: "Описание",
          field: "description",
          pinned: 'left',
          width: 220,
          cellStyle: params => ({
            fontWeight: params.data.type === 'category' ? 'bold' : 'normal',
            backgroundColor: params.data.type === 'category' ? '#f0f8ff' : 'transparent'
          })
        },
        {
          headerName: "Звонки",
          field: "calls_effective",
          type: 'numericColumn',
          width: 110
        },
        {
          headerName: "Лиды",
          field: "leads_effective",
          type: 'numericColumn',
          width: 110
        },
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
        {
          headerName: "Эфф. факт",
          field: "effective_rate",
          type: 'numericColumn',
          width: 100,
          valueFormatter: p => p.value?.toFixed(2) || '0.00'
        },
        {
          headerName: "Эфф. план",
          field: "expecting_rate",
          type: 'numericColumn',
          width: 100,
          valueFormatter: p => p.value?.toFixed(2) || '-'
        },
        {
          headerName: "Без треша",
          field: "leads_non_trash",
          type: 'numericColumn',
          width: 120
        },
        {
          headerName: "Аппрувы",
          field: "leads_approved",
          type: 'numericColumn',
          width: 110
        },
        {
          headerName: "% Аппрув",
          field: "approve_percent_fact",
          type: 'numericColumn',
          width: 120,
          valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
        },
        {
          headerName: "План аппрув",
          field: "approve_rate_plan",
          type: 'numericColumn',
          width: 120,
          valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '-'
        },
        {
          headerName: "Выкупы",
          field: "leads_buyout",
          type: 'numericColumn',
          width: 110
        },
        {
          headerName: "% Выкуп",
          field: "buyout_percent_fact",
          type: 'numericColumn',
          width: 120,
          valueFormatter: p => p.value ? p.value.toFixed(1) + '%' : '0%'
        },
        {
          headerName: "Коррекция",
          field: "correction_eff",
          width: 100,
          cellStyle: { color: 'red', fontWeight: 'bold' }
        }
      ]
    } else {
      // КОЛОНКИ ДЛЯ ОБЫЧНОГО РЕЖИМА (GOOGLE SHEETS)
      return Array.from({ length: 26 }, (_, i) => ({
        headerName: String.fromCharCode(65 + i),
        field: `col${i}`,
        editable: true,
        width: 120,
        cellStyle: { fontFamily: 'Arial, sans-serif', fontSize: '13px' },
        valueFormatter: params => {
          if (!params.value) return ''
          return params.value
        }
      }))
    }
  }

  // === ЭКСПОРТ ===
  const exportToCSV = () => {
    if (gridRef.current?.api) {
      gridRef.current.api.exportDataAsCsv({
        fileName: isKpiMode
          ? `kpi_${kpiFilters.date_from}_to_${kpiFilters.date_to}`
          : `sheet_${selectedSheet?.name || 'export'}`
      })
    }
  }

  return (
    <div className="sheets-page" style={{ padding: '20px', height: '100vh' }}>
      <div style={{ marginBottom: '20px' }}>
        <h1>Google Sheets + KPI Анализ</h1>

        <div style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '20px' }}>
          {/* ВЫБОР ЛИСТА (только в обычном режиме) */}
          {!isKpiMode && (
            <select
              onChange={(e) => loadSheet(e.target.value)}
              style={{ padding: '10px', borderRadius: '6px', minWidth: '300px' }}
              disabled={loading}
            >
              <option value="">Выберите лист...</option>
              {spreadsheets.map(ss =>
                ss.sheets.map(sheet => (
                  <option key={sheet.id} value={sheet.id}>
                    {ss.name} → {sheet.name}
                  </option>
                ))
              )}
            </select>
          )}

          {/* ФИЛЬТРЫ KPI (только в режиме KPI) */}
          {isKpiMode && (
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <input
                type="date"
                value={kpiFilters.date_from}
                onChange={e => setKpiFilters({...kpiFilters, date_from: e.target.value})}
                style={{ padding: '8px', borderRadius: '4px' }}
              />
              <input
                type="date"
                value={kpiFilters.date_to}
                onChange={e => setKpiFilters({...kpiFilters, date_to: e.target.value})}
                style={{ padding: '8px', borderRadius: '4px' }}
              />
              <select
                value={kpiFilters.group_rows}
                onChange={e => setKpiFilters({...kpiFilters, group_rows: e.target.value})}
                style={{ padding: '8px', borderRadius: '4px' }}
              >
                <option value="Да">С группировкой</option>
                <option value="Нет">Без группировки</option>
              </select>
            </div>
          )}

          {/* КНОПКИ ДЕЙСТВИЙ */}
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
            {isKpiMode ? 'Обновить KPI' : 'KPI Анализ'}
          </button>

          <button
            onClick={exportToCSV}
            style={{
              padding: '10px 20px',
              background: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            Экспорт CSV
          </button>

          {isKpiMode && (
            <button
              onClick={() => {
                setIsKpiMode(false)
                if (selectedSheet) loadSheet(selectedSheet.id)
              }}
              style={{
                padding: '10px 20px',
                background: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              Вернуться к таблицам
            </button>
          )}

          {loading && <span style={{ marginLeft: '10px' }}>Загрузка...</span>}
        </div>
      </div>

      {/* ТАБЛИЦА */}
      <div className="ag-theme-quartz" style={{ height: 'calc(100vh - 200px)', width: '100%' }}>
        <AgGridReact
          ref={gridRef}
          columnDefs={getColumnDefs()}
          rowData={rowData}
          defaultColDef={{
            resizable: true,
            sortable: true,
            filter: true,
            editable: !isKpiMode // РЕДАКТИРОВАНИЕ ТОЛЬКО В ОБЫЧНОМ РЕЖИМЕ
          }}
          onCellValueChanged={isKpiMode ? undefined : onCellValueChanged}
          groupDisplayType="multipleColumns"
          animateRows={true}
          pagination={true}
          paginationPageSize={isKpiMode ? 50 : 100}
          overlayNoRowsTemplate="Нет данных"
          getRowStyle={params => {
            if (!params.data) return null
            if (params.data.type === 'category') return { backgroundColor: '#f0f8ff', fontWeight: 'bold' }
            if (params.data.type === 'offer') return { backgroundColor: '#f8fff8' }
            return null
          }}
        />
      </div>

      {/* РЕКОМЕНДАЦИИ KPI */}
      {isKpiMode && kpiData?.recommendations?.length > 0 && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          background: '#f8f9fa',
          borderRadius: '8px',
          border: '1px solid #dee2e6'
        }}>
          <h3>Рекомендации по KPI</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {kpiData.recommendations.map((r, i) => (
              <div key={i} style={{
                padding: '8px',
                background: 'white',
                borderRadius: '4px',
                border: '1px solid #e9ecef'
              }}>
                <strong>{r.category}</strong>: {r.type === 'efficiency' ? 'Эффективность' : 'Аппрув'}{' '}
                {r.current}% → <span style={{ color: 'green', fontWeight: 'bold' }}>{r.recommended}%</span>
                {' '}<em style={{ color: '#6c757d' }}>({r.comment})</em>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default SheetsPage