<template>
  <div class="strategy-type-selector" :class="{ 'theme-dark': isDark }">
    <a-row :gutter="16">
      <a-col :xs="24" :md="12">
        <div
          class="strategy-type-card"
          :class="{ selected: selected === 'indicator' }"
          @click="$emit('select', 'indicator')">
          <div class="strategy-type-content">
            <div class="strategy-type-icon">
              <a-icon type="line-chart" />
            </div>
            <h3>{{ tt('trading-assistant.strategyMode.indicator', 'Indicator Strategy') }}</h3>
            <p>{{ tt('trading-assistant.strategyMode.indicatorDesc', 'Build a strategy from your custom or purchased indicators, then add execution and risk settings.') }}</p>
          </div>
        </div>
      </a-col>

      <a-col :xs="24" :md="12">
        <div
          class="strategy-type-card"
          :class="{ selected: selected === 'script' }"
          @click="$emit('select', 'script')">
          <div class="strategy-type-content">
            <div class="strategy-type-icon">
              <a-icon type="code" />
            </div>
            <h3>{{ tt('trading-assistant.strategyMode.script', 'Script Strategy') }}</h3>
            <p>{{ tt('trading-assistant.strategyMode.scriptDesc', 'Write Python hooks directly, use built-in starter templates, and verify the strategy before launch.') }}</p>
            <a-button type="primary" size="small" @click.stop="$emit('use-template', { mode: 'script', templateKey: 'ma_cross' })">
              <a-icon type="copy" />
              {{ tt('trading-assistant.strategyMode.useTemplate', 'Use Starter Template') }}
            </a-button>
          </div>
        </div>
      </a-col>
    </a-row>
  </div>
</template>

<script>
export default {
  name: 'StrategyTypeSelector',
  props: {
    selected: {
      type: String,
      default: 'indicator'
    },
    isDark: {
      type: Boolean,
      default: false
    }
  },
  methods: {
    tt (key, fallback) {
      const translated = this.$t(key)
      return translated !== key ? translated : fallback
    }
  }
}
</script>
