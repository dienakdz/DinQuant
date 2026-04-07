<template>
  <a-modal
    :visible="visible"
    :title="tt('polymarket.analysis.title', 'Polymarket Analysis')"
    :width="900"
    :footer="null"
    :wrap-class-name="isDarkTheme ? 'qd-dark-modal' : ''"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <div class="polymarket-analysis-modal" :class="{ 'theme-dark': isDarkTheme }">
      <a-tabs v-model="activeTab" @change="handleTabChange">
        <a-tab-pane key="analyze" :tab="tt('polymarket.analysis.tabAnalyze', 'Analyze')">
          <div v-if="!analysisResult" class="input-section">
            <a-alert
              style="margin-bottom: 16px"
              type="info"
              show-icon
              :message="tt('polymarket.analysis.inputHint', 'Paste a Polymarket URL or market title to start analysis.')"
            />
            <a-textarea
              v-model="inputText"
              :rows="3"
              :disabled="analyzing"
              :placeholder="tt('polymarket.analysis.inputPlaceholder', 'https://polymarket.com/... or a market title')"
              @pressEnter="handleAnalyze"
            />
            <a-button
              style="width: 100%; margin-top: 12px"
              type="primary"
              size="large"
              icon="thunderbolt"
              :loading="analyzing"
              :disabled="!inputText.trim()"
              @click="handleAnalyze"
            >
              {{ tt('polymarket.analysis.analyzeButton', 'Analyze') }}
            </a-button>
          </div>

          <div v-if="analysisResult" class="result-section">
            <div class="market-info">
              <h3>{{ analysisResult.market.question }}</h3>
              <div class="market-meta">
                <a-tag :color="getStatusColor(analysisResult.market.status)">{{ analysisResult.market.status }}</a-tag>
                <span class="meta-item"><a-icon type="percentage" /> {{ analysisResult.market.current_probability }}%</span>
                <span v-if="analysisResult.market.volume_24h" class="meta-item"><a-icon type="dollar" /> {{ formatVolume(analysisResult.market.volume_24h) }}</span>
                <a-button
                  v-if="analysisResult.market.polymarket_url"
                  type="link"
                  size="small"
                  icon="link"
                  :href="analysisResult.market.polymarket_url"
                  target="_blank"
                >
                  {{ tt('polymarket.analysis.viewOnPolymarket', 'Open on Polymarket') }}
                </a-button>
              </div>
            </div>

            <div class="analysis-result">
              <a-divider>{{ tt('polymarket.analysis.aiAnalysis', 'AI Analysis') }}</a-divider>
              <div class="probability-comparison">
                <div class="prob-item">
                  <div class="prob-label">{{ tt('polymarket.analysis.marketProbability', 'Market probability') }}</div>
                  <div class="prob-value">{{ analysisResult.analysis.market_probability }}%</div>
                </div>
                <div class="prob-item">
                  <div class="prob-label">{{ tt('polymarket.analysis.aiPredictedProbability', 'AI predicted probability') }}</div>
                  <div class="prob-value ai-prob">{{ analysisResult.analysis.ai_predicted_probability }}%</div>
                </div>
                <div class="prob-item">
                  <div class="prob-label">{{ tt('polymarket.analysis.divergence', 'Divergence') }}</div>
                  <div class="prob-value" :class="getDivergenceClass(analysisResult.analysis.divergence)">
                    {{ analysisResult.analysis.divergence >= 0 ? '+' : '' }}{{ Number(analysisResult.analysis.divergence || 0).toFixed(2) }}%
                  </div>
                </div>
              </div>

              <a-row :gutter="16" class="recommendation-section">
                <a-col :span="8">
                  <div class="rec-card">
                    <div class="rec-label">{{ tt('polymarket.analysis.recommendation', 'Recommendation') }}</div>
                    <a-tag :color="getRecommendationColor(analysisResult.analysis.recommendation)" style="font-size: 16px; padding: 4px 12px">
                      {{ getRecommendationLabel(analysisResult.analysis.recommendation) }}
                    </a-tag>
                  </div>
                </a-col>
                <a-col :span="8">
                  <div class="rec-card">
                    <div class="rec-label">{{ tt('polymarket.analysis.confidenceScore', 'Confidence') }}</div>
                    <div class="rec-value">{{ Number(analysisResult.analysis.confidence_score || 0).toFixed(0) }}</div>
                  </div>
                </a-col>
                <a-col :span="8">
                  <div class="rec-card">
                    <div class="rec-label">{{ tt('polymarket.analysis.opportunityScore', 'Opportunity') }}</div>
                    <div class="rec-value">{{ Number(analysisResult.analysis.opportunity_score || 0).toFixed(0) }}</div>
                  </div>
                </a-col>
              </a-row>

              <div v-if="analysisResult.analysis.reasoning" class="text-block">
                <h4>{{ tt('polymarket.analysis.reasoning', 'Reasoning') }}</h4>
                <p>{{ analysisResult.analysis.reasoning }}</p>
              </div>

              <div v-if="analysisResult.analysis.key_factors && analysisResult.analysis.key_factors.length > 0" class="text-block">
                <h4>{{ tt('polymarket.analysis.keyFactors', 'Key factors') }}</h4>
                <a-tag v-for="(factor, index) in analysisResult.analysis.key_factors" :key="index" color="blue" style="margin: 4px">
                  {{ factor }}
                </a-tag>
              </div>

              <div v-if="analysisResult.credits_charged > 0" class="billing-info">
                <a-alert
                  type="success"
                  show-icon
                  :message="tt('polymarket.analysis.creditsCharged', `Credits charged: ${analysisResult.credits_charged}`, { credits: analysisResult.credits_charged })"
                />
                <div v-if="analysisResult.remaining_credits !== undefined" class="remaining-credits">
                  {{ tt('polymarket.analysis.remainingCredits', `Remaining credits: ${Number(analysisResult.remaining_credits).toFixed(0)}`, { credits: Number(analysisResult.remaining_credits).toFixed(0) }) }}
                </div>
              </div>
            </div>

            <div class="result-actions">
              <a-button style="margin-right: 8px" @click="handleNewAnalysis">{{ tt('polymarket.analysis.newAnalysis', 'New analysis') }}</a-button>
              <a-button type="primary" @click="handleClose">{{ tt('common.close', 'Close') }}</a-button>
            </div>
          </div>

          <div v-if="analyzing" class="loading-section">
            <a-spin size="large" />
            <p>{{ tt('polymarket.analysis.analyzing', 'Analyzing...') }}</p>
          </div>
        </a-tab-pane>

        <a-tab-pane key="history" :tab="tt('polymarket.analysis.tabHistory', 'History')">
          <a-spin :spinning="historyLoading">
            <a-table
              size="small"
              :columns="historyColumns"
              :data-source="historyList"
              :pagination="historyPagination"
              :row-key="record => record.id"
              @change="handleHistoryTableChange"
            >
              <template slot="market_title" slot-scope="text, record">
                <a-button type="link" style="padding: 0" @click="viewHistoryItem(record)">{{ text }}</a-button>
              </template>
              <template slot="recommendation" slot-scope="text">
                <a-tag :color="getRecommendationColor(text)">{{ getRecommendationLabel(text) }}</a-tag>
              </template>
              <template slot="created_at" slot-scope="text">
                {{ formatDateTime(text) }}
              </template>
            </a-table>
          </a-spin>
        </a-tab-pane>
      </a-tabs>
    </div>
  </a-modal>
