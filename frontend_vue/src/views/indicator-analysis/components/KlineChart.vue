<template>
  <div class="chart-left" :class="{ 'theme-dark': chartTheme === 'dark' }">
    <div class="chart-wrapper">
      <!-- Drawing Tools Toolbar -->
      <div class="drawing-toolbar">
        <a-tooltip
          v-for="tool in drawingTools"
          :key="tool.name"
          :title="tool.title"
          placement="right"
        >
          <div
            class="drawing-tool-btn"
            :class="{ active: activeDrawingTool === tool.name }"
            @click="selectDrawingTool(tool.name)"
          >
            <a-icon :type="tool.icon" />
          </div>
        </a-tooltip>
        <a-divider type="vertical" />
        <a-tooltip :title="$t('dashboard.indicator.drawing.clearAll')" placement="right">
          <div class="drawing-tool-btn" @click="clearAllDrawings">
            <a-icon type="delete" />
          </div>
        </a-tooltip>
      </div>
      <!-- Chart Content Area -->
      <div class="chart-content-area">
        <!-- Indicators Toolbar -->
        <div class="indicator-toolbar">
          <div
            v-for="indicator in indicatorButtons"
            :key="indicator.id"
            class="indicator-btn"
            :class="{ active: isIndicatorActive(indicator.id) }"
            @click="toggleIndicator(indicator)"
            :title="indicator.name"
          >
            {{ indicator.shortName }}
          </div>
        </div>
        <div
          id="kline-chart-container"
          class="kline-chart-container"
        ></div>
      </div>

      <div v-if="loading" class="chart-overlay">
        <a-spin size="large">
          <a-icon slot="indicator" type="loading" style="font-size: 24px; color: #13c2c2" spin />
        </a-spin>
      </div>

      <div v-if="error" class="chart-overlay">
        <div class="error-box">
          <a-icon type="warning" style="font-size: 24px; color: #ef5350; margin-bottom: 10px" />
          <span>{{ error }}</span>
          <a-button type="primary" size="small" ghost @click="handleRetry" style="margin-top: 12px">
            {{ $t('dashboard.indicator.retry') }}
          </a-button>
        </div>
      </div>

      <!-- Pyodide Load Failed Hint -->
      <div v-if="pyodideLoadFailed" class="chart-overlay pyodide-warning">
        <div class="warning-box">
          <a-icon type="warning" style="font-size: 32px; color: #faad14; margin-bottom: 12px" />
          <div class="warning-title">{{ $t('dashboard.indicator.warning.pyodideLoadFailed') }}</div>
          <div class="warning-desc">{{ $t('dashboard.indicator.warning.pyodideLoadFailedDesc') }}</div>
        </div>
      </div>

      <!-- Initial Mask Hint -->
      <div v-if="!symbol && !loading && !error && !pyodideLoadFailed" class="chart-overlay initial-hint">
        <div class="hint-box">
          <a-icon type="line-chart" style="font-size: 48px; color: #1890ff; margin-bottom: 16px" />
          <div class="hint-title">{{ $t('dashboard.indicator.hint.selectSymbol') }}</div>
          <div class="hint-desc">{{ $t('dashboard.indicator.hint.selectSymbolDesc') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch, shallowRef, getCurrentInstance } from 'vue'
import { init, registerIndicator, registerOverlay } from 'klinecharts'
import request from '@/utils/request'
import { decryptCodeAuto, needsDecrypt } from '@/utils/codeDecrypt'

export default {
  name: 'KlineChart',
  props: {
    symbol: {
      type: String,
      default: ''
    },
    market: {
      type: String,
      default: ''
    },
    timeframe: {
      type: String,
      default: '1H'
    },
    theme: {
      type: String,
      default: 'light'
    },
    activeIndicators: {
      type: Array,
      default: () => []
    },
    realtimeEnabled: {
      type: Boolean,
      default: false
    },
    userId: {
      type: Number,
      default: null
    }
  },
  emits: ['retry', 'price-change', 'load', 'indicator-toggle'],
  setup (props, { emit }) {
    // K-line data
    const klineData = shallowRef([])
    const loading = ref(false)
    const error = ref(null)
    const loadingHistory = ref(false)
    const hasMoreHistory = ref(true)
    // Track ongoing load requests to prevent duplicate requests
    let loadingHistoryPromise = null
    // Mark if chart is initialized to avoid triggering load during initialization
    const chartInitialized = ref(false)

    // Chart instance
    const chartRef = shallowRef(null)
    const chartTheme = ref(props.theme || 'light')

    // Real-time update settings
    const realtimeTimer = ref(null)
    const realtimeInterval = ref(5000)

    // Indicator refresh lock: avoid updateIndicators re-entry when real-time timer triggers (Python indicators might be slow)
    const indicatorsUpdating = ref(false)
    // Indicator refresh throttle: K-line/price can refresh at high frequency, but indicators can refresh at lower frequency (default 10s)
    const indicatorRefreshInterval = ref(10000)
    const lastIndicatorRefreshTs = ref(0)

    // When K-line refresh is frequent, indicator calculations don't need to sync; throttle used here (with re-entry lock).
    const maybeUpdateIndicators = (force = false) => {
      if (!chartRef.value) return
      const now = Date.now()
      const iv = Number(indicatorRefreshInterval.value || 10000)
      if (force || !lastIndicatorRefreshTs.value || (now - lastIndicatorRefreshTs.value) >= iv) {
        lastIndicatorRefreshTs.value = now
        updateIndicators()
      }
    }

    // List of added indicator IDs (for cleanup)
    const addedIndicatorIds = ref([])
    // List of added signal overlay IDs (for cleanup)
    const addedSignalOverlayIds = ref([])
    // List of added drawing overlay IDs (for cleanup and management)
    const addedDrawingOverlayIds = ref([])
    // Currently active drawing tool
    const activeDrawingTool = ref(null)

    // Drawing tool definitions (uses computed for multi-language support)
    const { proxy } = getCurrentInstance()

    const drawingTools = computed(() => [
      { name: 'line', title: proxy.$t('dashboard.indicator.drawing.line'), icon: 'line' },
      { name: 'horizontalLine', title: proxy.$t('dashboard.indicator.drawing.horizontalLine'), icon: 'minus' },
      { name: 'verticalLine', title: proxy.$t('dashboard.indicator.drawing.verticalLine'), icon: 'column-width' },
      { name: 'ray', title: proxy.$t('dashboard.indicator.drawing.ray'), icon: 'arrow-right' },
      { name: 'straightLine', title: proxy.$t('dashboard.indicator.drawing.straightLine'), icon: 'menu' },
      { name: 'parallelStraightLine', title: proxy.$t('dashboard.indicator.drawing.parallelLine'), icon: 'menu' },
      { name: 'priceLine', title: proxy.$t('dashboard.indicator.drawing.priceLine'), icon: 'dollar' },
      { name: 'priceChannelLine', title: proxy.$t('dashboard.indicator.drawing.priceChannel'), icon: 'border' },
      { name: 'fibonacciLine', title: proxy.$t('dashboard.indicator.drawing.fibonacciLine'), icon: 'rise' }
    ])

    // Indicator button definitions
    const indicatorButtons = ref([
      { id: 'sma', name: 'SMA (Simple Moving Average)', shortName: 'SMA', type: 'line', defaultParams: { length: 20 } },
      { id: 'ema', name: 'EMA (Exponential Moving Average)', shortName: 'EMA', type: 'line', defaultParams: { length: 20 } },
      { id: 'rsi', name: 'RSI (Relative Strength Index)', shortName: 'RSI', type: 'line', defaultParams: { length: 14 } },
      { id: 'macd', name: 'MACD', shortName: 'MACD', type: 'macd', defaultParams: { fast: 12, slow: 26, signal: 9 } },
      { id: 'bb', name: 'Bollinger Bands', shortName: 'BB', type: 'band', defaultParams: { length: 20, mult: 2 } },
      { id: 'atr', name: 'ATR (Average True Range)', shortLine: 'ATR', type: 'line', defaultParams: { period: 14 } },
      { id: 'cci', name: 'CCI (Commodity Channel Index)', shortName: 'CCI', type: 'line', defaultParams: { length: 20 } },
      { id: 'williams', name: 'Williams %R', shortName: 'W%R', type: 'line', defaultParams: { length: 14 } },
      { id: 'mfi', name: 'MFI (Money Flow Index)', shortName: 'MFI', type: 'line', defaultParams: { length: 14 } },
      { id: 'adx', name: 'ADX (Average Directional Index)', shortName: 'ADX', type: 'adx', defaultParams: { length: 14 } },
      { id: 'obv', name: 'OBV (On-Balance Volume)', shortName: 'OBV', type: 'line', defaultParams: {} },
      { id: 'adosc', name: 'ADOSC (Accumulation/Distribution Oscillator)', shortName: 'ADOSC', type: 'line', defaultParams: { fast: 3, slow: 10 } },
      { id: 'ad', name: 'AD (Accumulation/Distribution Line)', shortName: 'AD', type: 'line', defaultParams: {} },
      { id: 'kdj', name: 'KDJ (Stochastic Oscillator)', shortName: 'KDJ', type: 'line', defaultParams: { period: 9, k: 3, d: 3 } }
    ])

    // Check if indicator is active
    const isIndicatorActive = (indicatorId) => {
      return props.activeIndicators.some(ind => ind.id === indicatorId)
    }

    // Select drawing tool
    const selectDrawingTool = (toolName) => {
      if (!chartRef.value) {
        return
      }

      // Tool name mapping (UI tool name -> klinecharts internal overlay name)
      const toolMap = {
        line: 'segment',
        horizontalLine: 'horizontalStraightLine',
        verticalLine: 'verticalStraightLine',
        ray: 'rayLine',
        straightLine: 'straightLine',
        parallelStraightLine: 'parallelStraightLine',
        priceLine: 'priceLine',
        priceChannelLine: 'priceChannelLine',
        fibonacciLine: 'fibonacciLine'
      }

      const overlayName = toolMap[toolName] || toolName

      // If current tool is clicked again, deactivate it
      if (activeDrawingTool.value === toolName) {
        activeDrawingTool.value = null
        // Cancel current drawing mode
        // KLineChart lacks a direct "cancelDrawing" API; usually removes the last incomplete overlay
        // Or use overrideOverlay(null) to cancel ongoing actions (if supported)
        try {
          if (typeof chartRef.value.overrideOverlay === 'function') {
            chartRef.value.overrideOverlay(null)
          }
        } catch (e) {
        }
        return
      }

      // Activate new drawing tool
      activeDrawingTool.value = toolName

      try {
        // Prepare overlay configuration
        const overlayConfig = {
          name: overlayName,
          lock: false, // Allow editing
          extendData: {
            isDrawing: true // Flag as drawing
          }
        }

        // Call createOverlay without points; library automatically enters drawing mode
        const overlayId = chartRef.value.createOverlay(overlayConfig)

        if (overlayId) {
          addedDrawingOverlayIds.value.push(overlayId)
        } else {
          activeDrawingTool.value = null
        }
      } catch (err) {
        activeDrawingTool.value = null
      }
    }

    // Clear all drawings
    const clearAllDrawings = () => {
      if (!chartRef.value) return

      try {
        // Remove all added drawing overlays
        addedDrawingOverlayIds.value.forEach(overlayId => {
          try {
            if (typeof chartRef.value.removeOverlay === 'function') {
              chartRef.value.removeOverlay(overlayId)
            } else if (typeof chartRef.value.removeOverlayById === 'function') {
              chartRef.value.removeOverlayById(overlayId)
            }
          } catch (err) {
          }
        })
        addedDrawingOverlayIds.value = []
        activeDrawingTool.value = null

        // Cancel current drawing mode
        if (typeof chartRef.value.overrideOverlay === 'function') {
          chartRef.value.overrideOverlay(null)
        }
      } catch (err) {
      }
    }

    // Toggle indicator visibility
    const toggleIndicator = (indicator) => {
      const isActive = isIndicatorActive(indicator.id)

      if (isActive) {
        // Remove indicator
        emit('indicator-toggle', {
          action: 'remove',
          indicator: { id: indicator.id }
        })
      } else {
        // Add indicator
        const indicatorToAdd = {
          ...indicator,
          params: { ...indicator.defaultParams },
          calculate: null // calculate function determined by id in updateIndicators
        }
        emit('indicator-toggle', {
          action: 'add',
          indicator: indicatorToAdd
        })
      }
    }

    // Pyodide related
    const pyodide = ref(null)
    const loadingPython = ref(false)
    const pythonReady = ref(false)
    const pyodideLoadFailed = ref(false)

    // Theme configuration
    const themeConfig = computed(() => {
      if (chartTheme.value === 'dark') {
        return {
          backgroundColor: '#131722',
          textColor: '#d1d4dc',
          textColorSecondary: '#787b86',
          borderColor: '#2a2e39',
          gridLineColor: '#1f2943',
          gridLineColorDashed: '#363c4e',
          tooltipBg: 'rgba(25, 27, 32, 0.95)',
          tooltipBorder: '#333',
          tooltipText: '#ccc',
          tooltipTextSecondary: '#888',
          axisLabelColor: '#787b86',
          splitAreaColor: ['rgba(250,250,250,0.05)', 'rgba(200,200,200,0.02)'],
          dataZoomBorder: '#2a2e39',
          dataZoomFiller: 'rgba(41, 98, 255, 0.15)',
          dataZoomHandle: '#13c2c2',
          dataZoomText: 'transparent',
          dataZoomBg: '#1f2943'
        }
      } else {
        return {
          backgroundColor: '#fff',
          textColor: '#333',
          textColorSecondary: '#666',
          borderColor: '#e8e8e8',
          gridLineColor: '#e8e8e8',
          gridLineColorDashed: '#e8e8e8',
          tooltipBg: 'rgba(255, 255, 255, 0.95)',
          tooltipBorder: '#e8e8e8',
          tooltipText: '#333',
          tooltipTextSecondary: '#666',
          axisLabelColor: '#666',
          splitAreaColor: ['rgba(250,250,250,0.05)', 'rgba(200,200,200,0.02)'],
          dataZoomBorder: '#e8e8e8',
          dataZoomFiller: 'rgba(24, 144, 255, 0.15)',
          dataZoomHandle: '#1890ff',
          dataZoomText: '#999',
          dataZoomBg: '#f0f2f5'
        }
      }
    })

    // Get indicator color based on theme
    const getIndicatorColor = (idx) => {
      if (chartTheme.value === 'dark') {
        return ['#13c2c2', '#e040fb', '#ffeb3b', '#00e676', '#ff6d00', '#9c27b0'][idx % 6]
      } else {
        return ['#13c2c2', '#9c27b0', '#f57c00', '#1976d2', '#c2185b', '#7b1fa2'][idx % 6]
      }
    }

    // ========== Pyodide Initialization ==========
    const loadPyodide = () => {
      return new Promise((resolve, reject) => {
        // Check if already loaded
        if (window.pyodide) {
          pyodide.value = window.pyodide
          pythonReady.value = true
          resolve(window.pyodide)
          return
        }

        loadingPython.value = true

        // Dynamically load Pyodide (production default CDN priority, avoid local static resource missing causing 404/error)
        // Can be customized via environment variables:
        // - VUE_APP_PYODIDE_CDN_BASE: Override CDN base path (must end with / or will be appended)
        // - VUE_APP_PYODIDE_LOCAL_BASE: Override local base path (must end with / or will be appended)
        // - VUE_APP_PYODIDE_PREFER_CDN: 'true'/'false' force priority
        const PYODIDE_VERSION = '0.25.0'
        const _ensureTrailingSlash = (s) => (s && s.endsWith('/')) ? s : (s ? (s + '/') : s)
        const defaultLocalBase = `/assets/pyodide/v${PYODIDE_VERSION}/full/`
        const defaultCdnBase = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`
        const localBase = _ensureTrailingSlash(process.env.VUE_APP_PYODIDE_LOCAL_BASE || defaultLocalBase)
        const cdnBase = _ensureTrailingSlash(process.env.VUE_APP_PYODIDE_CDN_BASE || defaultCdnBase)
        const preferCdnEnv = (process.env.VUE_APP_PYODIDE_PREFER_CDN || '').toString().toLowerCase()
        const preferCdn = preferCdnEnv
          ? (preferCdnEnv === 'true' || preferCdnEnv === '1' || preferCdnEnv === 'yes')
          : (process.env.NODE_ENV === 'production')

        const loadScript = (src) => new Promise((resolve, reject) => {
          // If script already inserted, reuse it
          const existing = document.querySelector(`script[data-pyodide-src="${src}"]`)
          if (existing) {
            // If already loaded, resolve immediately.
            if (typeof window.loadPyodide === 'function') return resolve()
            // Otherwise wait for load/error.
            existing.addEventListener('load', () => resolve(), { once: true })
            existing.addEventListener('error', () => reject(new Error('Pyodide script failed to load')), { once: true })
            return
          }

          const s = document.createElement('script')
          s.dataset.pyodideSrc = src
          s.src = src
          s.onload = () => resolve()
          s.onerror = () => reject(new Error('Pyodide script failed to load'))
          document.head.appendChild(s)
        })

        const initFromBase = async (baseUrl) => {
          if (typeof window.loadPyodide !== 'function') {
            throw new Error('loadPyodide function not found')
          }
          window.pyodide = await window.loadPyodide({ indexURL: baseUrl })

              // Preload pandas and numpy
              await window.pyodide.loadPackage(['pandas', 'numpy'])

              pyodide.value = window.pyodide
              pythonReady.value = true
              loadingPython.value = false
              resolve(window.pyodide)
        }

        (async () => {
          const tryLoad = async (base) => {
            await loadScript(base + 'pyodide.js')
            await initFromBase(base)
          }

          try {
            if (preferCdn) {
              // 1) CDN-first (production default)
              await tryLoad(cdnBase)
            } else {
              // 1) Local-first (dev convenience)
              await tryLoad(localBase)
            }
          } catch (firstErr) {
            try {
              // 2) Fallback
              await tryLoad(preferCdn ? localBase : cdnBase)
            } catch (secondErr) {
              throw secondErr || firstErr
            }
          }
        })().catch((err) => {
          loadingPython.value = false
          pyodideLoadFailed.value = true
          reject(err)
        })
      })
    }

    // ========== Python Code Parsing ==========
    // Parse Python code, extract parameter info
    const parsePythonStrategy = (code) => {
      if (!code || typeof code !== 'string') {
        return null
      }

      try {
        // Simple parameter extraction: search for comments like @param or #param, or function arguments
        // Extract possible parameters
        const params = {}

        // Try to extract parameters from code (if any)
        // For example: find parameters like span=144
        const paramMatches = code.match(/(\w+)\s*=\s*(\d+\.?\d*)/g)
        if (paramMatches) {
          paramMatches.forEach(match => {
            const parts = match.split('=')
            if (parts.length === 2) {
              const key = parts[0].trim()
              const value = parseFloat(parts[1].trim())
              if (!isNaN(value)) {
                params[key] = value
              }
            }
          })
        }

        // Return resolution results
        return {
          params: params,
          plots: [], // Cannot directly extract plots from code, must be determined during execution
          success: true
        }
      } catch (err) {
        // Even if parsing fails, return a basic object, allowing execution
        return {
          params: {},
          plots: [],
          success: false
        }
      }
    }

    // ========== Python Execution Engine ==========
    const executePythonStrategy = async (userCode, klineData, params = {}, indicatorInfo = {}) => {
      if (!pythonReady.value || !pyodide.value) {
        // If loading, wait and retry
        if (loadingPython.value) {
          // Wait up to 15 seconds (30 times * 500ms)
          let waitCount = 0
          while (loadingPython.value && waitCount < 30) {
            await new Promise(resolve => setTimeout(resolve, 500))
            waitCount++
            // If loading complete, exit loop
            if (pythonReady.value && pyodide.value) {
              break
            }
          }
        }

        // If still not ready, check if loading failed
        if (!pythonReady.value || !pyodide.value) {
          // If not loading, indicates failure or timeout
          if (!loadingPython.value) {
            pyodideLoadFailed.value = true
          } else {
            // If still loading but timed out, mark as failed
            loadingPython.value = false
            pyodideLoadFailed.value = true
          }
          throw new Error('Python engine not ready, please wait for loading to complete')
        }
      }

      try {
        // Check if code needs decryption (purchased indicators)
        let finalCode = userCode
        const isEncrypted = indicatorInfo.is_encrypted || indicatorInfo.isEncrypted || 0
        if (isEncrypted || needsDecrypt(userCode, isEncrypted)) {
          // Get user ID (priority: indicatorInfo > props > params)
          const userId = indicatorInfo.user_id || indicatorInfo.userId || props.userId || params.userId
          // Use original database ID (originalId), if not available use id
          const indicatorId = indicatorInfo.originalId || indicatorInfo.id || params.indicatorId

          if (userId && indicatorId) {
            try {
              finalCode = await decryptCodeAuto(finalCode, userId, indicatorId)
            } catch (decryptError) {
              throw new Error('Code decryption failed, cannot execute indicator: ' + (decryptError.message || 'Unknown Error'))
            }
          } else {
            throw new Error('Missing necessary decryption parameters (User ID or Indicator ID), cannot execute encrypted indicator')
          }
        }
        // 1. Data conversion: convert JS klineData / params to JSON string
        // klineData might be internal format (time) or KLineChart format (timestamp)
        const rawData = klineData.map(item => {
          // Compatible with both formats
          let timeValue = item.timestamp || item.time
          // If second-level timestamp, convert to milliseconds
          if (timeValue < 1e10) {
            timeValue = timeValue * 1000
          }
          return {
            time: Math.floor(timeValue / 1000), // Python side uses second-level timestamp
            open: parseFloat(item.open) || 0,
            high: parseFloat(item.high) || 0,
            low: parseFloat(item.low) || 0,
            close: parseFloat(item.close) || 0,
            volume: parseFloat(item.volume) || 0
          }
        })
        const rawDataJson = JSON.stringify(rawData)
        const paramsJson = JSON.stringify(params || {})

        // 2. Construct Python execution code
        // Escape special characters in JSON string
        const escapedJson = rawDataJson.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n').replace(/\r/g, '\\r')
        const escapedParams = paramsJson.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n').replace(/\r/g, '\\r')

        const pythonCode = `
import json
import pandas as pd
import numpy as np

# Recursively clean NaN values
def clean_nan(obj):
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(item) for item in obj]
    elif isinstance(obj, (pd.Series, np.ndarray)):
        return [None if (isinstance(x, float) and (np.isnan(x) or np.isinf(x))) else x for x in obj]
    elif isinstance(obj, (float, np.floating)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif pd.isna(obj):
        return None
    else:
        return obj

# Receive JSON data
raw_data = json.loads('${escapedJson}')
params = json.loads('${escapedParams}')

# Inject frontend parameters as variables directly usable in indicator code (align with backtest/live environment)
# Compatible with multiple naming conventions (snake_case / camelCase)
def _get_param(key, default=None):
    if key in params:
        return params.get(key, default)
    # camelCase fallback
    camel = ''.join([key.split('_')[0]] + [p.capitalize() for p in key.split('_')[1:]])
    return params.get(camel, default)

try:
    leverage = float(_get_param('leverage', 1) or 1)
except Exception:
    leverage = 1

trade_direction = _get_param('trade_direction', _get_param('tradeDirection', 'both')) or 'both'

try:
    initial_position = int(_get_param('initial_position', 0) or 0)
except Exception:
    initial_position = 0

try:
    initial_avg_entry_price = float(_get_param('initial_avg_entry_price', 0.0) or 0.0)
except Exception:
    initial_avg_entry_price = 0.0

try:
    initial_position_count = int(_get_param('initial_position_count', 0) or 0)
except Exception:
    initial_position_count = 0

try:
    initial_last_add_price = float(_get_param('initial_last_add_price', 0.0) or 0.0)
except Exception:
    initial_last_add_price = 0.0

try:
    initial_highest_price = float(_get_param('initial_highest_price', 0.0) or 0.0)
except Exception:
    initial_highest_price = 0.0

# Convert to DataFrame
df = pd.DataFrame(raw_data)

# Convert data types
df['open'] = df['open'].astype(float)
df['high'] = df['high'].astype(float)
df['low'] = df['low'].astype(float)
df['close'] = df['close'].astype(float)
df['volume'] = df['volume'].astype(float)

# User code (decrypted)
${finalCode}

# Construct output (if output undefined, try to get from result_json)
if 'output' not in locals():
    if 'result_json' in locals():
        output = json.loads(result_json)
    else:
        output = {"plots": []}
else:
    # Ensure output is in dictionary format
    if isinstance(output, str):
        output = json.loads(output)

# Clean all NaN values in output
output = clean_nan(output)

# Return JSON string
json.dumps(output)
`

        // 3. Execute Python code
        const resultJson = await pyodide.value.runPythonAsync(pythonCode)

        // Check returned results
        if (!resultJson || typeof resultJson !== 'string') {
          throw new Error(`Python code execution did not return a valid JSON string, return type: ${typeof resultJson}`)
        }

        let result
        try {
          result = JSON.parse(resultJson)
        } catch (parseError) {
          throw new Error(`JSON parsing failed: ${parseError.message}. Data might contain NaN or other invalid values.`)
        }

        // 4. Verify and format output
        if (!result) {
          return { plots: [], signals: [], calculatedVars: {} }
        }

        // Ensure plots exist and are an array
        if (!result.plots || !Array.isArray(result.plots)) {
          result.plots = []
        }

        // 5. Process data for each plot, converting NaN to null
        result.plots = result.plots.map(plot => {
          if (plot.data && Array.isArray(plot.data)) {
            plot.data = plot.data.map(val => {
              if (val === null || val === undefined || (typeof val === 'number' && isNaN(val))) {
                return null
              }
              return val
            })
          }
          return plot
        })

        // 6. Process signals (if any)
        if (result.signals && Array.isArray(result.signals)) {
          result.signals = result.signals.map(signal => {
            if (signal.data && Array.isArray(signal.data)) {
              signal.data = signal.data.map(val => {
                if (val === null || val === undefined || (typeof val === 'number' && isNaN(val))) {
                  return null
                }
                return val
              })
            }
            return signal
          })
        }

        // 7. Ensure calculatedVars exist
        if (!result.calculatedVars) {
          result.calculatedVars = {}
        }

        return result
      } catch (err) {
        throw new Error(`Python execution failed: ${err.message}`)
      }
    }

    // --- Indicator Calculation Functions ---
    // These functions might be indirectly called via indicator.calculate, so ESLint might not recognize them

    // eslint-disable-next-line no-unused-vars
    function calculateSMA (data, length) {
      const result = []
      for (let i = 0; i < data.length; i++) {
        if (i < length - 1) {
          result.push(null)
        } else {
          let sum = 0
          for (let j = i - length + 1; j <= i; j++) {
            sum += data[j].close
          }
          result.push(sum / length)
        }
      }
      return result
    }

    function calculateEMA (data, length) {
      const result = []
      const multiplier = 2 / (length + 1)
      let ema = null
      for (let i = 0; i < data.length; i++) {
        if (i === 0) {
          ema = data[i].close
        } else {
          ema = (data[i].close - ema) * multiplier + ema
        }
        result.push(ema)
      }
      return result
    }

    // eslint-disable-next-line no-unused-vars
    function calculateBollingerBands (data, length, mult) {
      // Internally calculate SMA
      const sma = []
      for (let i = 0; i < data.length; i++) {
        if (i < length - 1) {
          sma.push(null)
        } else {
          let sum = 0
          for (let j = i - length + 1; j <= i; j++) {
            sum += data[j].close
          }
          sma.push(sum / length)
        }
      }

      const result = []
      for (let i = 0; i < data.length; i++) {
        if (i < length - 1) {
          result.push({ upper: null, middle: null, lower: null })
          continue
        }
        let sum = 0
        for (let j = i - length + 1; j <= i; j++) {
          sum += Math.pow(data[j].close - sma[i], 2)
        }
        const std = Math.sqrt(sum / length)
        result.push({
          upper: sma[i] + mult * std,
          middle: sma[i],
          lower: sma[i] - mult * std
        })
      }
      return result
    }

    // eslint-disable-next-line no-unused-vars
    function calculateRSI (data, length) {
      const result = []
      let avgGain = 0
      let avgLoss = 0

      for (let i = 0; i < data.length; i++) {
        if (i === 0) {
          result.push(null)
          continue
        }

        const change = data[i].close - data[i - 1].close
        const gain = change > 0 ? change : 0
        const loss = change < 0 ? Math.abs(change) : 0

        if (i < length) {
          // First length-1 values, accumulate but don't calculate RSI
          result.push(null)
        } else if (i === length) {
          // length-th value, calculate initial average
          let sumGain = 0
          let sumLoss = 0
          for (let j = 1; j <= length; j++) {
            const chg = data[j].close - data[j - 1].close
            if (chg > 0) sumGain += chg
            else sumLoss += Math.abs(chg)
          }
          avgGain = sumGain / length
          avgLoss = sumLoss / length
          const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
          result.push(100 - (100 / (1 + rs)))
        } else {
          // Subsequent values, use smoothed moving average (SMMA)
          avgGain = (avgGain * (length - 1) + gain) / length
          avgLoss = (avgLoss * (length - 1) + loss) / length
          const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
          result.push(100 - (100 / (1 + rs)))
        }
      }
      return result
    }

    // eslint-disable-next-line no-unused-vars
    function calculateMACD (data, fast, slow, signal) {
      const fastEMA = calculateEMA(data, fast)
      const slowEMA = calculateEMA(data, slow)
      const macdLine = []

      // Calculate MACD line
      for (let i = 0; i < data.length; i++) {
        if (fastEMA[i] == null || slowEMA[i] == null) {
          macdLine.push(null)
        } else {
          macdLine.push(fastEMA[i] - slowEMA[i])
        }
      }

      // Calculate Signal line (EMA of MACD)
      // Need to maintain original array length, handle null values specially
      const signalLine = []
      const histogram = []
      let signalEMA = null
      let signalStartIdx = -1

      // Find the first non-null MACD value as the starting point for signal calculation
      for (let i = 0; i < macdLine.length; i++) {
        if (macdLine[i] !== null && signalStartIdx === -1) {
          signalStartIdx = i
          signalEMA = macdLine[i]
          break
        }
      }

      // If starting point found, continue signal calculation
      if (signalStartIdx >= 0) {
        const multiplier = 2 / (signal + 1)
        for (let i = 0; i < macdLine.length; i++) {
          if (i < signalStartIdx + signal - 1) {
            // Signal requires enough MACD values
            signalLine.push(null)
            histogram.push(null)
          } else if (macdLine[i] === null) {
            signalLine.push(null)
            histogram.push(null)
          } else {
            if (i === signalStartIdx + signal - 1) {
              // First signal value: calculate average of the first signal-many MACD values
              let sum = 0
              let count = 0
              for (let j = signalStartIdx; j <= i; j++) {
                if (macdLine[j] !== null) {
                  sum += macdLine[j]
                  count++
                }
              }
              signalEMA = sum / count
            } else {
              // Subsequent values: use EMA formula
              signalEMA = (macdLine[i] - signalEMA) * multiplier + signalEMA
            }
            signalLine.push(signalEMA)
            histogram.push(macdLine[i] - signalEMA)
          }
        }
      } else {
        // If no valid MACD values, set all to null
        for (let i = 0; i < macdLine.length; i++) {
          signalLine.push(null)
          histogram.push(null)
        }
      }

      return { macd: macdLine, signal: signalLine, histogram }
    }

    // Calculate ATR (Average True Range)
    function calculateATR (data, period) {
      const tr = [] // True Range
      for (let i = 0; i < data.length; i++) {
        if (i === 0) {
          tr.push(data[i].high - data[i].low)
        } else {
          const hl = data[i].high - data[i].low
          const hc = Math.abs(data[i].high - data[i - 1].close)
          const lc = Math.abs(data[i].low - data[i - 1].close)
          tr.push(Math.max(hl, hc, lc))
        }
      }

      // Calculate ATR (SMA of TR)
      const atr = []
      for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
          atr.push(null)
        } else {
          let sum = 0
          for (let j = i - period + 1; j <= i; j++) {
            sum += tr[j]
          }
          atr.push(sum / period)
        }
      }
      return atr
    }

    // Calculate CCI (Commodity Channel Index)
    function calculateCCI (data, length) {
      const cci = []
      for (let i = 0; i < data.length; i++) {
        if (i < length - 1) {
          cci.push(null)
        } else {
          // Calculate Typical Price (TP)
          const tp = []
          for (let j = i - length + 1; j <= i; j++) {
            tp.push((data[j].high + data[j].low + data[j].close) / 3)
          }
          // Calculate SMA of TP
          const sma = tp.reduce((sum, val) => sum + val, 0) / length
          // Calculate mean deviation
          const meanDev = tp.reduce((sum, val) => sum + Math.abs(val - sma), 0) / length
          // Calculate CCI
          const currentTP = (data[i].high + data[i].low + data[i].close) / 3
          const cciValue = meanDev === 0 ? 0 : (currentTP - sma) / (0.015 * meanDev)
          cci.push(cciValue)
        }
      }
      return cci
    }

    // Calculate Williams %R (Williams Index)
    function calculateWilliamsR (data, length) {
      const williamsR = []
      for (let i = 0; i < data.length; i++) {
        if (i < length - 1) {
          williamsR.push(null)
        } else {
          let highest = -Infinity
          let lowest = Infinity
          for (let j = i - length + 1; j <= i; j++) {
            highest = Math.max(highest, data[j].high)
            lowest = Math.min(lowest, data[j].low)
          }
          const wr = (highest - lowest) === 0 ? -50 : ((highest - data[i].close) / (highest - lowest)) * -100
          williamsR.push(wr)
        }
      }
      return williamsR
    }

    // Calculate MFI (Money Flow Index)
    function calculateMFI (data, length) {
      const mfi = []
      for (let i = 0; i < data.length; i++) {
        if (i < length) {
          mfi.push(null)
        } else {
          let positiveFlow = 0
          let negativeFlow = 0
          for (let j = i - length + 1; j <= i; j++) {
            const typicalPrice = (data[j].high + data[j].low + data[j].close) / 3
            const rawMoneyFlow = typicalPrice * data[j].volume
            if (j > i - length + 1) {
              const prevTypicalPrice = (data[j - 1].high + data[j - 1].low + data[j - 1].close) / 3
              if (typicalPrice > prevTypicalPrice) {
                positiveFlow += rawMoneyFlow
              } else if (typicalPrice < prevTypicalPrice) {
                negativeFlow += rawMoneyFlow
              }
            }
          }
          const moneyFlowRatio = negativeFlow === 0 ? 100 : positiveFlow / negativeFlow
          const mfiValue = 100 - (100 / (1 + moneyFlowRatio))
          mfi.push(mfiValue)
        }
      }
      return mfi
    }

    // Calculate ADX (Average Directional Index) and DMI (+DI, -DI)
    function calculateADX (data, length) {
      const plusDI = []
      const minusDI = []
      const adx = []

      // Calculate True Range (TR) and Directional Movement (+DM, -DM)
      const tr = []
      const plusDM = []
      const minusDM = []

      for (let i = 0; i < data.length; i++) {
        if (i === 0) {
          tr.push(data[i].high - data[i].low)
          plusDM.push(0)
          minusDM.push(0)
        } else {
          const hl = data[i].high - data[i].low
          const hc = Math.abs(data[i].high - data[i - 1].close)
          const lc = Math.abs(data[i].low - data[i - 1].close)
          tr.push(Math.max(hl, hc, lc))

          const upMove = data[i].high - data[i - 1].high
          const downMove = data[i - 1].low - data[i].low

          if (upMove > downMove && upMove > 0) {
            plusDM.push(upMove)
          } else {
            plusDM.push(0)
          }

          if (downMove > upMove && downMove > 0) {
            minusDM.push(downMove)
          } else {
            minusDM.push(0)
          }
        }
      }

      // Calculate smoothed TR, +DM, -DM
      const smoothTR = []
      const smoothPlusDM = []
      const smoothMinusDM = []

      for (let i = 0; i < data.length; i++) {
        if (i < length - 1) {
          smoothTR.push(null)
          smoothPlusDM.push(null)
          smoothMinusDM.push(null)
          plusDI.push(null)
          minusDI.push(null)
          adx.push(null)
        } else if (i === length - 1) {
          // Initial values: simple summation
          let sumTR = 0
          let sumPlusDM = 0
          let sumMinusDM = 0
          for (let j = 0; j <= i; j++) {
            sumTR += tr[j]
            sumPlusDM += plusDM[j]
            sumMinusDM += minusDM[j]
          }
          smoothTR.push(sumTR)
          smoothPlusDM.push(sumPlusDM)
          smoothMinusDM.push(sumMinusDM)
        } else {
          // Smoothed calculation: Wilder's smoothing
          smoothTR.push(smoothTR[i - 1] - (smoothTR[i - 1] / length) + tr[i])
          smoothPlusDM.push(smoothPlusDM[i - 1] - (smoothPlusDM[i - 1] / length) + plusDM[i])
          smoothMinusDM.push(smoothMinusDM[i - 1] - (smoothMinusDM[i - 1] / length) + minusDM[i])
        }

        if (i >= length - 1) {
          const trVal = smoothTR[i]
          const plusDMVal = smoothPlusDM[i]
          const minusDMVal = smoothMinusDM[i]

          if (trVal === 0) {
            plusDI.push(0)
            minusDI.push(0)
          } else {
            plusDI.push((plusDMVal / trVal) * 100)
            minusDI.push((minusDMVal / trVal) * 100)
          }

          // Calculate DX
          if (i >= length - 1) {
            const diSum = plusDI[i] + minusDI[i]
            const dx = diSum === 0 ? 0 : Math.abs(plusDI[i] - minusDI[i]) / diSum * 100

            // Calculate ADX (Smoothing of DX)
            if (i === length - 1) {
              adx.push(dx)
            } else if (i === length) {
              // Second ADX value: average of first two DX values
              const prevDX = Math.abs(plusDI[i - 1] - minusDI[i - 1]) / (plusDI[i - 1] + minusDI[i - 1]) * 100
              adx.push((prevDX + dx) / 2)
            } else {
              // ADX smoothing: Wilder's smoothing
              adx.push((adx[i - 1] * (length - 1) + dx) / length)
            }
          }
        }
      }

      return { adx, plusDI, minusDI }
    }

    // Calculate OBV (On-Balance Volume)
    function calculateOBV (data) {
      const obv = []
      let obvValue = 0

      for (let i = 0; i < data.length; i++) {
        if (i === 0) {
          obvValue = data[i].volume
        } else {
          if (data[i].close > data[i - 1].close) {
            obvValue += data[i].volume
          } else if (data[i].close < data[i - 1].close) {
            obvValue -= data[i].volume
          }
          // If close price is same, OBV remains unchanged
        }
        obv.push(obvValue)
      }
      return obv
    }

    // Calculate AD (Accumulation/Distribution Line)
    function calculateAD (data) {
      const ad = []
      let adValue = 0

      for (let i = 0; i < data.length; i++) {
        const high = data[i].high
        const low = data[i].low
        const close = data[i].close
        const volume = data[i].volume

        if (high !== low) {
          const clv = ((close - low) - (high - close)) / (high - low)
          adValue += clv * volume
        }
        ad.push(adValue)
      }
      return ad
    }

    // Calculate ADOSC (Accumulation/Distribution Oscillator) = Fast EMA of AD - Slow EMA of AD
    function calculateADOSC (data, fast, slow) {
      const ad = calculateAD(data)
      const fastEMA = []
      const slowEMA = []
      const adosc = []

      const fastMultiplier = 2 / (fast + 1)
      const slowMultiplier = 2 / (slow + 1)

      let fastEMAValue = ad[0]
      let slowEMAValue = ad[0]

      for (let i = 0; i < ad.length; i++) {
        if (i === 0) {
          fastEMA.push(ad[0])
          slowEMA.push(ad[0])
          adosc.push(0)
        } else {
          fastEMAValue = (ad[i] - fastEMAValue) * fastMultiplier + fastEMAValue
          slowEMAValue = (ad[i] - slowEMAValue) * slowMultiplier + slowEMAValue

          fastEMA.push(fastEMAValue)
          slowEMA.push(slowEMAValue)
          adosc.push(fastEMAValue - slowEMAValue)
        }
      }

      return adosc
    }

    // Calculate KDJ (Stochastic Oscillator)
    function calculateKDJ (data, period, kPeriod, dPeriod) {
      const kValues = []
      const dValues = []
      const jValues = []

      for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
          kValues.push(null)
          dValues.push(null)
          jValues.push(null)
        } else {
          // Find highest and lowest prices within period
          let highest = -Infinity
          let lowest = Infinity
          for (let j = i - period + 1; j <= i; j++) {
            highest = Math.max(highest, data[j].high)
            lowest = Math.min(lowest, data[j].low)
          }

          // Calculate RSV
          const rsv = (highest - lowest) === 0 ? 50 : ((data[i].close - lowest) / (highest - lowest)) * 100

          // Calculate K value (Moving average of RSV)
          if (kValues[i - 1] === null) {
            kValues.push(rsv)
          } else {
            kValues.push((rsv * 2 + kValues[i - 1] * (kPeriod - 2)) / kPeriod)
          }

          // Calculate D value (Moving average of K)
          if (dValues[i - 1] === null) {
            dValues.push(kValues[i])
          } else {
            dValues.push((kValues[i] * 2 + dValues[i - 1] * (dPeriod - 2)) / dPeriod)
          }

          // Calculate J value
          jValues.push(3 * kValues[i] - 2 * dValues[i])
        }
      }

      return { k: kValues, d: dValues, j: jValues }
    }

    // ========== Register Custom Signal Overlay (Signal Tag) ==========
    // This is a custom overlay that can draw "Dot + Colored background text box"
// ========== Register Custom Signal Overlay (Signal Tag) ==========
registerOverlay({
      name: 'signalTag',
      // [Critical Change 1] Must be changed to 1. Tells chart that this figure needs only one point to finish.
      // If it is 1, the chart won't draw that blue "editing" handle.
      totalStep: 1,

      // [Critical Change 2] Completely prohibit this overlay from responding to any mouse events.
      // This way there won't be a blue selection box when hovering mouse
      lock: true,
      needDefaultPointFigure: false,
      needDefaultXAxisFigure: false,
      needDefaultYAxisFigure: false,

      // [Recommended to keep] Further ensure events are not intercepted
      checkEventOn: () => false,

      createPointFigures: ({ coordinates, overlay }) => {
        const { text } = overlay.extendData || {}
        const color = overlay.extendData?.color || '#555555'

        // 1. Get signal point coordinates
        if (!coordinates[0]) return []
        const x = coordinates[0].x
        const signalY = coordinates[0].y // Point 0: Compiled label position in Python (includes vertical spacing)

        // 2. Get K-line extrema coordinates (for drawing the dot)
        const anchorY = coordinates[1] ? coordinates[1].y : signalY // Point 1: K-line high/low

        const boxPaddingX = 8
        const boxPaddingY = 4
        const fontSize = 12
        const textStr = String(text || '')
        // Simple character width estimation
        const textWidth = textStr.split('').reduce((acc, char) => acc + (char.charCodeAt(0) > 255 ? 12 : 7), 0)
        const boxWidth = textWidth + boxPaddingX * 2
        const boxHeight = fontSize + boxPaddingY * 2

        // Compatibility: old overlays used extendData.type='buy'/'sell', new overlays use extendData.side='buy'/'sell'
        const side = overlay.extendData?.side || overlay.extendData?.type || 'buy'
        const isBuy = side === 'buy'

        // 3. Calculate Box Y-axis position
        // [Critical Change] Use signalY directly (adjusted position in Python), don't use fixed margin anymore
        // signalY already includes adjustment for inverted signal's vertical spacing
        const boxY = isBuy ? signalY : (signalY - boxHeight)

        // Calculate segment connection point
        // Dot drawn at K-line extrema position (anchorY), right next to K-line
        // Connector line from dot to label box
        const circleY = anchorY // Dot position: K-line High or Low
        const lineStartY = circleY // Connector line start: Dot position
        const lineEndY = isBuy ? boxY : (boxY + boxHeight) // Connector line end: Label box edge

        return [
          // 1. Dashed line (from dot to label box)
          {
            type: 'line',
            attrs: {
              coordinates: [
                { x, y: lineStartY }, // From dot (K-line extrema position)
                { x, y: lineEndY } // Connect to label box edge
              ]
            },
            styles: { style: 'stroke', color: color, dashedValue: [2, 2] },
            ignoreEvent: true
          },
          // 2. Dot (drawn at K-line extrema position, right next to K-line)
          {
            type: 'circle',
            attrs: { x, y: circleY, r: 4 },
            styles: { style: 'fill', color: color },
            ignoreEvent: true
          },
          // 3. Background box (based on boxY)
          {
            type: 'rect',
            attrs: {
              x: x - boxWidth / 2,
              y: boxY,
              width: boxWidth,
              height: boxHeight,
              r: 4
            },
            styles: { style: 'fill', color: color, borderSize: 0 },
            ignoreEvent: true
          },
          // 4. Text
          {
            type: 'text',
            attrs: {
              x: x,
              y: boxY + boxHeight / 2,
              text: textStr,
              align: 'center',
              baseline: 'middle'
            },
            styles: { color: '#ffffff', size: fontSize, weight: 'bold', backgroundColor: color, borderRadius: 5 },
            ignoreEvent: true
          }
        ]
      }
    })

    // --- Data loading related functions ---
    // Format data to KLineChart format (timestamp needs to be in milliseconds)
    const formatKlineData = (data) => {
      return data.map(item => {
        let timeValue = item.time || item.timestamp
        if (typeof timeValue === 'string') {
          timeValue = parseInt(timeValue)
        }
        // KLineChart needs millisecond timestamp; if currently second-level, convert to milliseconds
        if (timeValue < 1e10) {
          timeValue = timeValue * 1000
        }
        return {
          timestamp: timeValue,
          open: parseFloat(item.open),
          high: parseFloat(item.high),
          low: parseFloat(item.low),
          close: parseFloat(item.close),
          volume: parseFloat(item.volume || 0)
        }
      }).filter(item => item.timestamp && !isNaN(item.open) && !isNaN(item.high) && !isNaN(item.low) && !isNaN(item.close))
        .sort((a, b) => a.timestamp - b.timestamp)
    }

    const updatePricePanel = (data) => {
      if (data.length > 0) {
        const last = data[data.length - 1]
        if (data.length > 1) {
          const prev = data[data.length - 2]
          const price = last.close.toFixed(2)
          const change = ((last.close - prev.close) / prev.close) * 100
          emit('price-change', { price, change })
        } else {
          const price = last.close.toFixed(2)
          emit('price-change', { price, change: 0 })
        }
      }
    }

    // Convert KLineChart format data to internal format (used for functions like isSameTimeframe)
    const convertToInternalFormat = (data) => {
      return data.map(item => ({
        time: Math.floor(item.timestamp / 1000), // Convert back to second-level timestamp for comparison
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
        volume: item.volume
      }))
    }

    const isSameTimeframe = (time1, time2, tf) => {
      const date1 = new Date(time1 * 1000)
      const date2 = new Date(time2 * 1000)

      switch (tf) {
        case '1m':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate() &&
                 date1.getHours() === date2.getHours() &&
                 date1.getMinutes() === date2.getMinutes()
        case '5m':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate() &&
                 date1.getHours() === date2.getHours() &&
                 Math.floor(date1.getMinutes() / 5) === Math.floor(date2.getMinutes() / 5)
        case '15m':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate() &&
                 date1.getHours() === date2.getHours() &&
                 Math.floor(date1.getMinutes() / 15) === Math.floor(date2.getMinutes() / 15)
        case '30m':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate() &&
                 date1.getHours() === date2.getHours() &&
                 Math.floor(date1.getMinutes() / 30) === Math.floor(date2.getMinutes() / 30)
        case '1H':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate() &&
                 date1.getHours() === date2.getHours()
        case '4H':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate() &&
                 Math.floor(date1.getHours() / 4) === Math.floor(date2.getHours() / 4)
        case '1D':
          return date1.getFullYear() === date2.getFullYear() &&
                 date1.getMonth() === date2.getMonth() &&
                 date1.getDate() === date2.getDate()
        case '1W':
          const week1 = Math.floor((date1.getTime() - new Date(date1.getFullYear(), 0, 1).getTime()) / (7 * 24 * 60 * 60 * 1000))
          const week2 = Math.floor((date2.getTime() - new Date(date2.getFullYear(), 0, 1).getTime()) / (7 * 24 * 60 * 60 * 1000))
          return date1.getFullYear() === date2.getFullYear() && week1 === week2
        default:
          return time1 === time2
      }
    }

    const loadKlineData = async (silent = false) => {
      if (!props.symbol) return
      if (loading.value && !silent) return

      loading.value = true
      error.value = null

      try {
        let formattedData = []
        try {
          const response = await request({
            url: '/api/indicator/kline',
            method: 'get',
            params: {
              market: props.market,
              symbol: props.symbol,
              timeframe: props.timeframe,
              limit: 500
            }
          })

          if (response.code === 1 && response.data && Array.isArray(response.data)) {
            formattedData = formatKlineData(response.data)
          } else {
            // Special handling for Tiingo subscription limit notice
            let errMsg = response.msg || 'Failed to fetch Kline data'
            if (response.hint === 'tiingo_subscription') {
              errMsg = proxy.$t('dashboard.indicator.error.tiingoSubscription') || 'Forex 1-minute data requires Tiingo paid subscription'
            }
            throw new Error(errMsg)
          }
        } catch (apiErr) {
          throw apiErr
        }

        // Check if data is empty
        if (!formattedData || formattedData.length === 0) {
          throw new Error('No Kline data fetched')
        }

        klineData.value = formattedData
        hasMoreHistory.value = true
        const internalData = convertToInternalFormat(formattedData)
        updatePricePanel(internalData)

        nextTick(() => {
          if (!chartRef.value) {
            initChart()
          } else {
            // Ensure data format is correct
            const validData = klineData.value.filter(item =>
              item.timestamp &&
              !isNaN(item.open) &&
              !isNaN(item.high) &&
              !isNaN(item.low) &&
              !isNaN(item.close)
            )

            if (validData.length > 0 && chartRef.value) {
              // Use applyNewData for initialization
              try {
                chartRef.value.applyNewData(validData)
              } catch (e) {
                chartRef.value.applyNewData(validData)
              }

              // Delayed indicator update
              setTimeout(() => {
                if (chartRef.value) {
                  updateIndicators()
                }
              }, 100)
            }
          }

          if (props.realtimeEnabled) {
            stopRealtime()
            startRealtime()
          }
        })
      } catch (err) {
        error.value = proxy.$t('dashboard.indicator.error.loadDataFailed') + ': ' + (err.message || proxy.$t('dashboard.indicator.error.loadDataFailedDesc'))
        // Clear Kline data, don't show chart
        klineData.value = []
        // If chart instance exists, clear data
        if (chartRef.value) {
          try {
            chartRef.value.applyNewData([])
          } catch (e) {
          }
        }
      } finally {
        loading.value = false
      }
    }

    // Load more historical data (for infinite scroll, maintains scroll position)
    const loadMoreHistoryDataForScroll = async (timestamp) => {
      if (!props.symbol || !klineData.value || klineData.value.length === 0) {
        return
      }

      // [Core Fix] Prevent duplicate requests: if a request is already in progress, return immediately
      if (loadingHistory.value || loadingHistoryPromise) {
        // If a request is in progress, wait for it to complete
        if (loadingHistoryPromise) {
          try {
            await loadingHistoryPromise
          } catch (e) {
          }
        }
        return
      }

      if (!hasMoreHistory.value) {
        // If no more data, notify the chart
        if (chartRef.value && typeof chartRef.value.noMoreData === 'function') {
          chartRef.value.noMoreData()
        }
        return
      }

      // Set loading state and create Promise immediately to prevent concurrent requests
      loadingHistory.value = true
      loadingHistoryPromise = (async () => {
        // Force trigger update
        await nextTick()

        try {
        // timestamp is in ms, convert to seconds for API
        const beforeTime = Math.floor(timestamp / 1000)

        const response = await request({
          url: '/api/indicator/kline',
          method: 'get',
          params: {
            market: props.market,
            symbol: props.symbol,
            timeframe: props.timeframe,
            limit: 500,
            before_time: beforeTime // Fetch data prior to this time
          }
        })

        if (response.code === 1 && response.data && Array.isArray(response.data)) {
          const newData = formatKlineData(response.data)

          if (newData.length === 0) {
            // No more data
            hasMoreHistory.value = false
            if (chartRef.value && typeof chartRef.value.noMoreData === 'function') {
              chartRef.value.noMoreData()
            }
            return
          }

          // Ensure new data time is earlier than passed timestamp
          const filteredNewData = newData.filter(item => item.timestamp < timestamp)

          if (filteredNewData.length === 0) {
            // No earlier data
            hasMoreHistory.value = false
            if (chartRef.value && typeof chartRef.value.noMoreData === 'function') {
              chartRef.value.noMoreData()
            }
            return
          }

          // Save current visible range for restoring scroll position
          // klinecharts 9.x getVisibleRange() returns from/to as data indices (integers), not percentages
          let savedVisibleRange = null
          try {
            if (chartRef.value && typeof chartRef.value.getVisibleRange === 'function') {
              savedVisibleRange = chartRef.value.getVisibleRange()
            }
          } catch (e) {
          }

          // 记录新数据的数量，用于后续计算偏移
          const newDataCount = filteredNewData.length

          // Prepended new data to existing data
          klineData.value = [...filteredNewData, ...klineData.value]

          // Use applyNewData to add historical data (applyMoreData is deprecated in v9.8.0)
          nextTick(() => {
            if (chartRef.value) {
              // Apply new data
              chartRef.value.applyNewData(klineData.value)

              // Restore scroll position
              // Since new data is prepended, original indices need an offset of newDataCount
              if (savedVisibleRange && typeof savedVisibleRange.from === 'number') {
                // 计算新的可见范围索引
                // Originally viewed indices from-to now become from+newDataCount to to+newDataCount
                const newFrom = savedVisibleRange.from + newDataCount
                const newTo = savedVisibleRange.to + newDataCount

                // Use setTimeout to ensure data has finished rendering
                setTimeout(() => {
                  try {
                    if (chartRef.value) {
                      // Try using scrollToDataIndex method (if it exists)
                      if (typeof chartRef.value.scrollToDataIndex === 'function') {
                        chartRef.value.scrollToDataIndex(newFrom)
                      } else if (typeof chartRef.value.setVisibleRange === 'function') {
                        // Use setVisibleRange to set visible range (parameters are data indices)
                        chartRef.value.setVisibleRange(newFrom, newTo)
                      }
                    }
                  } catch (e) {
                  }
                }, 50)
              }

              // Update indicators
              updateIndicators()
            }
          })
        } else {
          // API returned error, notify chart of load failure
          if (chartRef.value && typeof chartRef.value.noMoreData === 'function') {
            chartRef.value.noMoreData()
          }
        }
        } catch (err) {
          // Load failed, notify chart
          if (chartRef.value && typeof chartRef.value.noMoreData === 'function') {
            chartRef.value.noMoreData()
          }
        } finally {
          loadingHistory.value = false
          loadingHistoryPromise = null // Clear request tracking
        }
      })() // Execute Promise immediately

      // Wait for request completion
      try {
        await loadingHistoryPromise
      } catch (err) {
        // Error handled in internal catch, this just ensures Promise completes
      }
    }

    // Load more historical data (keeps original function for other scenarios)
    const loadMoreHistoryData = async () => {
      if (!props.symbol || !klineData.value || klineData.value.length === 0) {
        return
      }

      if (loadingHistory.value || !hasMoreHistory.value) {
        return
      }

      loadingHistory.value = true

      try {
        // Get current earliest data time (convert to seconds for API)
        const earliestTimestamp = klineData.value[0].timestamp
        const earliestTime = Math.floor(earliestTimestamp / 1000) // Convert to seconds
        const response = await request({
          url: '/api/indicator/kline',
          method: 'get',
          params: {
            market: props.market,
            symbol: props.symbol,
            timeframe: props.timeframe,
            limit: 500,
            before_time: earliestTime // Fetch data before this time
          }
        })

        if (response.code === 1 && response.data && Array.isArray(response.data)) {
          const newData = formatKlineData(response.data)

          if (newData.length === 0) {
            // No more data
            hasMoreHistory.value = false
            loadingHistory.value = false
            return
          }

          // Ensure new data time is earlier than existing earliest data
          const filteredNewData = newData.filter(item => item.timestamp < earliestTimestamp)

          if (filteredNewData.length === 0) {
            // No earlier data
            hasMoreHistory.value = false
            loadingHistory.value = false
            return
          }

          // Prepended new data to existing data
          klineData.value = [...filteredNewData, ...klineData.value]

          // Update chart
          nextTick(() => {
            if (chartRef.value) {
              chartRef.value.applyNewData(klineData.value)
              updateIndicators()
            }
          })
        } else {
          // API error, but doesn't necessarily mean no more data, could be network issue
          // Don't set hasMoreHistory = false, allow user retry
        }
      } catch (err) {
        // Load failure could be network issue, shouldn't immediately assume no more data
        // Only set hasMoreHistory = false when explicitly known no more earlier data exists
        // Not setting here, allowing user retry
      } finally {
        loadingHistory.value = false
      }
    }

    // Incremental update of Kline data (real-time update)
    const updateKlineRealtime = async () => {
      if (!props.symbol || !klineData.value || klineData.value.length === 0) {
        return // If no existing data, don't perform incremental update
      }

      try {
        // Only fetch latest 5 Klines for update
        const response = await request({
          url: '/api/indicator/kline',
          method: 'get',
          params: {
            market: props.market,
            symbol: props.symbol,
            timeframe: props.timeframe,
            limit: 5 // Only fetch latest 5
          }
        })

        if (response.code === 1 && response.data && Array.isArray(response.data) && response.data.length > 0) {
          const newData = formatKlineData(response.data)
          const existingData = [...klineData.value]

          if (newData.length > 0) {
            const lastNewTime = Math.floor(newData[newData.length - 1].timestamp / 1000) // Convert back to seconds for comparison
            const lastExistingTime = Math.floor(existingData[existingData.length - 1].timestamp / 1000)

            // Check if belonging to same timeframe
            if (isSameTimeframe(lastNewTime, lastExistingTime, props.timeframe)) {
              // Same timeframe, merge and update the last Kline data
              // Kline merge rules:
              // - open: remain unchanged (price at start of timeframe)
              // - high: take maximum (highest price within timeframe)
              // - low: take minimum (lowest price within timeframe)
              // - close: update to latest price (current price)
              // - volume: use latest API value (API already returns total volume for the period)
              const existingLast = existingData[existingData.length - 1]
              const newLast = newData[newData.length - 1]

              existingData[existingData.length - 1] = {
                timestamp: existingLast.timestamp, // 保持原有时间戳（毫秒）
                open: existingLast.open, // 开盘价保持不变
                high: Math.max(existingLast.high, newLast.high), // 最高价取最大值
                low: Math.min(existingLast.low, newLast.low), // 最低价取最小值
                close: newLast.close, // 收盘价更新为最新价格
                volume: newLast.volume // volume from latest API value (already total volume for the period)
              }
              klineData.value = existingData

              // Update price panel (using internal format)
              const internalData = convertToInternalFormat(klineData.value)
              updatePricePanel(internalData)

              // Update KLineChart - use updateData to maintain scroll position
              if (chartRef.value && typeof chartRef.value.updateData === 'function') {
                // 更新最后一根K线数据，保持滚动位置
                // updateData needs only one argument: data object to update (v9.8.0+ no longer accepts callback)
                const lastIndex = klineData.value.length - 1
                chartRef.value.updateData(existingData[lastIndex])
                // Indicator calculation throttle: default 10s refresh (avoid CPU spiking at 1s frequency)
                maybeUpdateIndicators(false)
              } else if (chartRef.value) {
                // Fallback: use applyNewData (resets scroll position)
                chartRef.value.applyNewData(klineData.value)
                maybeUpdateIndicators(false)
              }
            } else if (lastNewTime > lastExistingTime) {
              // New timeframe, append new data
              // Remove potentially duplicate Klines first (based on timeframe, not precise timestamp)
              const uniqueNewData = newData.filter(newItem => {
                const newItemTime = Math.floor(newItem.timestamp / 1000)
                // Check if belonging to same timeframe as any existing data
                return !existingData.some(existingItem => {
                  const existingItemTime = Math.floor(existingItem.timestamp / 1000)
                  return isSameTimeframe(newItemTime, existingItemTime, props.timeframe)
                })
              })

              if (uniqueNewData.length > 0) {
                klineData.value = [...existingData, ...uniqueNewData]
                // 如果数据超过限制，保留最新的数据
                if (klineData.value.length > 500) {
                  klineData.value = klineData.value.slice(-500)
                }

                // 更新价格面板（使用内部格式）
                const internalData = convertToInternalFormat(klineData.value)
                updatePricePanel(internalData)

                // Update KLineChart - use applyMoreData to maintain scroll position
                if (chartRef.value && typeof chartRef.value.applyMoreData === 'function') {
                  // 追加新K线，使用 applyMoreData 保持滚动位置
                  chartRef.value.applyMoreData(uniqueNewData)
                  // Force single indicator refresh when new Kline appears
                  maybeUpdateIndicators(true)
                } else if (chartRef.value) {
                  // 降级方案：使用 applyNewData（会重置滚动位置）
                  chartRef.value.applyNewData(klineData.value)
                  maybeUpdateIndicators(true)
                }
              }
            }
            // 如果新数据的时间更早，说明没有更新，保持原数据不变
          }
        }
      } catch (err) {
        // Silently handle incremental update failure, no effect on existing data
      }
    }

    // Start real-time update
    const startRealtime = () => {
      // Clear existing timer first
      if (realtimeTimer.value) {
        clearInterval(realtimeTimer.value)
      }

      // Intelligently adjust update frequency based on timeframe
      const intervalMap = {
        '1m': 5000,  // 1m K-line, 5s interval
        '5m': 10000, // 5m K-line, 10s interval
        '15m': 15000, // 15m K-line, 15s interval
        '30m': 30000, // 30m K-line, 30s interval
        '1H': 60000,  // 1H K-line, 60s interval
        '4H': 300000, // 4H K-line, 5m interval
        '1D': 600000, // Daily, 10m interval
        '1W': 1800000 // Weekly, 30m interval
      }
      // UI Experience Priority: allow high-frequency refresh for observing "Price/Kline/Indicator" synchronization.
      // Limit maximum refresh interval to 1s; if calculation is slow, updateIndicators uses a lock internally to prevent re-entry.
      const base = intervalMap[props.timeframe] || 10000
      realtimeInterval.value = Math.min(base, 1000)

      // If real-time update enabled and symbol selected
      if (props.realtimeEnabled && props.symbol && klineData.value.length > 0) {
        realtimeTimer.value = setInterval(() => {
          // Incrementally update Kline only when not loading and data exists
          if (!loading.value && props.symbol && klineData.value && klineData.value.length > 0) {
            updateKlineRealtime() // 增量更新K线
          }
        }, realtimeInterval.value)
      }
    }

    // Stop real-time update
    const stopRealtime = () => {
      if (realtimeTimer.value) {
        clearInterval(realtimeTimer.value)
        realtimeTimer.value = null
      }
    }

    // --- Chart initialization function ---
    const initChart = () => {
      const container = document.getElementById('kline-chart-container')
      if (!container) return

      if (container.clientWidth === 0 || container.clientHeight === 0) {
        let retryCount = 0
        const maxRetries = 10
        const checkAndInit = () => {
          const checkContainer = document.getElementById('kline-chart-container')
          if (checkContainer && checkContainer.clientWidth > 0 && checkContainer.clientHeight > 0) {
            initChart()
          } else if (retryCount < maxRetries) {
            retryCount++
            setTimeout(checkAndInit, 200)
          } else {
            initChart()
          }
        }
        setTimeout(checkAndInit, 200)
        return
      }

      // If chart already exists, destroy it first
      if (chartRef.value) {
        try {
          chartRef.value.destroy()
        } catch (e) {}
        chartRef.value = null
      }

      try {
        // Initialize KLineChart
        const container = document.getElementById('kline-chart-container')
        if (!container) {
          throw new Error('容器元素不存在')
        }

        // Try initializing with options to check for built-in drawing toolbar support
        try {
          // 尝试使用第二个参数传入配置选项
          chartRef.value = init(container, {
            drawingBarVisible: true, // Try enabling built-in drawing toolbar
            overlay: {
              visible: true
            }
          })
        } catch (e) {
          // If options not supported, use default initialization
          chartRef.value = init(container)
        }

        // If options approach not supported, try calling method to enable drawing toolbar
        if (chartRef.value && typeof chartRef.value.setDrawingBarVisible === 'function') {
          chartRef.value.setDrawingBarVisible(true)
        } else if (chartRef.value && typeof chartRef.value.setDrawingBar === 'function') {
          chartRef.value.setDrawingBar(true)
        } else if (chartRef.value && typeof chartRef.value.enableDrawing === 'function') {
          chartRef.value.enableDrawing(true)
        }

        if (!chartRef.value) {
          throw new Error('图表初始化失败：无法创建图表实例')
        }

        // Debug: output all chart instance methods, check for drawing toolbar related ones
        if (chartRef.value) {
          // Check for built-in drawing toolbar methods
          if (typeof chartRef.value.setDrawingBarVisible === 'function') {
            chartRef.value.setDrawingBarVisible(true)
          }
          if (typeof chartRef.value.setDrawingBar === 'function') {
            chartRef.value.setDrawingBar(true)
          }
          if (typeof chartRef.value.enableDrawing === 'function') {
            chartRef.value.enableDrawing(true)
          }
        }

        // 设置主题样式
        updateChartTheme()

        // Listen for overlay creation completion, automatically exit drawing mode
        if (chartRef.value && typeof chartRef.value.subscribeAction === 'function') {
          // 监听覆盖物创建完成事件
          chartRef.value.subscribeAction('onOverlayCreated', (overlay) => {
            // If overlay created via drawing tool, record ID and exit drawing mode
            if (activeDrawingTool.value && overlay && overlay.id) {
              addedDrawingOverlayIds.value.push(overlay.id)
              // 重置激活状态
              activeDrawingTool.value = null
              // 退出绘制模式
              try {
                if (typeof chartRef.value.overrideOverlay === 'function') {
                  chartRef.value.overrideOverlay(null)
                }
              } catch (e) {
              }
            }
          })

          // Listen for overlay drawing completion (some versions might use this event)
          if (typeof chartRef.value.subscribeAction === 'function') {
            try {
              chartRef.value.subscribeAction('onOverlayComplete', (overlay) => {
                if (activeDrawingTool.value && overlay && overlay.id) {
                  addedDrawingOverlayIds.value.push(overlay.id)
                  activeDrawingTool.value = null
                  // Exit drawing mode - don't call overrideOverlay(null) as it causes errors
                }
              })
            } catch (e) {
              // 如果 onOverlayComplete 不存在，忽略错误
            }
          }

          // Listen for overlay removal event
          chartRef.value.subscribeAction('onOverlayRemoved', (overlayId) => {
            // 从列表中移除
            const index = addedDrawingOverlayIds.value.indexOf(overlayId)
            if (index > -1) {
              addedDrawingOverlayIds.value.splice(index, 1)
            }
          })
        }

        // Use subscribeAction to listen for visible range changes, manually trigger load-more
        // Replaces setLoadMoreDataCallback, which might not trigger in some versions
        if (chartRef.value && typeof chartRef.value.subscribeAction === 'function') {
          // Save last visible range to detect scrolling to the far left
          let lastVisibleFrom = null
          // Mark if initialization visible range change handled
          let initialRangeProcessed = false

          chartRef.value.subscribeAction('onVisibleRangeChange', async (data) => {
            if (data && typeof data.from === 'number') {
              // If first visible range change at initialization, record only, don't trigger load
              if (!initialRangeProcessed) {
                lastVisibleFrom = data.from
                initialRangeProcessed = true
                // Delayed marking of chart initialization as complete, to allow loads thereafter
                setTimeout(() => {
                  chartInitialized.value = true
                }, 1000)
                return
              }

              // If chart not yet initialized, don't trigger load
              if (!chartInitialized.value) {
                lastVisibleFrom = data.from
                return
              }

              // If loading history and user tries to scroll left further, block scroll
              if (loadingHistory.value && data.from <= 0) {
                // Try to keep visible range after the first data point to prevent further left scroll
                try {
                  if (chartRef.value && typeof chartRef.value.setVisibleRange === 'function') {
                    const dataLength = klineData.value.length
                    if (dataLength > 0) {
                      // 获取当前可见范围
                      const currentRange = chartRef.value.getVisibleRange()
                      if (currentRange) {
                        // Calculate number of visible data points
                        const visibleCount = Math.ceil((currentRange.to - currentRange.from) * dataLength / 100)
                        // Set new visible range from the first data point (index 0 is 0%, but we go slightly right)
                        // Use percentage: first point is approx 0%, set to 0.1% to prevent further left scroll
                        const minFrom = 0.1
                        const newTo = Math.min(100, minFrom + (visibleCount / dataLength * 100))
                        chartRef.value.setVisibleRange(minFrom, newTo)
                      }
                    }
                  }
                } catch (e) {
                }
                return
              }

              // Trigger load when scrolled to far left (index close to 0 or <= 5)
              // Only trigger on active left scroll (lastVisibleFrom > data.from)
              // [Critical] Check both loadingHistory and loadingHistoryPromise to ensure no ongoing requests
              if (data.from <= 5 && !loadingHistory.value && !loadingHistoryPromise && hasMoreHistory.value && chartInitialized.value) {
                // 检查是否是用户主动向左滚动（避免初始化时触发）
                if (lastVisibleFrom !== null && lastVisibleFrom > data.from) {
                  if (klineData.value.length > 0) {
                    const earliestTimestamp = klineData.value[0].timestamp
                    await loadMoreHistoryDataForScroll(earliestTimestamp)
                  }
                }
              }

              // 更新上一次的可见范围
              lastVisibleFrom = data.from
            }
          })
        }

        // If data exists, apply it
        if (klineData.value && klineData.value.length > 0) {
          // Ensure data format is correct
          const validData = klineData.value.filter(item =>
            item.timestamp &&
            !isNaN(item.open) &&
            !isNaN(item.high) &&
            !isNaN(item.low) &&
            !isNaN(item.close)
          )

          if (validData.length > 0) {
            // Use applyNewData for initialization
            try {
              chartRef.value.applyNewData(validData)
            } catch (e) {
              // 尝试降级处理
              try {
                chartRef.value.applyNewData(validData)
              } catch (e2) {
              }
            }

            // Create volume indicator (show by default)
            try {
              chartRef.value.createIndicator('VOL', false, { height: 100, dragEnabled: true })
            } catch (e) {
            }

            // Delayed indicator update to ensure Klines render first
            nextTick(() => {
              updateIndicators()
            })
          }
        }

        window.addEventListener('resize', handleResize)
      } catch (error) {
        error.value = proxy.$t('dashboard.indicator.error.chartInitFailed') + ': ' + (error.message || '未知错误')
      }
    }

    const handleResize = () => {
      if (chartRef.value) {
        setTimeout(() => {
          if (chartRef.value) {
            chartRef.value.resize()
          }
        }, 100)
      } else {
        const container = document.getElementById('kline-chart-container')
        if (container && container.clientWidth > 0 && container.clientHeight > 0) {
          initChart()
        }
      }
    }

    // Update chart theme
    const updateChartTheme = () => {
      if (!chartRef.value) return

      const theme = themeConfig.value
      const isDark = chartTheme.value === 'dark'

      chartRef.value.setStyles({
        grid: {
          show: true,
          horizontal: {
            show: true,
            color: theme.gridLineColor,
            style: 'dashed',
            size: 1
          },
          vertical: {
            show: false
          }
        },
        candle: {
          priceMark: {
            show: true,
            high: {
              show: true,
              color: theme.axisLabelColor
            },
            low: {
              show: true,
              color: theme.axisLabelColor
            }
          },
          tooltip: {
            showRule: 'always',
            showType: 'standard',
            labels: [
              proxy.$t('dashboard.indicator.tooltip.time'),
              proxy.$t('dashboard.indicator.tooltip.open'),
              proxy.$t('dashboard.indicator.tooltip.high'),
              proxy.$t('dashboard.indicator.tooltip.low'),
              proxy.$t('dashboard.indicator.tooltip.close'),
              proxy.$t('dashboard.indicator.tooltip.volume')
            ],
            values: (kLineData) => {
              const d = new Date(kLineData.timestamp)
              return [
                `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()} ${d.getHours()}:${d.getMinutes()}`,
                kLineData.open.toFixed(2),
                kLineData.high.toFixed(2),
                kLineData.low.toFixed(2),
                kLineData.close.toFixed(2),
                kLineData.volume.toFixed(0)
              ]
            }
          },
          bar: {
            upColor: isDark ? '#0ecb81' : '#13c2c2',
            downColor: isDark ? '#f6465d' : '#fa541c',
            noChangeColor: theme.borderColor
          }
        },
        indicator: {
          tooltip: {
            showRule: 'always',
            showType: 'standard'
          }
        },
        xAxis: {
          show: true,
          axisLine: {
            show: true,
            color: theme.borderColor
          }
        },
        yAxis: {
          show: true,
          axisLine: {
            show: false
          }
        },
        crosshair: {
          show: true,
          horizontal: {
            show: true,
            line: {
              show: true,
              style: 'dashed',
              color: theme.gridLineColor,
              size: 1
            }
          },
          vertical: {
            show: true,
            line: {
              show: true,
              style: 'dashed',
              color: theme.gridLineColor,
              size: 1
            }
          }
        },
        watermark: {
          show: false
        }
      })
    }

    // --- Register custom indicator helper functions ---
    const registerCustomIndicator = (name, calcFunc, figures, calcParams = [], precision = 2, shouldOverlay = false) => {
      try {
        // KLineChart v9 uses series: 'price' to identify main plot indicators
        const indicatorConfig = {
          name,
          shortName: name, // Add shortName
          calc: calcFunc,
          figures,
          calcParams,
          precision,
          series: shouldOverlay ? 'price' : 'normal'
        }

        registerIndicator(indicatorConfig)
        // console.log(`成功注册指标: ${name}, series: ${indicatorConfig.series}`)
        return true
      } catch (err) {
        // If already registered, ignore error
        if (err.message && err.message.includes('already registered')) {
          return true
        }
        return false
      }
    }

    // --- Update indicators (KLineChart version) ---
    const updateIndicators = async () => {
      if (indicatorsUpdating.value) {
        return
      }
      // Use JSON serialization/deserialization to remove Vue 2 Observer interference
      if (!chartRef.value || klineData.value.length === 0) {
        return
      }

      indicatorsUpdating.value = true
      try {
      // 1. Remove all added signal overlays
      try {
        if (addedSignalOverlayIds.value.length > 0 && chartRef.value) {
          addedSignalOverlayIds.value.forEach(overlayId => {
            try {
              if (typeof chartRef.value.removeOverlay === 'function') {
                chartRef.value.removeOverlay(overlayId)
              } else if (typeof chartRef.value.removeOverlayById === 'function') {
                chartRef.value.removeOverlayById(overlayId)
              }
            } catch (err) {
            }
          })
          // 清空列表
          addedSignalOverlayIds.value = []
        }
      } catch (e) {
      }

      // 2. Remove all added indicators
      try {
        if (addedIndicatorIds.value.length > 0) {
          addedIndicatorIds.value.forEach(info => {
            // info can be { paneId, name } object or just name string
            const name = typeof info === 'string' ? info : info.name
            const paneId = typeof info === 'string' ? undefined : info.paneId

            // 尝试移除指标
            // KLineChart v9: removeIndicator(paneId, name)
            if (paneId) {
              chartRef.value.removeIndicator(paneId, name)
            } else {
              // If no paneId, try removing from main plot
              chartRef.value.removeIndicator('candle_pane', name)
              // Can also try without passing paneId
              chartRef.value.removeIndicator(name)
            }
          })
          // 清空列表
          addedIndicatorIds.value = []
        }
      } catch (e) {
      }

      // Convert data format (KLineChart needs internal format for calculations)
      const internalData = convertToInternalFormat(klineData.value)

      // Iterate through all active indicators
      for (let idx = 0; idx < props.activeIndicators.length; idx++) {
        const indicator = props.activeIndicators[idx]
        try {
          // Python indicators
          if (indicator.type === 'python') {
            if (!indicator.code) continue

            try {
              // If calculate function exists, use it (for Python indicators)
              if (indicator.calculate && typeof indicator.calculate === 'function') {
                const result = await indicator.calculate(internalData, indicator.params || {})

                // Handle plots in result - merge all plots into one indicator
                // Signals are not added to the indicator, but handled separately to avoid "n/a" display
                let allPlots = []
                if (result && result.plots && Array.isArray(result.plots)) {
                  allPlots = [...result.plots]
                }

                // 处理 signals - 使用 KLineChart 的 createOverlay 显示（不添加到指标中）
                if (result && result.signals && Array.isArray(result.signals)) {
                  for (const signal of result.signals) {
                    if (signal.data && Array.isArray(signal.data) && signal.data.length > 0) {
                      // 统计非空值的数量
                      const sampleValues = []
                      for (let i = 0; i < Math.min(signal.data.length, 20); i++) {
                        const val = signal.data[i]
                        if (val !== null && val !== undefined && !isNaN(val)) {
                          if (sampleValues.length < 5) {
                            sampleValues.push({ index: i, value: val })
                          }
                        }
                      }

                      // 找到所有非空的信号点
                      const signalPoints = []
                      for (let i = 0; i < signal.data.length && i < internalData.length; i++) {
                        const signalValue = signal.data[i]
                        if (signalValue !== null && signalValue !== undefined && !isNaN(signalValue)) {
                          const klineItem = internalData[i]
                          const timestamp = klineItem.timestamp || klineItem.time

                          // 【核心修改】获取当前 K 线的 High 和 Low
                          // 注意：internalData 已经是你转换过的格式，直接取即可
                          const highPrice = klineItem.high
                          const lowPrice = klineItem.low

                          // Signal type: chart only displays indicator signals (buy/sell).
                          const signalTypeRaw = (signal.type || 'buy')
                          const signalType = String(signalTypeRaw).toLowerCase()
                          // Chart only displays indicator signals (no position mgmt / TP/SL / trailing etc).
                          const allowedSignalTypes = ['buy', 'sell']
                          if (!allowedSignalTypes.includes(signalType)) {
                            continue
                          }
                          // Buy-side labels are shown below candles; sell-side labels above candles.
                          const isBuySignal = signalType === 'buy'

                          // Text: prefer per-point textData, otherwise use signal.text, otherwise fallback to B/S.
                          let pointText = signal.text || (isBuySignal ? 'B' : 'S')
                          if (signal.textData && signal.textData[i] != null) {
                            pointText = signal.textData[i]
                          }

                          signalPoints.push({
                            timestamp,
                            price: signalValue,
                            // Determine anchor price: Low for buy, High for sell
                            anchorPrice: isBuySignal ? lowPrice : highPrice,
                            // side is used for layout/styling; action preserves the original type (buy/sell).
                            side: isBuySignal ? 'buy' : 'sell',
                            action: signalType,
                            color: signal.color || (isBuySignal ? '#00E676' : '#FF5252'),
                            text: pointText
                          })
                        }
                      }

                      // 使用 KLineChart 的 createOverlay 添加标记
                      if (signalPoints.length > 0 && chartRef.value) {
                        for (const point of signalPoints) {
                          try {
                            // 确保时间戳是毫秒级
                            let timestamp = point.timestamp
                            if (timestamp < 1e10) {
                              timestamp = timestamp * 1000
                            }

                            // 只显示 buy 或 sell，不显示金额
                            const displaySimpleText = point.text

                            // === 使用自定义 signalTag ===
                            if (typeof chartRef.value.createOverlay === 'function') {
                              const overlayId = chartRef.value.createOverlay({
                                name: 'signalTag',
                                // 【核心修改】传入两个点：
                                // Point 0: 信号触发价格 (用于画圆点)
                                // Point 1: K线极值价格 (用于定位标签)
                                points: [
                                  { timestamp: timestamp, value: point.price },
                                  { timestamp: timestamp, value: point.anchorPrice }
                                ],
                                extendData: {
                                  text: displaySimpleText,
                                  color: point.color,
                                  side: point.side,
                                  action: point.action,
                                  price: point.price
                                },
                                lock: true // 锁定防止拖动
                              }, 'candle_pane') // 绘制在主图

                              if (overlayId) {
                                addedSignalOverlayIds.value.push(overlayId)
                              }
                            }
                            // === 修改结束 ===
                          } catch (overlayErr) {
                          }
                        }
                      } else {
                      }
                    }
                  }
                }

                // 只处理 plots（不包括 signals）
                if (allPlots.length > 0) {
                  // 过滤出有效的 plots
                  const validPlots = allPlots.filter(plot => plot.data && Array.isArray(plot.data) && plot.data.length > 0)

                  if (validPlots.length > 0) {
                    // 构建 figures 数组，包含所有 plots
                    const figures = []
                    const plotDataMap = {}

                    for (let plotIdx = 0; plotIdx < validPlots.length; plotIdx++) {
                      const plot = validPlots[plotIdx]
                      const plotName = plot.name || `PLOT_${plotIdx}_${idx}`
                      const figureKey = plotName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '_')
                      const plotColor = plot.color || getIndicatorColor(plotIdx)

                      // 对于普通 plot，使用原类型或 'line'
                      const figureType = plot.type || 'line'

                      figures.push({
                        key: figureKey,
                        title: plot.name || plotName,
                        type: figureType,
                        color: plotColor
                      })

                      plotDataMap[figureKey] = plot.data
                    }

                    // 确定是否叠加在主图上（如果所有 plots 都是 overlay，则叠加）
                    const allOverlay = validPlots.every(plot => plot.overlay !== false)
                    // const customIndicatorName = `${indicator.id}_combined`
                    let customIndicatorName = `${indicator.id}_combined`
                    if (result && result.name) {
                      customIndicatorName = result.name
                    }
                    try {
                      // 注册合并的自定义指标
                      const registered = registerCustomIndicator(
                        customIndicatorName,
                        (kLineDataList) => {
                          const result = []
                          for (let i = 0; i < kLineDataList.length; i++) {
                            const dataPoint = {}
                            for (const figureKey in plotDataMap) {
                              const plotData = plotDataMap[figureKey]
                              dataPoint[figureKey] = i < plotData.length ? plotData[i] : null
                            }
                            result.push(dataPoint)
                          }
                          return result
                        },
                        figures,
                        [],
                        2,
                        allOverlay
                      )

                      if (registered) {
                        if (allOverlay) {
                          // 主图指标
                          const paneId = chartRef.value.createIndicator(
                            customIndicatorName,
                            false,
                            { id: 'candle_pane' }
                          )
                          if (paneId) {
                            addedIndicatorIds.value.push({ paneId, name: customIndicatorName })
                          } else {
                            addedIndicatorIds.value.push({ paneId: 'candle_pane', name: customIndicatorName })
                          }
                        } else {
                          // 副图指标
                          const indicatorId = chartRef.value.createIndicator(
                            customIndicatorName,
                            false,
                            { height: 100, dragEnabled: true }
                          )
                          if (indicatorId) {
                            addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                          }
                        }
                      }
                    } catch (plotErr) {
                    }
                  }
                }
              } else {
                // If no calculate function, use executePythonStrategy directly
                // Construct information required for decryption
                const decryptInfo = {
                  id: indicator.originalId || indicator.id, // Prefer original database ID
                  user_id: indicator.user_id || indicator.userId,
                  is_encrypted: indicator.is_encrypted || indicator.isEncrypted || 0
                }
                const pythonResult = await executePythonStrategy(
                  indicator.code,
                  internalData,
                  indicator.params || {},
                  decryptInfo // Pass decryption info
                )

                // Handle plots - merge all plots into one indicator
                // Signals are not added to the indicator, but handled separately to avoid "n/a" display
                let allPlots = []
                if (pythonResult && pythonResult.plots && Array.isArray(pythonResult.plots)) {
                  allPlots = [...pythonResult.plots]
                }

                // 处理 signals - 使用 KLineChart 的 createOverlay 显示（不添加到指标中）
                if (pythonResult && pythonResult.signals && Array.isArray(pythonResult.signals)) {
                  for (const signal of pythonResult.signals) {
                    if (signal.data && Array.isArray(signal.data) && signal.data.length > 0) {
                      // 统计非空值的数量
                      const sampleValues = []
                      for (let i = 0; i < Math.min(signal.data.length, 20); i++) {
                        const val = signal.data[i]
                        if (val !== null && val !== undefined && !isNaN(val)) {
                          if (sampleValues.length < 5) {
                            sampleValues.push({ index: i, value: val })
                          }
                        }
                      }

                      // 找到所有非空的信号点
                      const signalPoints = []
                      for (let i = 0; i < signal.data.length && i < internalData.length; i++) {
                        const signalValue = signal.data[i]
                        if (signalValue !== null && signalValue !== undefined && !isNaN(signalValue)) {
                          const klineItem = internalData[i]
                          const timestamp = klineItem.timestamp || klineItem.time

                          // 【核心修改】获取当前 K 线的 High 和 Low
                          // 注意：internalData 已经是你转换过的格式，直接取即可
                          const highPrice = klineItem.high
                          const lowPrice = klineItem.low

                          // Signal type: chart only displays indicator signals (buy/sell).
                          const signalTypeRaw = (signal.type || 'buy')
                          const signalType = String(signalTypeRaw).toLowerCase()
                          // Chart only displays indicator signals (no position mgmt / TP/SL / trailing etc).
                          const allowedSignalTypes = ['buy', 'sell']
                          if (!allowedSignalTypes.includes(signalType)) {
                            continue
                          }
                          const isBuySignal = signalType === 'buy'

                          // Text: prefer per-point textData, otherwise use signal.text, otherwise fallback to B/S.
                          let pointText = signal.text || (isBuySignal ? 'B' : 'S')
                          if (signal.textData && signal.textData[i] != null) {
                            pointText = signal.textData[i]
                          }

                          signalPoints.push({
                            timestamp,
                            price: signalValue,
                            // 确定锚点价格：买入看 Low，卖出看 High
                            anchorPrice: isBuySignal ? lowPrice : highPrice,
                            side: isBuySignal ? 'buy' : 'sell',
                            action: signalType,
                            color: signal.color || (isBuySignal ? '#00E676' : '#FF5252'),
                            text: pointText
                          })
                        }
                      }

                      // 使用 KLineChart 的 createOverlay 添加标记
                      if (signalPoints.length > 0 && chartRef.value) {
                        for (const point of signalPoints) {
                          try {
                            // 确保时间戳是毫秒级
                            let timestamp = point.timestamp
                            if (timestamp < 1e10) {
                              timestamp = timestamp * 1000
                            }

                            // 只显示 buy 或 sell，不显示金额
                            const displaySimpleText = point.text

                            // === 使用自定义 signalTag ===
                            if (typeof chartRef.value.createOverlay === 'function') {
                              const overlayId = chartRef.value.createOverlay({
                                name: 'signalTag',
                                // 【核心修改】传入两个点：
                                // Point 0: 信号触发价格 (用于画圆点)
                                // Point 1: K线极值价格 (用于定位标签)
                                points: [
                                  { timestamp: timestamp, value: point.price },
                                  { timestamp: timestamp, value: point.anchorPrice }
                                ],
                                extendData: {
                                  text: displaySimpleText,
                                  color: point.color,
                                  side: point.side,
                                  action: point.action,
                                  price: point.price
                                },
                                lock: true // 锁定防止拖动
                              }, 'candle_pane') // 绘制在主图

                              if (overlayId) {
                                addedSignalOverlayIds.value.push(overlayId)
                              }
                            }
                            // === 修改结束 ===
                          } catch (overlayErr) {
                          }
                        }
                      } else {
                      }
                    }
                  }
                }

                // 只处理 plots（不包括 signals）
                if (allPlots.length > 0) {
                  // 过滤出有效的 plots
                  const validPlots = allPlots.filter(plot => plot.data && Array.isArray(plot.data) && plot.data.length > 0)

                  if (validPlots.length > 0) {
                    // 构建 figures 数组，包含所有 plots
                    const figures = []
                    const plotDataMap = {}

                    for (let plotIdx = 0; plotIdx < validPlots.length; plotIdx++) {
                      const plot = validPlots[plotIdx]
                      const plotName = plot.name || `PLOT_${plotIdx}`
                      const figureKey = plotName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '_')
                      const plotColor = plot.color || getIndicatorColor(plotIdx)

                      // 对于普通 plot，使用原类型或 'line'
                      const figureType = plot.type || 'line'

                      figures.push({
                        key: figureKey,
                        title: plot.name || plotName,
                        type: figureType,
                        color: plotColor
                      })

                      plotDataMap[figureKey] = plot.data
                    }

                    // 确定是否叠加在主图上（如果所有 plots 都是 overlay，则叠加）
                    const allOverlay = validPlots.every(plot => plot.overlay !== false)
                    // const customIndicatorName = `${indicator.id}_combined`
                    let customIndicatorName = `${indicator.id}_combined`
                    if (pythonResult && pythonResult.name) {
                      customIndicatorName = pythonResult.name
                    }

                    try {
                      // 注册合并的自定义指标
                      const registered = registerCustomIndicator(
                        customIndicatorName,
                        (kLineDataList) => {
                          const result = []
                          for (let i = 0; i < kLineDataList.length; i++) {
                            const dataPoint = {}
                            for (const figureKey in plotDataMap) {
                              const plotData = plotDataMap[figureKey]
                              dataPoint[figureKey] = i < plotData.length ? plotData[i] : null
                            }
                            result.push(dataPoint)
                          }
                          return result
                        },
                        figures,
                        [],
                        2,
                        allOverlay
                      )

                      if (registered) {
                        if (allOverlay) {
                          // 主图指标
                          const paneId = chartRef.value.createIndicator(
                            customIndicatorName,
                            false,
                            { id: 'candle_pane' }
                          )
                          if (paneId) {
                            addedIndicatorIds.value.push({ paneId, name: customIndicatorName })
                          } else {
                            addedIndicatorIds.value.push({ paneId: 'candle_pane', name: customIndicatorName })
                          }
                        } else {
                          // 副图指标
                          const indicatorId = chartRef.value.createIndicator(
                            customIndicatorName,
                            false,
                            { height: 100, dragEnabled: true }
                          )
                          if (indicatorId) {
                            addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                          }
                        }
                      }
                    } catch (plotErr) {
                    }
                  }
                }
              }
            } catch (err) {
              // If Python engine not ready error, set load failure state
              if (err.message && err.message.includes('Python 引擎未就绪')) {
                if (!loadingPython.value) {
                  pyodideLoadFailed.value = true
                }
              }
            }
            continue
          }

          // Note: calculate function might be null, as logic is determined by id in updateIndicators
          // So we don't check calculate, but handle directly via indicator.id

          const color = getIndicatorColor(idx)

          // Create KLineChart indicator based on indicator type
          if (indicator.id === 'sma' || indicator.id === 'ema') {
            const maType = indicator.id === 'sma' ? 'SMA' : 'EMA'
            const period = indicator.params?.length || indicator.params?.period || 20
            const customIndicatorName = `${maType}_${period}`
            const figureKey = maType.toLowerCase()
            const calcPeriod = period

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const p = indicator.calcParams[0] || calcPeriod
                  // calculateSMA/EMA needs an array of objects with close property, not a numeric array
                  const values = maType === 'SMA'
                    ? calculateSMA(kLineDataList, p)
                    : calculateEMA(kLineDataList, p)
                  return values.map(v => ({ [figureKey]: v }))
                },
                [{ key: figureKey, title: `${maType}(${period})`, type: 'line' }],
                [period],
                2,
                true // shouldOverlay: true 表示主图指标
              )

              if (registered) {
                // 创建指标
                const paneId = chartRef.value.createIndicator(
                  customIndicatorName,
                  false, // isStack
                  { id: 'candle_pane' }
                )

                if (paneId) {
                  addedIndicatorIds.value.push({ paneId, name: customIndicatorName })
                } else {
                  // If null returned (main plot indicator might return null), record it too
                  addedIndicatorIds.value.push({ paneId: 'candle_pane', name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'macd') {
            // MACD drawn on sub-plot by default
            const indicatorId = chartRef.value.createIndicator('MACD', false, { height: 100, dragEnabled: true })
            if (indicatorId) {
              addedIndicatorIds.value.push({ paneId: indicatorId, name: 'MACD' })
            }
          } else if (indicator.id === 'rsi') {
             const indicatorId = chartRef.value.createIndicator('RSI', false, { height: 100, dragEnabled: true })
             if (indicatorId) {
               addedIndicatorIds.value.push({ paneId: indicatorId, name: 'RSI' })
             }
          } else if (indicator.id === 'bollinger_bands' || indicator.id === 'bb') {
            // Bollinger Bands requires custom indicator registration
            const length = indicator.params?.length || 20
            const mult = indicator.params?.mult || 2
            const customIndicatorName = `BOLL_${length}_${mult}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const length = indicator.calcParams[0] || 20
                  const mult = indicator.calcParams[1] || 2
                  // calculateBollingerBands needs an array of objects with close property
                  const bbResult = calculateBollingerBands(kLineDataList, length, mult)
                  // KLineChart requires an array of objects, with keys matching figures keys
                  const result = []
                  for (let i = 0; i < bbResult.length; i++) {
                    result.push({
                      upper: bbResult[i]?.upper ?? null,
                      middle: bbResult[i]?.middle ?? null,
                      lower: bbResult[i]?.lower ?? null
                    })
                  }
                  return result
                },
                [
                  { key: 'upper', title: `Upper(${length},${mult})`, type: 'line' },
                  { key: 'middle', title: `Middle(${length})`, type: 'line' },
                  { key: 'lower', title: `Lower(${length},${mult})`, type: 'line' }
                ],
                [length, mult], // calcParams
                2, // precision
                true // shouldOverlay: true 表示主图指标
              )

              if (registered) {
                // Create indicator (main plot indicator)
                const paneId = chartRef.value.createIndicator(
                  customIndicatorName,
                  false, // isStack: false denotes no stacking
                  { id: 'candle_pane' }
                )
                if (paneId) {
                  addedIndicatorIds.value.push({ paneId, name: customIndicatorName })
                } else {
                  addedIndicatorIds.value.push({ paneId: 'candle_pane', name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'atr') {
            // ATR requires custom indicator registration
            const period = indicator.params?.period || indicator.params?.length || 14
            const customIndicatorName = `ATR_${period}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const period = indicator.calcParams[0] || 14
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close
                  }))
                  const atrValues = calculateATR(data, period)
                  // 转换为 KLineChart 需要的格式：返回对象数组
                  return atrValues.map(value => ({ atr: value }))
                },
                [{
                  key: 'atr',
                  title: `ATR(${period})`,
                  type: 'line',
                  color: color
                }],
                [period]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'williams' || indicator.id === 'williams_r') {
            // Williams %R requires custom indicator registration
            const length = indicator.params?.length || 14
            const customIndicatorName = `WPR_${length}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const length = indicator.calcParams[0] || 14
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close
                  }))
                  const wrValues = calculateWilliamsR(data, length)
                  // 转换为 KLineChart 需要的格式：返回对象数组
                  return wrValues.map(value => ({ wr: value }))
                },
                [{
                  key: 'wr',
                  title: `W%R(${length})`,
                  type: 'line',
                  color: color
                }],
                [length]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'mfi') {
            // MFI requires custom indicator registration
            const length = indicator.params?.length || 14
            const customIndicatorName = `MFI_${length}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const length = indicator.calcParams[0] || 14
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close,
                    volume: d.volume
                  }))
                  const mfiValues = calculateMFI(data, length)
                  // 转换为 KLineChart 需要的格式：返回对象数组
                  return mfiValues.map(value => ({ mfi: value }))
                },
                [{
                  key: 'mfi',
                  title: `MFI(${length})`,
                  type: 'line',
                  color: color
                }],
                [length]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'cci') {
            // CCI requires custom indicator registration
            const length = indicator.params?.length || 20
            const customIndicatorName = `CCI_${length}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const length = indicator.calcParams[0] || 20
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close
                  }))
                  const cciValues = calculateCCI(data, length)
                  // 转换为 KLineChart 需要的格式：返回对象数组
                  return cciValues.map(value => ({ cci: value }))
                },
                [{
                  key: 'cci',
                  title: `CCI(${length})`,
                  type: 'line',
                  color: color
                }],
                [length]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'adx') {
            // ADX requires custom indicator registration
            const length = indicator.params?.length || 14
            const customIndicatorName = `ADX_${length}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const length = indicator.calcParams[0] || 14
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close
                  }))
                  const result = calculateADX(data, length)
                  // 转换为 KLineChart 需要的格式：返回对象数组
                  return result.adx.map(value => ({ adx: value }))
                },
                [{
                  key: 'adx',
                  title: `ADX(${length})`,
                  type: 'line',
                  color: color
                }],
                [length]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'obv') {
            // OBV requires custom indicator registration
            const customIndicatorName = 'OBV'

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const data = kLineDataList.map(d => ({
                    close: d.close,
                    volume: d.volume || 0
                  }))
                  const obvValues = calculateOBV(data)
                  return obvValues.map(value => ({ obv: value }))
                },
                [{
                  key: 'obv',
                  title: 'OBV',
                  type: 'line',
                  color: color
                }],
                []
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'adosc') {
            // ADOSC requires custom indicator registration
            const fast = indicator.params?.fast || 3
            const slow = indicator.params?.slow || 10
            const customIndicatorName = `ADOSC_${fast}_${slow}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const fast = indicator.calcParams[0] || 3
                  const slow = indicator.calcParams[1] || 10
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close,
                    volume: d.volume || 0
                  }))
                  const adoscValues = calculateADOSC(data, fast, slow)
                  return adoscValues.map(value => ({ adosc: value }))
                },
                [{
                  key: 'adosc',
                  title: `ADOSC(${fast},${slow})`,
                  type: 'line',
                  color: color
                }],
                [fast, slow]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'ad') {
            // AD requires custom indicator registration
            const customIndicatorName = 'AD'

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close,
                    volume: d.volume || 0
                  }))
                  const adValues = calculateAD(data)
                  return adValues.map(value => ({ ad: value }))
                },
                [{
                  key: 'ad',
                  title: 'AD',
                  type: 'line',
                  color: color
                }],
                []
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else if (indicator.id === 'kdj') {
            // KDJ requires custom indicator registration
            const period = indicator.params?.period || 9
            const kPeriod = indicator.params?.k || 3
            const dPeriod = indicator.params?.d || 3
            const customIndicatorName = `KDJ_${period}_${kPeriod}_${dPeriod}`

            try {
              const registered = registerCustomIndicator(
                customIndicatorName,
                (kLineDataList, indicator) => {
                  const period = indicator.calcParams[0] || 9
                  const kPeriod = indicator.calcParams[1] || 3
                  const dPeriod = indicator.calcParams[2] || 3
                  const data = kLineDataList.map(d => ({
                    high: d.high,
                    low: d.low,
                    close: d.close
                  }))
                  const result = calculateKDJ(data, period, kPeriod, dPeriod)
                  return result.k.map((k, i) => ({
                    k: k,
                    d: result.d[i],
                    j: result.j[i]
                  }))
                },
                [
                  { key: 'k', title: `K(${period},${kPeriod})`, type: 'line', color: '#FF6B6B' },
                  { key: 'd', title: `D(${dPeriod})`, type: 'line', color: '#4ECDC4' },
                  { key: 'j', title: `J`, type: 'line', color: '#95E1D3' }
                ],
                [period, kPeriod, dPeriod]
              )

              if (registered) {
                const indicatorId = chartRef.value.createIndicator(customIndicatorName, false, { height: 100, dragEnabled: true })
                if (indicatorId) {
                  addedIndicatorIds.value.push({ paneId: indicatorId, name: customIndicatorName })
                }
              }
            } catch (err) {
            }
          } else {
            // Try creating directly with indicator.id (assuming built-in indicator name)
            try {
              const indicatorName = indicator.id.toUpperCase()
              const indicatorId = chartRef.value.createIndicator(indicatorName, false, { height: 100, dragEnabled: true })
              if (indicatorId) {
                addedIndicatorIds.value.push({ paneId: indicatorId, name: indicatorName })
              }
            } catch (err) {
            }
          }
          // ... Other indicators ...
        } catch (e) {
        }
      }
      } finally {
        indicatorsUpdating.value = false
      }
    }

    const handleRetry = () => {
      loadKlineData()
    }

    // Lifecycle
    watch(() => props.symbol, () => {
      if (props.symbol) {
        loadKlineData()
      }
    })
    watch(() => props.theme, (newTheme) => {
      chartTheme.value = newTheme
      if (chartRef.value) {
        updateChartTheme()
        updateIndicators()
      }
    })

    watch(() => props.symbol, () => {
      if (props.symbol) {
        loadKlineData()
      }
    })

    watch(() => props.market, () => {
      if (props.symbol) {
        loadKlineData()
      }
    })

    watch(() => props.timeframe, () => {
      if (props.symbol) {
        loadKlineData()
      }
      // Restart real-time update on timeframe change (if enabled)
      if (props.realtimeEnabled) {
        stopRealtime()
        startRealtime()
      }
    })

    watch(() => props.activeIndicators, (newVal, oldVal) => {
      // Rerender chart when indicator list changes
      if (chartRef.value && klineData.value.length > 0) {
        // Use nextTick to ensure chart updates after DOM update completion
        nextTick(() => {
          if (chartRef.value) {
            updateIndicators()
          }
        })
      }
    }, { deep: true })

    watch(() => props.realtimeEnabled, (newVal) => {
      if (newVal) {
        startRealtime()
      } else {
        stopRealtime()
      }
    })

    onMounted(async () => {
      // Prioritize props.theme (from Vuex store) to ensure synchronization with system theme
      // Use nextTick to ensure props are correctly passed
      await nextTick()
      if (props.theme && (props.theme === 'dark' || props.theme === 'light')) {
        chartTheme.value = props.theme
      }

      // Load Pyodide
      try {
        await loadPyodide()
      } catch (err) {
        pyodideLoadFailed.value = true
      }

      nextTick(() => {
        setTimeout(() => {
          if (!chartRef.value && props.symbol) {
            initChart()
          }
        }, 300)
      })
    })

    onBeforeUnmount(() => {
      stopRealtime()
      if (chartRef.value) {
        chartRef.value.destroy()
        chartRef.value = null
      }
      window.removeEventListener('resize', handleResize)
    })

    return {
      klineData,
      loading,
      error,
      loadingHistory,
      chartRef,
      chartTheme,
      themeConfig,
      getIndicatorColor,
      handleRetry,
      loadingPython,
      pythonReady,
      pyodideLoadFailed,
      formatKlineData,
      updatePricePanel,
      isSameTimeframe,
      loadKlineData,
      loadMoreHistoryData,
      updateKlineRealtime,
      startRealtime,
      stopRealtime,
      initChart,
      handleResize,
      updateChartTheme,
      updateIndicators,
      executePythonStrategy,
      parsePythonStrategy,
      indicatorButtons,
      isIndicatorActive,
      toggleIndicator,
      drawingTools,
      activeDrawingTool,
      selectDrawingTool,
      clearAllDrawings
    }
  }
}
</script>

