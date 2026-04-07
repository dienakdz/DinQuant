<template>
  <div class="performance-analysis" :class="{ 'theme-dark': isDark }">
    <a-spin :spinning="loading">
      <div v-if="hasData" class="performance-shell">
        <div class="metrics-grid">
          <div class="metric-card" :class="getMetricClass(metrics.totalReturn)">
            <div class="metric-label">{{ tt('trading-assistant.performance.totalReturn', 'Total Return') }}</div>
            <div class="metric-value">{{ formatPercent(metrics.totalReturn) }}</div>
          </div>
          <div class="metric-card" :class="getMetricClass(metrics.annualReturn)">
            <div class="metric-label">{{ tt('trading-assistant.performance.annualReturn', 'Annual Return') }}</div>
            <div class="metric-value">{{ formatPercent(metrics.annualReturn) }}</div>
          </div>
          <div class="metric-card negative">
            <div class="metric-label">{{ tt('trading-assistant.performance.maxDrawdown', 'Max Drawdown') }}</div>
            <div class="metric-value">{{ formatPercent(metrics.maxDrawdown) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ tt('trading-assistant.performance.sharpe', 'Sharpe') }}</div>
            <div class="metric-value">{{ formatNumber(metrics.sharpe) }}</div>
          </div>
          <div class="metric-card" :class="getMetricClass(metrics.winRate - 0.5)">
            <div class="metric-label">{{ tt('trading-assistant.performance.winRate', 'Win Rate') }}</div>
            <div class="metric-value">{{ formatPercent(metrics.winRate) }}</div>
          </div>
          <div class="metric-card" :class="getMetricClass((metrics.profitFactor || 0) - 1)">
            <div class="metric-label">{{ tt('trading-assistant.performance.profitFactor', 'Profit Factor') }}</div>
            <div class="metric-value">{{ formatNumber(metrics.profitFactor) }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ tt('trading-assistant.performance.totalTrades', 'Trades') }}</div>
            <div class="metric-value">{{ metrics.totalTrades || 0 }}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">{{ tt('trading-assistant.performance.runningDays', 'Running Days') }}</div>
            <div class="metric-value">{{ metrics.runningDays || 0 }}</div>
          </div>
        </div>

        <div class="chart-section">
          <div class="chart-title">{{ tt('trading-assistant.performance.equityCurve', 'Equity Curve') }}</div>
          <div ref="equityChart" class="chart-container"></div>
        </div>

        <div class="chart-section">
          <div class="chart-title">{{ tt('trading-assistant.performance.dailyReturns', 'Daily Returns') }}</div>
          <div ref="dailyChart" class="chart-container chart-container-sm"></div>
        </div>
      </div>

      <a-empty
        v-else-if="!loading"
        class="performance-empty"
        :description="tt('trading-assistant.performance.noData', 'No performance data yet')"
      />
    </a-spin>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import { getStrategyEquityCurve } from '@/api/strategy'

