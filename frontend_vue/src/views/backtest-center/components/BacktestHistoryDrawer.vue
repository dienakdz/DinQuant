<template>
  <a-drawer
    class="backtest-history-drawer"
    :title="drawerTitle"
    :visible="visible"
    :width="isMobile ? '100%' : 1080"
    :maskClosable="true"
    @close="$emit('cancel')"
  >
    <div class="drawer-toolbar">
      <div class="toolbar-left">
        <a-button type="primary" icon="reload" size="small" :loading="loading" @click="loadRuns">
          {{ tt('dashboard.indicator.backtest.historyRefresh', 'Refresh') }}
        </a-button>
        <a-button
          v-if="canAIAnalyze"
          type="primary"
          ghost
          size="small"
          :disabled="selectedRowKeys.length === 0"
          :loading="analyzing"
          @click="handleAIAnalyze"
        >
          <a-icon type="bulb" />
          {{ tt('dashboard.indicator.backtest.historyAISuggest', 'AI suggestions') }}
        </a-button>
        <span v-if="canAIAnalyze && selectedRowKeys.length" class="selected-tip">
          {{ tt('dashboard.indicator.backtest.historySelectedCount', `${selectedRowKeys.length} runs selected`, { count: selectedRowKeys.length }) }}
        </span>
      </div>

      <div class="toolbar-right">
        <a-input
          v-model="filterSymbol"
          size="small"
          allow-clear
          :placeholder="tt('dashboard.indicator.backtest.historyFilterSymbol', 'Filter by symbol')"
          style="width: 170px;"
          @change="debouncedLoad"
        />
        <a-select
          v-model="filterTimeframe"
          size="small"
          allow-clear
          :placeholder="tt('dashboard.indicator.backtest.historyFilterTimeframe', 'Timeframe')"
          style="width: 110px;"
          @change="loadRuns"
        >
          <a-select-option v-for="tf in timeframes" :key="tf" :value="tf">{{ tf }}</a-select-option>
        </a-select>
      </div>
    </div>

    <a-table
      :columns="columns"
      :data-source="runs"
      :loading="loading"
      size="small"
      :pagination="{ pageSize: 15, size: 'small' }"
      rowKey="id"
      :scroll="{ x: 1000 }"
      :rowSelection="canAIAnalyze ? { selectedRowKeys, onChange: onRowSelectionChange } : null"
    >
      <template slot="symbol" slot-scope="text, record">
        <span class="symbol-cell">
          <strong>{{ record.symbol || '-' }}</strong>
          <a-tag v-if="record.market" size="small">{{ record.market }}</a-tag>
        </span>
      </template>
      <template slot="range" slot-scope="text, record">
        <span>{{ formatRange(record) }}</span>
      </template>
      <template slot="returnPct" slot-scope="text">
        <span v-if="text !== null && text !== undefined" :class="Number(text) >= 0 ? 'positive' : 'negative'">
          {{ Number(text) >= 0 ? '+' : '' }}{{ Number(text).toFixed(2) }}%
        </span>
        <span v-else>-</span>
      </template>
      <template slot="createdAt" slot-scope="text">
        <span>{{ formatLocalDateTime(text) }}</span>
      </template>
      <template slot="status" slot-scope="text">
        <a-tag :color="text === 'success' ? 'green' : text === 'failed' ? 'red' : 'blue'">
          {{ text === 'success' ? tt('dashboard.indicator.backtest.historyStatusSuccess', 'Success') : text === 'failed' ? tt('dashboard.indicator.backtest.historyStatusFailed', 'Failed') : text }}
        </a-tag>
      </template>
      <template slot="actions" slot-scope="text, record">
        <a-button type="link" size="small" :loading="detailLoadingId === record.id" @click="viewRun(record)">
          {{ tt('dashboard.indicator.backtest.historyView', 'View') }}
        </a-button>
      </template>
    </a-table>

    <a-empty v-if="!loading && runs.length === 0" :description="tt('dashboard.indicator.backtest.historyNoData', 'No backtest runs yet')" />

    <a-modal
      :title="tt('dashboard.indicator.backtest.historyAIAnalyzeTitle', 'AI suggestions')"
      :visible="showAIResult"
      :footer="null"
      :width="isMobile ? '100%' : 900"
      @cancel="showAIResult = false"
    >
      <div v-if="analyzing" class="ai-result-loading">
        <a-spin />
      </div>
      <div v-else class="ai-result-text">
        {{ aiResult || tt('dashboard.indicator.backtest.historyNoAIResult', 'No AI result available.') }}
      </div>
    </a-modal>
  </a-drawer>
</template>

<script>
import request from '@/utils/request'
import { getStrategyBacktestHistory, getStrategyBacktestRun } from '@/api/strategy'

