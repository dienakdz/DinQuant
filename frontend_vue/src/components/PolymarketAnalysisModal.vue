<template>
  <a-modal
    :visible="visible"
    :title="tt('polymarket.analysis.title', 'Polymarket Analysis')"
    :width="960"
    :footer="null"
    :destroyOnClose="true"
    :wrap-class-name="isDarkTheme ? 'qd-dark-modal' : ''"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <polymarket-analysis-workspace
      v-if="visible"
      show-close-action
      @close="handleClose"
    />
  </a-modal>
</template>

<script>
import { mapState } from 'vuex'
import PolymarketAnalysisWorkspace from '@/components/PolymarketAnalysisWorkspace.vue'

export default {
  name: 'PolymarketAnalysisModal',
  components: {
    PolymarketAnalysisWorkspace
  },
  props: {
    visible: {
      type: Boolean,
      default: false
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
  methods: {
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    handleClose () {
      this.$emit('close')
    }
  }
}
</script>
