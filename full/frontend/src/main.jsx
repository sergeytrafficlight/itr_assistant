import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import './index.css'

// Инициализация темы
const savedTheme = localStorage.getItem('theme') || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)

// РЕГИСТРАЦИЯ ВСЕХ МОДУЛЕЙ AG-GRID
import { ModuleRegistry } from 'ag-grid-community'

// Импортируем модули из вашего файла
import { ClientSideRowModelModule } from 'ag-grid-community'
import { CsvExportModule } from 'ag-grid-community'
import { InfiniteRowModelModule } from 'ag-grid-community'
import { ValidationModule } from 'ag-grid-community'
import { TextEditorModule } from 'ag-grid-community'
import { NumberEditorModule } from 'ag-grid-community'
import { DateEditorModule } from 'ag-grid-community'
import { CheckboxEditorModule } from 'ag-grid-community'
import { SelectEditorModule } from 'ag-grid-community'
import { LargeTextEditorModule } from 'ag-grid-community'
import { TextFilterModule } from 'ag-grid-community'
import { NumberFilterModule } from 'ag-grid-community'
import { DateFilterModule } from 'ag-grid-community'
import { QuickFilterModule } from 'ag-grid-community'
import { PaginationModule } from 'ag-grid-community'
import { RowDragModule } from 'ag-grid-community'
import { PinnedRowModule } from 'ag-grid-community'
import { RowSelectionModule } from 'ag-grid-community'
import { CellStyleModule } from 'ag-grid-community'
import { RowStyleModule } from 'ag-grid-community'
import { TooltipModule } from 'ag-grid-community'
import { RowAutoHeightModule } from 'ag-grid-community'
import { DragAndDropModule } from 'ag-grid-community'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  CsvExportModule,
  InfiniteRowModelModule,
  ValidationModule,
  TextEditorModule,
  NumberEditorModule,
  DateEditorModule,
  CheckboxEditorModule,
  SelectEditorModule,
  LargeTextEditorModule,
  TextFilterModule,
  NumberFilterModule,
  DateFilterModule,
  QuickFilterModule,
  PaginationModule,
  RowDragModule,
  PinnedRowModule,
  RowSelectionModule,
  CellStyleModule,
  RowStyleModule,
  TooltipModule,
  RowAutoHeightModule,
  DragAndDropModule
])

// Рендер
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)