<style lang="less" scoped>
/* Left chart container */
.chart-left {
  width: 70% !important;
  flex: 0 0 70% !important;
  position: relative;
  border-right: 1px solid #e8e8e8;
  background: #fff;
  transition: background-color 0.3s;
  touch-action: pan-x pan-y;
  -webkit-overflow-scrolling: touch;

  &.theme-dark {
    background: #131722;
    border-right-color: #2a2e39;
  }
}

.chart-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  background: #fff;
  transition: background-color 0.3s;
  touch-action: pan-x pan-y;
  -webkit-overflow-scrolling: touch;
  display: flex;

  .theme-dark & {
    background: #131722;
  }
}

/* Drawing Tools Toolbar */
.drawing-toolbar {
  flex-shrink: 0;
  width: 40px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  gap: 4px;
  z-index: 10;
  overflow-y: auto;
  overflow-x: hidden;
}

.chart-left.theme-dark .drawing-toolbar {
  background: #131722;
  border-right-color: #2a2e39;
}

.drawing-tool-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
  color: #666;
  font-size: 16px;
  user-select: none;
}

.chart-left.theme-dark .drawing-tool-btn {
  color: #d1d4dc;
}

.drawing-tool-btn:hover {
  background: #f0f2f5;
  color: #1890ff;
}

