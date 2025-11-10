// KPI Analyzer Frontend Application
class KpiAnalyzerApp {
    constructor() {
        this.currentSpreadsheetId = null;
        this.socket = null;
        this.isConnected = false;
        this.formulaEngine = new FormulaEngine();
    }

    init() {
        this.initSpreadsheet();
        this.initWebSocket();
        this.loadKpiData();
    }

    initSpreadsheet() {
        const options = {
            container: 'luckysheet',
            lang: 'ru',
            showinfobar: false,
            row: 100,
            column: 50,
            allowEdit: true,
            enableAddRow: true,
            enableAddBackTop: true,
            showtoolbar: true,
            showsheetbar: true,
            showstatisticBar: true,
            sheetFormulaBar: true,
            enableAddRow: true,
            enableAddCol: true,
            userInfo: false,
            showConfigWindowResize: true,
            forceCalculation: true,
            
            hook: {
                onCellUpdated: this.onCellUpdated.bind(this),
                onRangeSelected: this.onRangeSelected.bind(this),
                onFormulaParser: this.onFormulaParser.bind(this),
                onMounted: this.onSpreadsheetMounted.bind(this)
            }
        };

        luckysheet.create(options);
    }

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/spreadsheet/global/`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
            this.isConnected = true;
            this.updateConnectionStatus(true);
            console.log('WebSocket connected');
        };

        this.socket.onclose = () => {
            this.isConnected = false;
            this.updateConnectionStatus(false);
            console.log('WebSocket disconnected');
            // Попытка переподключения через 5 секунд
            setTimeout(() => this.initWebSocket(), 5000);
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'cell_updated':
                this.updateCell(data.cell);
                break;
            case 'sheet_updated':
                this.updateSheet(data.sheet);
                break;
            case 'kpi_data_updated':
                this.updateKpiDashboard(data.data);
                break;
        }
    }

    onCellUpdated(cell, value, isForward) {
        if (!this.isConnected) return;

        const cellData = {
            type: 'cell_update',
            cell: {
                row: cell.r,
                col: cell.c,
                value: value,
                formula: cell.f || '',
                sheet_id: 1 // TODO: получить актуальный ID листа
            }
        };

        this.socket.send(JSON.stringify(cellData));

        // Автоматическое вычисление формул
        if (cell.f && cell.f.startsWith('=')) {
            this.evaluateFormula(cell);
        }
    }

    onRangeSelected(range) {
        // Показать информацию о выделенном диапазоне
        console.log('Range selected:', range);
    }

    onFormulaParser(formula, cell, sheet) {
        // Кастомный парсер формул с поддержкой русских функций
        return this.formulaEngine.preprocessFormula(formula);
    }

    onSpreadsheetMounted() {
        console.log('Spreadsheet mounted');
        this.loadInitialData();
    }

    async evaluateFormula(cell) {
        try {
            const response = await fetch('/api/spreadsheets/formulas/evaluate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    formula: cell.f,
                    sheet_data: luckysheet.getSheetData()
                })
            });

            const result = await response.json();
            
            if (result.result && !result.result.startsWith('#ERROR')) {
                // Обновляем ячейку с вычисленным значением
                luckysheet.setCellValue(cell.r, cell.c, result.result, {f: cell.f});
            }
        } catch (error) {
            console.error('Formula evaluation error:', error);
        }
    }

    async loadKpiData() {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/kpi-data/analytics/');
            const data = await response.json();
            
            this.updateKpiDashboard(data.summary);
            
            // Загружаем структуру колонок из google_kpi.txt
            const columnsResponse = await fetch('/api/kpi-data/google_kpi_columns/');
            const columnsData = await columnsResponse.json();
            
            this.setupKpiTemplate(columnsData.columns, data.data);
            
        } catch (error) {
            console.error('Error loading KPI data:', error);
        } finally {
            this.showLoading(false);
        }
    }

    setupKpiTemplate(columns, data) {
        // Создаем шапку таблицы с колонками из google_kpi.txt
        const headerRow = columns.map(col => col.name);
        
        // Создаем данные для таблицы
        const sheetData = [
            {
                name: 'KPI Анализ',
                celldata: [
                    // Заголовки
                    ...headerRow.map((header, index) => ({
                        r: 0,
                        c: index,
                        v: header
                    })),
                    // Данные
                    ...data.map((row, rowIndex) => 
                        columns.map((col, colIndex) => ({
                            r: rowIndex + 1,
                            c: colIndex,
                            v: row[col.field] || ''
                        }))
                    ).flat()
                ],
                config: {
                    columnlen: {},
                    rowlen: {},
                    borderInfo: {}
                }
            }
        ];

        // Загружаем данные в Luckysheet
        luckysheet.load(sheetData);
    }

    updateKpiDashboard(summary) {
        if (!summary) return;

        document.getElementById('total-calls').textContent = summary.total_calls?.toLocaleString() || '0';
        document.getElementById('total-leads').textContent = summary.total_leads?.toLocaleString() || '0';
        document.getElementById('cr-rate').textContent = summary.cr_rate ? summary.cr_rate.toFixed(1) + '%' : '0%';
        document.getElementById('avg-effectiveness').textContent = summary.avg_effectiveness ? summary.avg_effectiveness.toFixed(1) + '%' : '0%';
    }

    updateCell(cellData) {
        // Обновляем ячейку в реальном времени
        luckysheet.setCellValue(cellData.row, cellData.col, cellData.value);
    }

    updateSheet(sheetData) {
        // Обновляем весь лист
        luckysheet.load(sheetData);
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (connected) {
            statusElement.innerHTML = '● Подключено';
            statusElement.style.color = '#34a853';
        } else {
            statusElement.innerHTML = '● Отключено';
            statusElement.style.color = '#ea4335';
        }
    }

    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        overlay.style.display = show ? 'flex' : 'none';
    }

    async saveSpreadsheet() {
        try {
            const data = luckysheet.getAllSheets();
            
            await fetch('/api/spreadsheets/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: 'KPI Analysis ' + new Date().toLocaleDateString(),
                    data: data
                })
            });
            
            alert('Таблица сохранена!');
        } catch (error) {
            console.error('Error saving spreadsheet:', error);
            alert('Ошибка при сохранении!');
        }
    }

    async createPivotTable() {
        // Открываем диалог создания сводной таблицы
        const pivotConfig = await this.showPivotDialog();
        if (pivotConfig) {
            try {
                const response = await fetch('/api/pivot-tables/generate/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(pivotConfig)
                });

                const result = await response.json();
                this.displayPivotTable(result.data);
            } catch (error) {
                console.error('Error creating pivot table:', error);
                alert('Ошибка при создании сводной таблицы!');
            }
        }
    }

    displayPivotTable(pivotData) {
        // Создаем новый лист со сводной таблицей
        const sheetData = {
            name: 'Сводная таблица',
            celldata: [
                // Заголовки строк
                ...pivotData.rows.map((row, rowIndex) => ({
                    r: rowIndex + 1,
                    c: 0,
                    v: Object.values(row).join(' - ')
                })),
                // Заголовки колонок
                ...pivotData.columns.map((col, colIndex) => ({
                    r: 0,
                    c: colIndex + 1,
                    v: Object.values(col).join(' - ')
                })),
                // Данные
                ...pivotData.data.map((row, rowIndex) => 
                    row.map((value, colIndex) => ({
                        r: rowIndex + 1,
                        c: colIndex + 1,
                        v: value
                    }))
                ).flat()
            ]
        };

        luckysheet.createSheet(sheetData);
    }

    showPivotDialog() {
        // Простой диалог для конфигурации сводной таблицы
        return new Promise((resolve) => {
            const rows = prompt('Поля для строк (через запятую):', 'category, operator_name');
            const columns = prompt('Поля для колонок (через запятую):', 'date_from');
            const values = prompt('Поля для значений (через запятую):', 'calls_count, leads_count');
            const aggregation = prompt('Тип агрегации (SUM, COUNT, AVG, MIN, MAX):', 'SUM');

            if (rows && values) {
                resolve({
                    rows: rows.split(',').map(s => s.trim()),
                    columns: columns ? columns.split(',').map(s => s.trim()) : [],
                    values: values.split(',').map(s => s.trim()),
                    aggregation: aggregation || 'SUM'
                });
            } else {
                resolve(null);
            }
        });
    }

    exportToExcel() {
        luckysheet.getLuckysheetfile();
    }

    loadKpiTemplate() {
        this.loadKpiData();
    }

    showKpiDashboard() {
        document.getElementById('kpi-dashboard').style.display = 'block';
    }

    hideKpiDashboard() {
        document.getElementById('kpi-dashboard').style.display = 'none';
    }

    toggleTheme() {
        // Переключение между светлой и темной темой
        document.body.classList.toggle('light-theme');
    }
}

// Вспомогательный класс для работы с формулами
class FormulaEngine {
    preprocessFormula(formula) {
        // Преобразование русских функций в английские
        const translations = {
            'СУММ': 'SUM',
            'СРЗНАЧ': 'AVERAGE',
            'СЧЁТ': 'COUNT',
            'МАКС': 'MAX',
            'МИН': 'MIN',
            'ЕСЛИ': 'IF',
            'ВПР': 'VLOOKUP',
            'СЦЕПИТЬ': 'CONCATENATE',
            'ФИЛЬТР': 'QUERY'
        };

        let processedFormula = formula;
        for (const [rus, eng] of Object.entries(translations)) {
            const regex = new RegExp(rus, 'gi');
            processedFormula = processedFormula.replace(regex, eng);
        }

        return processedFormula;
    }
}

// Глобальные функции для кнопок
function saveSpreadsheet() {
    window.kpiApp.saveSpreadsheet();
}

function createPivotTable() {
    window.kpiApp.createPivotTable();
}

function exportToExcel() {
    window.kpiApp.exportToExcel();
}

function loadKpiTemplate() {
    window.kpiApp.loadKpiTemplate();
}

function showKpiDashboard() {
    window.kpiApp.showKpiDashboard();
}

function hideKpiDashboard() {
    window.kpiApp.hideKpiDashboard();
}

function toggleTheme() {
    window.kpiApp.toggleTheme();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    window.kpiApp = new KpiAnalyzerApp();
    window.kpiApp.init();
});