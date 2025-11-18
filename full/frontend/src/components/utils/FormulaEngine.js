// utils/FormulaEngine.js
class FormulaEngine {
  constructor() {
    this.functions = {
      // Основные математические
      'SUM': (args) => args.reduce((a, b) => a + b, 0),
      'AVERAGE': (args) => args.length ? this.sum(args) / args.length : 0,
      'COUNT': (args) => args.length,
      'MAX': (args) => Math.max(...args),
      'MIN': (args) => Math.min(...args),

      // Логические
      'IF': (args) => {
        if (args.length < 2) return null
        return args[0] ? args[1] : (args[2] || null)
      },

      // KPI-специфичные функции
      'EFFECTIVE_RATE': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1])
      },
      'ЭФФЕКТИВНОСТЬ': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1])
      },
      'APPROVE_RATE': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1]) * 100
      },
      'АППРУВ_ПРОЦЕНТ': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1]) * 100
      },
      'BUYOUT_RATE': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1]) * 100
      },
      'ВЫКУП_ПРОЦЕНТ': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1]) * 100
      },
      'CR': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1]) * 100
      },
      'CPL': (args) => {
        if (args.length < 2) return 0
        return this.safeDiv(args[0], args[1])
      }
    }
  }

  safeDiv(a, b) {
    if (b === 0 || b === null || b === undefined) return 0
    return a / b
  }

  sum(args) {
    return args.reduce((a, b) => a + b, 0)
  }

  evaluateFormula(formula, context = {}) {
    try {
      if (!formula || !formula.startsWith('=')) {
        return formula
      }

      // Убираем знак равенства
      let expression = formula.substring(1).trim()

      // Заменяем русские названия функций на английские
      expression = this.translateRussianFunctions(expression)

      // Заменяем ссылки на переменные контекста
      expression = this.replaceVariables(expression, context)

      // Парсим и вычисляем выражение
      return this.evaluateExpression(expression)

    } catch (error) {
      console.error('Formula evaluation error:', error)
      return '#ERROR'
    }
  }

  translateRussianFunctions(expression) {
    const translations = {
      'СУММ': 'SUM',
      'СРЗНАЧ': 'AVERAGE',
      'СЧЁТ': 'COUNT',
      'МАКС': 'MAX',
      'МИН': 'MIN',
      'ЕСЛИ': 'IF',
      'ЭФФЕКТИВНОСТЬ': 'EFFECTIVE_RATE',
      'АППРУВ_ПРОЦЕНТ': 'APPROVE_RATE',
      'ВЫКУП_ПРОЦЕНТ': 'BUYOUT_RATE'
    }

    let result = expression
    for (const [rus, eng] of Object.entries(translations)) {
      const regex = new RegExp(rus, 'gi')
      result = result.replace(regex, eng)
    }

    return result
  }

  replaceVariables(expression, context) {
    let result = expression

    // Заменяем переменные контекста на их значения
    for (const [key, value] of Object.entries(context)) {
      const regex = new RegExp(`\\b${key}\\b`, 'gi')
      result = result.replace(regex, value)
    }

    return result
  }

  evaluateExpression(expression) {
    try {
      // Безопасное вычисление математических выражений
      // Внимание: используем Function только для trusted выражений
      const func = new Function('return ' + expression)
      return func()
    } catch (error) {
      // Если прямое вычисление не работает, пытаемся разобрать функции
      return this.evaluateWithFunctions(expression)
    }
  }

  evaluateWithFunctions(expression) {
    // Простой парсер для функций
    const functionRegex = /([A-Z_]+)\(([^)]*)\)/g
    let result = expression

    let match
    while ((match = functionRegex.exec(expression)) !== null) {
      const [fullMatch, funcName, argsStr] = match
      const args = this.parseArguments(argsStr)

      if (this.functions[funcName]) {
        const funcResult = this.functions[funcName](args)
        result = result.replace(fullMatch, funcResult)
      }
    }

    // Вычисляем оставшееся выражение
    try {
      return eval(result) // eslint-disable-line no-eval
    } catch (error) {
      return '#ERROR'
    }
  }

  parseArguments(argsStr) {
    if (!argsStr.trim()) return []

    return argsStr.split(',')
      .map(arg => arg.trim())
      .map(arg => {
        // Пытаемся преобразовать в число
        const num = parseFloat(arg)
        return isNaN(num) ? arg : num
      })
  }
}

export default FormulaEngine