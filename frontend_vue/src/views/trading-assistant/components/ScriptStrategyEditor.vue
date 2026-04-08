<template>
  <div class="script-strategy-editor" :class="{ 'theme-dark': isDark }">
    <div class="editor-toolbar">
      <div class="editor-title-group">
        <div class="editor-title">{{ tt('trading-assistant.editor.title', 'Script Editor') }}</div>
        <div class="editor-subtitle">{{ tt('trading-assistant.editor.subtitle', 'Write Python hooks directly, verify syntax and safety, or start from a template.') }}</div>
      </div>
      <div class="editor-actions">
        <a-button size="small" @click="handleVerifyCode" :loading="verifying">
          <a-icon type="check-circle" />
          {{ tt('trading-assistant.editor.verify', 'Verify') }}
        </a-button>
        <a-button size="small" @click="openDocsLink">
          <a-icon type="book" />
          {{ tt('trading-assistant.editor.docsButton', 'Open Docs') }}
        </a-button>
      </div>
    </div>

    <a-alert
      type="info"
      show-icon
      class="editor-alert"
      :message="tt('trading-assistant.editor.hintTitle', 'Script strategies run custom Python hooks')"
      :description="tt('trading-assistant.editor.hintDesc', 'Define at least on_init(ctx) and on_bar(ctx, bar). Use the docs tab for the helper API and the template tab for starter code.')"
    />

    <div class="editor-layout">
      <div class="code-pane">
        <div ref="codeEditorContainer" class="code-editor-container"></div>
      </div>

      <div class="side-pane">
        <a-tabs v-model="activeTab" size="small" class="editor-tabs">
          <a-tab-pane key="template" :tab="tt('trading-assistant.editor.templateTab', 'Templates')">
            <div class="side-section">
              <div class="section-title">{{ tt('trading-assistant.editor.templateIntroTitle', 'Starter Templates') }}</div>
              <div class="section-copy">{{ tt('trading-assistant.editor.templateIntroDesc', 'Choose a strategy scaffold, tune the parameters, then inject the generated code into the editor.') }}</div>

              <div class="template-list">
                <div
                  v-for="item in templateOptions"
                  :key="item.key"
                  class="template-card"
                  :class="{ active: selectedTemplateKey === item.key }"
                  @click="selectTemplate(item.key)">
                  <div class="template-card-head">
                    <span class="template-name">{{ item.title }}</span>
                    <a-tag size="small" :color="selectedTemplateKey === item.key ? 'blue' : 'default'">
                      {{ item.family }}
                    </a-tag>
                  </div>
                  <div class="template-desc">{{ item.description }}</div>
                </div>
              </div>

              <div v-if="selectedTemplate" class="template-params">
                <div class="params-head">
                  <span>{{ tt('trading-assistant.editor.paramsTab', 'Template Parameters') }}</span>
                  <span class="params-hint">{{ tt('trading-assistant.editor.paramsHint', 'Apply to overwrite the current editor content with the selected template.') }}</span>
                </div>

                <div class="param-grid">
                  <div v-for="param in selectedTemplate.params" :key="param.key" class="param-item">
                    <label class="param-label">{{ param.label }}</label>
                    <a-select
                      v-if="param.type === 'select'"
                      v-model="templateParamValues[param.key]"
                      size="small"
                      :getPopupContainer="getPopupContainer">
                      <a-select-option v-for="option in param.options" :key="option.value" :value="option.value">
                        {{ option.label }}
                      </a-select-option>
                    </a-select>
                    <a-input-number
                      v-else
                      v-model="templateParamValues[param.key]"
                      size="small"
                      :min="param.min"
                      :max="param.max"
                      :step="param.step || 1"
                      :precision="param.precision"
                      style="width: 100%" />
                  </div>
                </div>

                <div class="template-actions">
                  <a-button size="small" @click="resetTemplateParams">
                    {{ tt('trading-assistant.editor.resetTemplateParams', 'Reset') }}
                  </a-button>
                  <a-button type="primary" size="small" @click="applySelectedTemplateToCode">
                    {{ tt('trading-assistant.editor.applyTemplateParams', 'Apply Template') }}
                  </a-button>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="docs" :tab="tt('trading-assistant.editor.docsTab', 'Docs')">
            <div class="side-section docs-section">
              <div class="section-title">{{ tt('trading-assistant.editor.docsIntroTitle', 'Strategy API Reference') }}</div>
              <div class="section-copy">{{ tt('trading-assistant.editor.docsIntroDesc', 'The private build exposes the same hook model below. Keep the required hooks and use the ctx helpers shown here.') }}</div>

              <div class="docs-card">
                <div class="docs-subtitle">{{ tt('trading-assistant.editor.requiredHooks', 'Required Hooks') }}</div>
                <pre class="docs-code">def on_init(ctx):
    pass