.chart-left.theme-dark .drawing-tool-btn:hover {
  background: #1f2943;
  color: #13c2c2;
}

.drawing-tool-btn.active {
  background: #e6f7ff;
  color: #1890ff;
  border: 1px solid #1890ff;
}

.chart-left.theme-dark .drawing-tool-btn.active {
  background: #1f2943;
  color: #13c2c2;
  border-color: #13c2c2;
}

.drawing-toolbar .ant-divider-vertical {
  margin: 8px 0;
  height: 20px;
}

/* Indicator Toolbar */
.indicator-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  flex-wrap: wrap;
  z-index: 1;
  position: relative;
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE 10+ */
}

.indicator-toolbar::-webkit-scrollbar {
  display: none; /* Chrome Safari */
  width: 0;
  height: 0;
}

/* Chart content area */
.chart-content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0; /* Prevent flex sub-element overflow */
  overflow: hidden;
}

.chart-left.theme-dark .indicator-toolbar {
  background: #131722;
  border-bottom-color: #2a2e39;
}

.indicator-btn {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  background: #f0f2f5;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  min-width: 40px;
  text-align: center;
  user-select: none;
}

.chart-left.theme-dark .indicator-btn {
  color: #d1d4dc;
  background: #1f2943;
  border-color: #2a2e39;
}