</template>

<script>
import { mapState } from 'vuex'
import { analyzePolymarket, getPolymarketHistory } from '@/api/polymarket'

export default {
  name: 'PolymarketAnalysisModal',
  props: {
    visible: {
      type: Boolean,
      default: false
    }
  },
  data () {
    return {
      inputText: '',
      analyzing: false,
      analysisResult: null,
      activeTab: 'analyze',
      historyLoading: false,
      historyList: [],
      historyPagination: {
        current: 1,
        pageSize: 20,
        total: 0,
        showSizeChanger: true,
        showTotal: total => `Total ${total}`
      },
      historyColumns: []
    }
  },
  computed: {
    ...mapState({
      navTheme: state => state.app.theme
    }),
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    }
  },
  mounted () {
    this.historyColumns = [
      { title: this.tt('polymarket.analysis.historyMarket', 'Market'), dataIndex: 'market_title', key: 'market_title', scopedSlots: { customRender: 'market_title' } },
      { title: this.tt('polymarket.analysis.historyRecommendation', 'Recommendation'), dataIndex: 'recommendation', key: 'recommendation', width: 120, scopedSlots: { customRender: 'recommendation' } },
      { title: this.tt('polymarket.analysis.historyOpportunityScore', 'Opportunity'), dataIndex: 'opportunity_score', key: 'opportunity_score', width: 120, align: 'right' },
      { title: this.tt('polymarket.analysis.historyCreatedAt', 'Created at'), dataIndex: 'created_at', key: 'created_at', width: 180, scopedSlots: { customRender: 'created_at' } }
    ]
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    async handleAnalyze () {
      if (!this.inputText.trim()) {
        this.$message.warning(this.tt('polymarket.analysis.inputRequired', 'Please enter a Polymarket URL or market title'))
        return
      }
      this.analyzing = true
      this.analysisResult = null
      try {
        const res = await analyzePolymarket({
          input: this.inputText.trim(),
          language: this.$i18n.locale || 'zh-CN'
        })
        if (res && res.code === 1) {
          this.analysisResult = res.data
          this.$message.success(this.tt('polymarket.analysis.success', 'Analysis completed'))
        } else if (res && res.msg === 'Insufficient credits') {
          this.$message.error(this.tt('polymarket.analysis.insufficientCredits', 'Insufficient credits'))
          this.$router.push('/billing')
        } else {
          this.$message.error((res && res.msg) || this.tt('polymarket.analysis.failed', 'Analysis failed'))
        }
      } catch (error) {
        const message = error && error.response && error.response.data && error.response.data.msg
        if (message === 'Insufficient credits') {
          this.$message.error(this.tt('polymarket.analysis.insufficientCredits', 'Insufficient credits'))
          this.$router.push('/billing')
        } else {
          this.$message.error(message || this.tt('polymarket.analysis.failed', 'Analysis failed'))
        }
      } finally {
        this.analyzing = false
      }
    },
    handleNewAnalysis () {
      this.inputText = ''
      this.analysisResult = null
    },
    handleClose () {
      this.$emit('close')
      setTimeout(() => {
        this.inputText = ''
        this.analysisResult = null
        this.analyzing = false
      }, 300)
    },
    handleTabChange (key) {
      this.activeTab = key
      if (key === 'history' && this.historyList.length === 0) {
        this.loadHistory()
      }
    },
    async loadHistory () {
      this.historyLoading = true
      try {
        const res = await getPolymarketHistory({
          page: this.historyPagination.current,
          page_size: this.historyPagination.pageSize
        })
        if (res && res.code === 1 && res.data) {
          this.historyList = res.data.items || []
          this.historyPagination.total = res.data.total || 0
        }
      } catch (error) {
        this.$message.error(this.tt('polymarket.analysis.loadHistoryFailed', 'Failed to load history'))
      } finally {
        this.historyLoading = false
      }
    },
    handleHistoryTableChange (pagination) {
      this.historyPagination.current = pagination.current
      this.historyPagination.pageSize = pagination.pageSize
      this.loadHistory()
    },
    viewHistoryItem (record) {
      this.activeTab = 'analyze'
      this.analysisResult = {
        market: {
          question: record.market_title,
          market_id: record.market_id,
          polymarket_url: record.market_url,
          current_probability: record.market_probability,
          status: 'active'
        },
        analysis: {
          ai_predicted_probability: record.ai_predicted_probability,
          market_probability: record.market_probability,
          recommendation: record.recommendation,
          opportunity_score: record.opportunity_score,
          confidence_score: record.confidence_score
        }
      }
    },
    getStatusColor (status) {
      return { active: 'green', closed: 'default', resolved: 'blue' }[status] || 'default'
    },
    getRecommendationColor (value) {
      return { YES: 'green', NO: 'red', HOLD: 'orange' }[value] || 'default'
    },
    getRecommendationLabel (value) {
      const map = {
        YES: this.tt('polymarket.analysis.recommendationYes', 'YES'),
        NO: this.tt('polymarket.analysis.recommendationNo', 'NO'),
        HOLD: this.tt('polymarket.analysis.recommendationHold', 'HOLD')
      }
      return map[value] || value
    },
    getDivergenceClass (value) {
      if (value > 5) return 'divergence-positive'
      if (value < -5) return 'divergence-negative'
      return 'divergence-neutral'
    },
    formatVolume (value) {
      const number = Number(value || 0)
      if (number >= 1000000) return `$${(number / 1000000).toFixed(2)}M`
      if (number >= 1000) return `$${(number / 1000).toFixed(2)}K`
      return `$${number.toFixed(2)}`
    },
    formatDateTime (value) {
      if (!value) return ''
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return value
      return date.toLocaleString(this.$i18n.locale === 'zh-CN' ? 'zh-CN' : 'en-US')
    }
  }
}
</script>

