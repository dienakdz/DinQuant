<template>
  <div class="result-view" :class="{ 'theme-dark': isDark }">
    <div v-if="running" class="result-state result-state--loading">
      <a-spin size="large" />
      <div class="result-state-title">{{ tt('backtest-center.running', 'Running backtest...') }}</div>
      <div class="result-state-desc">{{ runTip || tt('backtest-center.runningDesc', 'This can take longer for larger time ranges and lower timeframes.') }}</div>
    </div>

    <div v-else-if="!hasResult || !safeResult" class="result-state">
      <div class="result-state-icon">
        <a-icon type="line-chart" />
      </div>
      <div class="result-state-title">{{ tt('backtest-center.result.placeholderTitle', 'Your backtest results will appear here') }}</div>
      <div class="result-state-desc">{{ tt('backtest-center.result.placeholderDesc', 'Configure the left panel, run a backtest, then inspect equity, trades, and risk metrics in one place.') }}</div>
    </div>

    <div v-else class="result-body">
      <div class="result-meta" v-if="symbol || timeframe || market">
        <a-tag v-if="market" size="small">{{ market }}</a-tag>
        <a-tag v-if="symbol" size="small">{{ symbol }}</a-tag>
        <a-tag v-if="timeframe" size="small">{{ timeframe }}</a-tag>
        <a-tag v-if="backtestRunId" color="blue" size="small">Run #{{ backtestRunId }}</a-tag>
      </div>

      <div class="metrics-grid">
        <div class="metric-card" :class="{ positive: metricValue('totalReturn') > 0, negative: metricValue('totalReturn') < 0 }">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.totalReturn', 'Total return') }}</div>
          <div class="metric-value">{{ formatPercent(safeResult.totalReturn) }}</div>
          <div class="metric-sub">{{ formatMoney(safeResult.totalProfit) }}</div>
        </div>
        <div class="metric-card" :class="{ positive: metricValue('annualReturn') > 0, negative: metricValue('annualReturn') < 0 }">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.annualReturn', 'Annual return') }}</div>
          <div class="metric-value">{{ formatPercent(safeResult.annualReturn) }}</div>
        </div>
        <div class="metric-card negative">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.maxDrawdown', 'Max drawdown') }}</div>
          <div class="metric-value">{{ formatPercent(safeResult.maxDrawdown) }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.sharpeRatio', 'Sharpe ratio') }}</div>
          <div class="metric-value">{{ formatNumber(safeResult.sharpeRatio, 2) }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.winRate', 'Win rate') }}</div>
          <div class="metric-value">{{ formatPercent(safeResult.winRate) }}</div>
        </div>
        <div class="metric-card" :class="{ positive: metricValue('profitFactor') >= 1.5, negative: metricValue('profitFactor') > 0 && metricValue('profitFactor') < 1 }">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.profitFactor', 'Profit factor') }}</div>
          <div class="metric-value">{{ formatNumber(safeResult.profitFactor, 2) }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.totalTrades', 'Total trades') }}</div>
          <div class="metric-value">{{ metricInteger('totalTrades') }}</div>
        </div>
        <div class="metric-card negative">
          <div class="metric-label">{{ tt('dashboard.indicator.backtest.totalCommission', 'Total commission') }}</div>
          <div class="metric-value">{{ formatMoney(-(Number(safeResult.totalCommission) || 0)) }}</div>
        </div>
      </div>

      <div class="panel-card">
        <div class="panel-title">{{ tt('dashboard.indicator.backtest.equityCurve', 'Equity curve') }}</div>
        <div ref="equityChartRef" class="equity-chart"></div>
      </div>

      <div class="panel-card">
        <div class="panel-title">{{ tt('dashboard.indicator.backtest.tradeHistory', 'Trade history') }}</div>
        <a-table
          :columns="tradeColumns"
          :data-source="safeResult.trades || []"
          :pagination="{ pageSize: 10, size: 'small' }"
          size="small"
          :scroll="{ x: 820 }"
          :rowKey="rowKey"
        >
          <template slot="type" slot-scope="text">
            <a-tag :color="getTradeTypeColor(text)">
              {{ getTradeTypeText(text) }}
            </a-tag>
          </template>
          <template slot="balance" slot-scope="text">
            <span class="money-emphasis">
              {{ formatMoney(text, false) }}
            </span>
          </template>
          <template slot="profit" slot-scope="text">
            <span :class="text > 0 ? 'positive' : text < 0 ? 'negative' : 'muted'">
              {{ formatMoney(text) }}
            </span>
          </template>
        </a-table>
      </div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'BacktestResultView',
  props: {
    running: { type: Boolean, default: false },
    runTip: { type: String, default: '' },
    hasResult: { type: Boolean, default: false },
    result: { type: Object, default: null },
    backtestRunId: { type: [Number, String], default: null },
    symbol: { type: String, default: '' },
    market: { type: String, default: '' },
    timeframe: { type: String, default: '' },
    isDark: { type: Boolean, default: false }
  },
  data () {
    return {
      equityChart: null
    }
  },
  computed: {
    safeResult () {
      if (!this.result) return null
      return this.result.result || this.result
    },
    tradeColumns () {
      return [
        { title: this.tt('dashboard.indicator.backtest.tradeTime', 'Trade time'), dataIndex: 'time', key: 'time', width: 170 },
        { title: this.tt('dashboard.indicator.backtest.tradeType', 'Trade type'), dataIndex: 'type', key: 'type', width: 150, scopedSlots: { customRender: 'type' } },
        { title: this.tt('dashboard.indicator.backtest.price', 'Price'), dataIndex: 'price', key: 'price', width: 120 },
        { title: this.tt('dashboard.indicator.backtest.amount', 'Amount'), dataIndex: 'amount', key: 'amount', width: 110 },
        { title: this.tt('dashboard.indicator.backtest.profit', 'Profit'), dataIndex: 'profit', key: 'profit', width: 120, scopedSlots: { customRender: 'profit' } },
        { title: this.tt('dashboard.indicator.backtest.balance', 'Balance'), dataIndex: 'balance', key: 'balance', width: 140, scopedSlots: { customRender: 'balance' } }
      ]
    }
  },
  watch: {
    result: {
      deep: true,
      handler () {
        this.$nextTick(() => {
          this.renderEquityChart()
        })
      }
    },
    isDark () {
      this.$nextTick(() => {
        this.renderEquityChart()
      })
    }
  },
  mounted () {
    window.addEventListener('resize', this.handleResize)
    this.$nextTick(() => {
      this.renderEquityChart()
    })
  },
  beforeDestroy () {
    window.removeEventListener('resize', this.handleResize)
    this.disposeChart()
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    rowKey (record, index) {
      return (record && record.id) || index
    },
    metricValue (key) {
      return Number(this.safeResult && this.safeResult[key]) || 0
    },
    metricInteger (key) {
      return Number(this.safeResult && this.safeResult[key]) || 0
    },
    formatNumber (value, precision = 2) {
      const number = Number(value)
      if (!Number.isFinite(number)) return '--'
      return number.toFixed(precision)
    },
    formatPercent (value) {
      const number = Number(value)
      if (!Number.isFinite(number)) return '--'
      const sign = number >= 0 ? '+' : ''
      return `${sign}${number.toFixed(2)}%`
    },
    formatMoney (value, signed = true) {
      const number = Number(value)
      if (!Number.isFinite(number)) return '--'
      const abs = Math.abs(number).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      if (!signed) return `$${abs}`
      const sign = number >= 0 ? '+' : '-'
      return `${sign}$${abs}`
    },
    getTradeTypeColor (type) {
      const colorMap = {
        buy: 'green',
        sell: 'red',
        liquidation: 'orange',
        open_long: 'green',
        add_long: 'cyan',
        close_long: 'orange',
        close_long_stop: 'red',
        close_long_profit: 'lime',
        close_long_trailing: 'gold',
        reduce_long: 'volcano',
        open_short: 'red',
        add_short: 'magenta',
        close_short: 'blue',
        close_short_stop: 'red',
        close_short_profit: 'cyan',
        close_short_trailing: 'gold',
        reduce_short: 'volcano'
      }
      return colorMap[type] || 'default'
    },
    getTradeTypeText (type) {
      const map = {
        open_long: this.tt('dashboard.indicator.backtest.openLong', 'Open long'),
        add_long: this.tt('dashboard.indicator.backtest.addLong', 'Add long'),
        close_long: this.tt('dashboard.indicator.backtest.closeLong', 'Close long'),
        close_long_stop: this.tt('dashboard.indicator.backtest.closeLongStop', 'Close long stop'),
        close_long_profit: this.tt('dashboard.indicator.backtest.closeLongProfit', 'Close long take-profit'),
        close_long_trailing: this.tt('dashboard.indicator.backtest.closeLongTrailing', 'Close long trailing'),
        reduce_long: this.tt('dashboard.indicator.backtest.reduceLong', 'Reduce long'),
        open_short: this.tt('dashboard.indicator.backtest.openShort', 'Open short'),
        add_short: this.tt('dashboard.indicator.backtest.addShort', 'Add short'),
        close_short: this.tt('dashboard.indicator.backtest.closeShort', 'Close short'),
        close_short_stop: this.tt('dashboard.indicator.backtest.closeShortStop', 'Close short stop'),
        close_short_profit: this.tt('dashboard.indicator.backtest.closeShortProfit', 'Close short take-profit'),
        close_short_trailing: this.tt('dashboard.indicator.backtest.closeShortTrailing', 'Close short trailing'),
        reduce_short: this.tt('dashboard.indicator.backtest.reduceShort', 'Reduce short'),
        liquidation: this.tt('dashboard.indicator.backtest.liquidation', 'Liquidation')
      }
      return map[type] || type
    },
    disposeChart () {
      if (this.equityChart) {
        this.equityChart.dispose()
        this.equityChart = null
      }
    },
    handleResize () {
      if (this.equityChart) {
        this.equityChart.resize()
      }
    },
    renderEquityChart () {
      if (!this.$refs.equityChartRef || !this.safeResult || !Array.isArray(this.safeResult.equityCurve)) {
        this.disposeChart()
        return
      }

      const data = this.safeResult.equityCurve || []
      if (!data.length) {
        this.disposeChart()
        return
      }

      if (this.equityChart) {
        this.equityChart.dispose()
      }
      this.equityChart = echarts.init(this.$refs.equityChartRef)

      const dates = data.map(item => item.time || item.date)
      const equity = data.map(item => item.value !== undefined ? item.value : item.equity)
      const initialValue = equity[0] || 0
      const finalValue = equity[equity.length - 1] || initialValue
      const positive = finalValue >= initialValue
      const lineColor = positive ? '#22c55e' : '#ef4444'
      const axisColor = this.isDark ? '#94a3b8' : '#64748b'
      const splitColor = this.isDark ? 'rgba(148, 163, 184, 0.14)' : 'rgba(148, 163, 184, 0.18)'
      const areaStops = positive
        ? [{ offset: 0, color: 'rgba(34, 197, 94, 0.30)' }, { offset: 1, color: 'rgba(34, 197, 94, 0.02)' }]
        : [{ offset: 0, color: 'rgba(239, 68, 68, 0.30)' }, { offset: 1, color: 'rgba(239, 68, 68, 0.02)' }]

      this.equityChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          valueFormatter: value => (Number.isFinite(Number(value)) ? `$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : value)
        },
        grid: { left: 20, right: 20, bottom: 24, top: 16, containLabel: true },
        xAxis: {
          type: 'category',
          data: dates,
          boundaryGap: false,
          axisLabel: { color: axisColor },
          axisLine: { lineStyle: { color: splitColor } }
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            color: axisColor,
            formatter: value => `$${Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
          },
          splitLine: { lineStyle: { color: splitColor } }
        },
        series: [
          {
            name: this.tt('dashboard.indicator.backtest.strategy', 'Strategy'),
            type: 'line',
            data: equity,
            smooth: 0.35,
            symbol: 'none',
            sampling: 'lttb',
            lineStyle: { width: 2.5, color: lineColor },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, areaStops)
            }
          }
        ]
      })
    }
  }
}
</script>

