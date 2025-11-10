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
  const gridRef = useRef()

  useEffect(() => {
    loadSpreadsheets()
  }, [])

  const loadSpreadsheets = async () => {
    try {
      setLoading(true)
      const res = await axios.get('/api/spreadsheets/')
      setSpreadsheets(res.data)
      if (res.data.length > 0 && res.data[0].sheets.length > 0) {
        await loadSheet(res.data[0].sheets[0].id)
      }
    } catch (err) {
      console.error("❌ Ошибка загрузки таблиц:", err)
    } finally {
      setLoading(false)
    }
  }

  const loadSheet = async (sheetId) => {
    try {
      setLoading(true)
      const res = await axios.get(`/api/sheets/${sheetId}/`)
      setSelectedSheet(res.data)

      // Создаём сетку 100x26 (A-Z)
      const rows = []
      for (let r = 0; r < 100; r++) {
        const row = { id: r }
        for (let c = 0; c < 26; c++) {
          const cell = res.data.cells?.find(cell => cell.row === r && cell.col === c)
          row[`col${c}`] = cell ? (cell.formula ? `=${cell.formula}` : cell.value) : ''
        }
        rows.push(row)
      }
      setRowData(rows)
    } catch (err) {
      console.error("❌ Ошибка загрузки листа:", err)
    } finally {
      setLoading(false)
    }
  }

 const onCellValueChanged = async (params) => {
  if (!selectedSheet) return

  const col = parseInt(params.column.colId.replace('col', ''))
  const row = params.node.id
  const value = params.newValue || ''

  try {
    const isFormula = value.startsWith('=')
    const formula = isFormula ? value.slice(1) : null
    const cellValue = isFormula ? null : value

    // СОХРАНЕНИЕ ЯЧЕЙКИ
    await axios.post(`/api/cells/`, {
      sheet: selectedSheet.id,
      row: row,
      col: col,
      value: cellValue,
      formula: formula
    })

    // ВЫЧИСЛЕНИЕ ФОРМУЛЫ
    if (isFormula) {
      try {
        const evalRes = await axios.post('/api/formulas/evaluate/', {
          formula: formula,
          sheet_data: { celldata: selectedSheet.cells || [] }
        })

        // ОБНОВЛЯЕМ ВЫЧИСЛЕННОЕ ЗНАЧЕНИЕ
        params.node.setDataValue(params.column.colId, evalRes.data.result)

      } catch (e) {
        console.error("❌ Ошибка вычисления формулы:", e)
        params.node.setDataValue(params.column.colId, '#ОШИБКА!')
      }
    }

  } catch (err) {
    console.error("❌ Ошибка сохранения ячейки:", err)
    params.node.setDataValue(params.column.colId, params.oldValue)
  }
}

  const columnDefs = Array.from({ length: 26 }, (_, i) => ({
    headerName: String.fromCharCode(65 + i),
    field: `col${i}`,
    editable: true,
    width: 120,
    cellStyle: {
      fontFamily: 'Arial, sans-serif',
      fontSize: '13px',
      padding: '2px 4px'
    },
    cellRenderer: (params) => {
      if (params.value && params.value.startsWith('=')) {
        return '📐 ' + params.value
      }
      return params.value
    }
  }))

  return (
    <div className="sheets-page" style={{ padding: '20px', height: '100vh' }}>
      <div style={{ marginBottom: '20px' }}>
        <h1>📊 Google Sheets Аналог</h1>

        <div style={{ display: 'flex', gap: '15px', alignItems: 'center', marginBottom: '15px' }}>
          <select
            onChange={(e) => loadSheet(e.target.value)}
            style={{
              padding: '10px 15px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              minWidth: '300px'
            }}
            disabled={loading}
          >
            <option value="">Выберите таблицу...</option>
            {spreadsheets.map(ss =>
              ss.sheets.map(sheet => (
                <option key={sheet.id} value={sheet.id}>
                  {ss.name} → {sheet.name}
                </option>
              ))
            )}
          </select>

          {loading && <span>🔄 Загрузка...</span>}
        </div>
      </div>

      <div
        className="ag-theme-quartz"
        style={{
          height: 'calc(100vh - 180px)',
          width: '100%',
          border: '1px solid #e0e0e0',
          borderRadius: '8px'
        }}
      >
        <AgGridReact
          ref={gridRef}
          columnDefs={columnDefs}
          rowData={rowData}
          defaultColDef={{
            resizable: true,
            sortable: true,
            filter: true,
            editable: true,
            minWidth: 100
          }}
          onCellValueChanged={onCellValueChanged}
          rowSelection="single"
          animateRows={true}
          suppressRowTransform={true}
          overlayNoRowsTemplate={
            loading ? '🔄 Загрузка данных...' : '📝 Нет данных для отображения'
          }
        />
      </div>

      <div style={{
        marginTop: '15px',
        fontSize: '14px',
        color: '#666',
        padding: '15px',
        backgroundColor: '#f8f9fa',
        borderRadius: '8px',
        border: '1px solid #e9ecef'
      }}>
        <strong>💡 Подсказка:</strong> Поддерживаются формулы:
        <code> =СУММ(A1:A10) </code> •
        <code> =A1*B2 </code> •
        <code> =ЕСЛИ(C1&gt;500;"ТОП";"Норм") </code> •
        <code> =ВПР(D1;A1:F100;2;0) </code>
      </div>
    </div>
  )
}

export default SheetsPage