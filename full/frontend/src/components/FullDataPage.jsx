import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import Select from 'react-select';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';
import { useNavigate } from 'react-router-dom';
import { legacyAPI, kpiAPI } from '../api/admin';
import { useAuth } from '../contexts/AuthContext';
import './FullDataPage.css';

const FullDataPage = () => {
  const [structuredData, setStructuredData] = useState([]);
  const [rowData, setRowData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedCategories, setExpandedCategories] = useState(new Set());
  const { user, isLoading: authLoading } = useAuth();

  const [filters, setFilters] = useState({
    date_from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    date_to: new Date().toISOString().split('T')[0],
    output: 'Все',
    group_rows: 'Нет'
  });

  const [categories, setCategories] = useState([]);
  const [advertisers, setAdvertisers] = useState([]);

  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedAdvertisers, setSelectedAdvertisers] = useState([]);

  const gridRef = useRef();
  const navigate = useNavigate();
  const abortControllerRef = useRef(null);

  // Загрузка справочников (только категории и advertisers)
  const loadAllDictionaries = useCallback(async () => {
    if (!user) return;

    try {
      const [categoriesRes, advertisersRes] = await Promise.all([
        legacyAPI.getCategories(),
        legacyAPI.getAdvertisers()
      ]);

      setCategories(categoriesRes.data || []);
      setAdvertisers(advertisersRes.data || []);

    } catch (err) {
      console.error('Ошибка загрузки справочников:', err);
    }
  }, [user]);

  // ОСНОВНАЯ ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ - ВЫЗЫВАЕТСЯ ТОЛЬКО ПО КНОПКЕ
  const loadStructuredData = async () => {
    if (!user) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort('Отмена предыдущего запроса');
    }

    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError('');
    try {
      const requestFilters = {
        date_from: filters.date_from,
        date_to: filters.date_to,
        category: selectedCategories.length > 0 ? selectedCategories.map(cat => cat.value) : [],
        advertiser: selectedAdvertisers.length > 0 ? selectedAdvertisers.map(adv => adv.value) : [],
        output: filters.output,
        group_rows: filters.group_rows
      };

      console.log('FullDataPage - Отправляемые фильтры:', requestFilters);

      const res = await kpiAPI.fullStructuredData(requestFilters, {
        signal: abortControllerRef.current.signal
      });

      if (res.data.success) {
        setStructuredData(res.data.data || []);
        setExpandedCategories(new Set());
      } else {
        setError(res.data.error || 'Ошибка загрузки данных');
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError('Сервер недоступен или сессия истекла');
        console.error('Ошибка загрузки структурированных данных:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleCategory = useCallback((categoryDescription) => {
    setExpandedCategories(prev => {
      const newSet = new Set(prev)
      if (newSet.has(categoryDescription)) {
        newSet.delete(categoryDescription)
      } else {
        newSet.add(categoryDescription)
      }
      return newSet
    })
  }, [])

  // Функция преобразования данных для новой структуры output_formatter
  const convertToFlatData = useCallback((structuredData, expandedSet) => {
    const flatData = []
    let rowIndex = 0

    structuredData.forEach(category => {
      const shouldShowCategory = selectedCategories.length === 0 ||
        selectedCategories.some(selectedCat => selectedCat.value === category.description);

      if (!shouldShowCategory) return;

      if (filters.output === 'Есть активность') {
        const hasCalls = category.kpi_stat?.calls_group_effective_count > 0;
        const hasLeads = category.lead_container?.leads_non_trash_count > 0;
        if (!hasCalls && !hasLeads) return;
      }

      flatData.push({
        id: rowIndex++,
        level: 0,
        isCategory: true,
        isExpanded: expandedSet.has(category.description),
        ...createCategoryRow(category)
      })

      if (expandedSet.has(category.description)) {
        // Офферы
        category.offers?.forEach(offer => {
          if (filters.output === 'Есть активность') {
            const hasCalls = offer.kpi_stat?.calls_group_effective_count > 0;
            const hasLeads = offer.lead_container?.leads_non_trash_count > 0;
            if (!hasCalls && !hasLeads) return;
          }

          flatData.push({
            id: rowIndex++,
            level: 1,
            type: 'Оффер',
            parentCategory: category.description,
            ...createOfferRow(offer, category)
          })
        })

        // Операторы
        category.operators?.forEach(operator => {
          if (filters.output === 'Есть активность') {
            const hasCalls = operator.kpi_stat?.calls_group_effective_count > 0;
            const hasLeads = operator.lead_container?.leads_non_trash_count > 0;
            if (!hasCalls && !hasLeads) return;
          }

          flatData.push({
            id: rowIndex++,
            level: 1,
            type: 'Оператор',
            parentCategory: category.description,
            ...createOperatorRow(operator)
          })
        })

        // Вебмастеры
        category.affiliates?.forEach(affiliate => {
          if (filters.output === 'Есть активность') {
            const hasCalls = affiliate.kpi_stat?.calls_group_effective_count > 0;
            const hasLeads = affiliate.lead_container?.leads_non_trash_count > 0;
            if (!hasCalls && !hasLeads) return;
          }

          flatData.push({
            id: rowIndex++,
            level: 1,
            type: 'Вебмастер',
            parentCategory: category.description,
            ...createAffiliateRow(affiliate)
          })
        })
      }
    })

    return flatData
  }, [filters.output, selectedCategories])

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort('Компонент размонтирован');
      }
    };
  }, []);

  // ИНИЦИАЛИЗАЦИЯ - ТОЛЬКО ЗАГРУЗКА СПРАВОЧНИКОВ
  useEffect(() => {
    if (!authLoading && user) {
      loadAllDictionaries();
    }
  }, [authLoading, user, loadAllDictionaries]);

  // ПРЕОБРАЗОВАНИЕ ДАННЫХ ПРИ ИХ ИЗМЕНЕНИИ
  useEffect(() => {
    const flatData = convertToFlatData(structuredData, expandedCategories)
    setRowData(flatData)
  }, [structuredData, expandedCategories, convertToFlatData])

  // Создание строки категории для новой структуры данных
  const createCategoryRow = (category) => {
    const kpiPlan = category.kpi_current_plan || {};

    return {
      type: 'Категория',
      description: category.description,
      calls_effective: category.kpi_stat?.calls_group_effective_count || 0,
      leads_raw: category.lead_container?.leads_raw_count || 0,
      leads_effective: category.kpi_stat?.leads_effective_count || 0,
      effective_percent: category.kpi_stat?.effective_percent || 0,
      effective_rate_fact: category.kpi_stat?.effective_rate || 0,
      effective_rate_plan: category.kpi_stat?.expecting_effective_rate || 0,
      effective_recommendation: category.recommended_efficiency || null,
      leads_non_trash: category.lead_container?.leads_non_trash_count || 0,
      leads_approved: category.lead_container?.leads_approved_count || 0,
      approve_percent_fact: category.approve_percent_fact || 0,
      approve_percent_plan: category.approve_rate_plan || 0,
      approve_recommendation: category.recommended_approve || null,
      leads_buyout: category.lead_container?.leads_buyout_count || 0,
      buyout_percent_fact: category.buyout_percent_fact || 0,
      buyout_percent_plan: category.buyout_rate_plan || 0,
      buyout_recommendation: category.recommended_buyout || null,
      trash_percent: category.trash_percent || 0,
      raw_to_approve_percent: category.raw_to_approve_percent || 0,
      raw_to_buyout_percent: category.raw_to_buyout_percent || 0,
      non_trash_to_buyout_percent: category.non_trash_to_buyout_percent || 0,
      summary_effective_rec: category.recommended_efficiency || null,
      summary_approve_rec: category.recommended_approve || null,
      summary_buyout_rec: category.recommended_buyout || null,
      summary_check_rec: category.recommended_confirmation_price || null,
      needs_efficiency_correction: category.needs_efficiency_correction || false,
      needs_approve_correction: category.needs_approve_correction || false,
      needs_buyout_correction: category.needs_buyout_correction || false,
      effective_update_date: kpiPlan.operator_efficiency_update_date || '',
      approve_update_date: kpiPlan.planned_approve_update_date || '',
      buyout_update_date: kpiPlan.planned_buyout_update_date || '',
      plan_type: kpiPlan.plan_type || '',
    }
  }

  // Создание строки оффера для новой структуры данных
  const createOfferRow = (offer, category) => {
    const kpiPlan = offer.kpi_current_plan || {}

    return {
      offer_id: offer.key,
      offer_name: offer.description,
      description: offer.description,
      category: category.description,
      calls_effective: offer.kpi_stat?.calls_group_effective_count || 0,
      leads_raw: offer.lead_container?.leads_raw_count || 0,
      leads_effective: offer.kpi_stat?.leads_effective_count || 0,
      effective_percent: offer.kpi_stat?.effective_percent || 0,
      effective_rate_fact: offer.kpi_stat?.effective_rate || 0,
      effective_rate_plan: kpiPlan.operator_efficiency || 0,
      effective_recommendation: offer.recommended_efficiency || null,
      leads_non_trash: offer.lead_container?.leads_non_trash_count || 0,
      leads_approved: offer.lead_container?.leads_approved_count || 0,
      approve_percent_fact: offer.approve_percent_fact || 0,
      approve_percent_plan: kpiPlan.planned_approve || 0,
      approve_recommendation: offer.recommended_approve || null,
      leads_buyout: offer.lead_container?.leads_buyout_count || 0,
      buyout_percent_fact: offer.buyout_percent_fact || 0,
      buyout_percent_plan: kpiPlan.planned_buyout || 0,
      buyout_recommendation: offer.recommended_buyout || null,
      trash_percent: offer.trash_percent || 0,
      raw_to_approve_percent: offer.raw_to_approve_percent || 0,
      raw_to_buyout_percent: offer.raw_to_buyout_percent || 0,
      non_trash_to_buyout_percent: offer.non_trash_to_buyout_percent || 0,
      summary_effective_rec: offer.recommended_efficiency || null,
      summary_approve_rec: offer.recommended_approve || null,
      summary_buyout_rec: offer.recommended_buyout || null,
      summary_check_rec: offer.recommended_confirmation_price || null,
      needs_efficiency_correction: offer.needs_efficiency_correction || false,
      needs_approve_correction: offer.needs_approve_correction || false,
      needs_buyout_correction: offer.needs_buyout_correction || false,
      needs_confirmation_price_correction: offer.needs_confirmation_price_correction || false,
      effective_update_date: kpiPlan.operator_efficiency_update_date || '',
      approve_update_date: kpiPlan.planned_approve_update_date || '',
      buyout_update_date: kpiPlan.planned_buyout_update_date || '',
      plan_type: kpiPlan.plan_type || '',
      link: {
        url: `https://admin.crm.itvx.biz/partners/tloffer/${offer.key}/change/`,
        text: offer.key
      },
    }
  }

  // Создание строки оператора для новой структуры данных
  const createOperatorRow = (operator) => {
    return {
      operator_name: operator.key,
      description: operator.description,
      calls_effective: operator.kpi_stat?.calls_group_effective_count || 0,
      leads_raw: operator.lead_container?.leads_raw_count || 0,
      leads_effective: operator.kpi_stat?.leads_effective_count || 0,
      effective_percent: operator.kpi_stat?.effective_percent || 0,
      effective_rate_fact: operator.kpi_stat?.effective_rate || 0,
      leads_non_trash: operator.lead_container?.leads_non_trash_count || 0,
      leads_approved: operator.lead_container?.leads_approved_count || 0,
      approve_percent_fact: operator.approve_percent_fact || 0,
      leads_buyout: operator.lead_container?.leads_buyout_count || 0,
      buyout_percent_fact: operator.buyout_percent_fact || 0,
      trash_percent: operator.trash_percent || 0,
      raw_to_approve_percent: operator.raw_to_approve_percent || 0,
      raw_to_buyout_percent: operator.raw_to_buyout_percent || 0,
      non_trash_to_buyout_percent: operator.non_trash_to_buyout_percent || 0,
      recommended_efficiency: operator.recommended_efficiency || null,
      recommended_approve: operator.recommended_approve || null,
      recommended_buyout: operator.recommended_buyout || null,
      recommended_confirmation_price: operator.recommended_confirmation_price || null,
      needs_efficiency_correction: operator.needs_efficiency_correction || false,
      needs_approve_correction: operator.needs_approve_correction || false,
      needs_buyout_correction: operator.needs_buyout_correction || false,
    }
  }

  // Создание строки вебмастера для новой структуры данных
  const createAffiliateRow = (affiliate) => {
    return {
      aff_id: affiliate.key,
      description: `Веб #${affiliate.key}`,
      calls_effective: affiliate.kpi_stat?.calls_group_effective_count || 0,
      leads_raw: affiliate.lead_container?.leads_raw_count || 0,
      leads_effective: affiliate.kpi_stat?.leads_effective_count || 0,
      effective_percent: affiliate.kpi_stat?.effective_percent || 0,
      effective_rate_fact: affiliate.kpi_stat?.effective_rate || 0,
      leads_non_trash: affiliate.lead_container?.leads_non_trash_count || 0,
      leads_approved: affiliate.lead_container?.leads_approved_count || 0,
      approve_percent_fact: affiliate.approve_percent_fact || 0,
      leads_buyout: affiliate.lead_container?.leads_buyout_count || 0,
      buyout_percent_fact: affiliate.buyout_percent_fact || 0,
      trash_percent: affiliate.trash_percent || 0,
      raw_to_approve_percent: affiliate.raw_to_approve_percent || 0,
      raw_to_buyout_percent: affiliate.raw_to_buyout_percent || 0,
      non_trash_to_buyout_percent: affiliate.non_trash_to_buyout_percent || 0,
      recommended_efficiency: affiliate.recommended_efficiency || null,
      recommended_approve: affiliate.recommended_approve || null,
      recommended_buyout: affiliate.recommended_buyout || null,
      recommended_confirmation_price: affiliate.recommended_confirmation_price || null,
      needs_efficiency_correction: affiliate.needs_efficiency_correction || false,
      needs_approve_correction: affiliate.needs_approve_correction || false,
      needs_buyout_correction: affiliate.needs_buyout_correction || false,
    }
  }

  const columnDefs = [
    {
      headerName: "",
      field: "isCategory",
      width: 60,
      pinned: 'left',
      cellRenderer: params => {
        if (!params.data?.isCategory) {
          return <span style={{ marginLeft: '20px' }}>↳</span>
        }
        return (
          <button
            onClick={() => toggleCategory(params.data.description)}
            className="expand-btn"
            style={{
              background: 'none',
              border: 'none',
              fontSize: '16px',
              cursor: 'pointer',
              padding: '4px 8px'
            }}
          >
            {params.data.isExpanded ? '−' : '+'}
          </button>
        )
      }
    },
    {
      headerName: "Тип данных",
      field: "type",
      width: 120,
      pinned: 'left',
      cellRenderer: params => {
        if (params.data?.type === 'Категория') {
          return params.data.description
        }
        return params.data?.type || ''
      },
      cellStyle: params => {
        const type = params.data?.type
        if (type === 'Категория') return { backgroundColor: '#e3f2fd', fontWeight: 'bold' }
        if (type === 'Оффер') return { backgroundColor: '#f3e5f5' }
        if (type === 'Оператор') return { backgroundColor: '#e8f5e8' }
        if (type === 'Вебмастер') return { backgroundColor: '#fff3e0' }
        return null
      }
    },
    {
      headerName: "ID Оффер",
      field: "offer_id",
      width: 100,
      cellStyle: params => {
        if (!params.data?.offer_id) return { paddingLeft: '20px' }
        return null
      }
    },
    {
      headerName: "Оффер",
      field: "offer_name",
      width: 200,
      cellStyle: params => {
        if (!params.data?.offer_id) return { paddingLeft: '20px' }
        return null
      }
    },
    { headerName: "ID Вебмастер", field: "aff_id", width: 120 },
    { headerName: "Оператор", field: "operator_name", width: 150 },
    { headerName: "Категория", field: "category", width: 150 },
    {
      headerName: "Ко-во звонков (эфф)",
      field: "calls_effective",
      width: 140,
      type: 'numericColumn'
    },
    {
      headerName: "Лиды",
      field: "leads_raw",
      width: 110,
      type: 'numericColumn'
    },
    {
      headerName: "Продажи",
      field: "leads_effective",
      width: 110,
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
      headerName: "Коррекция эфф.",
      field: "needs_efficiency_correction",
      width: 120,
      cellRenderer: params => params.value ? '❌ Требует' : '✅ OK',
      cellStyle: params => params.value ?
        { backgroundColor: '#ffebee', color: '#c62828' } :
        { backgroundColor: '#e8f5e8', color: '#2e7d32' }
    },
    { headerName: "", field: "blank2", width: 50 },
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
      headerName: "Коррекция аппрув",
      field: "needs_approve_correction",
      width: 120,
      cellRenderer: params => params.value ? '❌ Требует' : '✅ OK',
      cellStyle: params => params.value ?
        { backgroundColor: '#ffebee', color: '#c62828' } :
        { backgroundColor: '#e8f5e8', color: '#2e7d32' }
    },
    { headerName: "", field: "blank3", width: 50 },
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
      headerName: "Коррекция выкуп",
      field: "needs_buyout_correction",
      width: 120,
      cellRenderer: params => params.value ? '❌ Требует' : '✅ OK',
      cellStyle: params => params.value ?
        { backgroundColor: '#ffebee', color: '#c62828' } :
        { backgroundColor: '#e8f5e8', color: '#2e7d32' }
    },
    {
      headerName: "% Треш",
      field: "trash_percent",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "% Аппрув от сырых",
      field: "raw_to_approve_percent",
      width: 140,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "% Выкуп от сырых",
      field: "raw_to_buyout_percent",
      width: 140,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "% Выкуп от нетреша",
      field: "non_trash_to_buyout_percent",
      width: 150,
      type: 'numericColumn',
      valueFormatter: p => p.value ? `${p.value.toFixed(1)}%` : '0%'
    },
    {
      headerName: "Эфф. Рек.",
      field: "summary_effective_rec",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(1) || '-'
    },
    {
      headerName: "Апп. Рек.",
      field: "summary_approve_rec",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(1) || '-'
    },
    {
      headerName: "Чек Рек.",
      field: "summary_check_rec",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(1) || '-'
    },
    {
      headerName: "Выкуп. Рек.",
      field: "summary_buyout_rec",
      width: 100,
      type: 'numericColumn',
      valueFormatter: p => p.value?.toFixed(1) || '-'
    },
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

  const customStyles = {
    control: (base) => ({
      ...base,
      minHeight: '40px',
      border: '1px solid #ddd',
      boxShadow: 'none',
      '&:hover': {
        border: '1px solid #28a745'
      }
    }),
    menu: (base) => ({
      ...base,
      zIndex: 9999
    }),
    multiValue: (base) => ({
      ...base,
      backgroundColor: '#d4edda',
      color: '#155724',
      border: '1px solid #c3e6cb'
    }),
    multiValueLabel: (base) => ({
      ...base,
      color: '#155724',
      fontWeight: '500'
    }),
    multiValueRemove: (base) => ({
      ...base,
      color: '#155724',
      '&:hover': {
        backgroundColor: '#f5c6cb',
        color: '#721c24'
      }
    }),
    option: (base, state) => ({
      ...base,
      backgroundColor: state.isSelected
        ? '#28a745'
        : state.isFocused
          ? '#e8f5e8'
          : base.backgroundColor,
      color: state.isSelected
        ? 'white'
        : state.isFocused
          ? '#155724'
          : base.color,
    }),
    indicatorsContainer: (base) => ({
      ...base,
      color: '#6c757d'
    }),
    indicatorSeparator: (base) => ({
      ...base,
      backgroundColor: '#ddd'
    }),
    dropdownIndicator: (base) => ({
      ...base,
      color: '#6c757d',
      '&:hover': {
        color: '#28a745'
      }
    }),
    clearIndicator: (base) => ({
      ...base,
      color: '#6c757d',
      '&:hover': {
        color: '#dc3545'
      }
    }),
    placeholder: (base) => ({
      ...base,
      color: '#6c757d'
    })
  };

  // Подготовка опций для селектов (только категории и advertisers)
  const categoryOptions = categories.map(cat => ({ value: cat, label: cat }));
  const advertiserOptions = advertisers.map(adv => ({ value: adv, label: adv }));

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
      output: 'Все',
      group_rows: 'Нет'
    })
    setSelectedCategories([]);
    setSelectedAdvertisers([]);
    // Очищаем данные при сбросе фильтров
    setStructuredData([]);
    setRowData([]);
  }

  const expandAll = () => {
    const allCategories = new Set(structuredData.map(cat => cat.description))
    setExpandedCategories(allCategories)
  }

  const collapseAll = () => {
    setExpandedCategories(new Set())
  }

  if (authLoading) {
    return <div className="loading">Проверка авторизации...</div>
  }

  return (
    <div className="full-data-page">
      <header className="full-data-header">
        <div className="header-top">
          <button onClick={() => navigate('/analytics')} className="btn back-btn">
            ← Назад к аналитике
          </button>
          <h1>Полные данные KPI</h1>
          <div>
            <button onClick={expandAll} className="btn secondary" style={{ marginRight: '10px' }}>
              Развернуть все
            </button>
            <button onClick={collapseAll} className="btn secondary" style={{ marginRight: '10px' }}>
              Свернуть все
            </button>
            <button onClick={exportToCSV} disabled={structuredData.length === 0} className="btn primary">
              Экспорт в CSV
            </button>
          </div>
        </div>
      </header>

      <div className="filters-section">
        <h3>Фильтры</h3>

        {/* Первая строка фильтров */}
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
            <select value={filters.output} onChange={e => setFilters({...filters, output: e.target.value})}>
              <option value="Все">Все</option>
              <option value="Есть активность">Активные</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Группировка:</label>
            <select value={filters.group_rows} onChange={e => setFilters({...filters, group_rows: e.target.value})}>
              <option value="Нет">Без группировки</option>
              <option value="Да">С группировкой</option>
            </select>
          </div>
        </div>

        {/* Вторая строка фильтров - только категории и advertisers */}
        <div className="filter-row">
          <div className="filter-group wide">
            <label>Категории:</label>
            <Select
              isMulti
              options={categoryOptions}
              value={selectedCategories}
              onChange={setSelectedCategories}
              placeholder="Выберите категории..."
              styles={customStyles}
              className="react-select-container"
              classNamePrefix="react-select"
            />
          </div>
          <div className="filter-group wide">
            <label>Advertisers:</label>
            <Select
              isMulti
              options={advertiserOptions}
              value={selectedAdvertisers}
              onChange={setSelectedAdvertisers}
              placeholder="Выберите advertisers..."
              styles={customStyles}
              className="react-select-container"
              classNamePrefix="react-select"
            />
          </div>
        </div>

        <div className="action-buttons">
          <button onClick={loadStructuredData} disabled={loading} className="btn primary">
            {loading ? '🔄 Загрузка...' : '📊 Обновить'}
          </button>
          <button onClick={resetFilters} className="btn secondary">🔄 Сброс</button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="table-section">
        <div className="table-header">
          <h3>Полные данные KPI ({rowData.length} строк)</h3>
          <div className="table-info">
            {structuredData.length === 0 ? 'Нажмите "Обновить" для загрузки данных' : 'Прокрутите горизонтально для просмотра всех колонок • Цветовые коды:'}
            {structuredData.length > 0 && (
              <>
                <span className="color-code category">Категория</span>
                <span className="color-code offer">Оффер</span>
                <span className="color-code operator">Оператор</span>
                <span className="color-code affiliate">Вебмастер</span>
              </>
            )}
          </div>
        </div>

        {loading ? (
          <div className="loading-indicator">Загрузка структурированных данных...</div>
        ) : rowData.length === 0 ? (
          <div className="no-data-message">
            {structuredData.length === 0 ? 'Нажмите "Обновить" для загрузки данных' : 'Нет данных для отображения'}
          </div>
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

export default FullDataPage;