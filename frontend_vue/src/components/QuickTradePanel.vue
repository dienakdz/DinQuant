<template>
  <a-drawer
    class="quick-trade-drawer"
    :class="{ 'theme-dark': isDark }"
    :title="null"
    :width="380"
    :visible="visible"
    :closable="false"
    :body-style="{ padding: 0 }"
    @close="handleClose"
  >
    <div class="qt-header">
      <div class="qt-header-left">
        <a-icon class="qt-icon" type="thunderbolt" theme="filled" />
        <span class="qt-header-title">{{ tt('quickTrade.title', 'Quick Trade') }}</span>
      </div>
      <a-icon class="qt-close" type="close" @click="handleClose" />
    </div>

    <div class="qt-symbol-bar">
      <a-select
        v-model="currentSymbol"
        show-search
        style="width: 100%"
        :filter-option="false"
        :loading="symbolSearching"
        :placeholder="tt('quickTrade.selectSymbol', 'Select symbol')"
        :not-found-content="symbolSearching ? tt('common.loading', 'Loading...') : tt('common.noData', 'No data')"
        @search="handleSymbolSearch"
        @change="handleSymbolChange"
        @focus="handleSymbolFocus"
      >
        <a-select-option v-for="item in symbolSuggestions" :key="item.value" :value="item.value">
          <div class="qt-symbol-option">
            <span class="qt-symbol-option-name">{{ item.symbol }}</span>
            <span v-if="item.name" class="qt-symbol-option-desc">{{ item.name }}</span>
          </div>
        </a-select-option>
      </a-select>
      <div class="qt-price">${{ formatPrice(currentPrice) }}</div>
    </div>

    <div class="qt-section">
      <div class="qt-label">
        {{ tt('quickTrade.exchange', 'Exchange') }}
        <span class="qt-crypto-hint">{{ tt('quickTrade.cryptoOnly', 'Crypto only') }}</span>
      </div>
      <a-select
        v-model="selectedCredentialId"
        style="width: 100%"
        :loading="credLoading"
        :placeholder="tt('quickTrade.selectExchange', 'Select exchange')"
        :not-found-content="tt('quickTrade.noExchange', 'No exchange credential')"
        @change="onCredentialChange"
      >
        <a-select-option v-for="item in credentials" :key="item.id" :value="item.id">
          <span class="qt-credential-name">{{ item.exchange_id || item.name }}</span>
          <a-tag v-if="item.enable_demo_trading" color="orange" size="small">{{ tt('quickTrade.testnetTag', 'Testnet') }}</a-tag>
          <a-tag v-if="item.market_type" size="small">{{ item.market_type }}</a-tag>
        </a-select-option>
      </a-select>
      <div class="qt-manage-link">
        <router-link to="/profile?tab=exchange">
          <a-icon type="setting" />
          {{ tt('profile.exchange.goToManage', 'Manage exchange credentials') }}
        </router-link>
      </div>
      <div v-if="balance.available > 0" class="qt-balance">
        <span>{{ tt('quickTrade.available', 'Available') }}</span>
        <strong>${{ formatPrice(balance.available) }}</strong>
      </div>
    </div>

    <div class="qt-section">
      <div class="qt-direction-toggle">
        <div class="qt-dir-btn qt-dir-long" :class="{ active: side === 'buy' }" @click="side = 'buy'">
          <a-icon type="arrow-up" /> {{ tt('quickTrade.long', 'Long') }}
        </div>
        <div class="qt-dir-btn qt-dir-short" :class="{ active: side === 'sell' }" @click="side = 'sell'">
          <a-icon type="arrow-down" /> {{ tt('quickTrade.short', 'Short') }}
        </div>
      </div>
    </div>

    <div class="qt-section">
      <a-radio-group v-model="orderType" button-style="solid" size="small" style="width: 100%">
        <a-radio-button value="market" style="width: 50%; text-align: center">{{ tt('quickTrade.market', 'Market') }}</a-radio-button>
        <a-radio-button value="limit" style="width: 50%; text-align: center">{{ tt('quickTrade.limit', 'Limit') }}</a-radio-button>
      </a-radio-group>
    </div>

    <div v-if="orderType === 'limit'" class="qt-section">
      <div class="qt-label">{{ tt('quickTrade.limitPrice', 'Limit price') }}</div>
      <a-input-number v-model="limitPrice" style="width: 100%" :min="0" :step="priceStep" :precision="pricePrecision" />
    </div>

    <div class="qt-section">
      <div class="qt-label">{{ tt('quickTrade.amount', 'Amount') }} (USDT)</div>
      <a-input-number v-model="amount" style="width: 100%" :min="1" :step="10" :precision="2" />
      <div class="qt-quick-amounts">
        <a-button v-for="pct in quickAmountPcts" :key="pct" size="small" :disabled="balance.available <= 0" @click="setAmountByPercent(pct)">
          {{ pct }}%
        </a-button>
      </div>
    </div>

    <div v-if="selectedMarketType !== 'spot'" class="qt-section">
      <div class="qt-label">{{ tt('quickTrade.leverage', 'Leverage') }}</div>
      <div class="qt-leverage-row">
        <a-slider
          v-model="leverage"
          style="flex: 1; margin-right: 12px"
          :min="1"
          :max="125"
          :marks="leverageMarks"
          :tip-formatter="value => `${value}x`"
        />
        <a-input-number
          v-model="leverage"
          style="width: 80px"
          :min="1"
          :max="125"
          :formatter="value => `${value}x`"
          :parser="value => value.replace('x', '')"
        />
      </div>
    </div>

    <a-collapse :bordered="false" style="background: transparent; margin: 0 16px">
      <a-collapse-panel key="tpsl" :header="tt('quickTrade.tpsl', 'Take profit / stop loss')" :style="collapseStyle">
        <div class="qt-tpsl-row">
          <div class="qt-tpsl-item">
            <span class="qt-label qt-green">{{ tt('quickTrade.tp', 'TP') }}</span>
            <a-input-number v-model="tpPrice" style="width: 100%" :min="0" :step="priceStep" :precision="pricePrecision" />
          </div>
          <div class="qt-tpsl-item">
            <span class="qt-label qt-red">{{ tt('quickTrade.sl', 'SL') }}</span>
            <a-input-number v-model="slPrice" style="width: 100%" :min="0" :step="priceStep" :precision="pricePrecision" />
          </div>
        </div>
      </a-collapse-panel>
    </a-collapse>

    <div class="qt-submit-section">
      <a-button
        class="qt-submit-btn"
        :class="side === 'buy' ? 'qt-btn-long' : 'qt-btn-short'"
        :type="side === 'buy' ? 'primary' : 'danger'"
        size="large"
        block
        :loading="submitting"
        :disabled="!canSubmit"
        @click="handleSubmit"
      >
        <a-icon :type="side === 'buy' ? 'arrow-up' : 'arrow-down'" />
        {{ side === 'buy' ? tt('quickTrade.buyLong', 'Buy / Long') : tt('quickTrade.sellShort', 'Sell / Short') }}
      </a-button>
    </div>

    <div class="qt-panel">
      <div class="qt-section-title"><a-icon type="wallet" /> {{ tt('quickTrade.currentPosition', 'Current position') }}</div>
      <div v-if="currentPosition" class="qt-position-card" :class="currentPosition.side">
        <div class="qt-row"><span>{{ tt('quickTrade.side', 'Side') }}</span><a-tag :color="currentPosition.side === 'long' ? '#52c41a' : '#f5222d'" size="small">{{ currentPosition.side === 'long' ? tt('quickTrade.long', 'Long') : tt('quickTrade.short', 'Short') }}</a-tag></div>
        <div class="qt-row"><span>{{ tt('quickTrade.posSize', 'Size') }}</span><span>{{ currentPosition.size }}</span></div>
        <div class="qt-row"><span>{{ tt('quickTrade.entryPrice', 'Entry') }}</span><span>${{ formatPrice(currentPosition.entry_price) }}</span></div>
        <div v-if="currentPosition.mark_price" class="qt-row"><span>{{ tt('quickTrade.markPrice', 'Mark') }}</span><span>${{ formatPrice(currentPosition.mark_price) }}</span></div>
        <div class="qt-row"><span>{{ tt('quickTrade.unrealizedPnl', 'PnL') }}</span><span :class="Number(currentPosition.unrealized_pnl) >= 0 ? 'qt-green' : 'qt-red'">${{ formatPrice(currentPosition.unrealized_pnl) }}</span></div>
        <a-button
          type="danger"
          size="small"
          ghost
          block
          :loading="closingPosition"
          style="margin-top: 8px"
          @click="handleClosePosition"
        >
          {{ tt('quickTrade.closePosition', 'Close position') }}
        </a-button>
      </div>
      <div v-else class="qt-empty">
        <div class="qt-empty-title">{{ tt('quickTrade.noPosition', 'No open position') }}</div>
        <div class="qt-empty-hint">{{ tt('quickTrade.noPositionHint', 'Open a trade to see live position data here.') }}</div>
      </div>
    </div>

    <div v-if="recentTrades.length > 0" class="qt-panel">
      <a-collapse :bordered="false" :active-key="historyCollapsed ? [] : ['history']" @change="handleHistoryCollapse">
        <a-collapse-panel key="history" :show-arrow="false" :style="collapseStyle">
          <template slot="header">
            <div class="qt-history-header">
              <span><a-icon type="history" /> {{ tt('quickTrade.recentTrades', 'Recent trades') }}</span>
              <span>({{ recentTrades.length }})</span>
            </div>
          </template>
          <div class="qt-trade-list">
            <div v-for="item in recentTrades" :key="item.id" class="qt-trade-item">
              <div class="qt-trade-main">
                <a-tag :color="item.side === 'buy' ? '#52c41a' : '#f5222d'" size="small">{{ item.side === 'buy' ? 'LONG' : 'SHORT' }}</a-tag>
                <span class="qt-trade-symbol">{{ item.symbol }}</span>
                <span class="qt-trade-amount">${{ formatPrice(item.amount) }}</span>
              </div>
              <div class="qt-trade-meta">
                <a-tag :color="item.status === 'filled' ? '#52c41a' : (item.status === 'failed' ? '#f5222d' : '#faad14')" size="small">{{ item.status }}</a-tag>
                <span>{{ formatTime(item.created_at) }}</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>
      </a-collapse>
    </div>
  </a-drawer>
