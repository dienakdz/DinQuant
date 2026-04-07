<template>
  <div class="polymarket-workspace" :class="{ 'theme-dark': isDarkTheme, embedded }">
    <a-tabs v-model="activeTab" @change="handleTabChange">
      <a-tab-pane key="analyze" :tab="tt('polymarket.analysis.tabAnalyze', 'Analyze')">
        <div v-if="!analysisResult && !analyzing" class="input-shell">
          <div class="input-hero">
            <div>
              <div class="hero-eyebrow">{{ tt('polymarket.analysis.title', 'Polymarket Analysis') }}</div>
              <h3 class="hero-title">{{ tt('polymarket.analysis.heroTitle', 'Compare market pricing with AI conviction') }}</h3>
              <p class="hero-desc">
                {{ tt('polymarket.analysis.description', 'Analyze a prediction market by URL or title and compare market pricing with AI probability.') }}
              </p>
            </div>
            <div class="hero-stats">
              <div class="hero-stat">
                <span class="stat-label">{{ tt('polymarket.analysis.statInput', 'Input') }}</span>
                <strong class="stat-value">{{ tt('polymarket.analysis.statInputValue', 'URL or title') }}</strong>
              </div>
              <div class="hero-stat">
                <span class="stat-label">{{ tt('polymarket.analysis.statOutput', 'Output') }}</span>
                <strong class="stat-value">{{ tt('polymarket.analysis.statOutputValue', 'Probability gap') }}</strong>
              </div>
            </div>
          </div>

          <a-alert
            class="input-alert"
            type="info"
            show-icon
            :message="tt('polymarket.analysis.inputHint', 'Paste a Polymarket URL or market title to start analysis.')"
          />

          <a-textarea
            ref="inputTextarea"
            v-model="inputText"
            :rows="4"
            :disabled="analyzing"
            :placeholder="tt('polymarket.analysis.inputPlaceholder', 'https://polymarket.com/... or a market title')"
            @pressEnter="handleAnalyze"
          />

          <div class="input-actions">
            <a-button
              type="primary"
              size="large"
              icon="thunderbolt"
              :loading="analyzing"
              :disabled="!inputText.trim()"
              @click="handleAnalyze"
            >
              {{ tt('polymarket.analysis.analyzeButton', 'Analyze') }}
            </a-button>
            <a-button size="large" icon="history" @click="activeTab = 'history'">
              {{ tt('polymarket.analysis.tabHistory', 'History') }}
            </a-button>
          </div>
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
                  <a-tag :color="getRecommendationColor(analysisResult.analysis.recommendation)" class="rec-tag">
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
              <a-tag v-for="(factor, index) in analysisResult.analysis.key_factors" :key="index" color="blue" class="factor-tag">
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
            <a-button @click="handleNewAnalysis">{{ tt('polymarket.analysis.newAnalysis', 'New analysis') }}</a-button>
            <a-button v-if="showCloseAction" type="primary" @click="$emit('close')">{{ tt('common.close', 'Close') }}</a-button>
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
</template>

<script>
import { mapState } from 'vuex'
import { analyzePolymarket, getPolymarketHistory } from '@/api/polymarket'

export default {
  name: 'PolymarketAnalysisWorkspace',
  props: {
    showCloseAction: {
      type: Boolean,
      default: false
    },
    embedded: {
      type: Boolean,
      default: false
    },
    initialInput: {
      type: String,
      default: ''
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
  watch: {
    initialInput: {
      immediate: true,
      handler (value) {
        if (value) {
          this.inputText = String(value)
        }
      }
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
    focusInput () {
      this.$nextTick(() => {
        const textarea = this.$refs.inputTextarea
        if (textarea && textarea.focus) {
          textarea.focus()
        }
      })
    },
    setInput (value) {
      this.inputText = value ? String(value) : ''
      this.activeTab = 'analyze'
      this.focusInput()
    },
    async startFromInput (value) {
      this.inputText = value ? String(value) : ''
      this.activeTab = 'analyze'
      await this.handleAnalyze()
    },
    resetWorkspace () {
      this.inputText = ''
      this.analysisResult = null
      this.analyzing = false
      this.activeTab = 'analyze'
      this.focusInput()
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
      this.focusInput()
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
.polymarket-workspace {
  padding: 8px 0 0;
}

.input-shell,
.result-section {
  border-radius: 20px;
  border: 1px solid #e5edf5;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.06);
}

.input-shell {
  padding: 24px;
}

.input-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.hero-eyebrow {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-title {
  margin: 8px 0 10px;
  color: #0f172a;
  font-size: 26px;
  font-weight: 700;
}

.hero-desc {
  max-width: 620px;
  margin: 0;
  color: rgba(15, 23, 42, 0.7);
  line-height: 1.7;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 12px;
  min-width: 260px;
}

.hero-stat,
.prob-item,
.rec-card {
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
}

.stat-label,
.prob-label,
.rec-label,
.remaining-credits {
  color: rgba(15, 23, 42, 0.6);
  font-size: 12px;
}

.stat-value,
.prob-value,
.rec-value {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
}

.input-alert {
  margin-bottom: 16px;
}

.input-actions,
.market-meta,
.probability-comparison,
.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.input-actions {
  margin-top: 16px;
}

.result-section {
  padding: 24px;
}

.market-info h3,
.text-block h4 {
  color: #0f172a;
}

.probability-comparison {
  margin-bottom: 16px;
}

.ai-prob {
  color: #1890ff;
}

.rec-tag {
  font-size: 16px;
  padding: 4px 12px;
}

.text-block {
  margin-top: 20px;
}

.text-block p {
  color: rgba(15, 23, 42, 0.75);
  line-height: 1.7;
}

.factor-tag {
  margin: 4px;
}

.billing-info {
  margin-top: 16px;
}

.remaining-credits {
  margin-top: 8px;
  text-align: right;
}

.result-actions {
  justify-content: flex-end;
  margin-top: 20px;
}

.loading-section {
  padding: 48px 0;
  text-align: center;
}

.loading-section p {
  margin-top: 16px;
  color: rgba(15, 23, 42, 0.65);
}

.divergence-positive {
  color: #16a34a;
}

.divergence-negative {
  color: #dc2626;
}

.divergence-neutral {
  color: #475569;
}

.theme-dark {
  .input-shell,
  .result-section {
    border-color: rgba(59, 130, 246, 0.16);
    background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.28);
  }

  .hero-eyebrow {
    color: #60a5fa;
  }

  .hero-title,
  .market-info h3,
  .text-block h4,
  .stat-value,
  .prob-value,
  .rec-value {
    color: #f8fafc;
  }

  .hero-desc,
  .text-block p,
  .loading-section p,
  .stat-label,
  .prob-label,
  .rec-label,
  .remaining-credits {
    color: rgba(248, 250, 252, 0.72);
  }

  .hero-stat,
  .prob-item,
  .rec-card {
    background: rgba(15, 23, 42, 0.72);
  }

  .divergence-neutral {
    color: #cbd5e1;
  }
}

@media (max-width: 900px) {
  .input-hero {
    flex-direction: column;
  }

  .hero-stats {
    min-width: 0;
  }
}

@media (max-width: 768px) {
  .input-shell,
  .result-section {
    padding: 18px;
  }

  .hero-title {
    font-size: 22px;
  }

  .hero-stats {
    grid-template-columns: 1fr;
  }

  .probability-comparison {
    flex-direction: column;
    align-items: stretch;
  }

  .recommendation-section /deep/ .ant-col {
    width: 100%;
    max-width: 100%;
    flex: 0 0 100%;
  }
}
</style>