export default {
  name: 'PerformanceAnalysis',
  props: {
    strategyId: {
      type: [Number, String],
      default: null
    },
    isDark: {
      type: Boolean,
      default: false
    }
  },
  data () {
    return {
      loading: false,
      metrics: {},
      equityData: [],
      dailyReturns: [],
      equityChartInstance: null,
      dailyChartInstance: null
    }
  },
  computed: {
    hasData () {
      return this.equityData.length > 0
    }
  },
  watch: {
    strategyId: {
      immediate: true,
      handler (value) {
        if (value) {
          this.loadData()
        } else {
          this.resetState()
        }
      }
    },
    isDark () {
      this.$nextTick(() => {
        this.renderCharts()
      })
    }
  },
  mounted () {
    window.addEventListener('resize', this.handleResize)
  },
  beforeDestroy () {
    window.removeEventListener('resize', this.handleResize)
    this.disposeCharts()
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    resetState () {
      this.metrics = {}
      this.equityData = []
      this.dailyReturns = []
      this.disposeCharts()
    },
    async loadData () {
      if (!this.strategyId) {
        this.resetState()
        return
      }

      this.loading = true
      try {
        const res = await getStrategyEquityCurve(this.strategyId)
        const rawData = res && res.data
        const curve = Array.isArray(rawData)
          ? rawData
          : (rawData && Array.isArray(rawData.equity_curve) ? rawData.equity_curve : [])

        this.equityData = curve
          .map(item => ({
            time: item.time || item.timestamp || item.created_at,
            equity: Number(item.equity ?? item.value ?? item.y ?? 0),
            trade_count: Number(item.trade_count || 0),
            win_count: Number(item.win_count || 0),
            gross_profit: Number(item.gross_profit || 0),
            gross_loss: Number(item.gross_loss || 0)
          }))
          .filter(item => Number.isFinite(item.equity))

        this.computeMetrics()
        this.$nextTick(() => {
          this.renderCharts()
        })
      } catch (error) {
        this.resetState()
      } finally {
        this.loading = false
      }
    },
    computeMetrics () {
      if (!this.equityData.length) {
        this.metrics = {}
        this.dailyReturns = []
        return
      }

      const values = this.equityData.map(item => item.equity)
      const first = values[0] || 1
      const last = values[values.length - 1] || first
      const totalReturn = first > 0 ? (last - first) / first : 0

      let peak = first || 1
      let maxDrawdown = 0
      const returns = []

      for (let i = 1; i < values.length; i++) {
        const prev = values[i - 1]
        const current = values[i]
        if (current > peak) {
          peak = current
        }
        if (peak > 0) {
          maxDrawdown = Math.min(maxDrawdown, (current - peak) / peak)
        }
        if (prev > 0) {
          returns.push((current - prev) / prev)
        }
      }

      this.dailyReturns = returns

      const periods = Math.max(values.length - 1, 1)
      const annualFactor = 365 / periods
      const annualReturn = first > 0 && last > 0 ? Math.pow(last / first, annualFactor) - 1 : 0

      const mean = returns.length ? returns.reduce((sum, value) => sum + value, 0) / returns.length : 0
      const variance = returns.length > 1
        ? returns.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / (returns.length - 1)
        : 0
      const std = variance > 0 ? Math.sqrt(variance) : 0
      const sharpe = std > 0 ? (mean / std) * Math.sqrt(365) : 0

      const winningReturns = returns.filter(value => value > 0)
      const losingReturns = returns.filter(value => value < 0)
      const grossProfit = losingReturns.length || winningReturns.length
        ? winningReturns.reduce((sum, value) => sum + value, 0)
        : this.equityData.reduce((sum, item) => sum + Math.max(item.gross_profit || 0, 0), 0)
      const grossLoss = losingReturns.length
        ? Math.abs(losingReturns.reduce((sum, value) => sum + value, 0))
        : Math.abs(this.equityData.reduce((sum, item) => sum + Math.min(item.gross_loss || 0, 0), 0))

      this.metrics = {
        totalReturn,
        annualReturn: Number.isFinite(annualReturn) ? annualReturn : 0,
        maxDrawdown: Math.abs(maxDrawdown),
        sharpe: Number.isFinite(sharpe) ? sharpe : 0,
        winRate: returns.length ? winningReturns.length / returns.length : 0,
        profitFactor: grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? grossProfit : 0),
        totalTrades: Math.max(values.length - 1, 0),
        runningDays: values.length
      }
    },
    renderCharts () {
      if (!this.hasData) {
        this.disposeCharts()
        return
      }

      this.renderEquityChart()
      this.renderDailyChart()
    },
    renderEquityChart () {
      if (!this.$refs.equityChart) return
      if (!this.equityChartInstance) {
        this.equityChartInstance = echarts.init(this.$refs.equityChart)
      }

      const textColor = this.isDark ? '#d1d4dc' : '#1f2937'
      const axisColor = this.isDark ? '#4b5563' : '#dbe2ea'
      const areaTop = this.isDark ? 'rgba(34, 197, 94, 0.35)' : 'rgba(34, 197, 94, 0.22)'
      const areaBottom = this.isDark ? 'rgba(59, 130, 246, 0.04)' : 'rgba(59, 130, 246, 0.02)'

      this.equityChartInstance.setOption({
        backgroundColor: 'transparent',
        grid: { left: 16, right: 16, top: 24, bottom: 30, containLabel: true },
        tooltip: {
          trigger: 'axis',
          backgroundColor: this.isDark ? '#111827' : '#ffffff',
          borderColor: axisColor,
          textStyle: { color: textColor },
          formatter: (params) => {
            const point = params && params[0]
            if (!point) return ''
            return `${point.axisValueLabel}<br/>${this.formatCurrency(point.data)}`
          }
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          axisLine: { lineStyle: { color: axisColor } },
          axisLabel: { color: textColor, margin: 12 },
          data: this.equityData.map(item => this.formatAxisTime(item.time))
        },
        yAxis: {
          type: 'value',
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: axisColor, opacity: 0.55 } },
          axisLabel: {
            color: textColor,
            formatter: value => this.formatCurrency(value)
          }
        },
        series: [{
          type: 'line',
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 3, color: '#22c55e' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: areaTop },
              { offset: 1, color: areaBottom }
            ])
          },
          data: this.equityData.map(item => item.equity)
        }]
      })
    },
    renderDailyChart () {
      if (!this.$refs.dailyChart) return
      if (!this.dailyChartInstance) {
        this.dailyChartInstance = echarts.init(this.$refs.dailyChart)
      }

      const textColor = this.isDark ? '#d1d4dc' : '#1f2937'
      const axisColor = this.isDark ? '#4b5563' : '#dbe2ea'

      this.dailyChartInstance.setOption({
        backgroundColor: 'transparent',
        grid: { left: 16, right: 16, top: 20, bottom: 30, containLabel: true },
        tooltip: {
          trigger: 'axis',
          backgroundColor: this.isDark ? '#111827' : '#ffffff',
          borderColor: axisColor,
          textStyle: { color: textColor },
          formatter: (params) => {
            const point = params && params[0]
            if (!point) return ''
            return `${point.axisValueLabel}<br/>${this.formatPercent(point.data)}`
          }
        },
        xAxis: {
          type: 'category',
          axisLine: { lineStyle: { color: axisColor } },
          axisLabel: { color: textColor },
          data: this.dailyReturns.map((_, index) => `#${index + 1}`)
        },
        yAxis: {
          type: 'value',
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: axisColor, opacity: 0.55 } },
          axisLabel: {
            color: textColor,
            formatter: value => this.formatPercent(value)
          }
        },
        series: [{
          type: 'bar',
          barWidth: '62%',
          data: this.dailyReturns.map(value => ({
            value,
            itemStyle: {
              color: value >= 0 ? '#22c55e' : '#ef4444',
              borderRadius: value >= 0 ? [6, 6, 0, 0] : [0, 0, 6, 6]
            }
          }))
        }]
      })
    },
    handleResize () {
      if (this.equityChartInstance) {
        this.equityChartInstance.resize()
      }
      if (this.dailyChartInstance) {
        this.dailyChartInstance.resize()
      }
    },
    disposeCharts () {
      if (this.equityChartInstance) {
        this.equityChartInstance.dispose()
        this.equityChartInstance = null
      }
      if (this.dailyChartInstance) {
        this.dailyChartInstance.dispose()
        this.dailyChartInstance = null
      }
    },
    formatAxisTime (time) {
      if (!time) return '--'
      const raw = Number(time)
      const date = Number.isFinite(raw)
        ? new Date(raw < 1e12 ? raw * 1000 : raw)
        : new Date(time)
      if (Number.isNaN(date.getTime())) return '--'
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
      })
    },
    formatPercent (value) {
      const number = Number(value || 0) * 100
      return `${number >= 0 ? '+' : ''}${number.toFixed(2)}%`
    },
    formatCurrency (value) {
      const number = Number(value || 0)
      return `$${number.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    },
    formatNumber (value) {
      return Number(value || 0).toFixed(2)
    },
    getMetricClass (value) {
      return {
        positive: Number(value) > 0,
        negative: Number(value) < 0
      }
    }
  }
}
</script>

<style lang="less" scoped>
.performance-analysis {
  width: 100%;

  .performance-shell {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
  }

  .metric-card {
    padding: 14px 16px;
    border: 1px solid #e5edf5;
    border-radius: 16px;
    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);

    &.positive {
      border-color: rgba(34, 197, 94, 0.32);
    }

    &.negative {
      border-color: rgba(239, 68, 68, 0.28);
    }
  }

  .metric-label {
    color: #64748b;
    font-size: 12px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }

  .metric-value {
    margin-top: 8px;
    color: #0f172a;
    font-size: 24px;
    font-weight: 700;
    line-height: 1.1;
  }

  .chart-section {
    border: 1px solid #e5edf5;
    border-radius: 18px;
    padding: 16px;
    background: #ffffff;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
  }

  .chart-title {
    margin-bottom: 14px;
    color: #0f172a;
    font-size: 15px;
    font-weight: 600;
  }

  .chart-container {
    height: 280px;
  }

  .chart-container-sm {
    height: 240px;
  }

  .performance-empty {
    padding: 54px 0;
  }

  &.theme-dark {
    .metric-card,
    .chart-section {
      background: linear-gradient(180deg, #151d2f 0%, #101827 100%);
      border-color: #25324a;
      box-shadow: none;
    }

    .metric-label {
      color: #94a3b8;
    }

    .metric-value,
    .chart-title {
      color: #e2e8f0;
    }
  }
}
</style>