</template>

<script>
import { mapState } from 'vuex'
import request from '@/utils/request'
import { getWatchlist, getHotSymbols, searchSymbols } from '@/api/market'
import { listExchangeCredentials } from '@/api/credentials'
import { closeQuickTradePosition, getQuickTradeBalance, getQuickTradeHistory, getQuickTradePosition, placeQuickTradeOrder } from '@/api/quick-trade'

export default {
  name: 'QuickTradePanel',
  props: {
    visible: { type: Boolean, default: false },
    symbol: { type: String, default: '' },
    presetSide: { type: String, default: '' },
    presetPrice: { type: Number, default: 0 },
    source: { type: String, default: 'manual' },
    marketType: { type: String, default: 'swap' }
  },
  data () {
    return {
      credentials: [],
      selectedCredentialId: undefined,
      credLoading: false,
      balance: { available: 0, total: 0 },
      side: 'buy',
      orderType: 'market',
      limitPrice: 0,
      amount: 100,
      leverage: 5,
      tpPrice: null,
      slPrice: null,
      submitting: false,
      closingPosition: false,
      currentPrice: 0,
      currentPosition: null,
      recentTrades: [],
      historyCollapsed: false,
      currentSymbol: '',
      symbolSuggestions: [],
      symbolSearching: false,
      symbolSearchTimer: null,
      pollTimer: null,
      quickAmountPcts: [10, 25, 50, 75, 100],
      leverageMarks: { 1: '1x', 5: '5x', 10: '10x', 25: '25x', 50: '50x', 100: '100x', 125: '125x' }
    }
  },
  computed: {
    ...mapState({ navTheme: state => state.app.theme }),
    isDark () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    priceStep () {
      if (this.currentPrice > 10000) return 1
      if (this.currentPrice > 100) return 0.1
      if (this.currentPrice > 1) return 0.01
      return 0.0001
    },
    pricePrecision () {
      if (this.currentPrice > 10000) return 0
      if (this.currentPrice > 100) return 1
      if (this.currentPrice > 1) return 2
      return 4
    },
    canSubmit () {
      if (!this.selectedCredentialId || !this.currentSymbol || this.amount <= 0 || this.submitting) return false
      return this.orderType !== 'limit' || this.limitPrice > 0
    },
    collapseStyle () {
      return { background: 'transparent', borderRadius: '4px', border: 0, overflow: 'hidden' }
    },
    selectedMarketType () {
      return this.marketType === 'spot' ? 'spot' : 'swap'
    }
  },
  watch: {
    visible (value) {
      if (value) this.init()
      else this.stopPolling()
    },
    symbol: {
      immediate: true,
      handler (value) {
        if (value) this.currentSymbol = this.normalizeCryptoSymbol(value)
      }
    },
    currentSymbol (value) {
      if (!value) return
      this.loadPrice()
      if (this.selectedCredentialId) this.loadPosition()
      this.$emit('update:symbol', value)
    },
    selectedCredentialId (value) {
      if (!value) return
      this.loadBalance()
      if (this.currentSymbol) this.loadPosition()
    },
    presetSide (value) {
      if (value) this.side = value
    },
    presetPrice (value) {
      if (value > 0) {
        this.currentPrice = value
        this.limitPrice = value
      }
    }
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    normalizeCryptoSymbol (value) {
      if (!value) return ''
      let symbol = String(value).trim()
      if (symbol.includes(':')) symbol = symbol.split(':').pop()
      symbol = symbol.toUpperCase().replace(':USDT', '/USDT')
      if (symbol.includes('/')) return symbol
      if (symbol.endsWith('USDT') && symbol.length > 4) return `${symbol.slice(0, -4)}/USDT`
      return `${symbol}/USDT`
    },
    toSuggestion (item) {
      const symbol = this.normalizeCryptoSymbol(item.symbol || item.value || '')
      return symbol ? { value: symbol, symbol, name: item.name || '' } : null
    },
    async init () {
      this.currentSymbol = this.normalizeCryptoSymbol(this.symbol || this.currentSymbol)
      if (this.presetSide) this.side = this.presetSide
      if (this.presetPrice > 0) {
        this.currentPrice = this.presetPrice
        this.limitPrice = this.presetPrice
      }
      this.leverage = this.selectedMarketType === 'spot' ? 1 : Math.max(this.leverage, 5)
      await this.loadCredentials()
      await this.loadWatchlistSymbols()
      if (this.currentSymbol) await this.loadPrice()
      if (this.selectedCredentialId && this.currentSymbol) await this.loadPosition()
      await this.loadHistory()
      this.startPolling()
    },
    async loadWatchlistSymbols () {
      try {
        const [watchlistRes, hotRes] = await Promise.all([getWatchlist({}), getHotSymbols({ market: 'Crypto', limit: 12 })])
        const merged = []
        ;[...(watchlistRes && watchlistRes.code === 1 ? (watchlistRes.data || []) : []), ...(hotRes && hotRes.code === 1 ? (hotRes.data || []) : [])]
          .forEach(item => {
            const suggestion = this.toSuggestion(item)
            if (suggestion) merged.push(suggestion)
          })
        const uniqueMap = {}
        merged.forEach(item => { uniqueMap[item.value] = item })
        this.symbolSuggestions = Object.values(uniqueMap)
      } catch (error) {
        this.symbolSuggestions = []
      }
    },
    handleSymbolSearch (value) {
      if (this.symbolSearchTimer) clearTimeout(this.symbolSearchTimer)
      const keyword = (value || '').trim()
      if (!keyword) {
        this.loadWatchlistSymbols()
        return
      }
      this.symbolSearchTimer = setTimeout(async () => {
        this.symbolSearching = true
        try {
          const res = await searchSymbols({ market: 'Crypto', keyword, limit: 20 })
          this.symbolSuggestions = res && res.code === 1 ? (res.data || []).map(item => this.toSuggestion(item)).filter(Boolean) : []
        } catch (error) {
          this.symbolSuggestions = []
        } finally {
          this.symbolSearching = false
        }
      }, 250)
    },
    handleSymbolFocus () {
      if (!this.symbolSuggestions.length) this.loadWatchlistSymbols()
    },
    handleSymbolChange (value) {
      this.currentSymbol = this.normalizeCryptoSymbol(value)
    },
    async loadPrice () {
      if (!this.currentSymbol) {
        this.currentPrice = 0
        return
      }
      try {
        const res = await request({ url: '/api/market/price', method: 'get', params: { market: 'Crypto', symbol: this.currentSymbol } })
        if (res && res.code === 1 && res.data) {
          const price = Number(res.data.price || 0)
          if (price > 0) {
            this.currentPrice = price
            if (!this.limitPrice || this.orderType !== 'limit') this.limitPrice = price
          }
        }
      } catch (error) {
      }
    },
    async loadCredentials () {
      this.credLoading = true
      try {
        const res = await listExchangeCredentials({})
        const items = res && res.code === 1 && res.data ? (res.data.items || res.data || []) : []
        this.credentials = items.filter(item => !['ibkr', 'mt5'].includes(String(item.exchange_id || item.name || '').toLowerCase()))
        if (!this.selectedCredentialId && this.credentials.length > 0) this.selectedCredentialId = this.credentials[0].id
      } catch (error) {
        this.credentials = []
      } finally {
        this.credLoading = false
      }
    },
    onCredentialChange (value) {
      this.selectedCredentialId = value
    },
    async loadBalance () {
      if (!this.selectedCredentialId) return
      try {
        const res = await getQuickTradeBalance({ credential_id: this.selectedCredentialId, market_type: this.selectedMarketType })
        if (res && res.code === 1 && res.data) this.balance = { available: Number(res.data.available || 0), total: Number(res.data.total || 0) }
      } catch (error) {
      }
    },
    async loadPosition () {
      if (!this.selectedCredentialId || !this.currentSymbol) {
        this.currentPosition = null
        return false
      }
      try {
        const res = await getQuickTradePosition({ credential_id: this.selectedCredentialId, symbol: this.currentSymbol, market_type: this.selectedMarketType })
        const positions = (res && res.code === 1 && res.data && res.data.positions) || []
        if (positions.length > 0) {
          this.currentPosition = positions[0]
          return true
        }
      } catch (error) {
      }
      this.currentPosition = null
      return false
    },
    async loadPositionWithRetry (maxRetries = 3, delay = 2000) {
      for (let i = 0; i < maxRetries; i++) {
        if (await this.loadPosition()) return true
        await new Promise(resolve => setTimeout(resolve, delay))
      }
      return false
    },
    async loadHistory () {
      try {
        const res = await getQuickTradeHistory({ limit: 5 })
        if (res && res.code === 1 && res.data) this.recentTrades = res.data.trades || []
      } catch (error) {
      }
    },
    setAmountByPercent (pct) {
      if (this.balance.available <= 0) return
      this.amount = Math.floor((this.balance.available * pct / 100) * 100) / 100
    },
    async handleSubmit () {
      if (!this.canSubmit) {
        if (!this.currentSymbol) this.$message.warning(this.tt('quickTrade.symbolRequired', 'Please select a symbol'))
        return
      }
      this.submitting = true
      try {
        const payload = {
          credential_id: this.selectedCredentialId,
          symbol: this.currentSymbol,
          side: this.side,
          order_type: this.orderType,
          amount: this.amount,
          price: this.orderType === 'limit' ? this.limitPrice : 0,
          leverage: this.selectedMarketType === 'spot' ? 1 : this.leverage,
          market_type: this.selectedMarketType,
          tp_price: this.tpPrice || 0,
          sl_price: this.slPrice || 0,
          source: this.source
        }
        const res = await placeQuickTradeOrder(payload)
        if (res && res.code === 1) {
          this.$message.success(this.tt('quickTrade.orderPlaced', 'Order placed'))
          this.$emit('order-success', res.data)
          await this.loadBalance()
          await this.loadHistory()
          await this.loadPositionWithRetry()
        } else {
          this.$message.error((res && res.msg) || this.tt('quickTrade.orderFailed', 'Order failed'))
        }
      } catch (error) {
        this.$message.error((error && error.message) || this.tt('quickTrade.orderFailed', 'Order failed'))
      } finally {
        this.submitting = false
      }
    },
    async handleClosePosition () {
      if (!this.currentPosition || !this.selectedCredentialId) return
      this.closingPosition = true
      try {
        const res = await closeQuickTradePosition({ credential_id: this.selectedCredentialId, symbol: this.currentSymbol, market_type: this.selectedMarketType, size: 0, source: 'manual' })
        if (res && res.code === 1) {
          this.$message.success(this.tt('quickTrade.positionClosed', 'Position closed'))
          this.currentPosition = null
          await this.loadBalance()
          await this.loadHistory()
          setTimeout(() => this.loadPosition(), 1500)
        } else {
          this.$message.error((res && res.msg) || this.tt('quickTrade.orderFailed', 'Order failed'))
        }
      } catch (error) {
        this.$message.error((error && error.message) || this.tt('quickTrade.orderFailed', 'Order failed'))
      } finally {
        this.closingPosition = false
      }
    },
    startPolling () {
      this.stopPolling()
      this.pollTimer = setInterval(() => {
        if (this.currentSymbol) this.loadPrice()
        if (this.selectedCredentialId && this.currentSymbol) {
          this.loadBalance()
          this.loadPosition()
        }
      }, 10000)
    },
    stopPolling () {
      if (this.pollTimer) clearInterval(this.pollTimer)
      this.pollTimer = null
    },
    handleClose () {
      this.$emit('close')
      this.$emit('update:visible', false)
    },
    handleHistoryCollapse (keys) {
      this.historyCollapsed = !(keys || []).includes('history')
    },
    formatPrice (value) {
      const number = Number(value || 0)
      if (Math.abs(number) >= 10000) return number.toLocaleString('en-US', { maximumFractionDigits: 0 })
      if (Math.abs(number) >= 100) return number.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      if (Math.abs(number) >= 1) return number.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
      return number.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 })
    },
    formatTime (value) {
      if (!value) return ''
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      const pad = num => String(num).padStart(2, '0')
      return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
    }
  },
  beforeDestroy () {
    this.stopPolling()
    if (this.symbolSearchTimer) clearTimeout(this.symbolSearchTimer)
  }
}
</script>