.indicator-btn:hover {
  color: #1890ff;
  border-color: #1890ff;
  background: #f0f8ff;
}

.chart-left.theme-dark .indicator-btn:hover {
  color: #13c2c2;
  border-color: #13c2c2;
  background: #1f2943;
}

.indicator-btn.active {
  color: #1890ff;
  background: #fff;
  border-color: #1890ff;
  border-width: 2px;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
}

.chart-left.theme-dark .indicator-btn.active {
  color: #13c2c2;
  background: #1f2943;
  border-color: #13c2c2;
  box-shadow: 0 0 0 2px rgba(19, 194, 194, 0.2);
}

.kline-chart-container {
  flex: 1;
  width: 100%;
  min-width: 0; /* 防止 flex 子元素溢出 */
  background: #fff;
  transition: background-color 0.3s;
  touch-action: pan-x pan-y;
  -webkit-overflow-scrolling: touch;
  overflow: hidden;

  .theme-dark & {
    background: #131722;
  }
}

.chart-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1;
  backdrop-filter: blur(2px);
}

.chart-left.theme-dark .chart-overlay {
  background: rgba(19, 23, 34, 0.95);
}

.error-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #333;
}

.initial-hint {
  background: rgba(255, 255, 255, 0.98);
}

.chart-left.theme-dark .initial-hint {
  background: rgba(19, 23, 34, 0.98);
}