export default {
  name: 'BacktestHistoryDrawer',
  props: {
    visible: { type: Boolean, default: false },
    userId: { type: [Number, String], default: 1 },
    indicatorId: { type: [Number, String], default: null },
    strategyId: { type: [Number, String], default: null },
    runType: { type: String, default: 'indicator' },
    symbol: { type: String, default: '' },
    market: { type: String, default: '' },
    timeframe: { type: String, default: '' },
    isMobile: { type: Boolean, default: false }
  },
  data () {
    return {
      loading: false,
      detailLoadingId: null,
      analyzing: false,
      showAIResult: false,
      aiResult: '',
      selectedRowKeys: [],
      filterSymbol: '',
      filterTimeframe: '',
      searchTimer: null,
      runs: [],
      timeframes: ['1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W']
    }
  },
  computed: {
    canAIAnalyze () {
      return this.runType === 'indicator'
    },
    drawerTitle () {
      return this.runType === 'strategy'
        ? this.tt('backtest-center.strategy.history', 'Strategy backtest history')
        : this.tt('backtest-center.indicator.history', 'Indicator backtest history')
    },
    columns () {
      return [
        { title: this.tt('dashboard.indicator.backtest.historyRunId', 'Run ID'), dataIndex: 'id', key: 'id', width: 86 },
        { title: this.tt('dashboard.indicator.backtest.symbol', 'Symbol'), key: 'symbol', width: 180, scopedSlots: { customRender: 'symbol' } },
        { title: this.tt('dashboard.indicator.backtest.timeframe', 'Timeframe'), dataIndex: 'timeframe', key: 'timeframe', width: 96 },
        { title: this.tt('dashboard.indicator.backtest.historyRange', 'Date range'), key: 'range', width: 220, scopedSlots: { customRender: 'range' } },
        { title: this.tt('dashboard.indicator.backtest.totalReturn', 'Total return'), dataIndex: 'total_return', key: 'total_return', width: 120, scopedSlots: { customRender: 'returnPct' } },
        { title: this.tt('dashboard.indicator.backtest.historyCreatedAt', 'Created at'), dataIndex: 'created_at', key: 'created_at', width: 170, scopedSlots: { customRender: 'createdAt' } },
        { title: this.tt('dashboard.indicator.backtest.historyStatus', 'Status'), dataIndex: 'status', key: 'status', width: 100, scopedSlots: { customRender: 'status' } },
        { title: this.tt('dashboard.indicator.backtest.historyActions', 'Actions'), key: 'actions', width: 90, scopedSlots: { customRender: 'actions' } }
      ]
    }
  },
  watch: {
    visible (value) {
      if (!value) return
      this.filterSymbol = this.symbol || ''
      this.filterTimeframe = this.timeframe || ''
      this.selectedRowKeys = []
      this.aiResult = ''
      this.showAIResult = false
      this.loadRuns()
    }
  },
  beforeDestroy () {
    if (this.searchTimer) {
      clearTimeout(this.searchTimer)
      this.searchTimer = null
    }
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    onRowSelectionChange (keys) {
      this.selectedRowKeys = keys || []
    },
    formatRange (record) {
      const start = (record && record.start_date) ? String(record.start_date).slice(0, 10) : ''
      const end = (record && record.end_date) ? String(record.end_date).slice(0, 10) : ''
      return `${start} ~ ${end}`
    },
    formatLocalDateTime (value) {
      if (!value) return '-'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString()
    },
    debouncedLoad () {
      if (this.searchTimer) {
        clearTimeout(this.searchTimer)
      }
      this.searchTimer = setTimeout(() => {
        this.loadRuns()
      }, 350)
    },
    async loadRuns () {
      this.loading = true
      try {
        const params = {
          limit: 100,
          offset: 0,
          symbol: (this.filterSymbol || '').trim(),
          market: this.market || '',
          timeframe: this.filterTimeframe || ''
        }

        let res
        if (this.runType === 'strategy') {
          res = await getStrategyBacktestHistory({
            ...params,
            strategyId: this.strategyId
          })
        } else {
          res = await request({
            url: '/api/indicator/backtest/history',
            method: 'get',
            params: {
              ...params,
              userid: this.userId,
              indicatorId: this.indicatorId
            }
          })
        }

        this.runs = res && res.code === 1 && Array.isArray(res.data) ? res.data : []
      } finally {
        this.loading = false
      }
    },
    async viewRun (record) {
      if (!record || !record.id) return
      this.detailLoadingId = record.id
      try {
        let res
        if (this.runType === 'strategy') {
          res = await getStrategyBacktestRun(record.id)
        } else {
          res = await request({
            url: '/api/indicator/backtest/get',
            method: 'get',
            params: { userid: this.userId, runId: record.id }
          })
        }

        if (res && res.code === 1 && res.data) {
          this.$emit('view', res.data)
        }
      } finally {
        this.detailLoadingId = null
      }
    },
    async handleAIAnalyze () {
      if (!this.canAIAnalyze || !this.selectedRowKeys.length) return
      this.analyzing = true
      this.showAIResult = true
      this.aiResult = ''
      try {
        const lang = (this.$i18n && this.$i18n.locale) ? this.$i18n.locale : 'en-US'
        const res = await request({
          url: '/api/indicator/backtest/aiAnalyze',
          method: 'post',
          data: {
            userid: this.userId,
            runIds: this.selectedRowKeys,
            lang
          }
        })
        if (res && res.code === 1 && res.data && res.data.analysis) {
          this.aiResult = res.data.analysis
        } else {
          this.aiResult = (res && res.msg) || this.tt('dashboard.indicator.backtest.historyNoAIResult', 'No AI result available.')
        }
      } finally {
        this.analyzing = false
      }
    }
  }
}
</script>

<style lang="less" scoped>
.drawer-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right,
.symbol-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.selected-tip {
  color: #64748b;
  font-size: 12px;
}

.ai-result-loading {
  padding: 16px 0;
}

.ai-result-text {
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  line-height: 1.6;
}

.positive {
  color: #16a34a;
  font-weight: 600;
}

.negative {
  color: #dc2626;
  font-weight: 600;
}
</style>