def on_bar(ctx, bar):
    pass

def on_order_filled(ctx, order):
    pass

def on_stop(ctx):
    pass</pre>
              </div>

              <div class="docs-card">
                <div class="docs-subtitle">{{ tt('trading-assistant.editor.contextHelpers', 'Context Helpers') }}</div>
                <ul class="docs-list">
                  <li><code>ctx.buy(price, amount)</code></li>
                  <li><code>ctx.sell(price, amount)</code></li>
                  <li><code>ctx.close_position()</code></li>
                  <li><code>ctx.cancel_all_orders()</code></li>
                  <li><code>ctx.bars(n)</code></li>
                  <li><code>ctx.param(name, default)</code></li>
                  <li><code>ctx.position</code>, <code>ctx.balance</code>, <code>ctx.equity</code>, <code>ctx.log(message)</code></li>
                </ul>
              </div>

              <div class="docs-card">
                <div class="docs-subtitle">{{ tt('trading-assistant.editor.barFields', 'Bar Fields') }}</div>
                <pre class="docs-code">bar.open
bar.high
bar.low
bar.close
bar.volume
bar.timestamp</pre>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="ai" :tab="tt('trading-assistant.editor.aiTab', 'AI')">
            <div class="side-section">
              <div class="section-title">{{ tt('trading-assistant.editor.aiGenerate', 'Generate with AI') }}</div>
              <div class="section-copy">{{ tt('trading-assistant.editor.aiHint', 'Describe your trading idea in plain English. The backend returns Python code only.') }}</div>

              <div class="prompt-suggestions">
                <a-tag v-for="item in aiPromptSuggestions" :key="item.key" @click="applyPromptSuggestion(item.prompt)">
                  {{ item.label }}
                </a-tag>
              </div>

              <a-textarea
                v-model="aiPrompt"
                :rows="9"
                :auto-size="{ minRows: 9, maxRows: 14 }"
                :placeholder="tt('trading-assistant.editor.aiPromptPlaceholder', 'Example: Build a BTC breakout strategy that buys when price closes above the highest close of the last 20 bars and exits with a 2% stop loss.')"
              />

              <a-button
                type="primary"
                block
                size="large"
                :loading="aiGenerating"
                class="generate-btn"
                @click="handleAIGenerate">
                <a-icon type="robot" />
                {{ tt('trading-assistant.editor.aiGenerateBtn', 'Generate Code') }}
              </a-button>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>
  </div>
</template>

<script>
import CodeMirror from 'codemirror'
import 'codemirror/lib/codemirror.css'
import 'codemirror/mode/python/python'
import 'codemirror/theme/monokai.css'
import 'codemirror/theme/eclipse.css'
import 'codemirror/addon/edit/closebrackets'
import 'codemirror/addon/edit/matchbrackets'
import 'codemirror/addon/selection/active-line'
import { aiGenerateStrategyCode, verifyStrategyCode } from '@/api/strategy'

