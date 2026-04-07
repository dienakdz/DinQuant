<template>
  <div class="ai-asset-analysis-page" :class="{ 'theme-dark': isDarkTheme }">
    <div v-if="opportunities.length > 0" class="radar-section">
      <div class="radar-header">
        <div class="radar-header-left">
          <h2 class="radar-title">{{ $t('aiAssetAnalysis.opportunities.title') }}</h2>
          <p class="radar-subtitle">{{ $t('aiAssetAnalysis.opportunities.updateHint') }}</p>
        </div>
        <a-button class="radar-refresh-btn" size="small" :loading="oppLoading" @click="loadOpportunities(true)">
          <a-icon type="sync" /> {{ $t('common.refresh') || 'Refresh' }}
        </a-button>
      </div>

      <div class="radar-carousel" @mouseenter="oppHover = true" @mouseleave="oppHover = false">
        <div class="radar-track" :class="{ paused: oppHover }" :style="oppTrackStyle">
          <div
            v-for="(opp, index) in carouselItems"
            :key="`opp-${index}`"
            class="radar-card"
            :class="[opp.impact, { 'is-prediction': opp.market === 'PredictionMarket' }]"
            @click="analyzeOpportunity(opp)"
          >
            <div class="rc-head">
              <span class="rc-symbol" :class="{ 'rc-prediction-title': opp.market === 'PredictionMarket' }">
                {{ opp.market === 'PredictionMarket' && opp.name ? opp.name : opp.symbol }}
              </span>
              <span class="rc-market" :class="`rc-market-${(opp.market || '').toLowerCase()}`">{{ getMarketLabel(opp.market) }}</span>
            </div>

            <div class="rc-metrics">
              <template v-if="opp.market !== 'PredictionMarket'">
                <div class="rc-metric">
                  <span class="rc-metric-label">{{ isZhLocale ? '当前价格' : 'Price' }}</span>
                  <span class="rc-metric-value">${{ formatOppPrice(opp.price) }}</span>
                </div>
                <div class="rc-metric">
                  <span class="rc-metric-label">{{ isZhLocale ? '24h涨跌' : '24h Change' }}</span>
                  <span class="rc-metric-value" :class="Number(opp.change_24h) >= 0 ? 'rc-up' : 'rc-down'">
                    {{ Number(opp.change_24h) >= 0 ? '+' : '' }}{{ Number(opp.change_24h || 0).toFixed(2) }}%
                  </span>
                </div>
                <div class="rc-metric">
                  <span class="rc-metric-label">{{ isZhLocale ? '信号' : 'Signal' }}</span>
                  <span class="rc-metric-value rc-signal-val" :class="`rc-signal-${opp.signal || ''}`">{{ getSignalLabel(opp.signal) }}</span>
                </div>
              </template>
              <template v-else>
                <div class="rc-metric">
                  <span class="rc-metric-label">{{ isZhLocale ? '市场概率' : 'Probability' }}</span>
                  <span class="rc-metric-value">{{ Number(opp.price || 0).toFixed(1) }}%</span>
                </div>
                <div v-if="opp.ai_analysis" class="rc-metric">
                  <span class="rc-metric-label">{{ isZhLocale ? '机会评分' : 'Score' }}</span>
                  <span class="rc-metric-value rc-up">{{ Number(opp.ai_analysis.opportunity_score || 0).toFixed(0) }}</span>
                </div>
                <div v-if="opp.ai_analysis" class="rc-metric">
                  <span class="rc-metric-label">{{ isZhLocale ? '建议' : 'Rec.' }}</span>
                  <span class="rc-metric-value" :class="getRecommendationClass(opp.ai_analysis.recommendation)">
                    {{ getRecommendationLabel(opp.ai_analysis.recommendation) }}
                  </span>
                </div>
              </template>
            </div>

            <div class="rc-footer">
              <span class="rc-reason">{{ getReasonText(opp) }}</span>
              <span v-if="opp.market === 'Crypto'" class="rc-cta" @click.stop="openQuickTradeFromOpp(opp)">
                <a-icon type="transaction" /> {{ tt('quickTrade.tradeNow', 'Trade now') }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <a-tooltip :title="tt('quickTrade.openPanel', 'Open quick trade panel')" placement="left">
      <div
        v-if="!showQuickTrade && currentAnalysisSymbol && currentAnalysisMarket === 'Crypto'"
        class="qt-floating-btn"
        @click="openQuickTradeFromCurrent"
      >
        <a-icon type="thunderbolt" theme="filled" />
      </div>
    </a-tooltip>

    <quick-trade-panel
      :visible="showQuickTrade"
      :symbol="qtSymbol"
      :preset-side="qtSide"
      :preset-price="qtPrice"
      :source="qtSource"
      market-type="swap"
      @close="showQuickTrade = false"
      @order-success="onQuickTradeSuccess"
      @update:symbol="handleQuickTradeSymbolChange"
    />

    <a-card class="workspace-card" :bordered="false">
      <a-tabs v-model="activeTab" class="workspace-tabs" size="large">
        <a-tab-pane key="quick">
          <span slot="tab"><a-icon type="thunderbolt" /> {{ $t('aiAssetAnalysis.tabs.quick') }}</span>
          <div class="tab-body">
            <AnalysisView
              v-if="activeTab === 'quick'"
              :embedded="true"
              :preset-symbol="presetSymbol"
              :auto-analyze-signal="autoAnalyzeSignal"
              @symbol-change="onAnalysisSymbolChange"
            />
          </div>
        </a-tab-pane>

        <a-tab-pane key="polymarket">
          <span slot="tab"><a-icon type="radar-chart" /> {{ tt('aiAssetAnalysis.tabs.polymarket', 'Polymarket') }}</span>
          <div class="tab-body">
            <div class="polymarket-tab-content">
              <div class="polymarket-placeholder">
                <div class="placeholder-icon"><a-icon type="radar-chart" /></div>
                <h3>{{ tt('polymarket.analysis.title', 'Polymarket Analysis') }}</h3>
                <p>{{ tt('polymarket.analysis.description', 'Analyze a prediction market by URL or title and compare market pricing with AI probability.') }}</p>
                <a-button style="margin-top: 16px" type="primary" size="large" icon="thunderbolt" @click="showPolymarketModal = true">
                  {{ tt('polymarket.analysis.startAnalysis', 'Start analysis') }}
                </a-button>
              </div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <polymarket-analysis-modal :visible="showPolymarketModal" @close="showPolymarketModal = false" />
  </div>
</template>

<script>
import { mapState } from 'vuex'
import AnalysisView from '@/views/ai-analysis'
import { getTradingOpportunities } from '@/api/global-market'
import QuickTradePanel from '@/components/QuickTradePanel.vue'
import PolymarketAnalysisModal from '@/components/PolymarketAnalysisModal.vue'

export default {
  name: 'AIAssetAnalysis',
  components: {
    AnalysisView,
    QuickTradePanel,
    PolymarketAnalysisModal
  },
  data () {
    return {
      activeTab: 'quick',
      opportunities: [],
      oppLoading: false,
      oppHover: false,
      presetSymbol: '',
      autoAnalyzeSignal: 0,
      showQuickTrade: false,
      qtSymbol: '',
      qtSide: '',
      qtPrice: 0,
      qtSource: 'ai_radar',
      currentAnalysisSymbol: '',
      currentAnalysisMarket: '',
      showPolymarketModal: false
    }
  },
  computed: {
    ...mapState({
      navTheme: state => state.app.theme
    }),
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    isZhLocale () {
      return this.$i18n && this.$i18n.locale === 'zh-CN'
    },
    carouselItems () {
      return this.opportunities.length === 0 ? [] : [...this.opportunities, ...this.opportunities]
    },
    oppTrackStyle () {
      return {
        animationDuration: `${Math.max(this.opportunities.length * 3, 18)}s`
      }
    }
  },
  created () {
    this.loadOpportunities()
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    async loadOpportunities (force = false) {
      this.oppLoading = true
      try {
        const res = await getTradingOpportunities(force ? { force: true } : {})
        if (res && res.code === 1 && Array.isArray(res.data)) {
          this.opportunities = res.data.slice(0, 20)
        }
      } catch (error) {
      } finally {
        this.oppLoading = false
      }
    },
    getSignalLabel (signal) {
      const key = `aiAssetAnalysis.opportunities.signal.${signal}`
      const translated = this.$t(key)
      return translated !== key ? translated : signal
    },
    getMarketTagColor (market) {
      return { Crypto: 'purple', USStock: 'green', Forex: 'gold', PredictionMarket: 'cyan' }[market] || 'default'
    },
    getMarketLabel (market) {
      const key = `aiAssetAnalysis.opportunities.market.${market}`
      const translated = this.$t(key)
      if (translated !== key) return translated
      return { PredictionMarket: 'Prediction Market' }[market] || market
    },
    getReasonText (opp) {
      if (opp.market === 'PredictionMarket') return opp.reason || ''
      const market = (opp.market || 'Crypto').toLowerCase()
      const signal = opp.signal || ''
      const key = `aiAssetAnalysis.opportunities.reason.${market}.${signal}`
      const translated = this.$t(key)
      if (translated === key) return opp.reason || ''
      return translated
        .replace('{change}', Math.abs(opp.change_24h || 0).toFixed(1))
        .replace('{change7d}', Math.abs(opp.change_7d || 0).toFixed(1))
    },
    formatOppPrice (price) {
      const number = Number(price || 0)
      if (!number) return '--'
      if (number >= 10000) return `${(number / 1000).toFixed(1)}K`
      if (number >= 1) return number.toFixed(2)
      return number.toFixed(4)
    },
    analyzeOpportunity (opp) {
      if (opp.market === 'PredictionMarket') {
        this.activeTab = 'polymarket'
        this.showPolymarketModal = true
        return
      }
      this.activeTab = 'quick'
      const market = opp.market || 'Crypto'
      this.presetSymbol = `${market}:${opp.symbol}`
      this.$nextTick(() => {
        this.autoAnalyzeSignal++
      })
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
    getSideFromOpportunity (opp) {
      if (opp && opp.impact === 'bearish') return 'sell'
      if (opp && opp.impact === 'bullish') return 'buy'
      return ''
    },
    openQuickTradeFromCurrent () {
      if (this.currentAnalysisMarket !== 'Crypto') return
      this.qtSymbol = this.normalizeCryptoSymbol(this.currentAnalysisSymbol)
      this.qtSide = ''
      this.qtPrice = 0
      this.qtSource = 'ai_analysis'
      this.showQuickTrade = true
    },
    openQuickTradeFromOpp (opp) {
      this.qtSymbol = this.normalizeCryptoSymbol(opp.symbol)
      this.qtSide = this.getSideFromOpportunity(opp)
      this.qtPrice = Number(opp.price || 0)
      this.qtSource = 'ai_radar'
      this.showQuickTrade = true
    },
    onQuickTradeSuccess () {
      this.showQuickTrade = true
    },
    handleQuickTradeSymbolChange (symbol) {
      this.qtSymbol = symbol
    },
    onAnalysisSymbolChange (value) {
      if (!value) {
        this.currentAnalysisSymbol = ''
        this.currentAnalysisMarket = ''
        return
      }
      const parts = String(value).split(':')
      if (parts.length > 1) {
        this.currentAnalysisMarket = parts[0]
        this.currentAnalysisSymbol = parts.slice(1).join(':')
      } else {
        this.currentAnalysisMarket = ''
        this.currentAnalysisSymbol = value
      }
    },
    getRecommendationClass (value) {
      return { YES: 'rc-up', NO: 'rc-down', HOLD: '' }[value] || ''
    },
    getRecommendationColor (value) {
      return { YES: 'green', NO: 'red', HOLD: 'default' }[value] || 'default'
    },
    getRecommendationLabel (value) {
      return {
        YES: this.tt('polymarket.analysis.recommendationYes', 'YES'),
        NO: this.tt('polymarket.analysis.recommendationNo', 'NO'),
        HOLD: this.tt('polymarket.analysis.recommendationHold', 'HOLD')
      }[value] || value
    }
  }
}
</script>

<style lang="less" scoped>
.ai-asset-analysis-page { position: relative; min-height: calc(100vh - 120px); padding: 16px; background: #f3f6fb; }
.radar-section, .workspace-card { border-radius: 18px; overflow: hidden; box-shadow: 0 14px 40px rgba(15, 23, 42, 0.08); }
.radar-section { margin-bottom: 16px; padding: 18px; background: linear-gradient(135deg, #0f172a, #162033 60%, #11223f); color: #f8fafc; }
.radar-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.radar-title { margin: 0; color: #fff; font-size: 20px; font-weight: 700; }
.radar-subtitle { margin: 4px 0 0; color: rgba(248, 250, 252, 0.7); }
.radar-refresh-btn { border-color: rgba(148, 163, 184, 0.28); background: rgba(15, 23, 42, 0.42); color: #f8fafc; }
.radar-carousel { overflow: hidden; }
.radar-track { display: flex; gap: 14px; width: max-content; animation: radar-scroll linear infinite; }
.radar-track.paused { animation-play-state: paused; }
.radar-card { width: 280px; min-height: 190px; padding: 16px; border-radius: 16px; background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(148, 163, 184, 0.2); backdrop-filter: blur(10px); cursor: pointer; }
.radar-card.is-prediction { width: 320px; }
.rc-head, .rc-footer { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.rc-symbol { color: #fff; font-size: 16px; font-weight: 700; line-height: 1.4; }
.rc-prediction-title { display: -webkit-box; overflow: hidden; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.rc-market { padding: 4px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.rc-market-crypto { background: rgba(168, 85, 247, 0.18); color: #d8b4fe; }
.rc-market-usstock { background: rgba(34, 197, 94, 0.18); color: #86efac; }
.rc-market-forex { background: rgba(250, 204, 21, 0.18); color: #fde68a; }
.rc-market-predictionmarket { background: rgba(56, 189, 248, 0.18); color: #7dd3fc; }
.rc-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 18px 0; }
.rc-metric { padding: 10px; border-radius: 12px; background: rgba(15, 23, 42, 0.32); }
.rc-metric-label { display: block; color: rgba(248, 250, 252, 0.6); font-size: 11px; margin-bottom: 8px; }
.rc-metric-value { color: #fff; font-size: 15px; font-weight: 700; }
.rc-up { color: #4ade80; }
.rc-down { color: #f87171; }
.rc-footer { align-items: center; }
.rc-reason { color: rgba(248, 250, 252, 0.72); font-size: 12px; line-height: 1.6; }
.rc-cta { color: #38bdf8; font-size: 12px; font-weight: 700; white-space: nowrap; }
.qt-floating-btn { position: fixed; right: 26px; bottom: 28px; z-index: 9; display: flex; align-items: center; justify-content: center; width: 52px; height: 52px; border-radius: 50%; background: linear-gradient(135deg, #0ea5e9, #2563eb); color: #fff; font-size: 22px; box-shadow: 0 16px 30px rgba(37, 99, 235, 0.35); cursor: pointer; }
.workspace-card { background: #fff; }
.tab-body { min-height: 720px; }
.polymarket-tab-content { display: flex; align-items: center; justify-content: center; min-height: 520px; padding: 24px; }
.polymarket-placeholder { max-width: 560px; padding: 36px; border-radius: 24px; text-align: center; background: linear-gradient(180deg, #f8fafc, #eff6ff); }
.placeholder-icon { display: inline-flex; align-items: center; justify-content: center; width: 72px; height: 72px; margin-bottom: 18px; border-radius: 50%; background: linear-gradient(135deg, #0ea5e9, #2563eb); color: #fff; font-size: 28px; }
.polymarket-placeholder h3 { margin-bottom: 12px; color: #0f172a; font-size: 24px; }
.polymarket-placeholder p { margin: 0; color: rgba(15, 23, 42, 0.66); line-height: 1.7; }
.theme-dark.ai-asset-analysis-page { background: #0b1220; }
.theme-dark .workspace-card { background: #111827; }
.theme-dark .polymarket-placeholder { background: linear-gradient(180deg, #111827, #1f2937); }
.theme-dark .polymarket-placeholder h3 { color: #f8fafc; }
.theme-dark .polymarket-placeholder p { color: rgba(248, 250, 252, 0.72); }
@keyframes radar-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(calc(-50% - 7px)); }
}
@media (max-width: 900px) {
  .radar-header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .radar-card { width: 260px; }
  .radar-card.is-prediction { width: 280px; }
  .rc-metrics { grid-template-columns: 1fr; }
  .tab-body { min-height: auto; }
}
</style>