.hint-box {
  text-align: center;
  color: #666;
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 400px;
  padding: 20px;
}

.pyodide-warning {
  background: rgba(255, 255, 255, 0.98);
}

.chart-left.theme-dark .pyodide-warning {
  background: rgba(19, 23, 34, 0.98);
}

.warning-box {
  text-align: center;
  color: #666;
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 500px;
  padding: 20px;
}

.warning-title {
  font-size: 16px;
  font-weight: 600;
  color: #faad14;
  margin-bottom: 8px;
}

.warning-desc {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
}

.chart-left.theme-dark .warning-box {
  color: #d1d4dc;
}

.chart-left.theme-dark .warning-title {
  color: #faad14;
}

.chart-left.theme-dark .warning-desc {
  color: #868993;
}

.chart-left.theme-dark .hint-box {
  color: #d1d4dc;
}

.hint-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.chart-left.theme-dark .hint-title {
  color: #d1d4dc;
}

.hint-desc {
  font-size: 14px;
  color: #999;
  line-height: 1.6;
}

.chart-left.theme-dark .hint-desc {
  color: #787b86;
}

/* History data loading hint */
.history-loading-hint {
  position: absolute;
  left: 20px;
  top: 60px;
  z-index: 1000 !important;
  display: flex !important;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.98) !important;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  font-size: 14px;
  color: #666 !important;
  backdrop-filter: blur(4px);
  pointer-events: none;
  visibility: visible !important;
  opacity: 1 !important;
}