export default {
  name: 'ScriptStrategyEditor',
  props: {
    value: {
      type: String,
      default: ''
    },
    active: {
      type: Boolean,
      default: false
    },
    isDark: {
      type: Boolean,
      default: false
    },
    initialTemplateKey: {
      type: String,
      default: 'ma_cross'
    },
    templateApplyNonce: {
      type: Number,
      default: 0
    }
  },
  data () {
    return {
      codeEditor: null,
      activeTab: 'template',
      aiPrompt: '',
      aiGenerating: false,
      verifying: false,
      selectedTemplateKey: 'ma_cross',
      templateParamValues: {}
    }
  },
  computed: {
    templateOptions () {
      return [
        {
          key: 'ma_cross',
          title: 'Moving Average Cross',
          family: 'Trend',
          description: 'Follow directional momentum with a fast and slow average crossover.',
          params: [
            { key: 'fast', label: 'Fast MA', type: 'number', default: 10, min: 2, max: 100, step: 1, precision: 0 },
            { key: 'slow', label: 'Slow MA', type: 'number', default: 30, min: 5, max: 200, step: 1, precision: 0 },
            { key: 'positionSize', label: 'Order Size', type: 'number', default: 1, min: 0.01, max: 100, step: 0.1, precision: 2 }
          ]
        },
        {
          key: 'rsi_reversion',
          title: 'RSI Mean Reversion',
          family: 'Mean Reversion',
          description: 'Buy oversold conditions and fade overbought moves with RSI thresholds.',
          params: [
            { key: 'period', label: 'RSI Period', type: 'number', default: 14, min: 2, max: 100, step: 1, precision: 0 },
            { key: 'oversold', label: 'Oversold', type: 'number', default: 30, min: 1, max: 50, step: 1, precision: 0 },
            { key: 'overbought', label: 'Overbought', type: 'number', default: 70, min: 50, max: 99, step: 1, precision: 0 },
            { key: 'positionSize', label: 'Order Size', type: 'number', default: 1, min: 0.01, max: 100, step: 0.1, precision: 2 }
          ]
        },
        {
          key: 'breakout',
          title: 'Donchian Breakout',
          family: 'Breakout',
          description: 'Enter on a range breakout and close when price loses the breakout level.',
          params: [
            { key: 'lookback', label: 'Lookback Bars', type: 'number', default: 20, min: 5, max: 200, step: 1, precision: 0 },
            { key: 'bufferPct', label: 'Breakout Buffer %', type: 'number', default: 0.2, min: 0, max: 10, step: 0.1, precision: 2 },
            { key: 'positionSize', label: 'Order Size', type: 'number', default: 1, min: 0.01, max: 100, step: 0.1, precision: 2 }
          ]
        }
      ]
    },
    selectedTemplate () {
      return this.templateOptions.find(item => item.key === this.selectedTemplateKey) || null
    },
    aiPromptSuggestions () {
      return [
        {
          key: 'improve',
          label: this.tt('trading-assistant.editor.aiSuggestionImprove', 'Improve MA crossover'),
          prompt: 'Improve a moving-average crossover strategy with volatility filter and safer exits.'
        },
        {
          key: 'risk',
          label: this.tt('trading-assistant.editor.aiSuggestionRisk', 'Add risk controls'),
          prompt: 'Create a breakout strategy with stop loss, cooldown, and no-trade filter during low volume.'
        },
        {
          key: 'explain',
          label: this.tt('trading-assistant.editor.aiSuggestionExplain', 'Explainable reversion'),
          prompt: 'Generate a mean-reversion strategy that logs why it enters and exits each position.'
        }
      ]
    }
  },
  watch: {
    value (nextValue) {
      if (!this.codeEditor) return
      const editorValue = this.codeEditor.getValue()
      if (nextValue !== editorValue) {
        this.codeEditor.setValue(nextValue || this.buildDefaultCode())
        this.codeEditor.refresh()
      }
    },
    active (isActive) {
      if (isActive && this.codeEditor) {
        this.$nextTick(() => this.codeEditor.refresh())
      }
    },
    initialTemplateKey: {
      immediate: true,
      handler (nextKey) {
        this.selectTemplate(nextKey || 'ma_cross')
      }
    },
    templateApplyNonce: {
      immediate: true,
      handler (nextValue) {
        if (nextValue) {
          this.selectTemplate(this.initialTemplateKey || 'ma_cross')
          this.$nextTick(() => this.applySelectedTemplateToCode())
        }
      }
    }
  },
  mounted () {
    this.$nextTick(() => {
      this.initCodeEditor()
    })
  },
  beforeDestroy () {
    if (this.codeEditor) {
      try {
        if (typeof this.codeEditor.toTextArea === 'function') {
          this.codeEditor.toTextArea()
        } else if (typeof this.codeEditor.getWrapperElement === 'function') {
          const wrapper = this.codeEditor.getWrapperElement()
          if (wrapper && wrapper.parentNode) {
            wrapper.parentNode.removeChild(wrapper)
          }
        }
      } catch (e) {}
      this.codeEditor = null
    }
  },
  methods: {
    tt (key, fallback) {
      const translated = this.$t(key)
      return translated !== key ? translated : fallback
    },
    getPopupContainer (triggerNode) {
      return (triggerNode && triggerNode.parentNode) || document.body
    },
    initCodeEditor () {
      if (!this.$refs.codeEditorContainer) return

      this.$refs.codeEditorContainer.innerHTML = ''
      this.codeEditor = CodeMirror(this.$refs.codeEditorContainer, {
        value: this.value || this.buildDefaultCode(),
        mode: 'python',
        theme: this.isDark ? 'monokai' : 'eclipse',
        lineNumbers: true,
        lineWrapping: true,
        indentUnit: 4,
        indentWithTabs: false,
        smartIndent: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        styleActiveLine: true,
        gutters: ['CodeMirror-linenumbers'],
        tabSize: 4,
        viewportMargin: Infinity
      })

      this.codeEditor.on('change', (editor) => {
        this.$emit('input', editor.getValue())
      })

      this.$nextTick(() => {
        if (this.codeEditor) {
          this.codeEditor.refresh()
        }
      })
    },
    cleanMarkdownCodeBlocks (code) {
      if (!code || typeof code !== 'string') {
        return code
      }

      let cleanedCode = code.trim()
      cleanedCode = cleanedCode.replace(/^```[\w]*\s*\n?/i, '')
      cleanedCode = cleanedCode.replace(/\n?```\s*$/g, '')
      cleanedCode = cleanedCode.replace(/^\s*```[\w]*\s*$/gm, '')
      cleanedCode = cleanedCode.replace(/^\s*```\s*$/gm, '')
      cleanedCode = cleanedCode.replace(/\n{3,}/g, '\n\n')
      return cleanedCode.trim()
    },
    applyPromptSuggestion (prompt) {
      this.aiPrompt = prompt
      this.activeTab = 'ai'
    },
    selectTemplate (templateKey) {
      const found = this.templateOptions.find(item => item.key === templateKey) || this.templateOptions[0]
      this.selectedTemplateKey = found.key
      const nextValues = {}
      found.params.forEach(param => {
        nextValues[param.key] = param.default
      })
      this.templateParamValues = nextValues
    },
    resetTemplateParams () {
      this.selectTemplate(this.selectedTemplateKey)
    },
    applySelectedTemplateToCode () {
      if (!this.selectedTemplate) return
      const code = this.buildTemplateCode(this.selectedTemplateKey, this.templateParamValues)
      if (this.codeEditor) {
        this.codeEditor.setValue(code)
        this.codeEditor.refresh()
      }
      this.$emit('input', code)
      this.$message.success(this.tt('trading-assistant.editor.templateApplied', 'Template applied to the editor'))
    },
    buildDefaultCode () {
      return `def on_init(ctx):
    ctx.log("strategy initialized")


def on_bar(ctx, bar):
    closes = [item.close for item in ctx.bars(20)]
    if len(closes) < 20:
        return

    latest_close = closes[-1]
    average_close = sum(closes) / len(closes)

    if not ctx.position and latest_close > average_close:
        ctx.buy(price=latest_close, amount=1)
    elif ctx.position and latest_close < average_close:
        ctx.close_position()


def on_order_filled(ctx, order):
    ctx.log(f"order filled: {order}")


def on_stop(ctx):
    ctx.log("strategy stopped")
`
    },
    buildTemplateCode (templateKey, params) {
      if (templateKey === 'rsi_reversion') {
        return `def compute_rsi(closes, period):
    gains = []
    losses = []
    for idx in range(1, len(closes)):
        delta = closes[idx] - closes[idx - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def on_init(ctx):
    ctx.param("period", ${Number(params.period || 14)})
    ctx.param("oversold", ${Number(params.oversold || 30)})
    ctx.param("overbought", ${Number(params.overbought || 70)})
    ctx.param("position_size", ${Number(params.positionSize || 1)})


def on_bar(ctx, bar):
    period = int(ctx.param("period", ${Number(params.period || 14)}))
    bars = ctx.bars(period + 2)
    if len(bars) < period + 1:
        return

    closes = [item.close for item in bars]
    rsi = compute_rsi(closes, period)
    latest_price = closes[-1]

    if not ctx.position and rsi <= ctx.param("oversold", ${Number(params.oversold || 30)}):
        ctx.buy(price=latest_price, amount=ctx.param("position_size", ${Number(params.positionSize || 1)}))
    elif ctx.position and rsi >= ctx.param("overbought", ${Number(params.overbought || 70)}):
        ctx.close_position()


def on_order_filled(ctx, order):
    ctx.log(f"rsi strategy fill: {order}")


def on_stop(ctx):
    ctx.log("rsi reversion strategy stopped")
`
      }

      if (templateKey === 'breakout') {
        return `def on_init(ctx):
    ctx.param("lookback", ${Number(params.lookback || 20)})
    ctx.param("buffer_pct", ${Number(params.bufferPct || 0.2)})
    ctx.param("position_size", ${Number(params.positionSize || 1)})


def on_bar(ctx, bar):
    lookback = int(ctx.param("lookback", ${Number(params.lookback || 20)}))
    bars = ctx.bars(lookback + 1)
    if len(bars) < lookback + 1:
        return

    closes = [item.close for item in bars[:-1]]
    highest_close = max(closes)
    breakout_level = highest_close * (1 + ctx.param("buffer_pct", ${Number(params.bufferPct || 0.2)}) / 100)

    if not ctx.position and bar.close > breakout_level:
        ctx.buy(price=bar.close, amount=ctx.param("position_size", ${Number(params.positionSize || 1)}))
    elif ctx.position and bar.close < highest_close:
        ctx.close_position()


def on_order_filled(ctx, order):
    ctx.log(f"breakout fill: {order}")


def on_stop(ctx):
    ctx.log("breakout strategy stopped")
`
      }

      return `def sma(values, period):
    return sum(values[-period:]) / period


def on_init(ctx):
    ctx.param("fast", ${Number(params.fast || 10)})
    ctx.param("slow", ${Number(params.slow || 30)})
    ctx.param("position_size", ${Number(params.positionSize || 1)})


def on_bar(ctx, bar):
    slow = int(ctx.param("slow", ${Number(params.slow || 30)}))
    fast = int(ctx.param("fast", ${Number(params.fast || 10)}))
    bars = ctx.bars(slow + 2)
    if len(bars) < slow + 1:
        return

    closes = [item.close for item in bars]
    fast_now = sma(closes, fast)
    slow_now = sma(closes, slow)
    fast_prev = sma(closes[:-1], fast)
    slow_prev = sma(closes[:-1], slow)

    crossed_up = fast_prev <= slow_prev and fast_now > slow_now
    crossed_down = fast_prev >= slow_prev and fast_now < slow_now

    if not ctx.position and crossed_up:
        ctx.buy(price=bar.close, amount=ctx.param("position_size", ${Number(params.positionSize || 1)}))
    elif ctx.position and crossed_down:
        ctx.close_position()


def on_order_filled(ctx, order):
    ctx.log(f"ma cross fill: {order}")


def on_stop(ctx):
    ctx.log("moving average strategy stopped")
`
    },
    async handleVerifyCode () {
      const code = this.codeEditor ? this.codeEditor.getValue() : this.value
      if (!code || !code.trim()) {
        this.$message.warning(this.tt('trading-assistant.editor.codeHint', 'Please add strategy code before continuing'))
        return
      }

      this.verifying = true
      try {
        const res = await verifyStrategyCode(code)
        if (res && res.success) {
          this.$message.success(res.message || this.tt('trading-assistant.editor.verifySuccess', 'Code verification passed'))
        } else {
          this.$message.error((res && res.message) || this.tt('trading-assistant.editor.verifyFailed', 'Code verification failed'))
        }
      } catch (error) {
        this.$message.error(error.message || this.tt('trading-assistant.editor.verifyFailed', 'Code verification failed'))
      } finally {
        this.verifying = false
      }
    },
    async handleAIGenerate () {
      if (!this.aiPrompt || !this.aiPrompt.trim()) {
        this.$message.warning(this.tt('trading-assistant.editor.aiPromptRequired', 'Please enter your idea before generating code'))
        return
      }

      this.aiGenerating = true
      try {
        const res = await aiGenerateStrategyCode(this.aiPrompt.trim())
        const generatedCode = this.cleanMarkdownCodeBlocks(res && res.code ? res.code : '')
        if (!generatedCode) {
          this.$message.error((res && res.msg) || this.tt('trading-assistant.editor.aiGenerateFailed', 'AI code generation failed'))
          return
        }

        if (this.codeEditor) {
          this.codeEditor.setValue(generatedCode)
          this.codeEditor.refresh()
        }
        this.$emit('input', generatedCode)
        this.$message.success(this.tt('trading-assistant.editor.aiGenerateSuccess', 'Code generated successfully'))
      } catch (error) {
        this.$message.error(error.message || this.tt('trading-assistant.editor.aiGenerateFailed', 'AI code generation failed'))
      } finally {
        this.aiGenerating = false
      }
    },
    openDocsLink () {
      window.open('https://github.com/brokermr810/QuantDinger/blob/main/docs/STRATEGY_DEV_GUIDE.md', '_blank')
    }
  }
}
</script>

