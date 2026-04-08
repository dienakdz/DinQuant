<template>
  <div class="backtest-center" :class="{ 'theme-dark': isDarkTheme }">
    <div class="page-header">
      <h2 class="page-title">
        <a-icon class="title-icon" type="experiment" />
        {{ tt('backtest-center.title', 'Backtest Center') }}
      </h2>
      <p class="page-subtitle">
        {{ tt('backtest-center.subtitle', 'Replay indicator and strategy logic with current frontend controls, then inspect risk, trades, and equity before going live.') }}
      </p>
    </div>

    <a-tabs v-model="activeTab" class="main-tabs" :animated="false">
      <a-tab-pane key="indicator" :tab="tt('backtest-center.tabs.indicator', 'Indicator')">
        <a-row class="workspace" :gutter="20">
          <a-col :xs="24" :md="9" :lg="8" class="config-col">
            <div class="config-panel">
              <div class="section">
                <div class="section-title">{{ tt('backtest-center.indicator.selectIndicator', 'Select indicator') }}</div>
                <a-select
                  v-model="selectedIndicatorId"
                  style="width: 100%;"
                  show-search
                  allow-clear
                  optionFilterProp="label"
                  :placeholder="tt('backtest-center.indicator.selectIndicatorPlaceholder', 'Choose an indicator from your library')"
                  :loading="loadingIndicators"
                  @change="handleIndicatorChange"
                >
                  <a-select-option
                    v-for="indicator in indicators"
                    :key="String(indicator.id)"
                    :value="String(indicator.id)"
                    :label="indicator.name"
                  >
                    {{ indicator.name || `Indicator #${indicator.id}` }}
                  </a-select-option>
                </a-select>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.symbol', 'Symbol') }}</div>
                <a-select
                  v-model="indicatorForm.selectedWatchlistKey"
                  style="width: 100%;"
                  show-search
                  allow-clear
                  optionFilterProp="label"
                  :placeholder="tt('backtest-center.config.watchlistPlaceholder', 'Select from watchlist or add a symbol')"
                  @change="handleIndicatorWatchlistChange"
                >
                  <a-select-option
                    v-for="item in watchlist"
                    :key="buildWatchlistKey(item)"
                    :value="buildWatchlistKey(item)"
                    :label="getWatchlistOptionLabel(item)"
                  >
                    <a-tag :color="getMarketColor(item.market)" size="small">{{ item.market }}</a-tag>
                    <strong style="margin-left: 4px;">{{ item.symbol }}</strong>
                    <span v-if="item.name" class="watchlist-option-name">{{ item.name }}</span>
                  </a-select-option>
                  <a-select-option
                    key="__add__"
                    value="__add__"
                    :label="tt('backtest-center.config.addSymbol', 'Add symbol')"
                  >
                    <div class="add-option">
                      <a-icon type="plus" />
                      {{ tt('backtest-center.config.addSymbol', 'Add symbol') }}
                    </div>
                  </a-select-option>
                </a-select>
              </div>

              <div class="section">
                <div class="section-title">
                  {{ tt('backtest-center.config.timeframe', 'Timeframe') }}
                  <span class="hint">{{ indicatorTfLimitHint }}</span>
                </div>
                <a-radio-group v-model="indicatorForm.timeframe" size="small" button-style="solid">
                  <a-radio-button v-for="tf in timeframes" :key="`indicator-${tf}`" :value="tf">{{ tf }}</a-radio-button>
                </a-radio-group>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.dateRange', 'Date range') }}</div>
                <div class="date-presets">
                  <a-button
                    v-for="preset in indicatorDatePresets"
                    :key="preset.key"
                    size="small"
                    :type="indicatorForm.datePreset === preset.key ? 'primary' : 'default'"
                    @click="applyIndicatorDatePreset(preset)"
                  >
                    {{ preset.label }}
                  </a-button>
                </div>
                <a-row style="margin-top: 8px;" :gutter="8">
                  <a-col :span="12">
                    <a-date-picker
                      v-model="indicatorForm.startDate"
                      size="small"
                      style="width: 100%;"
                      :placeholder="tt('backtest-center.config.startDate', 'Start date')"
                    />
                  </a-col>
                  <a-col :span="12">
                    <a-date-picker
                      v-model="indicatorForm.endDate"
                      size="small"
                      style="width: 100%;"
                      :placeholder="tt('backtest-center.config.endDate', 'End date')"
                    />
                  </a-col>
                </a-row>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.capital', 'Capital and execution') }}</div>
                <a-row :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.initialCapital', 'Initial capital') }}</div>
                    <a-input-number
                      v-model="indicatorForm.initialCapital"
                      size="small"
                      :min="1000"
                      :step="1000"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.leverage', 'Leverage') }}</div>
                    <a-input-number
                      v-model="indicatorForm.leverage"
                      size="small"
                      :min="1"
                      :max="125"
                      :step="1"
                      :precision="0"
                      style="width: 100%;"
                    />
                  </a-col>
                </a-row>
                <a-row style="margin-top: 8px;" :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.commission', 'Commission') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.commission"
                      size="small"
                      :min="0"
                      :max="10"
                      :step="0.01"
                      :precision="4"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.slippage', 'Slippage') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.slippage"
                      size="small"
                      :min="0"
                      :max="10"
                      :step="0.01"
                      :precision="4"
                      style="width: 100%;"
                    />
                  </a-col>
                </a-row>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.direction', 'Trade direction') }}</div>
                <a-radio-group v-model="indicatorForm.tradeDirection" size="small" button-style="solid">
                  <a-radio-button value="long">{{ tt('backtest-center.config.long', 'Long') }}</a-radio-button>
                  <a-radio-button value="short">{{ tt('backtest-center.config.short', 'Short') }}</a-radio-button>
                  <a-radio-button value="both">{{ tt('backtest-center.config.both', 'Both') }}</a-radio-button>
                </a-radio-group>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.riskPanel', 'Risk panel') }}</div>
                <a-row :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.stopLoss', 'Stop loss') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.stopLossPct"
                      size="small"
                      :min="0"
                      :max="100"
                      :step="0.5"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.takeProfit', 'Take profit') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.takeProfitPct"
                      size="small"
                      :min="0"
                      :max="1000"
                      :step="0.5"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                </a-row>
                <a-row style="margin-top: 8px;" :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.entryPct', 'Entry size') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.entryPct"
                      size="small"
                      :min="0"
                      :max="100"
                      :step="5"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <a-checkbox v-model="indicatorForm.trailingEnabled" style="margin-top: 24px;">
                      {{ tt('backtest-center.config.trailing', 'Enable trailing stop') }}
                    </a-checkbox>
                  </a-col>
                </a-row>
                <a-row v-if="indicatorForm.trailingEnabled" style="margin-top: 8px;" :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.trailingPct', 'Trailing stop') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.trailingStopPct"
                      size="small"
                      :min="0"
                      :max="100"
                      :step="0.5"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.trailingActivation', 'Trailing activation') }} (%)</div>
                    <a-input-number
                      v-model="indicatorForm.trailingActivationPct"
                      size="small"
                      :min="0"
                      :max="1000"
                      :step="0.5"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                </a-row>
              </div>

              <div class="run-section">
                <a-button
                  type="primary"
                  block
                  size="large"
                  :loading="indicatorRunning"
                  :disabled="!canRunIndicator"
                  @click="runIndicatorBacktest"
                >
                  <a-icon v-if="!indicatorRunning" type="thunderbolt" />
                  {{ indicatorRunning ? tt('backtest-center.running', 'Running backtest...') : tt('backtest-center.indicator.runBacktest', 'Run indicator backtest') }}
                </a-button>
                <a-button block style="margin-top: 8px;" :disabled="!selectedIndicatorId" @click="openHistory('indicator')">
                  <a-icon type="history" />
                  {{ tt('backtest-center.indicator.history', 'Backtest history') }}
                </a-button>
              </div>
            </div>
          </a-col>

          <a-col :xs="24" :md="15" :lg="16" class="result-col">
            <div class="result-panel">
              <result-view
                :running="indicatorRunning"
                :run-tip="tt('backtest-center.runningDesc', 'This can take longer for larger time ranges and lower timeframes.')"
                :has-result="indicatorHasResult"
                :result="indicatorResult"
                :backtestRunId="indicatorBacktestRunId"
                :symbol="indicatorForm.symbol"
                :market="indicatorForm.market"
                :timeframe="indicatorForm.timeframe"
                :is-dark="isDarkTheme"
              />
            </div>
          </a-col>
        </a-row>
      </a-tab-pane>

      <a-tab-pane key="strategy" :tab="tt('backtest-center.tabs.strategy', 'Strategy')">
        <a-row class="workspace" :gutter="20">
          <a-col :xs="24" :md="9" :lg="8" class="config-col">
            <div class="config-panel">
              <div class="section">
                <div class="section-title">{{ tt('backtest-center.strategy.selectStrategy', 'Select strategy') }}</div>
                <a-select
                  v-model="selectedStrategyId"
                  style="width: 100%;"
                  show-search
                  allow-clear
                  optionFilterProp="label"
                  :placeholder="tt('backtest-center.strategy.selectStrategyPlaceholder', 'Choose a strategy from trading assistant')"
                  :loading="loadingStrategies"
                  @change="handleStrategyChange"
                >
                  <a-select-option
                    v-for="strategy in strategies"
                    :key="String(strategy.id)"
                    :value="String(strategy.id)"
                    :label="strategy.strategy_name"
                  >
                    {{ strategy.strategy_name || `Strategy #${strategy.id}` }}
                  </a-select-option>
                </a-select>

                <div v-if="selectedStrategyObj" class="strategy-summary-card">
                  <div class="strategy-summary-head">
                    <div class="strategy-summary-title">{{ selectedStrategyObj.strategy_name || `Strategy #${selectedStrategyObj.id}` }}</div>
                    <a-tag size="small" :color="strategyTypeColor(selectedStrategyObj)">{{ strategyTypeLabel(selectedStrategyObj) }}</a-tag>
                  </div>
                  <div class="strategy-summary-meta">
                    <a-tag v-if="selectedStrategyMarket" size="small">{{ selectedStrategyMarket }}</a-tag>
                    <a-tag v-if="selectedStrategySymbol" size="small">{{ selectedStrategySymbol }}</a-tag>
                    <a-tag v-if="strategyForm.timeframe" size="small">{{ strategyForm.timeframe }}</a-tag>
                  </div>
                  <div class="strategy-summary-text">{{ strategySummaryText(selectedStrategyObj) }}</div>
                  <a-alert
                    v-if="selectedStrategyIsCrossSectional"
                    type="warning"
                    show-icon
                    :message="tt('backtest-center.strategy.crossSectionalBlocked', 'Cross-sectional strategies are not supported in strategy backtest yet.')"
                    style="margin-top: 10px;"
                  />
                  <a-button type="link" size="small" style="padding-left: 0;" @click="goToStrategyAssistant">
                    {{ tt('backtest-center.strategy.goToAssistant', 'Open in trading assistant') }}
                  </a-button>
                </div>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.symbol', 'Symbol') }}</div>
                <a-select
                  v-model="strategyForm.selectedWatchlistKey"
                  style="width: 100%;"
                  show-search
                  allow-clear
                  optionFilterProp="label"
                  :placeholder="tt('backtest-center.config.watchlistPlaceholder', 'Select from watchlist or add a symbol')"
                  @change="handleStrategyWatchlistChange"
                >
                  <a-select-option
                    v-for="item in watchlist"
                    :key="`strategy-${buildWatchlistKey(item)}`"
                    :value="buildWatchlistKey(item)"
                    :label="getWatchlistOptionLabel(item)"
                  >
                    <a-tag :color="getMarketColor(item.market)" size="small">{{ item.market }}</a-tag>
                    <strong style="margin-left: 4px;">{{ item.symbol }}</strong>
                    <span v-if="item.name" class="watchlist-option-name">{{ item.name }}</span>
                  </a-select-option>
                  <a-select-option
                    key="strategy-add"
                    value="__add__"
                    :label="tt('backtest-center.config.addSymbol', 'Add symbol')"
                  >
                    <div class="add-option">
                      <a-icon type="plus" />
                      {{ tt('backtest-center.config.addSymbol', 'Add symbol') }}
                    </div>
                  </a-select-option>
                </a-select>
              </div>

              <div class="section">
                <div class="section-title">
                  {{ tt('backtest-center.config.timeframe', 'Timeframe') }}
                  <span class="hint">{{ strategyTfLimitHint }}</span>
                </div>
                <a-radio-group v-model="strategyForm.timeframe" size="small" button-style="solid">
                  <a-radio-button v-for="tf in timeframes" :key="`strategy-${tf}`" :value="tf">{{ tf }}</a-radio-button>
                </a-radio-group>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.dateRange', 'Date range') }}</div>
                <div class="date-presets">
                  <a-button
                    v-for="preset in strategyDatePresets"
                    :key="`strategy-${preset.key}`"
                    size="small"
                    :type="strategyForm.datePreset === preset.key ? 'primary' : 'default'"
                    @click="applyStrategyDatePreset(preset)"
                  >
                    {{ preset.label }}
                  </a-button>
                </div>
                <a-row style="margin-top: 8px;" :gutter="8">
                  <a-col :span="12">
                    <a-date-picker
                      v-model="strategyForm.startDate"
                      size="small"
                      style="width: 100%;"
                      :placeholder="tt('backtest-center.config.startDate', 'Start date')"
                    />
                  </a-col>
                  <a-col :span="12">
                    <a-date-picker
                      v-model="strategyForm.endDate"
                      size="small"
                      style="width: 100%;"
                      :placeholder="tt('backtest-center.config.endDate', 'End date')"
                    />
                  </a-col>
                </a-row>
              </div>

              <div class="section">
                <div class="section-title">{{ tt('backtest-center.config.capital', 'Capital and execution') }}</div>
                <a-row :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.initialCapital', 'Initial capital') }}</div>
                    <a-input-number
                      v-model="strategyForm.initialCapital"
                      size="small"
                      :min="1000"
                      :step="1000"
                      :precision="2"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.leverage', 'Leverage') }}</div>
                    <a-input-number
                      v-model="strategyForm.leverage"
                      size="small"
                      :min="1"
                      :max="125"
                      :step="1"
                      :precision="0"
                      style="width: 100%;"
                    />
                  </a-col>
                </a-row>
                <a-row style="margin-top: 8px;" :gutter="8">
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.commission', 'Commission') }} (%)</div>
                    <a-input-number
                      v-model="strategyForm.commission"
                      size="small"
                      :min="0"
                      :max="10"
                      :step="0.01"
                      :precision="4"
                      style="width: 100%;"
                    />
                  </a-col>
                  <a-col :span="12">
                    <div class="field-label">{{ tt('backtest-center.config.slippage', 'Slippage') }} (%)</div>
                    <a-input-number
                      v-model="strategyForm.slippage"
                      size="small"
                      :min="0"
                      :max="10"
                      :step="0.01"
                      :precision="4"
                      style="width: 100%;"
                    />
                  </a-col>
                </a-row>
              </div>

              <div class="run-section">
                <a-button
                  type="primary"
                  block
                  size="large"
                  :loading="strategyRunning"
                  :disabled="!canRunStrategy"
                  @click="runStrategyBacktest"
                >
                  <a-icon v-if="!strategyRunning" type="thunderbolt" />
                  {{ strategyRunning ? tt('backtest-center.running', 'Running backtest...') : tt('backtest-center.strategy.runBacktest', 'Run strategy backtest') }}
                </a-button>
                <a-button block style="margin-top: 8px;" :disabled="!selectedStrategyId" @click="openHistory('strategy')">
                  <a-icon type="history" />
                  {{ tt('backtest-center.strategy.history', 'Backtest history') }}
                </a-button>
              </div>
            </div>
          </a-col>

          <a-col :xs="24" :md="15" :lg="16" class="result-col">
            <div class="result-panel">
              <result-view
                :running="strategyRunning"
                :run-tip="tt('backtest-center.runningDesc', 'This can take longer for larger time ranges and lower timeframes.')"
                :has-result="strategyHasResult"
                :result="strategyResult"
                :backtestRunId="strategyBacktestRunId"
                :symbol="strategyForm.symbol"
                :market="strategyForm.market"
                :timeframe="strategyForm.timeframe"
                :is-dark="isDarkTheme"
              />
            </div>
          </a-col>
        </a-row>
      </a-tab-pane>
    </a-tabs>

    <a-modal
      :title="tt('dashboard.analysis.modal.addStock.title', 'Add symbol')"
      :visible="showAddModal"
      :confirmLoading="addingStock"
      :width="isMobile ? '95%' : 560"
      :wrapClassName="isDarkTheme ? 'bc-modal-wrap bc-modal-wrap--dark' : 'bc-modal-wrap'"
      @ok="handleAddStock"
      @cancel="showAddModal = false"
    >
      <a-tabs size="small" :activeKey="addMarketTab" @change="onAddMarketTabChange">
        <a-tab-pane key="Crypto" tab="Crypto" />
        <a-tab-pane key="USStock" tab="US Stock" />
        <a-tab-pane key="HKStock" tab="HK Stock" />
        <a-tab-pane key="Forex" tab="Forex" />
        <a-tab-pane key="Futures" tab="Futures" />
      </a-tabs>

      <a-input-search
        v-model="addSearchKeyword"
        size="large"
        allow-clear
        :loading="addSearching"
        :placeholder="tt('backtest-center.config.symbolPlaceholder', 'Search by symbol or company name')"
        style="margin: 12px 0;"
        @search="doAddSearch"
        @change="onAddSearchInput"
      />

      <a-list
        v-if="addSearchResults.length > 0"
        :data-source="addSearchResults"
        size="small"
        class="add-search-results"
      >
        <a-list-item
          slot="renderItem"
          slot-scope="item"
          :class="{ 'add-item-active': addSelectedItem && addSelectedItem.symbol === item.symbol }"
          @click="addSelectedItem = item"
        >
          <strong>{{ item.symbol }}</strong>
          <span v-if="item.name" class="search-result-name">{{ item.name }}</span>
          <a-icon v-if="addSelectedItem && addSelectedItem.symbol === item.symbol" type="check-circle" theme="filled" class="search-result-check" />
        </a-list-item>
      </a-list>

      <div v-else-if="addSearchKeyword && addSearched" class="no-search-result">
        {{ tt('backtest-center.config.noSearchResult', 'No search result. You can still add the typed symbol directly.') }}
      </div>
    </a-modal>

    <backtest-history-drawer
      :visible="showHistoryDrawer"
      :userId="userId"
      :indicatorId="historyContext.indicatorId"
      :strategyId="historyContext.strategyId"
      :runType="historyContext.runType"
      :symbol="historyContext.symbol"
      :market="historyContext.market"
      :timeframe="historyContext.timeframe"
      :isMobile="isMobile"
      @cancel="showHistoryDrawer = false"
      @view="handleViewRun"
    />

    <backtest-run-viewer
      :visible="showRunViewer"
      :run="selectedRun"
      @cancel="handleCloseRunViewer"
    />
  </div>