<style lang="less" scoped>
.quick-trade-drawer { ::v-deep .ant-drawer-body { background: #0f172a; color: #e2e8f0; } }
.qt-header, .qt-row, .qt-balance, .qt-history-header { display: flex; align-items: center; justify-content: space-between; }
.qt-header { padding: 18px 18px 14px; border-bottom: 1px solid rgba(148, 163, 184, 0.18); }
.qt-header-left, .qt-direction-toggle, .qt-trade-main, .qt-trade-meta { display: flex; align-items: center; gap: 8px; }
.qt-icon { color: #38bdf8; font-size: 18px; }
.qt-header-title { color: #f8fafc; font-size: 15px; font-weight: 700; }
.qt-close { color: rgba(226, 232, 240, 0.72); cursor: pointer; font-size: 16px; }
.qt-symbol-bar, .qt-section, .qt-submit-section, .qt-panel { padding: 16px; }
.qt-symbol-bar { border-bottom: 1px solid rgba(148, 163, 184, 0.12); }
.qt-price { margin-top: 12px; color: #f8fafc; font-size: 22px; font-weight: 700; text-align: right; }
.qt-symbol-option { display: flex; flex-direction: column; }
.qt-symbol-option-name { color: #e2e8f0; font-weight: 600; }
.qt-symbol-option-desc, .qt-empty-hint, .qt-trade-meta { color: rgba(226, 232, 240, 0.56); font-size: 12px; }
.qt-label { margin-bottom: 10px; color: rgba(226, 232, 240, 0.72); font-size: 12px; font-weight: 600; text-transform: uppercase; }
.qt-crypto-hint, .qt-manage-link a { color: #38bdf8; margin-left: 6px; }
.qt-balance { margin-top: 12px; padding: 10px 12px; border-radius: 10px; background: rgba(56, 189, 248, 0.12); }
.qt-direction-toggle { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.qt-dir-btn { padding: 12px 14px; border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 12px; color: rgba(226, 232, 240, 0.8); cursor: pointer; text-align: center; }
.qt-dir-long.active { background: rgba(34, 197, 94, 0.24); border-color: rgba(34, 197, 94, 0.5); color: #fff; }
.qt-dir-short.active { background: rgba(239, 68, 68, 0.24); border-color: rgba(239, 68, 68, 0.5); color: #fff; }
.qt-quick-amounts, .qt-trade-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.qt-leverage-row { display: flex; align-items: center; }
.qt-tpsl-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.qt-submit-btn { height: 44px; border-radius: 12px; font-weight: 700; }
.qt-btn-long { box-shadow: 0 10px 26px rgba(34, 197, 94, 0.18); }
.qt-btn-short { box-shadow: 0 10px 26px rgba(239, 68, 68, 0.18); }
.qt-section-title { color: #f8fafc; font-size: 13px; font-weight: 700; margin-bottom: 10px; }
.qt-position-card, .qt-empty, .qt-trade-item { padding: 14px; border-radius: 14px; background: rgba(15, 23, 42, 0.78); border: 1px solid rgba(148, 163, 184, 0.18); }
.qt-position-card.long { border-color: rgba(34, 197, 94, 0.24); }
.qt-position-card.short { border-color: rgba(239, 68, 68, 0.24); }
.qt-row { color: #e2e8f0; font-size: 13px; padding: 6px 0; }
.qt-empty-title, .qt-trade-symbol { color: #f8fafc; font-weight: 600; }
.qt-trade-item { display: flex; justify-content: space-between; }
.qt-trade-amount { color: rgba(226, 232, 240, 0.72); font-size: 12px; }
.qt-green { color: #4ade80; }
.qt-red { color: #f87171; }
::v-deep .quick-trade-drawer {
  .ant-select-selection, .ant-input-number, .ant-radio-group-solid .ant-radio-button-wrapper, .ant-collapse { background: rgba(15, 23, 42, 0.78); border-color: rgba(148, 163, 184, 0.2); color: #e2e8f0; }
  .ant-input-number-input, .ant-select-selection__rendered, .ant-select-arrow, .ant-slider-mark-text { color: #e2e8f0; }
  .ant-radio-group-solid .ant-radio-button-wrapper-checked:not(.ant-radio-button-wrapper-disabled) { background: #0ea5e9; border-color: #0ea5e9; }
  .ant-input-number-input { background: transparent; }
  .ant-collapse-content-box { padding: 0 0 8px; }
}
</style>