<style lang="less" scoped>
.script-strategy-editor {
  .editor-toolbar {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .editor-title {
    font-size: 18px;
    font-weight: 600;
    color: #1f1f1f;
  }

  .editor-subtitle {
    margin-top: 4px;
    font-size: 13px;
    line-height: 1.6;
    color: #8c8c8c;
  }

  .editor-actions {
    display: flex;
    gap: 8px;
  }

  .editor-alert {
    margin-bottom: 16px;
  }

  .editor-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.85fr);
    gap: 16px;
    align-items: stretch;
  }

  .code-pane,
  .side-pane {
    min-width: 0;
  }

  .code-editor-container {
    min-height: 520px;
    border: 1px solid #d9d9d9;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
  }

  /deep/ .CodeMirror {
    height: 520px;
    font-size: 13px;
  }

  .editor-tabs {
    height: 100%;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    background: #fff;
  }

  .side-section {
    padding: 4px 4px 0;
  }

  .section-title {
    font-size: 15px;
    font-weight: 600;
    color: #1f1f1f;
  }

  .section-copy {
    margin-top: 6px;
    margin-bottom: 14px;
    font-size: 13px;
    line-height: 1.6;
    color: #8c8c8c;
  }

  .template-list {
    display: grid;
    gap: 10px;
  }

  .template-card {
    padding: 12px;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      border-color: #91d5ff;
      box-shadow: 0 6px 18px rgba(24, 144, 255, 0.08);
    }

    &.active {
      border-color: #1890ff;
      background: #f0f7ff;
    }
  }

  .template-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
  }

  .template-name {
    font-size: 14px;
    font-weight: 600;
  }

  .template-desc {
    font-size: 12px;
    line-height: 1.6;
    color: #666;
  }

  .template-params {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid #f0f0f0;
  }

  .params-head {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 10px;
  }

  .params-hint {
    font-size: 12px;
    color: #8c8c8c;
  }

  .param-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .param-item {
    min-width: 0;
  }

  .param-label {
    display: block;
    margin-bottom: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #4a4a4a;
  }

  .template-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
  }

  .docs-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .docs-card {
    padding: 12px;
    border: 1px solid #f0f0f0;
    border-radius: 8px;
    background: #fafafa;
  }

  .docs-subtitle {
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 600;
  }

  .docs-code {
    margin: 0;
    padding: 10px;
    overflow: auto;
    border-radius: 6px;
    background: #111827;
    color: #dbeafe;
    font-size: 12px;
    line-height: 1.6;
  }

  .docs-list {
    margin: 0;
    padding-left: 18px;
    font-size: 12px;
    line-height: 1.8;
    color: #4a4a4a;
  }

  .prompt-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;

    .ant-tag {
      cursor: pointer;
      user-select: none;
    }
  }

  .generate-btn {
    margin-top: 12px;
  }

  &.theme-dark {
    .editor-title,
    .section-title,
    .template-name,
    .docs-subtitle,
    .param-label {
      color: #f5f5f5;
    }

    .editor-subtitle,
    .section-copy,
    .template-desc,
    .params-hint,
    .docs-list {
      color: rgba(255, 255, 255, 0.72);
    }

    .code-editor-container,
    .editor-tabs {
      border-color: rgba(255, 255, 255, 0.12);
      background: #111827;
    }

    .template-card {
      border-color: rgba(255, 255, 255, 0.12);
      background: #111827;

      &.active {
        border-color: #177ddc;
        background: rgba(23, 125, 220, 0.12);
      }
    }

    .template-params {
      border-top-color: rgba(255, 255, 255, 0.12);
    }

    .docs-card {
      border-color: rgba(255, 255, 255, 0.12);
      background: rgba(255, 255, 255, 0.04);
    }
  }

  @media (max-width: 992px) {
    .editor-layout {
      grid-template-columns: 1fr;
    }

    .code-editor-container {
      min-height: 420px;
    }

    /deep/ .CodeMirror {
      height: 420px;
    }
  }

  @media (max-width: 640px) {
    .editor-toolbar {
      flex-direction: column;
    }

    .editor-actions {
      width: 100%;
    }

    .editor-actions .ant-btn {
      flex: 1;
    }

    .param-grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>