</template>

<script>
import moment from 'moment'
import request from '@/utils/request'
import { getUserInfo } from '@/api/auth'
import { getStrategyList, runStrategyBacktest as runStrategyBacktestRequest } from '@/api/strategy'
import { getWatchlist, addWatchlist, searchSymbols, getHotSymbols } from '@/api/market'
import { baseMixin } from '@/store/app-mixin'
import ResultView from './components/ResultView.vue'
import BacktestHistoryDrawer from './components/BacktestHistoryDrawer.vue'
import BacktestRunViewer from '@/views/indicator-analysis/components/BacktestRunViewer.vue'

const TIMEFRAMES = ['1m', '5m', '15m', '1H', '4H', '1D', '1W']

const DATE_PRESETS = [
  { key: '7d', label: '7D', days: 7 },
  { key: '30d', label: '30D', days: 30 },
  { key: '90d', label: '90D', days: 90 },
  { key: '180d', label: '180D', days: 180 },
  { key: '1y', label: '1Y', days: 365 },
  { key: '3y', label: '3Y', days: 1095 }
]

function buildDateRangeState (days = 180, key = '180d') {
  const endDate = moment().startOf('day')
  const startDate = endDate.clone().subtract(days, 'days')
  return {
    datePreset: key,
    startDate,
    endDate
  }
}