.chart-left.theme-dark .history-loading-hint {
  background: rgba(19, 23, 34, 0.98) !important;
  border-color: #2a2e39;
  color: #d1d4dc !important;
}

.loading-text {
  white-space: nowrap;
  margin-left: 4px;
}

/* Mobile adaptation */
@media (max-width: 768px) {
  .drawing-toolbar {
    display: none; /* Hide drawing toolbar on mobile */
  }

  .indicator-toolbar {
    padding-left: 12px; /* Restore original padding on mobile */
    flex-wrap: nowrap; /* No wrapping on mobile, show only one row */
    overflow-x: auto; /* Allow horizontal scrolling */
    overflow-y: hidden; /* Prohibit vertical scrolling */
    scrollbar-width: none; /* Firefox: hide scrollbar */
    -ms-overflow-style: none; /* IE 10+: hide scrollbar */
    -webkit-overflow-scrolling: touch; /* iOS smooth scrolling */
  }

  .indicator-toolbar::-webkit-scrollbar {
    display: none; /* Chrome Safari: hide scrollbar */
    width: 0;
    height: 0;
  }

  .indicator-btn {
    flex-shrink: 0; /* Button doesn't shrink, maintains original size */
  }
}

@media (max-width: 1200px) {
  .drawing-toolbar {
    display: none; /* Hide drawing toolbar on mobile */
  }

  .indicator-toolbar {
    padding-left: 12px; /* Restore original padding on mobile */
  }

  .kline-chart-container {
    margin-left: 0; /* Restore original margin on mobile */
  }

  .chart-left {
    width: 100% !important;
    min-width: 100% !important;
    border-right: none;
    border-bottom: 1px solid #e8e8e8;
    height: 600px !important;
    min-height: 600px !important;
  }

  .chart-wrapper {
    height: 100% !important;
    min-height: 600px !important;
  }

  .kline-chart-container {
    height: 100% !important;
    min-height: 600px !important;
  }
}

@media (max-width: 992px) {
  .chart-left {
    height: 650px !important;
    min-height: 650px !important;
  }

  .chart-wrapper {
    height: 100% !important;
    min-height: 650px !important;
  }

  .kline-chart-container {
    height: 100% !important;
    min-height: 650px !important;
  }
}

@media (max-width: 768px) {
  .chart-left {
    height: 60vh !important;
    min-height: 400px !important;
    max-height: 80vh !important;
  }

  .chart-wrapper {
    height: 100% !important;
    min-height: 400px !important;
    max-height: 100% !important;
  }

  .kline-chart-container {
    height: calc(100% - 45px) !important; /* Subtract toolbar height */
    min-height: 350px !important;
    max-height: calc(100% - 45px) !important;
  }
}

@media (max-width: 576px) {
  .chart-left {
    height: 55vh !important;
    min-height: 350px !important;
    max-height: 75vh !important;
  }

  .chart-wrapper {
    height: 100% !important;
    min-height: 350px !important;
    max-height: 100% !important;
  }

  .kline-chart-container {
    height: calc(100% - 45px) !important; /* Subtract toolbar height */
    min-height: 300px !important;
    max-height: calc(100% - 45px) !important;
  }
}
</style>
