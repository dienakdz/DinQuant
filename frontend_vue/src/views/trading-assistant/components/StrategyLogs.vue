<template>
  <div class="strategy-logs" :class="{ 'theme-dark': isDark }">
    <div class="logs-toolbar">
      <div class="toolbar-left">
        <a-radio-group v-model="filterLevel" size="small" button-style="solid">
          <a-radio-button value="all">
            {{ tt('common.all', 'All') }} ({{ logs.length }})
          </a-radio-button>
          <a-radio-button value="trade">
            {{ tt('trading-assistant.logs.level.trade', 'Trade') }} ({{ countByLevel('trade') }})
          </a-radio-button>
          <a-radio-button value="signal">
            {{ tt('trading-assistant.logs.level.signal', 'Signal') }} ({{ countByLevel('signal') }})
          </a-radio-button>
          <a-radio-button value="error">
            {{ tt('trading-assistant.logs.level.error', 'Error') }} ({{ countByLevel('error') }})
          </a-radio-button>
        </a-radio-group>
      </div>
      <div class="toolbar-right">
        <a-switch size="small" :checked="autoRefresh" @change="toggleAutoRefresh" />
        <span class="auto-refresh-label">{{ tt('trading-assistant.logs.autoRefresh', 'Auto refresh') }}</span>
      </div>
    </div>

    <a-spin :spinning="loading">
      <div ref="logsContainer" class="logs-container custom-scrollbar">
        <div v-if="filteredLogs.length === 0" class="logs-empty">
          <a-icon type="file-text" />
          <p>{{ tt('trading-assistant.logs.noLogs', 'No logs yet') }}</p>
        </div>

        <div
          v-for="item in filteredLogs"
          :key="item.id || `${item.timestamp}-${item.message}`"
          class="log-entry"
          :class="`level-${item.level || 'info'}`"
        >
          <span class="log-time">{{ formatTime(item.timestamp) }}</span>
          <a-tag class="log-level" size="small" :color="getLevelColor(item.level)">
            {{ getLevelText(item.level) }}
          </a-tag>
          <span class="log-message">{{ item.message }}</span>
        </div>
      </div>
    </a-spin>
  </div>
</template>

<script>
import { getStrategyLogs } from '@/api/strategy'

export default {
  name: 'StrategyLogs',
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
      logs: [],
      filterLevel: 'all',
      autoRefresh: false,
      refreshTimer: null,
      loading: false
    }
  },
  computed: {
    filteredLogs () {
      if (this.filterLevel === 'all') {
        return this.logs
      }
      return this.logs.filter(item => item.level === this.filterLevel)
    }
  },
  watch: {
    strategyId: {
      immediate: true,
      handler (value) {
        if (value) {
          this.loadLogs()
        } else {
          this.logs = []
        }
      }
    }
  },
  beforeDestroy () {
    this.stopAutoRefresh()
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    async loadLogs () {
      if (!this.strategyId) return

      this.loading = true
      try {
        const res = await getStrategyLogs(this.strategyId, 200)
        if (res && res.code === 1 && Array.isArray(res.data)) {
          this.logs = res.data
          this.$nextTick(() => {
            this.scrollToBottom()
          })
        }
      } catch (error) {
      } finally {
        this.loading = false
      }
    },
    toggleAutoRefresh (checked) {
      this.autoRefresh = checked
      if (checked) {
        this.stopAutoRefresh()
        this.refreshTimer = setInterval(() => {
          this.loadLogs()
        }, 5000)
      } else {
        this.stopAutoRefresh()
      }
    },
    stopAutoRefresh () {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer)
        this.refreshTimer = null
      }
    },
    scrollToBottom () {
      const element = this.$refs.logsContainer
      if (element) {
        element.scrollTop = element.scrollHeight
      }
    },
    countByLevel (level) {
      return this.logs.filter(item => item.level === level).length
    },
    formatTime (value) {
      if (!value) return '--'
      try {
        const date = new Date(value)
        if (Number.isNaN(date.getTime())) {
          return value
        }
        return date.toLocaleTimeString('en-GB', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      } catch (error) {
        return value
      }
    },
    getLevelColor (level) {
      return {
        info: 'blue',
        warn: 'orange',
        error: 'red',
        trade: 'green',
        signal: 'purple'
      }[level] || 'default'
    },
    getLevelText (level) {
      const key = `trading-assistant.logs.level.${level}`
      const fallback = {
        info: 'Info',
        warn: 'Warn',
        error: 'Error',
        trade: 'Trade',
        signal: 'Signal'
      }[level] || String(level || 'info')
      return this.tt(key, fallback)
    }
  }
}
</script>

<style lang="less" scoped>
.strategy-logs {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 360px;

  .logs-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #64748b;
    font-size: 12px;
  }

  .logs-container {
    max-height: 420px;
    overflow-y: auto;
    padding: 14px;
    border: 1px solid #e5edf5;
    border-radius: 18px;
    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  }

  .logs-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 220px;
    color: #94a3b8;

    .anticon {
      margin-bottom: 12px;
      font-size: 32px;
    }
  }

  .log-entry {
    display: grid;
    grid-template-columns: 88px auto 1fr;
    gap: 10px;
    align-items: flex-start;
    padding: 10px 12px;
    border-radius: 12px;
    transition: background-color 0.2s ease;

    &:not(:last-child) {
      margin-bottom: 6px;
    }

    &.level-trade {
      background: rgba(34, 197, 94, 0.08);
    }

    &.level-signal {
      background: rgba(168, 85, 247, 0.08);
    }

    &.level-error {
      background: rgba(239, 68, 68, 0.08);
    }
  }

  .log-time {
    color: #64748b;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
    font-size: 12px;
    line-height: 22px;
  }

  .log-message {
    color: #0f172a;
    line-height: 1.55;
    word-break: break-word;
  }

  &.theme-dark {
    .toolbar-right {
      color: #94a3b8;
    }

    .logs-container {
      background: linear-gradient(180deg, #151d2f 0%, #101827 100%);
      border-color: #25324a;
    }

    .logs-empty,
    .log-time {
      color: #94a3b8;
    }

    .log-message {
      color: #e2e8f0;
    }
  }
}
</style>