<style lang="less" scoped>
.result-view {
  min-height: 560px;
}

.result-state {
  min-height: 560px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px 24px;
  border: 1px dashed #cbd5e1;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.96));

  &--loading {
    border-style: solid;
  }
}

.result-state-icon {
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  margin-bottom: 16px;
}

.result-state-title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin-top: 14px;
}

.result-state-desc {
  color: #64748b;
  margin-top: 8px;
  max-width: 520px;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 16px;
}

.metric-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.metric-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.metric-sub {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
}

.metric-card.positive .metric-value,
.positive {
  color: #16a34a;
}

.metric-card.negative .metric-value,
.negative {
  color: #dc2626;
}

.muted {
  color: #64748b;
}

.panel-card {
  margin-top: 14px;
  border-radius: 22px;
  border: 1px solid #e2e8f0;
  background: #fff;
  padding: 16px;
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 12px;
}

.equity-chart {
  height: 320px;
}

.money-emphasis {
  font-weight: 600;
  color: #2563eb;
}

.theme-dark {
  .result-state {
    border-color: rgba(148, 163, 184, 0.2);
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.96));
  }

  .result-state-title,
  .metric-value,
  .panel-title {
    color: #e2e8f0;
  }

  .result-state-desc,
  .metric-label,
  .metric-sub,
  .muted {
    color: #94a3b8;
  }

  .metric-card,
  .panel-card {
    border-color: rgba(148, 163, 184, 0.16);
    background: rgba(15, 23, 42, 0.86);
  }
}

@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .result-view,
  .result-state {
    min-height: 420px;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .equity-chart {
    height: 260px;
  }
}
</style>