function createIndicatorForm () {
  return {
    selectedWatchlistKey: undefined,
    symbol: '',
    market: 'Crypto',
    timeframe: '1D',
    initialCapital: 10000,
    leverage: 1,
    commission: 0.02,
    slippage: 0,
    tradeDirection: 'long',
    stopLossPct: 0,
    takeProfitPct: 0,
    entryPct: 100,
    trailingEnabled: false,
    trailingStopPct: 0,
    trailingActivationPct: 0,
    ...buildDateRangeState()
  }
}

function createStrategyForm () {
  return {
    selectedWatchlistKey: undefined,
    symbol: '',
    market: 'Crypto',
    timeframe: '1D',
    initialCapital: 10000,
    leverage: 1,
    commission: 0,
    slippage: 0,
    tradeDirection: 'long',
    ...buildDateRangeState()
  }
}

export default {
  name: 'BacktestCenter',
  mixins: [baseMixin],
  components: {
    ResultView,
    BacktestHistoryDrawer,
    BacktestRunViewer
  },
  data () {
    return {
      userId: 1,
      activeTab: 'indicator',
      timeframes: TIMEFRAMES,
      indicators: [],
      loadingIndicators: false,
      selectedIndicatorId: undefined,
      selectedIndicatorObj: null,
      strategies: [],
      loadingStrategies: false,
      selectedStrategyId: undefined,
      selectedStrategyObj: null,
      watchlist: [],
      loadingWatchlist: false,
      indicatorForm: createIndicatorForm(),
      strategyForm: createStrategyForm(),
      indicatorRunning: false,
      strategyRunning: false,
      indicatorResult: null,
      strategyResult: null,
      indicatorHasResult: false,
      strategyHasResult: false,
      indicatorBacktestRunId: null,
      strategyBacktestRunId: null,
      showHistoryDrawer: false,
      historyContext: {
        runType: 'indicator',
        indicatorId: null,
        strategyId: null,
        symbol: '',
        market: '',
        timeframe: ''
      },
      selectedRun: null,
      showRunViewer: false,
      showAddModal: false,
      addSymbolTarget: 'indicator',
      addMarketTab: 'Crypto',
      addSearchKeyword: '',
      addSearchResults: [],
      addSelectedItem: null,
      addSearching: false,
      addSearched: false,
      addingStock: false,
      addSearchTimer: null
    }
  },
  computed: {
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    indicatorDatePresets () {
      return this.getAllowedDatePresets(this.indicatorForm.timeframe)
    },
    strategyDatePresets () {
      return this.getAllowedDatePresets(this.strategyForm.timeframe)
    },
    indicatorTfLimitHint () {
      return this.getTimeframeLimitHint(this.indicatorForm.timeframe)
    },
    strategyTfLimitHint () {
      return this.getTimeframeLimitHint(this.strategyForm.timeframe)
    },
    canRunIndicator () {
      return Boolean(this.selectedIndicatorId && this.indicatorForm.symbol && this.indicatorForm.startDate && this.indicatorForm.endDate)
    },
    canRunStrategy () {
      return Boolean(this.selectedStrategyId && this.strategyForm.symbol && this.strategyForm.startDate && this.strategyForm.endDate && !this.selectedStrategyIsCrossSectional)
    },
    selectedStrategyIsCrossSectional () {
      if (!this.selectedStrategyObj) return false
      const tradingConfig = this.parseTradingConfig(this.selectedStrategyObj)
      const csType = String(tradingConfig.cs_strategy_type || tradingConfig.strategy_type || 'single').trim().toLowerCase()
      return csType === 'cross_sectional'
    },
    selectedStrategySymbol () {
      return this.strategyForm.symbol || ''
    },
    selectedStrategyMarket () {
      return this.strategyForm.market || ''
    }
  },
  watch: {
    activeTab (value) {
      this.setRouteQuery({ tab: value })
    },
    '$route.query': {
      deep: true,
      handler () {
        this.syncFromRoute()
      }
    },
    'indicatorForm.timeframe' (value) {
      this.enforceDateRangeLimit(this.indicatorForm, value)
    },
    'strategyForm.timeframe' (value) {
      this.enforceDateRangeLimit(this.strategyForm, value)
    }
  },
  async created () {
    await this.bootstrap()
  },
  beforeDestroy () {
    if (this.addSearchTimer) {
      clearTimeout(this.addSearchTimer)
      this.addSearchTimer = null
    }
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    async bootstrap () {
      await this.resolveUserId()
      await Promise.all([
        this.loadWatchlist(),
        this.loadIndicators(),
        this.loadStrategies()
      ])
      this.syncFromRoute()
      this.applyInitialDefaults()
    },
    async resolveUserId () {
      const storeUserInfo = (this.$store && this.$store.getters && this.$store.getters.userInfo) || {}
      if (storeUserInfo.id) {
        this.userId = storeUserInfo.id
        return
      }
      try {
        const res = await getUserInfo()
        if (res && res.code === 1 && res.data && res.data.id) {
          this.userId = res.data.id
          return
        }
      } catch (error) {
      }
      this.userId = 1
    },
    applyInitialDefaults () {
      if (!this.indicatorForm.symbol && this.watchlist.length > 0) {
        const first = this.watchlist[0]
        this.assignWatchlistSelection(this.indicatorForm, first)
      }
      if (!this.strategyForm.symbol && this.watchlist.length > 0 && !this.selectedStrategyObj) {
        const first = this.watchlist[0]
        this.assignWatchlistSelection(this.strategyForm, first)
      }
    },
    getAllowedDatePresets (timeframe) {
      const limitDays = this.getTimeframeLimitDays(timeframe)
      return DATE_PRESETS.filter(preset => preset.days <= limitDays)
    },
    getTimeframeLimitDays (timeframe) {
      if (timeframe === '1m') return 30
      if (timeframe === '5m') return 180
      if (timeframe === '15m' || timeframe === '30m') return 365
      return 1095
    },
    getTimeframeLimitHint (timeframe) {
      const days = this.getTimeframeLimitDays(timeframe)
      if (days === 30) return this.tt('backtest-center.config.limit30d', 'Max 30D')
      if (days === 180) return this.tt('backtest-center.config.limit180d', 'Max 180D')
      if (days === 365) return this.tt('backtest-center.config.limit1y', 'Max 1Y')
      return this.tt('backtest-center.config.limit3y', 'Max 3Y')
    },
    enforceDateRangeLimit (form, timeframe) {
      if (!form.startDate || !form.endDate) return
      const maxDays = this.getTimeframeLimitDays(timeframe)
      const diff = form.endDate.diff(form.startDate, 'days')
      if (diff <= maxDays) return
      const preset = this.getAllowedDatePresets(timeframe).slice(-1)[0]
      if (form === this.indicatorForm && preset) {
        this.applyIndicatorDatePreset(preset)
      }
      if (form === this.strategyForm && preset) {
        this.applyStrategyDatePreset(preset)
      }
    },
    applyIndicatorDatePreset (preset) {
      this.indicatorForm.datePreset = preset.key
      this.indicatorForm.endDate = moment().startOf('day')
      this.indicatorForm.startDate = this.indicatorForm.endDate.clone().subtract(preset.days, 'days')
    },
    applyStrategyDatePreset (preset) {
      this.strategyForm.datePreset = preset.key
      this.strategyForm.endDate = moment().startOf('day')
      this.strategyForm.startDate = this.strategyForm.endDate.clone().subtract(preset.days, 'days')
    },
    async loadIndicators () {
      this.loadingIndicators = true
      try {
        const res = await request({
          url: '/api/indicator/getIndicators',
          method: 'get',
          params: { userid: this.userId }
        })
        this.indicators = res && res.code === 1 && Array.isArray(res.data) ? res.data : []
      } finally {
        this.loadingIndicators = false
      }
    },
    async loadStrategies () {
      this.loadingStrategies = true
      try {
        const res = await getStrategyList()
        this.strategies = res && res.code === 1 && res.data && Array.isArray(res.data.strategies) ? res.data.strategies : []
      } finally {
        this.loadingStrategies = false
      }
    },
    async loadWatchlist () {
      this.loadingWatchlist = true
      try {
        const res = await getWatchlist({ userid: this.userId })
        this.watchlist = res && res.code === 1 && Array.isArray(res.data) ? res.data : []
      } finally {
        this.loadingWatchlist = false
      }
    },
    syncFromRoute () {
      const tab = String(this.$route.query.tab || '').trim()
      if (tab === 'indicator' || tab === 'strategy') {
        this.activeTab = tab
      }

      const indicatorId = this.$route.query.indicator_id
      if (indicatorId && this.indicators.length) {
        const exists = this.indicators.find(item => String(item.id) === String(indicatorId))
        if (exists && String(this.selectedIndicatorId || '') !== String(indicatorId)) {
          this.selectedIndicatorId = String(indicatorId)
          this.selectedIndicatorObj = exists
        }
      }

      const strategyId = this.$route.query.strategy_id
      if (strategyId && this.strategies.length) {
        const exists = this.strategies.find(item => String(item.id) === String(strategyId))
        if (exists && String(this.selectedStrategyId || '') !== String(strategyId)) {
          this.selectedStrategyId = String(strategyId)
          this.selectedStrategyObj = exists
          this.applyStrategyDefaults(exists)
        }
      }
    },
    setRouteQuery (patch) {
      const current = { ...this.$route.query }
      const next = { ...current }
      Object.keys(patch).forEach(key => {
        if (patch[key] === undefined || patch[key] === null || patch[key] === '') {
          delete next[key]
        } else {
          next[key] = patch[key]
        }
      })
      if (JSON.stringify(current) === JSON.stringify(next)) return
      this.$router.replace({ path: this.$route.path, query: next })
    },
    buildWatchlistKey (item) {
      const market = item && item.market ? item.market : ''
      const symbol = item && item.symbol ? item.symbol : ''
      return `${market}:${symbol}`
    },
    getWatchlistOptionLabel (item) {
      const base = `${item.market}:${item.symbol}`
      return item.name ? `${base} ${item.name}` : base
    },
    getMarketColor (market) {
      const colorMap = {
        Crypto: 'gold',
        USStock: 'blue',
        HKStock: 'geekblue',
        Forex: 'green',
        Futures: 'purple'
      }
      return colorMap[market] || 'default'
    },
    assignWatchlistSelection (form, item) {
      if (!item) return
      form.selectedWatchlistKey = this.buildWatchlistKey(item)
      form.market = item.market
      form.symbol = item.symbol
    },
    handleIndicatorWatchlistChange (value) {
      if (value === '__add__') {
        this.openAddModal('indicator')
        return
      }
      const item = this.watchlist.find(entry => this.buildWatchlistKey(entry) === value)
      if (item) {
        this.assignWatchlistSelection(this.indicatorForm, item)
      } else {
        this.indicatorForm.symbol = ''
      }
    },
    handleStrategyWatchlistChange (value) {
      if (value === '__add__') {
        this.openAddModal('strategy')
        return
      }
      const item = this.watchlist.find(entry => this.buildWatchlistKey(entry) === value)
      if (item) {
        this.assignWatchlistSelection(this.strategyForm, item)
      } else {
        this.strategyForm.symbol = ''
      }
    },
    handleIndicatorChange (value) {
      this.selectedIndicatorId = value || undefined
      this.selectedIndicatorObj = this.indicators.find(item => String(item.id) === String(value)) || null
      this.setRouteQuery({
        tab: 'indicator',
        indicator_id: value || undefined,
        strategy_id: undefined
      })
    },
    handleStrategyChange (value) {
      this.selectedStrategyId = value || undefined
      this.selectedStrategyObj = this.strategies.find(item => String(item.id) === String(value)) || null
      if (this.selectedStrategyObj) {
        this.applyStrategyDefaults(this.selectedStrategyObj)
      }
      this.setRouteQuery({
        tab: 'strategy',
        strategy_id: value || undefined,
        indicator_id: undefined
      })
    },
    parseTradingConfig (strategy) {
      const value = strategy && strategy.trading_config
      if (!value) return {}
      if (typeof value === 'object') return value
      try {
        return JSON.parse(value)
      } catch (error) {
        return {}
      }
    },
    applyStrategyDefaults (strategy) {
      const tradingConfig = this.parseTradingConfig(strategy)
      const rawSymbol = String(tradingConfig.symbol || strategy.symbol || '').trim()
      let market = String(strategy.market_category || tradingConfig.market_category || 'Crypto').trim() || 'Crypto'
      let symbol = rawSymbol
      if (rawSymbol.includes(':')) {
        const parts = rawSymbol.split(':')
        market = parts[0] || market
        symbol = parts[1] || symbol
      }

      this.strategyForm.market = market
      this.strategyForm.symbol = symbol
      this.strategyForm.timeframe = String(tradingConfig.timeframe || strategy.timeframe || '1D').trim() || '1D'
      this.strategyForm.initialCapital = Number(tradingConfig.initial_capital || strategy.initial_capital || 10000) || 10000
      this.strategyForm.leverage = Number(tradingConfig.leverage || strategy.leverage || 1) || 1
      this.strategyForm.commission = Number(tradingConfig.commission || 0) || 0
      this.strategyForm.slippage = Number(tradingConfig.slippage || 0) || 0
      this.strategyForm.tradeDirection = String(tradingConfig.trade_direction || 'long')

      const matchedWatchlist = this.watchlist.find(item => item.market === market && item.symbol === symbol)
      if (matchedWatchlist) {
        this.strategyForm.selectedWatchlistKey = this.buildWatchlistKey(matchedWatchlist)
      } else if (symbol) {
        this.strategyForm.selectedWatchlistKey = `${market}:${symbol}`
      }
    },
    strategyTypeLabel (strategy) {
      const mode = String(strategy.strategy_mode || '').trim()
      if (mode === 'script' || strategy.strategy_type === 'ScriptStrategy') {
        return this.tt('trading-assistant.strategyMode.script', 'Script')
      }
      return this.tt('trading-assistant.strategyMode.signal', 'Indicator')
    },
    strategyTypeColor (strategy) {
      const mode = String(strategy.strategy_mode || '').trim()
      return mode === 'script' || strategy.strategy_type === 'ScriptStrategy' ? 'green' : 'blue'
    },
    strategySummaryText (strategy) {
      const tradingConfig = this.parseTradingConfig(strategy)
      const symbol = this.strategyForm.symbol || tradingConfig.symbol || strategy.symbol || this.tt('backtest-center.strategy.anySymbol', 'No symbol')
      const timeframe = this.strategyForm.timeframe || tradingConfig.timeframe || strategy.timeframe || '1D'
      const mode = this.strategyTypeLabel(strategy)
      return `${mode} strategy prepared for ${symbol} on ${timeframe}. Override symbol, timeframe, or capital below before running a fresh backtest snapshot.`
    },
    goToStrategyAssistant () {
      if (this.selectedStrategyId) {
        this.$router.push(`/trading-assistant?tab=strategy&strategy_id=${this.selectedStrategyId}`)
        return
      }
      this.$router.push('/trading-assistant?tab=strategy')
    },
    validateDateRange (form) {
      if (!form.startDate || !form.endDate) {
        this.$message.warning(this.tt('backtest-center.validation.dateRange', 'Please select a valid date range.'))
        return false
      }
      if (form.endDate.isBefore(form.startDate, 'day')) {
        this.$message.warning(this.tt('backtest-center.validation.dateOrder', 'End date must be after start date.'))
        return false
      }
      const maxDays = this.getTimeframeLimitDays(form.timeframe)
      const diff = form.endDate.diff(form.startDate, 'days')
      if (diff > maxDays) {
        this.$message.warning(this.tt('backtest-center.validation.rangeExceeded', `This timeframe supports up to ${this.getTimeframeLimitHint(form.timeframe)}.`))
        return false
      }
      return true
    },
    buildIndicatorStrategyConfig () {
      const pct = value => Number(value || 0) / 100
      return {
        risk: {
          stopLossPct: pct(this.indicatorForm.stopLossPct),
          takeProfitPct: pct(this.indicatorForm.takeProfitPct),
          trailing: {
            enabled: !!this.indicatorForm.trailingEnabled,
            pct: pct(this.indicatorForm.trailingStopPct),
            activationPct: pct(this.indicatorForm.trailingActivationPct)
          }
        },
        position: {
          entryPct: pct(this.indicatorForm.entryPct)
        }
      }
    },
    async runIndicatorBacktest () {
      if (!this.canRunIndicator) return
      if (!this.validateDateRange(this.indicatorForm)) return

      this.indicatorRunning = true
      this.indicatorHasResult = false
      try {
        const pct = value => Number(value || 0) / 100
        const res = await request({
          url: '/api/indicator/backtest',
          method: 'post',
          data: {
            userid: this.userId,
            indicatorId: this.selectedIndicatorId,
            symbol: this.indicatorForm.symbol,
            market: this.indicatorForm.market,
            timeframe: this.indicatorForm.timeframe,
            startDate: this.indicatorForm.startDate.format('YYYY-MM-DD'),
            endDate: this.indicatorForm.endDate.format('YYYY-MM-DD'),
            initialCapital: this.indicatorForm.initialCapital,
            commission: pct(this.indicatorForm.commission),
            slippage: pct(this.indicatorForm.slippage),
            leverage: this.indicatorForm.leverage,
            tradeDirection: this.indicatorForm.tradeDirection,
            strategyConfig: this.buildIndicatorStrategyConfig(),
            enableMtf: String(this.indicatorForm.market || '').toLowerCase() === 'crypto'
          }
        })

        if (res && res.code === 1 && res.data) {
          this.indicatorResult = res.data.result || res.data
          this.indicatorBacktestRunId = res.data.runId || null
          this.indicatorHasResult = true
        } else {
          this.$message.error((res && res.msg) || this.tt('backtest-center.runFailed', 'Backtest failed.'))
        }
      } catch (error) {
        this.$message.error(this.tt('backtest-center.runFailed', 'Backtest failed.'))
      } finally {
        this.indicatorRunning = false
      }
    },
    async runStrategyBacktest () {
      if (!this.canRunStrategy) return
      if (!this.validateDateRange(this.strategyForm)) return
      if (this.selectedStrategyIsCrossSectional) {
        this.$message.warning(this.tt('backtest-center.strategy.crossSectionalBlocked', 'Cross-sectional strategies are not supported in strategy backtest yet.'))
        return
      }

      this.strategyRunning = true
      this.strategyHasResult = false
      try {
        const res = await runStrategyBacktestRequest({
          strategyId: Number(this.selectedStrategyId),
          startDate: this.strategyForm.startDate.format('YYYY-MM-DD'),
          endDate: this.strategyForm.endDate.format('YYYY-MM-DD'),
          overrideConfig: {
            symbol: this.strategyForm.symbol,
            market: this.strategyForm.market,
            timeframe: this.strategyForm.timeframe,
            initialCapital: this.strategyForm.initialCapital,
            leverage: this.strategyForm.leverage,
            commission: this.strategyForm.commission,
            slippage: this.strategyForm.slippage
          }
        })

        if (res && res.code === 1 && res.data) {
          this.strategyResult = res.data.result || res.data
          this.strategyBacktestRunId = res.data.runId || null
          this.strategyHasResult = true
        } else {
          this.$message.error((res && res.msg) || this.tt('backtest-center.runFailed', 'Backtest failed.'))
        }
      } catch (error) {
        this.$message.error(this.tt('backtest-center.runFailed', 'Backtest failed.'))
      } finally {
        this.strategyRunning = false
      }
    },
    openHistory (runType) {
      if (runType === 'strategy') {
        this.historyContext = {
          runType: 'strategy',
          indicatorId: null,
          strategyId: this.selectedStrategyId,
          symbol: this.strategyForm.symbol,
          market: this.strategyForm.market,
          timeframe: this.strategyForm.timeframe
        }
      } else {
        this.historyContext = {
          runType: 'indicator',
          indicatorId: this.selectedIndicatorId,
          strategyId: null,
          symbol: this.indicatorForm.symbol,
          market: this.indicatorForm.market,
          timeframe: this.indicatorForm.timeframe
        }
      }
      this.showHistoryDrawer = true
    },
    handleViewRun (run) {
      this.selectedRun = run
      this.showRunViewer = true
    },
    handleCloseRunViewer () {
      this.showRunViewer = false
      this.selectedRun = null
    },
    openAddModal (target) {
      this.addSymbolTarget = target
      this.showAddModal = true
      this.addMarketTab = target === 'strategy' ? (this.strategyForm.market || 'Crypto') : (this.indicatorForm.market || 'Crypto')
      this.addSearchKeyword = ''
      this.addSearchResults = []
      this.addSelectedItem = null
      this.addSearched = false
      this.loadHotSymbols(this.addMarketTab)
    },
    onAddMarketTabChange (market) {
      this.addMarketTab = market
      this.addSearchKeyword = ''
      this.addSearchResults = []
      this.addSelectedItem = null
      this.addSearched = false
      this.loadHotSymbols(market)
    },
    onAddSearchInput () {
      if (this.addSearchTimer) {
        clearTimeout(this.addSearchTimer)
      }
      if (!this.addSearchKeyword || !this.addSearchKeyword.trim()) {
        this.addSelectedItem = null
        this.addSearched = false
        this.loadHotSymbols(this.addMarketTab)
        return
      }
      this.addSearchTimer = setTimeout(() => {
        this.searchSymbolsInModal(this.addSearchKeyword)
      }, 350)
    },
    doAddSearch (keyword) {
      if (!keyword || !keyword.trim()) {
        this.loadHotSymbols(this.addMarketTab)
        return
      }
      this.searchSymbolsInModal(keyword)
    },
    async loadHotSymbols (market) {
      this.addSearching = true
      try {
        const res = await getHotSymbols({ market, limit: 20 })
        this.addSearchResults = res && res.code === 1 && Array.isArray(res.data) ? res.data : []
      } finally {
        this.addSearching = false
      }
    },
    async searchSymbolsInModal (keyword) {
      this.addSearching = true
      this.addSearched = true
      try {
        const res = await searchSymbols({
          market: this.addMarketTab,
          keyword: keyword.trim(),
          limit: 20
        })
        this.addSearchResults = res && res.code === 1 && Array.isArray(res.data) ? res.data : []
      } finally {
        this.addSearching = false
      }
    },
    async handleAddStock () {
      const symbol = (this.addSelectedItem && this.addSelectedItem.symbol) || (this.addSearchKeyword || '').trim()
      if (!symbol) {
        this.$message.warning(this.tt('backtest-center.validation.symbol', 'Please choose a symbol first.'))
        return
      }

      this.addingStock = true
      try {
        const res = await addWatchlist({
          userid: this.userId,
          market: this.addMarketTab,
          symbol
        })
        if (res && res.code === 1) {
          await this.loadWatchlist()
          const added = this.watchlist.find(item => item.market === this.addMarketTab && item.symbol === symbol) || {
            market: this.addMarketTab,
            symbol
          }
          if (this.addSymbolTarget === 'strategy') {
            this.assignWatchlistSelection(this.strategyForm, added)
          } else {
            this.assignWatchlistSelection(this.indicatorForm, added)
          }
          this.showAddModal = false
          this.$message.success(this.tt('backtest-center.addSymbolSuccess', 'Symbol added to watchlist.'))
        } else {
          this.$message.error((res && res.msg) || this.tt('backtest-center.addSymbolFailed', 'Failed to add symbol.'))
        }
      } catch (error) {
        this.$message.error(this.tt('backtest-center.addSymbolFailed', 'Failed to add symbol.'))
      } finally {
        this.addingStock = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.backtest-center {
  padding: 24px;
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.08), transparent 30%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
}

.page-header {
  margin-bottom: 18px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
}

.title-icon {
  color: #2563eb;
}

.page-subtitle {
  margin: 8px 0 0;
  max-width: 880px;
  color: #475569;
  font-size: 14px;
}

.workspace {
  margin-top: 4px;
}

.config-panel,
.result-panel {
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  padding: 18px;
}

.section + .section {
  margin-top: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.hint {
  font-size: 12px;
  color: #64748b;
  text-transform: none;
  letter-spacing: normal;
}

.field-label {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.date-presets {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.run-section {
  margin-top: 18px;
}

.strategy-summary-card {
  margin-top: 12px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.92), rgba(248, 250, 252, 0.96));
}

.strategy-summary-head,
.strategy-summary-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.strategy-summary-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.strategy-summary-meta {
  margin-top: 8px;
}

.strategy-summary-text {
  margin-top: 10px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.watchlist-option-name {
  margin-left: 6px;
  color: #64748b;
  font-size: 12px;
}

.add-option {
  text-align: center;
  color: #2563eb;
}

.add-search-results {
  max-height: 260px;
  overflow-y: auto;
}

.add-search-results :deep(.ant-list-item) {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.add-item-active {
  background: rgba(37, 99, 235, 0.08);
}

.search-result-name {
  color: #64748b;
}

.search-result-check {
  margin-left: auto;
  color: #16a34a;
}

.no-search-result {
  padding: 16px 0;
  text-align: center;
  color: #64748b;
}

.theme-dark {
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 30%),
    linear-gradient(180deg, #020617 0%, #0f172a 100%);

  .page-title,
  .section-title,
  .strategy-summary-title {
    color: #e2e8f0;
  }

  .page-subtitle,
  .field-label,
  .hint,
  .strategy-summary-text,
  .watchlist-option-name,
  .search-result-name,
  .no-search-result {
    color: #94a3b8;
  }

  .config-panel,
  .result-panel {
    border-color: rgba(148, 163, 184, 0.16);
    background: rgba(15, 23, 42, 0.88);
  }

  .strategy-summary-card {
    border-color: rgba(59, 130, 246, 0.22);
    background: linear-gradient(180deg, rgba(30, 41, 59, 0.92), rgba(15, 23, 42, 0.96));
  }
}

@media (max-width: 991px) {
  .backtest-center {
    padding: 16px;
  }

  .config-col {
    margin-bottom: 16px;
  }
}

@media (max-width: 767px) {
  .backtest-center {
    padding: 12px;
  }

  .page-title {
    font-size: 22px;
  }

  .config-panel,
  .result-panel {
    padding: 14px;
    border-radius: 20px;
  }

  .section-title {
    flex-direction: column;
    align-items: flex-start;
  }

  .date-presets {
    gap: 6px;
  }
}
</style>