<style lang="less" scoped>
.market-info h3, .text-block h4 { color: #0f172a; }
.market-meta, .probability-comparison, .result-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.probability-comparison { margin-bottom: 16px; }
.prob-item, .rec-card { flex: 1; min-width: 160px; padding: 16px; border-radius: 12px; background: #f8fafc; }
.prob-label, .rec-label, .remaining-credits { color: rgba(15, 23, 42, 0.6); font-size: 12px; }
.prob-value, .rec-value { color: #0f172a; font-size: 22px; font-weight: 700; margin-top: 8px; }
.ai-prob { color: #1890ff; }
.text-block { margin-top: 20px; }
.text-block p { color: rgba(15, 23, 42, 0.75); line-height: 1.7; }
.billing-info { margin-top: 16px; }
.remaining-credits { margin-top: 8px; text-align: right; }
.result-actions { justify-content: flex-end; margin-top: 20px; }
.loading-section { padding: 36px 0; text-align: center; }
.loading-section p { margin-top: 16px; color: rgba(15, 23, 42, 0.65); }
.divergence-positive { color: #16a34a; }
.divergence-negative { color: #dc2626; }
.divergence-neutral { color: #475569; }
.theme-dark {
  .market-info h3, .text-block h4, .prob-value, .rec-value { color: #f8fafc; }
  .prob-item, .rec-card { background: #111827; }
  .prob-label, .rec-label, .remaining-credits, .text-block p, .loading-section p { color: rgba(248, 250, 252, 0.7); }
  .divergence-neutral { color: #cbd5e1; }
}
</style>
