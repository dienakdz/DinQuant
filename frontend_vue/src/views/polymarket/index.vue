<template>
  <div class="polymarket-page" :class="{ 'theme-dark': isDarkTheme }">
    <div class="page-hero">
      <div class="hero-copy">
        <div class="hero-eyebrow">{{ tt('polymarket.analysis.title', 'Polymarket Analysis') }}</div>
        <h1>{{ tt('polymarket.analysis.heroTitle', 'Compare market pricing with AI conviction') }}</h1>
        <p>{{ tt('polymarket.analysis.description', 'Analyze a prediction market by URL or title and compare market pricing with AI probability.') }}</p>
      </div>
      <div class="hero-actions">
        <a-button size="large" icon="arrow-left" @click="$router.push('/ai-asset-analysis?tab=polymarket')">
          {{ tt('polymarket.analysis.backToAssetAnalysis', 'Back to AI Asset Analysis') }}
        </a-button>
      </div>
    </div>

    <polymarket-analysis-workspace ref="workspace" embedded />
  </div>
</template>

<script>
import { mapState } from 'vuex'
import PolymarketAnalysisWorkspace from '@/components/PolymarketAnalysisWorkspace.vue'

export default {
  name: 'PolymarketPage',
  components: {
    PolymarketAnalysisWorkspace
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
    '$route.query.input': {
      immediate: true,
      handler (value) {
        if (!value) return
        this.$nextTick(() => {
          const workspace = this.$refs.workspace
          if (workspace && workspace.startFromInput) {
            workspace.startFromInput(value)
          }
        })
      }
    }
  },
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    }
  }
}
</script>

<style lang="less" scoped>
.polymarket-page {
  min-height: calc(100vh - 120px);
  padding: 16px;
  background: linear-gradient(180deg, #f3f6fb 0%, #eef4fb 100%);
}

.page-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 18px;
  padding: 26px;
  border: 1px solid #dbe7f5;
  border-radius: 28px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 34%),
    linear-gradient(135deg, #ffffff 0%, #f8fbff 52%, #eef7ff 100%);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
}

.hero-copy {
  max-width: 760px;
}

.hero-eyebrow {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-hero h1 {
  margin: 10px 0 12px;
  color: #0f172a;
  font-size: 30px;
  font-weight: 700;
}

.page-hero p {
  margin: 0;
  color: rgba(15, 23, 42, 0.68);
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.theme-dark.polymarket-page {
  background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
}

.theme-dark .page-hero {
  border-color: rgba(59, 130, 246, 0.16);
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.22), transparent 34%),
    linear-gradient(135deg, #111827 0%, #0f172a 58%, #161b22 100%);
  box-shadow: 0 18px 42px rgba(0, 0, 0, 0.28);
}

.theme-dark .hero-eyebrow {
  color: #60a5fa;
}

.theme-dark .page-hero h1 {
  color: #f8fafc;
}

.theme-dark .page-hero p {
  color: rgba(248, 250, 252, 0.72);
}

@media (max-width: 900px) {
  .page-hero {
    flex-direction: column;
  }
}
</style>
