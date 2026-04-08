<template>
  <div class="ai-analysis-container" :class="{ 'theme-dark': isDarkTheme, embedded: embedded }" :style="{ '--primary-color': primaryColor }">
    <!-- Full-width main content area -->
    <div class="main-content-full">
      <!-- Top market index strip -->
      <div class="top-index-bar">
        <!-- Sentiment indicators load independently -->
        <template v-if="loadingSentiment">
          <div class="indicator-box skeleton-box">
            <span class="skeleton-text short"></span>
            <span class="skeleton-text"></span>
          </div>
          <div class="indicator-box skeleton-box">
            <span class="skeleton-text short"></span>
            <span class="skeleton-text"></span>
          </div>
          <div class="indicator-box skeleton-box">
            <span class="skeleton-text short"></span>
            <span class="skeleton-text"></span>
          </div>
        </template>
        <template v-else>
          <div class="indicator-box fear-greed" :class="getFearGreedClass(marketData.fearGreed)">
            <span class="ind-label">{{ $t('globalMarket.fearGreedShort') }}</span>
            <span class="ind-value">{{ marketData.fearGreed || '--' }}</span>
          </div>
          <div class="indicator-box vix" :class="getVixLevel(marketData.vix)">
            <span class="ind-label">VIX</span>
            <span class="ind-value">{{ marketData.vix || '--' }}</span>
          </div>
          <div class="indicator-box dxy">
            <span class="ind-label">DXY</span>
            <span class="ind-value">{{ marketData.dxy || '--' }}</span>
          </div>
        </template>

        <!-- Global index marquee loads independently -->
        <div class="indices-marquee">
          <template v-if="loadingIndices">
            <div class="indices-loading">
              <a-icon type="loading" /> {{ $t('common.loading') || 'Loading...' }}
            </div>
          </template>
          <template v-else-if="marketData.indices.length > 0">
            <div class="marquee-track">
              <div class="index-item" v-for="idx in marketData.indices" :key="'a-'+idx.symbol">
                <span class="idx-flag">{{ idx.flag }}</span>
                <span class="idx-symbol">{{ idx.symbol }}</span>
                <span class="idx-price">{{ formatPrice(idx.price) }}</span>
                <span class="idx-change" :class="idx.change >= 0 ? 'up' : 'down'">
                  <a-icon :type="idx.change >= 0 ? 'caret-up' : 'caret-down'" />
                  {{ Math.abs(idx.change).toFixed(2) }}%
                </span>
              </div>
              <div class="index-item" v-for="idx in marketData.indices" :key="'b-'+idx.symbol">
                <span class="idx-flag">{{ idx.flag }}</span>
                <span class="idx-symbol">{{ idx.symbol }}</span>
                <span class="idx-price">{{ formatPrice(idx.price) }}</span>
                <span class="idx-change" :class="idx.change >= 0 ? 'up' : 'down'">
                  <a-icon :type="idx.change >= 0 ? 'caret-up' : 'caret-down'" />
                  {{ Math.abs(idx.change).toFixed(2) }}%
                </span>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="indices-empty">--</div>
          </template>
        </div>
        <a-button type="link" size="small" class="refresh-btn" :loading="loadingMarket" @click="loadMarketData">
          <a-icon type="sync" :spin="loadingMarket" />
        </a-button>
      </div>

      <!-- Main three-column layout -->
      <div class="main-body">
        <!-- Left panel: heatmap and economic calendar -->
        <div class="left-panel">
          <!-- Heatmap loads independently -->
          <div class="heatmap-box">
            <div class="box-header">
              <a-radio-group v-model="heatmapType" size="small" button-style="solid">
                <a-radio-button value="crypto">{{ $t('globalMarket.cryptoHeatmap') }}</a-radio-button>
                <a-radio-button value="commodities">{{ $t('globalMarket.commoditiesHeatmap') }}</a-radio-button>
                <a-radio-button value="sectors">{{ $t('globalMarket.sectorHeatmap') }}</a-radio-button>
                <a-radio-button value="forex">{{ $t('globalMarket.forexHeatmap') }}</a-radio-button>
              </a-radio-group>
            </div>
            <div class="heatmap-grid">
              <template v-if="loadingHeatmap">
                <div v-for="i in 12" :key="'skel-'+i" class="heat-cell skeleton-cell">
                  <span class="skeleton-text short"></span>
                  <span class="skeleton-text"></span>
                </div>
              </template>
              <template v-else-if="currentHeatmap.length > 0">
                <div v-for="(item, i) in currentHeatmap.slice(0, 12)" :key="i" class="heat-cell" :style="getHeatmapStyle(item.value)">
                  <span class="heat-name">{{ getHeatmapName(item) }}</span>
                  <span class="heat-price" v-if="item.price">{{ formatHeatmapPrice(item.price) }}</span>
                  <span class="heat-val">{{ item.value >= 0 ? '+' : '' }}{{ formatNum(item.value) }}%</span>
                </div>
              </template>
              <template v-else>
                <div class="heatmap-empty">{{ $t('common.noData') || 'No data' }}</div>
              </template>
            </div>
          </div>

          <!-- Economic calendar loads independently -->
          <div class="calendar-box">
            <div class="box-header">
              <span class="box-title"><a-icon type="calendar" /> {{ $t('globalMarket.calendar') }}</span>
            </div>
            <div class="calendar-list">
              <template v-if="loadingCalendar">
                <div v-for="i in 5" :key="'cal-skel-'+i" class="cal-item skeleton-item">
                  <span class="skeleton-text short"></span>
                  <span class="skeleton-text short"></span>
                  <span class="skeleton-text"></span>
                </div>
              </template>
              <template v-else-if="marketData.calendar.length > 0">
                <div v-for="evt in marketData.calendar.slice(0, 10)" :key="evt.id" class="cal-item" :class="evt.importance">
                  <span class="cal-date">{{ formatCalendarDate(evt.date) }}</span>
                  <span class="cal-time">{{ evt.time || '--:--' }}</span>
                  <span class="cal-flag">{{ getCountryFlag(evt.country) }}</span>
                  <span class="cal-name">{{ isZhLocale ? evt.name : evt.name_en }}</span>
                  <span class="cal-impact" :class="getImpactClass(evt)">
                    <a-icon v-if="getImpactClass(evt) === 'bullish'" type="arrow-up" />
                    <a-icon v-else-if="getImpactClass(evt) === 'bearish'" type="arrow-down" />
                    <a-icon v-else type="minus" />
                    {{ evt.actual || evt.forecast || '--' }}
                  </span>
                </div>
              </template>
              <template v-else>
                <div class="cal-empty">{{ $t('globalMarket.noEvents') }}</div>
              </template>
            </div>
          </div>
        </div>

        <!-- Center panel: toolbar and AI analysis -->
        <div class="right-panel">
          <!-- Analysis toolbar -->
          <div class="analysis-toolbar">
            <a-select
              v-model="selectedSymbol"
              :placeholder="$t('dashboard.analysis.empty.selectSymbol')"
              size="large"
              show-search
              allow-clear
              :filter-option="filterSymbolOption"
              @change="handleSymbolChange"
              class="symbol-selector"
            >
              <a-select-option
                v-for="stock in (watchlist || [])"
                :key="`${stock.market}-${stock.symbol}`"
                :value="`${stock.market}:${stock.symbol}`"
              >
                <span class="symbol-option">
                  <a-tag :color="getMarketColor(stock.market)" size="small">{{ getMarketName(stock.market) }}</a-tag>
                  <strong style="margin-left: 6px;">{{ stock.symbol }}</strong>
                  <span v-if="stock.name" class="symbol-name">{{ stock.name }}</span>
                </span>
              </a-select-option>
              <a-select-option key="add-stock-option" value="__add_stock_option__" class="add-stock-option">
                <div style="text-align: center; padding: 4px 0; color: #1890ff;">
                  <a-icon type="plus" style="margin-right: 4px;" />{{ $t('dashboard.analysis.watchlist.add') }}
                </div>
              </a-select-option>
            </a-select>
            <a-button
type="primary"
size="large"
icon="thunderbolt"
@click="startFastAnalysis"
:loading="analyzing"
:disabled="!selectedSymbol"
class="analyze-button">
              {{ $t('fastAnalysis.startAnalysis') }}
            </a-button>
            <a-button size="large" icon="history" @click="showHistoryModal = true; loadHistoryList()" class="history-button">
              {{ $t('fastAnalysis.history') }}
            </a-button>
          </div>

          <!-- Analysis result area -->
          <div class="analysis-main">
            <div v-if="!analysisResult && !analyzing && !analysisError" class="analysis-placeholder">
              <div class="placeholder-hero">
                <div class="placeholder-mark">
                  <a-icon type="radar-chart" />
                </div>
                <div class="hero-body">
                  <div class="hero-badge">AI-POWERED</div>
                  <h2 class="hero-title">{{ tt('aiAssetAnalysis.placeholder.title', 'AI Market Intelligence Engine') }}</h2>
                  <p class="hero-subtitle">{{ tt('aiAssetAnalysis.placeholder.subtitle', 'Cross-market context, fast symbol analysis, and a tighter workflow between your watchlist and AI reports.') }}</p>

                  <div class="hero-stats">
                    <div class="hstat">
                      <div class="hstat-icon"><a-icon type="line-chart" /></div>
                      <div class="hstat-body">
                        <span class="hstat-val">{{ tt('aiAssetAnalysis.placeholder.feature1', 'Trend Framing') }}</span>
                        <span class="hstat-label">{{ tt('aiAssetAnalysis.placeholder.feature1Desc', 'Combine market context with symbol-specific momentum signals.') }}</span>
                      </div>
                    </div>
                    <div class="hstat">
                      <div class="hstat-icon"><a-icon type="dashboard" /></div>
                      <div class="hstat-body">
                        <span class="hstat-val">{{ tt('aiAssetAnalysis.placeholder.feature2', 'Decision Snapshot') }}</span>
                        <span class="hstat-label">{{ tt('aiAssetAnalysis.placeholder.feature2Desc', 'Get entry, stop-loss, take-profit, and confidence in one report.') }}</span>
                      </div>
                    </div>
                    <div class="hstat">
                      <div class="hstat-icon"><a-icon type="star" /></div>
                      <div class="hstat-body">
                        <span class="hstat-val">{{ tt('aiAssetAnalysis.placeholder.feature3', 'Watchlist Flow') }}</span>
                        <span class="hstat-label">{{ tt('aiAssetAnalysis.placeholder.feature3Desc', 'Move from watchlist selection to analysis without leaving the workspace.') }}</span>
                      </div>
                    </div>
                  </div>

                  <div class="hero-cta">
                    <a-button type="primary" size="large" icon="plus" @click="showAddStockModal = true">
                      {{ $t('dashboard.analysis.watchlist.add') }}
                    </a-button>
                    <a-button size="large" icon="thunderbolt" :disabled="!selectedSymbol" @click="startFastAnalysis">
                      {{ $t('fastAnalysis.startAnalysis') }}
                    </a-button>
                  </div>

                  <p class="hero-hint">{{ tt('aiAssetAnalysis.placeholder.quickStart', 'Pick a symbol from the watchlist on the right, or add one to begin.') }}</p>
                </div>
              </div>
            </div>
            <FastAnalysisReport
              v-if="analysisResult || analyzing || analysisError"
              :result="analysisResult"
              :loading="analyzing"
              :error="analysisError"
              :error-tone="analysisErrorTone"
              @retry="startFastAnalysis"
            />
          </div>
        </div>

        <!-- Right watchlist panel -->
        <div class="watchlist-panel">
          <div class="panel-header">
            <span class="panel-title"><a-icon type="star" theme="filled" /> {{ $t('dashboard.analysis.watchlist.title') }}</span>
            <span class="panel-header-actions">
              <a-tooltip :title="tt('aiAssetAnalysis.tasks.manage', 'Manage Tasks')">
                <a-badge
                  :count="monitors.length"
                  :offset="[-2, 2]"
                  :number-style="{ fontSize: '9px', minWidth: '14px', height: '14px', lineHeight: '14px', padding: '0 3px' }">
                  <a-icon type="unordered-list" class="panel-header-icon" @click="showTaskDrawer = true" />
                </a-badge>
              </a-tooltip>
              <a-tooltip :title="tt('aiAssetAnalysis.batch.schedule', 'Batch Schedule')">
                <a-icon type="schedule" class="panel-header-icon" @click="toggleBatchMode" />
              </a-tooltip>
              <a-icon type="plus" class="panel-header-icon" @click="showAddStockModal = true" />
            </span>
          </div>

          <div v-if="watchlist && watchlist.length > 0" class="panel-summary">
            <div class="summary-chip">
              <span class="sc-num">{{ watchlist.length }}</span>
              <span class="sc-label">{{ tt('aiAssetAnalysis.watchlist.totalAssets', 'Assets') }}</span>
            </div>
            <div v-if="watchlistPositionCount > 0" class="summary-chip">
              <span class="sc-num">{{ watchlistPositionCount }}</span>
              <span class="sc-label">{{ tt('aiAssetAnalysis.watchlist.positionCount', 'Positions') }}</span>
            </div>
            <div v-if="watchlistTaskCount > 0" class="summary-chip">
              <span class="sc-num">{{ watchlistTaskCount }}</span>
              <span class="sc-label">{{ tt('aiAssetAnalysis.watchlist.taskCount', 'Tasks') }}</span>
            </div>
            <div v-if="watchlistTotalPnl !== 0" class="summary-chip pnl">
              <span class="sc-num" :class="watchlistTotalPnl >= 0 ? 'up' : 'down'">
                {{ watchlistTotalPnl >= 0 ? '+' : '' }}{{ formatNum(watchlistTotalPnl) }}
              </span>
              <span class="sc-label">P&amp;L</span>
            </div>
          </div>

          <div v-if="batchMode" class="batch-bar">
            <a-checkbox
              class="batch-all-cb"
              :checked="batchSelectedAll"
              :indeterminate="batchIndeterminate"
              @change="onBatchSelectAll">
              {{ tt('aiAssetAnalysis.batch.selectAll', 'Select All') }}
            </a-checkbox>
            <a-button type="primary" size="small" :disabled="batchSelectedKeys.length === 0" @click="openBatchScheduleModal">
              {{ tt('aiAssetAnalysis.batch.schedule', 'Batch Schedule') }}
              <template v-if="batchSelectedKeys.length > 0"> {{ batchSelectedKeys.length }}</template>
            </a-button>
            <a-button size="small" @click="toggleBatchMode">
              {{ $t('common.cancel') }}
            </a-button>
          </div>

          <div class="watchlist-list">
            <div
              v-for="stock in (watchlist || [])"
              :key="`wl-${stock.market}-${stock.symbol}`"
              class="wl-card"
              :class="{ active: selectedSymbol === `${stock.market}:${stock.symbol}` }"
              @click="selectWatchlistItem(stock)"
            >
              <a-checkbox
                v-if="batchMode"
                class="wl-card-cb"
                :checked="batchSelectedKeys.includes(`${stock.market}:${stock.symbol}`)"
                @change="onBatchItemToggle(stock, $event)"
                @click.stop
              />
              <div class="wl-card-body" :class="{ 'with-cb': batchMode }">
                <div class="wl-row-main">
                  <span class="wl-symbol">{{ stock.symbol }}</span>
                  <span class="wl-market">{{ getMarketName(stock.market) }}</span>
                  <span class="wl-spacer"></span>
                  <template v-if="watchlistPrices[`${stock.market}:${stock.symbol}`]">
                    <span class="wl-price">{{ formatPrice(watchlistPrices[`${stock.market}:${stock.symbol}`].price) }}</span>
                    <span
                      class="wl-change"
                      :class="(watchlistPrices[`${stock.market}:${stock.symbol}`]?.change || 0) >= 0 ? 'up' : 'down'">
                      {{ (watchlistPrices[`${stock.market}:${stock.symbol}`]?.change || 0) >= 0 ? '+' : '' }}{{ formatNum(watchlistPrices[`${stock.market}:${stock.symbol}`]?.change) }}%
                    </span>
                  </template>
                </div>

                <div v-if="positionSummaryMap[`${stock.market}:${stock.symbol}`]" class="wl-row-pnl">
                  <span class="wl-pnl-qty">
                    {{ formatNum(positionSummaryMap[`${stock.market}:${stock.symbol}`].quantity, 4) }}
                    @
                    {{ formatPrice(positionSummaryMap[`${stock.market}:${stock.symbol}`].avgEntry || 0) }}
                  </span>
                  <span
                    class="wl-pnl-val"
                    :class="positionSummaryMap[`${stock.market}:${stock.symbol}`].pnl >= 0 ? 'up' : 'down'">
                    {{ positionSummaryMap[`${stock.market}:${stock.symbol}`].pnl >= 0 ? '+' : '' }}{{ formatNum(positionSummaryMap[`${stock.market}:${stock.symbol}`].pnl || 0) }}
                    ({{ positionSummaryMap[`${stock.market}:${stock.symbol}`].pnlPercent >= 0 ? '+' : '' }}{{ formatNum(positionSummaryMap[`${stock.market}:${stock.symbol}`].pnlPercent || 0) }}%)
                  </span>
                </div>

                <div v-if="getMonitorMeta(stock)" class="wl-row-task">
                  <span
                    class="wl-task-badge"
                    :class="getMonitorMeta(stock).activeCount > 0 ? 'active' : 'paused'"
                    @click.stop="toggleStockMonitor(stock)">
                    <a-icon :type="getMonitorMeta(stock).activeCount > 0 ? 'sync' : 'pause-circle'" :spin="getMonitorMeta(stock).activeCount > 0" />
                    {{ getMonitorMeta(stock).activeCount > 0 ? tt('aiAssetAnalysis.monitor.running', 'Running') : tt('aiAssetAnalysis.monitor.paused', 'Paused') }}
                  </span>
                  <span v-if="getMonitorMeta(stock).nextRunAtText" class="wl-task-next">{{ getMonitorMeta(stock).nextRunAtText }}</span>
                </div>
              </div>

              <div class="wl-card-hover-actions">
                <a-tooltip :title="tt('aiAssetAnalysis.position.quickAdd', 'Quick Add Position')">
                  <span class="wl-hover-btn" @click.stop="openPositionModal(stock)">
                    <a-icon type="wallet" />
                  </span>
                </a-tooltip>
                <a-tooltip :title="tt('aiAssetAnalysis.monitor.quickTask', 'Quick Task')">
                  <span class="wl-hover-btn" @click.stop="openMonitorModal(stock)">
                    <a-icon type="clock-circle" />
                  </span>
                </a-tooltip>
                <span class="wl-hover-btn danger" @click.stop="removeFromWatchlist(stock)">
                  <a-icon type="delete" />
                </span>
              </div>
            </div>

            <div v-if="!watchlist || watchlist.length === 0" class="watchlist-empty">
              <div class="we-icon"><a-icon type="star" /></div>
              <p>{{ $t('dashboard.analysis.empty.noWatchlist') }}</p>
              <a-button type="primary" size="small" @click="showAddStockModal = true">
                <a-icon type="plus" /> {{ $t('dashboard.analysis.watchlist.add') }}
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <a-drawer
      :title="tt('aiAssetAnalysis.tasks.manage', 'Manage Tasks')"
      :visible="showTaskDrawer"
      placement="right"
      :width="420"
      @close="showTaskDrawer = false">
      <div class="task-drawer-head">
        <div class="task-drawer-copy">
          <div class="task-drawer-title">{{ tt('aiAssetAnalysis.tasks.title', 'Watchlist Monitoring') }}</div>
          <div class="task-drawer-desc">{{ tt('aiAssetAnalysis.tasks.desc', 'Review active asset-monitor tasks, run them manually, or edit their schedule.') }}</div>
        </div>
      </div>

      <a-spin :spinning="loadingMonitors">
        <a-empty
          v-if="monitors.length === 0"
          :description="tt('aiAssetAnalysis.tasks.empty', 'No monitoring task yet')"
          :image="false" />

        <div v-else class="task-card-list">
          <div v-for="monitor in monitors" :key="monitor.id" class="task-card">
            <div class="task-card-head">
              <div class="task-card-title">
                <strong>{{ monitor.name }}</strong>
                <a-tag :color="monitor.is_active ? 'green' : 'default'">
                  {{ monitor.is_active ? tt('aiAssetAnalysis.monitor.running', 'Running') : tt('aiAssetAnalysis.monitor.paused', 'Paused') }}
                </a-tag>
              </div>
              <a-switch size="small" :checked="monitor.is_active" @change="toggleMonitorStatus(monitor, $event)" />
            </div>

            <div class="task-card-meta">
              <div class="task-meta-row">
                <span class="label">{{ tt('aiAssetAnalysis.tasks.target', 'Target') }}</span>
                <span class="value">{{ getMonitorTargetText(monitor) }}</span>
              </div>
              <div class="task-meta-row">
                <span class="label">{{ tt('aiAssetAnalysis.tasks.interval', 'Interval') }}</span>
                <span class="value">{{ getIntervalText(monitor.config?.interval_minutes) }}</span>
              </div>
              <div v-if="monitor.last_run_at" class="task-meta-row">
                <span class="label">{{ tt('aiAssetAnalysis.tasks.lastRun', 'Last Run') }}</span>
                <span class="value">{{ formatIsoTime(monitor.last_run_at) }}</span>
              </div>
              <div v-if="monitor.next_run_at" class="task-meta-row">
                <span class="label">{{ tt('aiAssetAnalysis.tasks.nextRun', 'Next Run') }}</span>
                <span class="value">{{ formatIsoTime(monitor.next_run_at) }}</span>
              </div>
            </div>

            <div class="task-card-actions">
              <a-button size="small" @click="runTaskNow(monitor)" :loading="runningMonitorId === monitor.id">
                <a-icon type="play-circle" />
                {{ tt('aiAssetAnalysis.tasks.runNow', 'Run Now') }}
              </a-button>
              <a-button size="small" @click="editMonitorTask(monitor)">
                <a-icon type="edit" />
                {{ $t('common.edit') || 'Edit' }}
              </a-button>
              <a-popconfirm
                :title="tt('aiAssetAnalysis.tasks.deleteConfirm', 'Delete this task?')"
                :ok-text="$t('common.confirm') || 'Confirm'"
                :cancel-text="$t('common.cancel') || 'Cancel'"
                @confirm="deleteMonitorTask(monitor)">
                <a-button size="small" type="danger">
                  <a-icon type="delete" />
                  {{ $t('common.delete') || 'Delete' }}
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </a-spin>
    </a-drawer>

    <a-modal
      :title="tt('aiAssetAnalysis.position.quickAdd', 'Quick Add Position')"
      :visible="showPositionModal"
      :confirmLoading="savingPosition"
      @ok="handleSavePosition"
      @cancel="closePositionModal">
      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="tt('aiAssetAnalysis.position.market', 'Market')">
              <a-input :value="getMarketName(positionDraft.market)" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="tt('aiAssetAnalysis.position.symbol', 'Symbol')">
              <a-input v-model="positionDraft.symbol" disabled />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="tt('aiAssetAnalysis.position.quantity', 'Quantity')">
              <a-input-number v-model="positionDraft.quantity" :min="0.0001" :step="0.1" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="tt('aiAssetAnalysis.position.entryPrice', 'Entry Price')">
              <a-input-number v-model="positionDraft.entry_price" :min="0.0001" :step="0.01" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="tt('aiAssetAnalysis.position.side', 'Side')">
          <a-radio-group v-model="positionDraft.side">
            <a-radio-button value="long">{{ tt('aiAssetAnalysis.position.long', 'Long') }}</a-radio-button>
            <a-radio-button value="short">{{ tt('aiAssetAnalysis.position.short', 'Short') }}</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="tt('aiAssetAnalysis.position.notes', 'Notes')">
          <a-textarea v-model="positionDraft.notes" :rows="3" :placeholder="tt('aiAssetAnalysis.position.notesPlaceholder', 'Optional desk notes for this position.')"/>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      :title="monitorDraft.id ? tt('aiAssetAnalysis.monitor.edit', 'Edit Task') : tt('aiAssetAnalysis.monitor.quickTask', 'Quick Task')"
      :visible="showMonitorModal"
      :confirmLoading="savingMonitor"
      @ok="handleSaveMonitor"
      @cancel="closeMonitorModal">
      <a-form layout="vertical">
        <a-form-item :label="tt('aiAssetAnalysis.monitor.name', 'Task Name')">
          <a-input v-model="monitorDraft.name" :placeholder="tt('aiAssetAnalysis.monitor.namePlaceholder', 'BTC monitor')" />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="tt('aiAssetAnalysis.monitor.market', 'Market')">
              <a-input :value="getMarketName(monitorDraft.market)" disabled />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="tt('aiAssetAnalysis.monitor.symbol', 'Symbol')">
              <a-input v-model="monitorDraft.symbol" disabled />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item :label="tt('aiAssetAnalysis.monitor.interval', 'Run Interval')">
          <a-select v-model="monitorDraft.interval_minutes">
            <a-select-option :value="5">5 {{ tt('aiAssetAnalysis.monitor.minutes', 'minutes') }}</a-select-option>
            <a-select-option :value="15">15 {{ tt('aiAssetAnalysis.monitor.minutes', 'minutes') }}</a-select-option>
            <a-select-option :value="30">30 {{ tt('aiAssetAnalysis.monitor.minutes', 'minutes') }}</a-select-option>
            <a-select-option :value="60">1 {{ tt('aiAssetAnalysis.monitor.hour', 'hour') }}</a-select-option>
            <a-select-option :value="240">4 {{ tt('aiAssetAnalysis.monitor.hours', 'hours') }}</a-select-option>
            <a-select-option :value="1440">24 {{ tt('aiAssetAnalysis.monitor.hours', 'hours') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="tt('aiAssetAnalysis.monitor.channels', 'Notification Channels')">
          <a-checkbox-group v-model="monitorDraft.channels">
            <a-row :gutter="12">
              <a-col :span="8"><a-checkbox value="browser">{{ tt('aiAssetAnalysis.monitor.browser', 'Browser') }}</a-checkbox></a-col>
              <a-col :span="8"><a-checkbox value="email">{{ tt('aiAssetAnalysis.monitor.email', 'Email') }}</a-checkbox></a-col>
              <a-col :span="8"><a-checkbox value="telegram">Telegram</a-checkbox></a-col>
            </a-row>
          </a-checkbox-group>
        </a-form-item>
        <a-form-item :label="tt('aiAssetAnalysis.monitor.prompt', 'Custom Prompt')">
          <a-textarea
            v-model="monitorDraft.prompt"
            :rows="4"
            :placeholder="tt('aiAssetAnalysis.monitor.promptPlaceholder', 'Optional instructions for the analysis task, such as focus on momentum, support/resistance, or macro context.')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      :title="tt('aiAssetAnalysis.batch.schedule', 'Batch Schedule')"
      :visible="showBatchScheduleModal"
      :confirmLoading="savingBatchSchedule"
      @ok="handleBatchSchedule"
      @cancel="closeBatchScheduleModal">
      <a-alert
        type="info"
        show-icon
        style="margin-bottom: 16px;"
        :message="tt('aiAssetAnalysis.batch.selected', 'Selected assets')"
        :description="tt('aiAssetAnalysis.batch.selectedDesc', 'Create or refresh monitoring tasks for the assets currently selected in the watchlist.') + ` (${batchSelectedKeys.length})`" />

      <a-form layout="vertical">
        <a-form-item :label="tt('aiAssetAnalysis.monitor.interval', 'Run Interval')">
          <a-select v-model="batchScheduleDraft.interval_minutes">
            <a-select-option :value="5">5 {{ tt('aiAssetAnalysis.monitor.minutes', 'minutes') }}</a-select-option>
            <a-select-option :value="15">15 {{ tt('aiAssetAnalysis.monitor.minutes', 'minutes') }}</a-select-option>
            <a-select-option :value="30">30 {{ tt('aiAssetAnalysis.monitor.minutes', 'minutes') }}</a-select-option>
            <a-select-option :value="60">1 {{ tt('aiAssetAnalysis.monitor.hour', 'hour') }}</a-select-option>
            <a-select-option :value="240">4 {{ tt('aiAssetAnalysis.monitor.hours', 'hours') }}</a-select-option>
            <a-select-option :value="1440">24 {{ tt('aiAssetAnalysis.monitor.hours', 'hours') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="tt('aiAssetAnalysis.monitor.channels', 'Notification Channels')">
          <a-checkbox-group v-model="batchScheduleDraft.channels">
            <a-row :gutter="12">
              <a-col :span="8"><a-checkbox value="browser">{{ tt('aiAssetAnalysis.monitor.browser', 'Browser') }}</a-checkbox></a-col>
              <a-col :span="8"><a-checkbox value="email">{{ tt('aiAssetAnalysis.monitor.email', 'Email') }}</a-checkbox></a-col>
              <a-col :span="8"><a-checkbox value="telegram">Telegram</a-checkbox></a-col>
            </a-row>
          </a-checkbox-group>
        </a-form-item>
        <a-form-item :label="tt('aiAssetAnalysis.monitor.prompt', 'Custom Prompt')">
          <a-textarea
            v-model="batchScheduleDraft.prompt"
            :rows="4"
            :placeholder="tt('aiAssetAnalysis.monitor.promptPlaceholder', 'Optional instructions for the analysis task, such as focus on momentum, support/resistance, or macro context.')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- Add-symbol modal -->
    <a-modal
      :title="$t('dashboard.analysis.modal.addStock.title')"
      :visible="showAddStockModal"
      @ok="handleAddStock"
      @cancel="handleCloseAddStockModal"
      :confirmLoading="addingStock"
      width="600px"
      :okText="$t('dashboard.analysis.modal.addStock.confirm')"
      :cancelText="$t('dashboard.analysis.modal.addStock.cancel')"
    >
      <div class="add-stock-modal-content">
        <!-- Tab navigation -->
        <a-tabs v-model="selectedMarketTab" @change="handleMarketTabChange" class="market-tabs">
          <a-tab-pane
            v-for="marketType in marketTypes"
            :key="marketType.value"
            :tab="$t(marketType.i18nKey || `dashboard.analysis.market.${marketType.value}`)"
          >
          </a-tab-pane>
        </a-tabs>

        <!-- Search / direct input -->
        <div class="symbol-search-section">
          <a-input-search
            v-model="symbolSearchKeyword"
            :placeholder="$t('dashboard.analysis.modal.addStock.searchOrInputPlaceholder')"
            @search="handleSearchOrInput"
            @change="handleSymbolSearchInput"
            :loading="searchingSymbols"
            size="large"
            allow-clear
          >
            <a-button slot="enterButton" type="primary" icon="search">
              {{ $t('dashboard.analysis.modal.addStock.search') }}
            </a-button>
          </a-input-search>
        </div>

        <!-- Search results -->
        <div v-if="symbolSearchResults.length > 0" class="search-results-section">
          <div class="section-title">
            <a-icon type="search" style="margin-right: 4px;" />
            {{ $t('dashboard.analysis.modal.addStock.searchResults') }}
          </div>
          <a-list
            :data-source="symbolSearchResults"
            :loading="searchingSymbols"
            size="small"
            class="symbol-list"
          >
            <a-list-item slot="renderItem" slot-scope="item" class="symbol-list-item" @click="selectSymbol(item)">
              <a-list-item-meta>
                <template slot="title">
                  <div class="symbol-item-content">
                    <span class="symbol-code">{{ item.symbol }}</span>
                    <span class="symbol-name">{{ item.name }}</span>
                    <a-tag v-if="item.exchange" size="small" color="blue" style="margin-left: 8px;">
                      {{ item.exchange }}
                    </a-tag>
                  </div>
                </template>
              </a-list-item-meta>
            </a-list-item>
          </a-list>
        </div>

        <!-- Popular symbols -->
        <div class="hot-symbols-section">
          <div class="section-title">
            <a-icon type="fire" style="color: #ff4d4f; margin-right: 4px;" />
            {{ $t('dashboard.analysis.modal.addStock.hotSymbols') }}
          </div>
          <a-spin :spinning="loadingHotSymbols">
            <a-list
              v-if="hotSymbols.length > 0"
              :data-source="hotSymbols"
              size="small"
              class="symbol-list"
            >
              <a-list-item slot="renderItem" slot-scope="item" class="symbol-list-item" @click="selectSymbol(item)">
                <a-list-item-meta>
                  <template slot="title">
                    <div class="symbol-item-content">
                      <span class="symbol-code">{{ item.symbol }}</span>
                      <span class="symbol-name">{{ item.name }}</span>
                      <a-tag v-if="item.exchange" size="small" color="orange" style="margin-left: 8px;">
                        {{ item.exchange }}
                      </a-tag>
                    </div>
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </a-list>
            <a-empty v-else :description="$t('dashboard.analysis.modal.addStock.noHotSymbols')" :image="false" />
          </a-spin>
        </div>

        <!-- Selected symbol summary -->
        <div v-if="selectedSymbolForAdd" class="selected-symbol-section">
          <a-alert
            :message="$t('dashboard.analysis.modal.addStock.selectedSymbol')"
            type="info"
            show-icon
            closable
            @close="selectedSymbolForAdd = null"
          >
            <template slot="description">
              <div class="selected-symbol-info">
                <a-tag :color="getMarketColor(selectedSymbolForAdd.market)" style="margin-right: 8px;">
                  {{ $t(`dashboard.analysis.market.${selectedSymbolForAdd.market}`) }}
                </a-tag>
                <strong>{{ selectedSymbolForAdd.symbol }}</strong>
                <span v-if="selectedSymbolForAdd.name" style="color: #999; margin-left: 8px;">{{ selectedSymbolForAdd.name }}</span>
              </div>
            </template>
          </a-alert>
        </div>
      </div>
    </a-modal>

    <!-- History modal -->
    <a-modal
      :title="$t('dashboard.analysis.modal.history.title')"
      :visible="showHistoryModal"
      @cancel="showHistoryModal = false"
      :footer="null"
      width="800px"
      :bodyStyle="{ maxHeight: '60vh', overflowY: 'auto' }"
    >
      <a-spin :spinning="historyLoading">
        <a-list
          :data-source="historyList"
          :pagination="{
            current: historyPage,
            pageSize: historyPageSize,
            total: historyTotal,
            onChange: (page) => { historyPage = page; loadHistoryList() },
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
            onShowSizeChange: (current, size) => { historyPageSize = size; historyPage = 1; loadHistoryList() }
          }"
        >
          <a-list-item slot="renderItem" slot-scope="item">
            <a-list-item-meta>
              <template slot="title">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <div>
                    <a-tag :color="getMarketColor(item.market)" style="margin-right: 8px;">
                      {{ getMarketName(item.market) }}
                    </a-tag>
                    <strong>{{ item.symbol }}</strong>
                    <a-tag
                      :color="item.decision === 'BUY' ? 'green' : (item.decision === 'SELL' ? 'red' : 'blue')"
                      style="margin-left: 12px;"
                    >
                      {{ item.decision }}
                    </a-tag>
                    <a-tag
                      :color="getStatusColor(item.status || 'completed')"
                      style="margin-left: 8px;"
                    >
                      {{ getStatusText(item.status || 'completed') }}
                    </a-tag>
                    <span style="color: #999; margin-left: 8px; font-size: 12px;">
                      {{ $t('fastAnalysis.confidence') }}: {{ item.confidence }}%
                    </span>
                  </div>
                  <div>
                    <a-button
                      type="link"
                      size="small"
                      icon="eye"
                      @click="viewHistoryResult(item)"
                    >
                      {{ $t('dashboard.analysis.modal.history.viewResult') }}
                    </a-button>
                    <a-popconfirm
                      :title="$t('dashboard.analysis.modal.history.deleteConfirm')"
                      :ok-text="$t('common.confirm')"
                      :cancel-text="$t('common.cancel')"
                      @confirm="deleteHistoryItem(item)"
                    >
                      <a-button
                        type="link"
                        size="small"
                        icon="delete"
                        style="color: #ff4d4f;"
                      >
                        {{ $t('dashboard.analysis.modal.history.delete') }}
                      </a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </template>
              <template slot="description">
                <div style="color: #666; font-size: 12px;">
                  <span v-if="item.price">${{ formatNumber(item.price) }}</span>
                  <span v-if="item.summary" style="margin-left: 8px;">{{ item.summary.substring(0, 80) }}{{ item.summary.length > 80 ? '...' : '' }}</span>
                </div>
                <div v-if="item.error_message" style="color: #ff4d4f; font-size: 12px; margin-top: 4px;">
                  {{ item.error_message }}
                </div>
                <div v-if="item.created_at" style="color: #999; font-size: 12px; margin-top: 4px;">
                  {{ formatIsoTime(item.created_at) }}
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </a-list>
        <a-empty v-if="!historyLoading && historyList.length === 0" :description="$t('dashboard.analysis.empty.noHistory')" />
      </a-spin>
    </a-modal>
  </div>
</template>

<script>
import { mapGetters, mapState } from 'vuex'
import { getUserInfo } from '@/api/login'
import { getWatchlist, addWatchlist, removeWatchlist, getWatchlistPrices, getMarketTypes, searchSymbols, getHotSymbols } from '@/api/market'
import { fastAnalyze, getAllAnalysisHistory, deleteAnalysisHistory } from '@/api/fast-analysis'
import { getMarketSentiment, getMarketOverview, getMarketHeatmap, getEconomicCalendar } from '@/api/global-market'
import { addMonitor, addPosition, deleteMonitor, getMonitors, getPositions, runMonitor, updateMonitor } from '@/api/portfolio'
import { getNotificationSettings } from '@/api/user'
import FastAnalysisReport from './components/FastAnalysisReport.vue'

export default {
  name: 'Analysis',
  props: {
    embedded: {
      type: Boolean,
      default: false
    },
    presetSymbol: {
      type: String,
      default: ''
    },
    autoAnalyzeSignal: {
      type: Number,
      default: 0
    }
  },
  components: {
    FastAnalysisReport
  },
  data () {
    return {
      loadingMarket: false,
      heatmapType: 'crypto',
      marketData: {
        fearGreed: null,
        vix: null,
        dxy: null,
        indices: [],
        heatmap: { crypto: [], commodities: [], sectors: [], forex: [] },
        calendar: []
      },
      // Independent progressive-loading state.
      loadingSentiment: false,
      loadingIndices: false,
      loadingHeatmap: false,
      loadingCalendar: false,
      watchlistPriceTimer: null,
      watchlistPrices: {},
      localUserInfo: {},
      loadingUserInfo: false,
      userId: 1,
      watchlist: [],
      loadingWatchlist: false,
      showAddStockModal: false,
      addingStock: false,
      selectedSymbol: undefined,
      analyzing: false,
      analysisResult: null,
      analysisError: null,
      analysisErrorTone: 'error',
      showHistoryModal: false,
      historyList: [],
      historyLoading: false,
      historyPage: 1,
      historyPageSize: 20,
      historyTotal: 0,
      taskPollingTimer: null,
      currentTaskId: null,
      taskPollingStartedAt: 0,
      marketTypes: [],
      selectedMarketTab: '',
      symbolSearchKeyword: '',
      symbolSearchResults: [],
      searchingSymbols: false,
      hotSymbols: [],
      loadingHotSymbols: false,
      selectedSymbolForAdd: null,
      searchTimer: null,
      hasSearched: false,
      positions: [],
      monitors: [],
      loadingPositions: false,
      loadingMonitors: false,
      showTaskDrawer: false,
      showPositionModal: false,
      showMonitorModal: false,
      showBatchScheduleModal: false,
      savingPosition: false,
      savingMonitor: false,
      savingBatchSchedule: false,
      runningMonitorId: null,
      batchMode: false,
      batchSelectedKeys: [],
      positionDraft: {
        market: '',
        symbol: '',
        name: '',
        side: 'long',
        quantity: 1,
        entry_price: 0,
        notes: '',
        group_name: ''
      },
      monitorDraft: {
        id: null,
        name: '',
        market: '',
        symbol: '',
        interval_minutes: 60,
        prompt: '',
        channels: ['browser'],
        is_active: true
      },
      batchScheduleDraft: {
        interval_minutes: 60,
        prompt: '',
        channels: ['browser']
      },
      userNotificationSettings: {
        default_channels: ['browser'],
        telegram_bot_token: '',
        telegram_chat_id: '',
        email: '',
        phone: '',
        discord_webhook: '',
        webhook_url: '',
        webhook_token: ''
      }
    }
  },
  computed: {
    ...mapGetters(['userInfo']),
    ...mapState({
      navTheme: state => state.app.theme,
      primaryColor: state => state.app.color || '#1890ff'
    }),
    isDarkTheme () {
      return this.navTheme === 'dark' || this.navTheme === 'realdark'
    },
    isZhLocale () {
      return this.$i18n.locale === 'zh-CN'
    },
    currentHeatmap () {
      return this.marketData.heatmap[this.heatmapType] || []
    },
    watchlistQuotedCount () {
      return (this.watchlist || []).filter(item => {
        return !!this.watchlistPrices[`${item.market}:${item.symbol}`]
      }).length
    },
    watchlistPositiveCount () {
      return (this.watchlist || []).filter(item => {
        const change = this.watchlistPrices[`${item.market}:${item.symbol}`]?.change || 0
        return change >= 0
      }).length
    },
    watchlistNegativeCount () {
      return Math.max(0, (this.watchlist || []).length - this.watchlistPositiveCount)
    },
    positionSummaryMap () {
      const summary = {}
      ;(this.positions || []).forEach(position => {
        const key = `${position.market}:${position.symbol}`
        if (!summary[key]) {
          summary[key] = {
            quantity: 0,
            totalCost: 0,
            avgEntry: 0,
            pnl: 0,
            pnlPercent: 0
          }
        }
        summary[key].quantity += Number(position.quantity || 0)
        summary[key].totalCost += Number(position.entry_price || 0) * Number(position.quantity || 0)
        summary[key].pnl += Number(position.pnl || 0)
      })

      Object.keys(summary).forEach(key => {
        const item = summary[key]
        item.avgEntry = item.quantity > 0 ? item.totalCost / item.quantity : 0
        item.pnlPercent = item.totalCost > 0 ? (item.pnl / item.totalCost) * 100 : 0
      })
      return summary
    },
    watchlistPositionCount () {
      return (this.watchlist || []).filter(item => !!this.positionSummaryMap[`${item.market}:${item.symbol}`]).length
    },
    watchlistTaskCount () {
      return (this.watchlist || []).filter(item => !!this.getMonitorMeta(item)).length
    },
    watchlistTotalPnl () {
      return (this.watchlist || []).reduce((sum, item) => {
        const summary = this.positionSummaryMap[`${item.market}:${item.symbol}`]
        return sum + Number(summary?.pnl || 0)
      }, 0)
    },
    batchSelectedAll () {
      return this.watchlist.length > 0 && this.batchSelectedKeys.length === this.watchlist.length
    },
    batchIndeterminate () {
      return this.batchSelectedKeys.length > 0 && this.batchSelectedKeys.length < this.watchlist.length
    },
    storeUserInfo () {
      return this.userInfo || {}
    },
    mergedUserInfo () {
      return this.localUserInfo && this.localUserInfo.email ? this.localUserInfo : this.storeUserInfo
    }
  },
  created () {
    this.loadUserInfo()
    this.loadMarketTypes()
    this.loadWatchlist()
    this.loadMarketData()
    this.loadPortfolioContext()
  },
  mounted () {
    this.startWatchlistPriceRefresh()
  },
  beforeDestroy () {
    if (this.watchlistPriceTimer) {
      clearInterval(this.watchlistPriceTimer)
    }
    this.stopTaskPolling()
    if (this.searchTimer) {
      clearTimeout(this.searchTimer)
    }
  },
  methods: {
    stopTaskPolling () {
      if (this.taskPollingTimer) {
        clearInterval(this.taskPollingTimer)
        this.taskPollingTimer = null
      }
      this.currentTaskId = null
      this.taskPollingStartedAt = 0
    },
    async pollTaskResult () {
      if (!this.currentTaskId) return

      try {
        const res = await getAllAnalysisHistory({ page: 1, pagesize: 50 })
        if (!res || res.code !== 1 || !res.data) return

        const list = res.data.list || []
        const target = list.find(item => Number(item.id) === Number(this.currentTaskId))
        if (!target) return

        const status = String(target.status || '').toLowerCase()
        if (status === 'completed') {
          this.analysisError = null
          this.analysisErrorTone = 'error'
          if (target.full_result) {
            this.analysisResult = target.full_result
            this.selectedSymbol = `${target.market}:${target.symbol}`
            this.showHistoryModal = false
          } else {
            await this.viewHistoryResult(target)
          }
          this.$message.success(this.$t('dashboard.analysis.message.analysisComplete'))
          await this.refreshUserInfoFromServer()
          this.analyzing = false
          this.stopTaskPolling()
          return
        }

        if (status === 'failed') {
          this.analysisError = target.error_message || this.$t('dashboard.analysis.message.analysisFailed')
          this.analysisErrorTone = 'error'
          this.$message.error(this.analysisError)
          await this.refreshUserInfoFromServer()
          this.analyzing = false
          this.stopTaskPolling()
          return
        }

        if (Date.now() - this.taskPollingStartedAt > 180000) {
          this.$message.warning(this.$t('fastAnalysis.analysisStillProcessing'))
          this.analyzing = false
          this.stopTaskPolling()
        }
      } catch (error) {
      }
    },
    async startTaskPolling (taskId) {
      this.stopTaskPolling()
      this.currentTaskId = Number(taskId)
      this.taskPollingStartedAt = Date.now()
      await this.pollTaskResult()
      if (!this.currentTaskId || !this.analyzing) {
        return
      }
      this.taskPollingTimer = setInterval(() => {
        this.pollTaskResult()
      }, 2500)
    },
    tt (key, fallback, params) {
      const translated = this.$t(key, params)
      return translated !== key ? translated : fallback
    },
    createEmptyPositionDraft () {
      return {
        market: '',
        symbol: '',
        name: '',
        side: 'long',
        quantity: 1,
        entry_price: 0,
        notes: '',
        group_name: ''
      }
    },
    createEmptyMonitorDraft () {
      return {
        id: null,
        name: '',
        market: '',
        symbol: '',
        interval_minutes: 60,
        prompt: '',
        channels: [...(this.userNotificationSettings.default_channels || ['browser'])],
        is_active: true
      }
    },
    createEmptyBatchDraft () {
      return {
        interval_minutes: 60,
        prompt: '',
        channels: [...(this.userNotificationSettings.default_channels || ['browser'])]
      }
    },
    async loadPortfolioContext () {
      await Promise.all([
        this.loadPositions(),
        this.loadMonitors(),
        this.loadUserNotificationSettings()
      ])
    },
    async loadUserNotificationSettings () {
      try {
        const res = await getNotificationSettings()
        if (res?.code === 1 && res?.data) {
          this.userNotificationSettings = {
            default_channels: res.data.default_channels || ['browser'],
            telegram_bot_token: res.data.telegram_bot_token || '',
            telegram_chat_id: res.data.telegram_chat_id || '',
            email: res.data.email || '',
            phone: res.data.phone || '',
            discord_webhook: res.data.discord_webhook || '',
            webhook_url: res.data.webhook_url || '',
            webhook_token: res.data.webhook_token || ''
          }
          if (!this.showMonitorModal) {
            this.monitorDraft.channels = [...(this.userNotificationSettings.default_channels || ['browser'])]
          }
          if (!this.showBatchScheduleModal) {
            this.batchScheduleDraft.channels = [...(this.userNotificationSettings.default_channels || ['browser'])]
          }
        }
      } catch (e) {
        // Fall back to browser-only notifications when the profile settings endpoint is unavailable.
      }
    },
    async loadPositions () {
      this.loadingPositions = true
      try {
        const res = await getPositions()
        if (res?.code === 1) {
          this.positions = res.data || []
        }
      } catch (e) {
        console.error('Load positions failed:', e)
      } finally {
        this.loadingPositions = false
      }
    },
    async loadMonitors () {
      this.loadingMonitors = true
      try {
        const res = await getMonitors()
        if (res?.code === 1) {
          this.monitors = res.data || []
        }
      } catch (e) {
        console.error('Load monitors failed:', e)
      } finally {
        this.loadingMonitors = false
      }
    },
    normalizeChannels (channels) {
      return Array.isArray(channels) && channels.length > 0 ? channels : ['browser']
    },
    buildNotificationTargets () {
      return {
        telegram: this.userNotificationSettings.telegram_chat_id || '',
        telegram_bot_token: this.userNotificationSettings.telegram_bot_token || '',
        email: this.userNotificationSettings.email || '',
        phone: this.userNotificationSettings.phone || '',
        discord: this.userNotificationSettings.discord_webhook || '',
        webhook: this.userNotificationSettings.webhook_url || '',
        webhook_token: this.userNotificationSettings.webhook_token || ''
      }
    },
    getMatchedPositions (stock) {
      if (!stock) return []
      return (this.positions || []).filter(position => {
        return position.market === stock.market && String(position.symbol || '').toUpperCase() === String(stock.symbol || '').toUpperCase()
      })
    },
    getMonitorMeta (stock) {
      if (!stock) return null
      const positionIds = this.getMatchedPositions(stock).map(position => position.id)
      const matched = (this.monitors || []).filter(monitor => {
        const config = monitor.config || {}
        const monitorSymbol = String(config.symbol || '').toUpperCase()
        const monitorMarket = config.market || ''
        const monitorPositionIds = Array.isArray(monitor.position_ids) ? monitor.position_ids : []
        return (monitorSymbol === String(stock.symbol || '').toUpperCase() && (!monitorMarket || monitorMarket === stock.market)) ||
          monitorPositionIds.some(id => positionIds.includes(id))
      })

      if (matched.length === 0) return null

      const activeCount = matched.filter(item => item.is_active).length
      const nextRunAt = matched
        .filter(item => item.is_active && item.next_run_at)
        .map(item => item.next_run_at)
        .sort()[0]

      return {
        list: matched,
        first: matched[0],
        activeCount,
        pausedCount: matched.length - activeCount,
        nextRunAtText: nextRunAt ? this.formatIsoTime(nextRunAt) : ''
      }
    },
    getMonitorTargetText (monitor) {
      const config = monitor?.config || {}
      if (config.market && config.symbol) {
        return `${this.getMarketName(config.market)}:${config.symbol}`
      }
      const positionIds = Array.isArray(monitor?.position_ids) ? monitor.position_ids : []
      if (positionIds.length > 0) {
        return this.tt('aiAssetAnalysis.tasks.positionScope', `${positionIds.length} positions`)
      }
      return this.tt('aiAssetAnalysis.tasks.unknownTarget', 'Unknown target')
    },
    getIntervalText (minutes) {
      const value = Number(minutes || 0)
      if (!value) return '-'
      if (value < 60) {
        return `${value} ${this.tt('aiAssetAnalysis.monitor.minutes', 'minutes')}`
      }
      const hours = value / 60
      return `${hours} ${hours > 1 ? this.tt('aiAssetAnalysis.monitor.hours', 'hours') : this.tt('aiAssetAnalysis.monitor.hour', 'hour')}`
    },
    filterSymbolOption (input, option) {
      const value = option.componentOptions?.propsData?.value || ''
      if (value === '__add_stock_option__') return true
      return value.toLowerCase().includes(input.toLowerCase())
    },
    formatCreditNum (value) {
      if (value === undefined || value === null || value === '') return '--'
      const num = Number(value)
      if (Number.isNaN(num)) return String(value)
      return Number.isInteger(num) ? String(num) : num.toFixed(2)
    },
    async refreshUserInfoFromServer () {
      try {
        const res = await getUserInfo()
        if (res && res.code === 1 && res.data) {
          this.localUserInfo = res.data
          this.userId = res.data.id
          this.$store.commit('SET_INFO', res.data)
        }
      } catch (error) {
      }
    },
    _displayDateTimeLocaleOptions () {
      const timezone = String((this.storeUserInfo && this.storeUserInfo.timezone) || '').trim()
      const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }
      if (!timezone) return options
      try {
        Intl.DateTimeFormat(undefined, { timeZone: timezone }).format(new Date())
        return {
          ...options,
          timeZone: timezone
        }
      } catch (error) {
        return options
      }
    },
    _parseInstantForDisplay (value) {
      let raw = String(value || '').trim()
      if (!raw) return null

      const hasTimezone = /[zZ]$/.test(raw) || /[+-]\d{2}:?\d{2}$/.test(raw)
      if (!hasTimezone) {
        const normalized = raw.replace(' ', 'T')
        raw = normalized.endsWith('Z') ? normalized : `${normalized}Z`
      }

      const date = new Date(raw)
      return Number.isNaN(date.getTime()) ? null : date
    },
    handleSymbolChange (value) {
      if (value === '__add_stock_option__') {
        this.showAddStockModal = true
        this.$nextTick(() => {
          this.selectedSymbol = undefined
        })
        return
      }
      this.selectedSymbol = value
      // Clear previous result when symbol changes
      this.analysisResult = null
      this.analysisError = null
      this.analysisErrorTone = 'error'
    },
    selectWatchlistItem (stock) {
      this.selectedSymbol = `${stock.market}:${stock.symbol}`
      this.analysisResult = null
      this.analysisError = null
      this.analysisErrorTone = 'error'
    },
    async loadMarketData () {
      // Progressive loading lets each data block render as soon as it is ready.
      this.loadingMarket = true

      // 1. Load sentiment metrics (fear/greed, VIX, DXY) first.
      this.loadSentimentData()

      // 2. Load global indices next.
      this.loadIndicesData()

      // 3. Load heatmap data.
      this.loadHeatmapData()

      // 4. Load the economic calendar.
      this.loadCalendarData()
    },
    async loadSentimentData () {
      this.loadingSentiment = true
      try {
        const res = await getMarketSentiment()
        if (res?.code === 1 && res?.data) {
          this.marketData.fearGreed = res.data.fear_greed?.value || null
          this.marketData.vix = res.data.vix?.value || null
          this.marketData.dxy = res.data.dxy?.value || null
        }
      } catch (e) {
        console.error('Load sentiment failed:', e)
      } finally {
        this.loadingSentiment = false
        this.checkAllLoaded()
      }
    },
    async loadIndicesData () {
      this.loadingIndices = true
      try {
        const res = await getMarketOverview()
        if (res?.code === 1 && res?.data) {
          this.marketData.indices = res.data.indices || []
        }
      } catch (e) {
        console.error('Load indices failed:', e)
      } finally {
        this.loadingIndices = false
        this.checkAllLoaded()
      }
    },
    async loadHeatmapData () {
      this.loadingHeatmap = true
      try {
        const res = await getMarketHeatmap()
        if (res?.code === 1 && res?.data) {
          this.marketData.heatmap = {
            crypto: res.data.crypto || [],
            commodities: res.data.commodities || [],
            sectors: res.data.sectors || [],
            forex: res.data.forex || []
          }
        }
      } catch (e) {
        console.error('Load heatmap failed:', e)
      } finally {
        this.loadingHeatmap = false
        this.checkAllLoaded()
      }
    },
    async loadCalendarData () {
      this.loadingCalendar = true
      try {
        const res = await getEconomicCalendar()
        if (res?.code === 1) {
          this.marketData.calendar = res.data || []
        }
      } catch (e) {
        console.error('Load calendar failed:', e)
      } finally {
        this.loadingCalendar = false
        this.checkAllLoaded()
      }
    },
    checkAllLoaded () {
      // Clear the global loading state once every panel has finished.
      if (!this.loadingSentiment && !this.loadingIndices && !this.loadingHeatmap && !this.loadingCalendar) {
        this.loadingMarket = false
      }
    },
    getFearGreedClass (val) {
      if (!val) return ''
      if (val <= 25) return 'extreme-fear'
      if (val <= 45) return 'fear'
      if (val <= 55) return 'neutral'
      if (val <= 75) return 'greed'
      return 'extreme-greed'
    },
    getVixLevel (val) {
      if (!val) return ''
      if (val < 15) return 'low'
      if (val < 25) return 'medium'
      return 'high'
    },
    formatNum (num, digits = 2) {
      if (num === undefined || num === null || isNaN(num)) return '--'
      return Number(num).toFixed(digits)
    },
    getHeatmapStyle (value) {
      const v = parseFloat(value) || 0
      const intensity = Math.min(Math.abs(v) / 5, 1)
      if (v >= 0) {
        return { background: `rgba(34, 197, 94, ${0.15 + intensity * 0.6})`, color: v > 2 ? '#fff' : '#166534' }
      } else {
        return { background: `rgba(239, 68, 68, ${0.15 + intensity * 0.6})`, color: v < -2 ? '#fff' : '#991b1b' }
      }
    },
    getCountryFlag (country) {
      const flags = { US: '🇺🇸', CN: '🇨🇳', EU: '🇪🇺', JP: '🇯🇵', UK: '🇬🇧', DE: '🇩🇪', AU: '🇦🇺', CA: '🇨🇦' }
      return flags[country] || '🌍'
    },
    formatCalendarDate (dateStr) {
      if (!dateStr) return ''
      try {
        const date = new Date(dateStr)
        const today = new Date()
        const tomorrow = new Date(today)
        tomorrow.setDate(tomorrow.getDate() + 1)

        // Highlight today and tomorrow with short labels.
        if (date.toDateString() === today.toDateString()) {
          return 'Today'
        }
        if (date.toDateString() === tomorrow.toDateString()) {
          return 'Tomorrow'
        }

        // Fall back to a compact month/day display.
        const month = date.getMonth() + 1
        const day = date.getDate()
        return `${month}/${day}`
      } catch (e) {
        return dateStr
      }
    },
    formatPrice (price) {
      if (!price) return '--'
      if (price >= 10000) return (price / 1000).toFixed(1) + 'K'
      if (price >= 1000) return price.toFixed(0)
      return price.toFixed(2)
    },
    formatHeatmapPrice (price) {
      if (!price) return ''
      if (price >= 10000) return '$' + (price / 1000).toFixed(1) + 'K'
      if (price >= 1000) return '$' + price.toFixed(0)
      if (price >= 1) return '$' + price.toFixed(2)
      return '$' + price.toFixed(4)
    },
    getHeatmapName (item) {
      // Sectors, commodities, and forex use locale-specific labels.
      if (this.heatmapType === 'sectors' || this.heatmapType === 'commodities' || this.heatmapType === 'forex') {
        return this.isZhLocale ? (item.name_cn || item.name) : (item.name_en || item.name)
      }
      return item.name
    },
    getImpactClass (evt) {
      return evt.actual_impact || evt.expected_impact || 'neutral'
    },
    getMarketColor (market) {
      const colors = {
        'USStock': 'green',
        'Crypto': 'purple',
        'Forex': 'gold',
        'Futures': 'cyan'
      }
      return colors[market] || 'default'
    },
    getCurrencySymbol (market) {
      return '$'
    },
    async startFastAnalysis () {
      if (this.analyzing) return
      if (!this.selectedSymbol) {
        this.$message.warning(this.$t('dashboard.analysis.message.selectSymbol'))
        return
      }

      this.analyzing = true
      this.analysisError = null
      this.analysisErrorTone = 'error'

      const [market, symbol] = this.selectedSymbol.split(':')
      const language = this.$store.getters.lang || 'en-US'
      let pendingAsyncTask = false

      try {
        const res = await fastAnalyze({
          market,
          symbol,
          language,
          timeframe: '1D',
          async_submit: true
        })

        if (!res || res.code !== 1 || !res.data) {
          throw new Error(res?.msg || 'Analysis failed')
        }

        if (res.data.status === 'processing') {
          pendingAsyncTask = true
          const remaining = res.data.remaining_credits
          if (remaining !== undefined && remaining !== null) {
            this.$message.success(this.$t('fastAnalysis.analysisSubmittedWithCredits', {
              remaining: this.formatCreditNum(remaining)
            }))
          } else {
            this.$message.success(this.$t('fastAnalysis.analysisSubmitted'))
          }
          await this.startTaskPolling(res.data.task_id)
        } else {
          const result = { ...res.data }
          delete result.credits_charged
          delete result.remaining_credits
          this.analysisResult = result

          const remaining = res.data.remaining_credits
          if (remaining !== undefined && remaining !== null) {
            this.$message.success(this.$t('fastAnalysis.analysisCompleteWithCredits', {
              remaining: this.formatCreditNum(remaining)
            }))
          } else {
            this.$message.success(this.$t('dashboard.analysis.message.analysisComplete'))
          }
        }
        await this.refreshUserInfoFromServer()
      } catch (error) {
        console.error('Fast analysis failed:', error)
        const status = error?.response?.status
        const responseData = error?.response?.data || {}
        const message = responseData?.msg
        const data = responseData?.data

        if (status === 429 && data?.in_progress) {
          this.analysisErrorTone = 'warning'
          this.analysisError = this.$t('fastAnalysis.analysisInProgress')
          this.$message.warning(this.analysisError)
        } else if (status === 400 && message === 'Insufficient credits') {
          this.analysisError = this.$t('fastAnalysis.insufficientCreditsDetail', {
            required: this.formatCreditNum(data?.required),
            current: this.formatCreditNum(data?.current),
            shortage: this.formatCreditNum(data?.shortage)
          })
          this.$message.error(this.analysisError)
        } else {
          this.analysisError = message || error?.message || this.$t('dashboard.analysis.message.analysisFailed')
          this.$message.error(this.analysisError)
        }
      } finally {
        if (!pendingAsyncTask) {
          this.analyzing = false
        }
      }
    },
    async loadHistoryList () {
      this.historyLoading = true
      try {
        const res = await getAllAnalysisHistory({
          page: this.historyPage,
          pagesize: this.historyPageSize
        })

        if (res && res.code === 1 && res.data) {
          this.historyList = res.data.list || []
          this.historyTotal = res.data.total || 0
        }
      } catch (error) {
        this.$message.error(this.$t('dashboard.analysis.message.loadHistoryFailed') || 'Failed to load history')
      } finally {
        this.historyLoading = false
      }
    },
    async viewHistoryResult (item) {
      if (String(item.status || '').toLowerCase() === 'processing') {
        this.$message.info(this.$t('fastAnalysis.analysisStillProcessing'))
        return
      }

      if (item.full_result) {
        this.analysisError = null
        this.analysisErrorTone = 'error'
        this.analysisResult = item.full_result
        this.selectedSymbol = `${item.market}:${item.symbol}`
        this.showHistoryModal = false
        return
      }

      const price = Number(item.price) || 0
      const decision = String(item.decision || 'HOLD').toUpperCase()
      let stopLoss = null
      let takeProfit = null

      if (price > 0) {
        if (decision === 'SELL') {
          stopLoss = price * 1.05
          takeProfit = price * 0.95
        } else if (decision === 'BUY') {
          stopLoss = price * 0.95
          takeProfit = price * 1.05
        }
      }

      this.analysisError = null
      this.analysisErrorTone = 'error'
      this.analysisResult = {
        decision: item.decision,
        confidence: item.confidence,
        summary: item.summary,
        market_data: {
          current_price: item.price,
          change_24h: 0
        },
        trading_plan: {
          entry_price: item.price,
          stop_loss: stopLoss,
          take_profit: takeProfit
        },
        scores: item.scores || {},
        reasons: item.reasons || [],
        risks: [],
        indicators: item.indicators || {},
        memory_id: item.id,
        analysis_time_ms: 0
      }
      this.selectedSymbol = `${item.market}:${item.symbol}`
      this.showHistoryModal = false
    },
    async deleteHistoryItem (item) {
      try {
        const res = await deleteAnalysisHistory(item.id)
        if (res && res.code === 1) {
          this.$message.success(this.$t('dashboard.analysis.message.deleteSuccess'))
          this.loadHistoryList()
        } else {
          this.$message.error(res?.msg || this.$t('dashboard.analysis.message.deleteFailed'))
        }
      } catch (error) {
        this.$message.error(this.$t('dashboard.analysis.message.deleteFailed'))
      }
    },
    formatTime (timestamp) {
      if (!timestamp) return '-'
      const date = new Date(timestamp * 1000)
      return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString(undefined, this._displayDateTimeLocaleOptions())
    },
    formatIsoTime (isoString) {
      const date = this._parseInstantForDisplay(isoString)
      return date ? date.toLocaleString(undefined, this._displayDateTimeLocaleOptions()) : '-'
    },
    getStatusColor (status) {
      const colors = {
        'pending': 'orange',
        'processing': 'blue',
        'completed': 'green',
        'failed': 'red'
      }
      return colors[status] || 'default'
    },
    getStatusText (status) {
      const statusMap = {
        'pending': 'dashboard.analysis.status.pending',
        'processing': 'dashboard.analysis.status.processing',
        'completed': 'dashboard.analysis.status.completed',
        'failed': 'dashboard.analysis.status.failed'
      }
      const key = statusMap[status]
      return key ? this.$t(key) : status
    },
    async loadUserInfo () {
      this.loadingUserInfo = true
      try {
        if (this.storeUserInfo && this.storeUserInfo.email) {
          this.localUserInfo = this.storeUserInfo
          this.userId = this.storeUserInfo.id
          this.loadingUserInfo = false
          this.loadWatchlist()
          return
        }
        const res = await getUserInfo()
        if (res && res.code === 1 && res.data) {
          this.localUserInfo = res.data
          this.userId = res.data.id
          this.$store.commit('SET_INFO', res.data)
          this.loadWatchlist()
        }
      } catch (error) {
        // Silent fail
      } finally {
        this.loadingUserInfo = false
      }
    },
    async loadWatchlist () {
      if (!this.userId) return
      this.loadingWatchlist = true
      try {
        const res = await getWatchlist({ userid: this.userId })
        if (res && res.code === 1 && res.data) {
          this.watchlist = res.data.map(item => ({
            ...item,
            price: 0,
            change: 0,
            changePercent: 0
          }))
          await this.loadWatchlistPrices()
        }
      } catch (error) {
        // Silent fail
      } finally {
        this.loadingWatchlist = false
      }
    },
    async loadWatchlistPrices () {
      if (!this.watchlist || this.watchlist.length === 0) return

      try {
        const watchlistData = this.watchlist.map(item => ({
          market: item.market,
          symbol: item.symbol
        }))

        const res = await getWatchlistPrices({
          watchlist: watchlistData
        })

        if (res && res.code === 1 && res.data) {
          const priceMap = {}
          const pricesObj = {}
          res.data.forEach(item => {
            priceMap[`${item.market}-${item.symbol}`] = item
            // Keep watchlistPrices in sync, using `Market:Symbol` as the key.
            pricesObj[`${item.market}:${item.symbol}`] = {
              price: item.price || 0,
              change: item.changePercent || 0
            }
          })
          this.watchlistPrices = pricesObj

          this.watchlist = this.watchlist.map(item => {
            const key = `${item.market}-${item.symbol}`
            const priceData = priceMap[key]
            if (priceData) {
              return {
                ...item,
                price: priceData.price || 0,
                change: priceData.change || 0,
                changePercent: priceData.changePercent || 0
              }
            }
            return item
          })
        }
      } catch (error) {
        // Silent fail
      }
    },
    startWatchlistPriceRefresh () {
      this.watchlistPriceTimer = setInterval(() => {
        if (this.watchlist && this.watchlist.length > 0) {
          this.loadWatchlistPrices()
        }
      }, 30000)

      if (this.watchlist && this.watchlist.length > 0) {
        this.loadWatchlistPrices()
      }
    },
    openPositionModal (stock) {
      const livePrice = Number(this.watchlistPrices[`${stock.market}:${stock.symbol}`]?.price || stock.price || 0)
      this.positionDraft = {
        market: stock.market,
        symbol: stock.symbol,
        name: stock.name || stock.symbol,
        side: 'long',
        quantity: 1,
        entry_price: livePrice > 0 ? livePrice : 1,
        notes: '',
        group_name: ''
      }
      this.showPositionModal = true
    },
    closePositionModal () {
      this.showPositionModal = false
      this.positionDraft = this.createEmptyPositionDraft()
    },
    async handleSavePosition () {
      if (!this.positionDraft.market || !this.positionDraft.symbol) {
        this.$message.warning(this.tt('aiAssetAnalysis.position.symbolRequired', 'Missing market or symbol'))
        return
      }
      if (!(Number(this.positionDraft.quantity) > 0)) {
        this.$message.warning(this.tt('aiAssetAnalysis.position.quantityRequired', 'Quantity must be greater than zero'))
        return
      }
      if (!(Number(this.positionDraft.entry_price) > 0)) {
        this.$message.warning(this.tt('aiAssetAnalysis.position.entryPriceRequired', 'Entry price must be greater than zero'))
        return
      }

      this.savingPosition = true
      try {
        const res = await addPosition({
          market: this.positionDraft.market,
          symbol: this.positionDraft.symbol,
          name: this.positionDraft.name || this.positionDraft.symbol,
          side: this.positionDraft.side || 'long',
          quantity: Number(this.positionDraft.quantity),
          entry_price: Number(this.positionDraft.entry_price),
          notes: this.positionDraft.notes || '',
          group_name: this.positionDraft.group_name || ''
        })

        if (res?.code === 1) {
          this.$message.success(this.tt('aiAssetAnalysis.position.saveSuccess', 'Position saved'))
          this.closePositionModal()
          await this.loadPositions()
        } else {
          this.$message.error(res?.msg || this.tt('aiAssetAnalysis.position.saveFailed', 'Failed to save position'))
        }
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.position.saveFailed', 'Failed to save position'))
      } finally {
        this.savingPosition = false
      }
    },
    openMonitorModal (stock) {
      const existing = this.getMonitorMeta(stock)?.first || null
      this.monitorDraft = existing
        ? {
            id: existing.id,
            name: existing.name || `${stock.symbol} monitor`,
            market: stock.market,
            symbol: stock.symbol,
            interval_minutes: Number(existing.config?.interval_minutes || 60),
            prompt: existing.config?.prompt || '',
            channels: [...this.normalizeChannels(existing.notification_config?.channels)],
            is_active: !!existing.is_active
          }
        : {
            id: null,
            name: `${stock.symbol} monitor`,
            market: stock.market,
            symbol: stock.symbol,
            interval_minutes: 60,
            prompt: '',
            channels: [...(this.userNotificationSettings.default_channels || ['browser'])],
            is_active: true
          }
      this.showMonitorModal = true
    },
    editMonitorTask (monitor) {
      const config = monitor.config || {}
      this.monitorDraft = {
        id: monitor.id,
        name: monitor.name || `${config.symbol || 'Asset'} monitor`,
        market: config.market || '',
        symbol: config.symbol || '',
        interval_minutes: Number(config.interval_minutes || 60),
        prompt: config.prompt || '',
        channels: [...this.normalizeChannels(monitor.notification_config?.channels)],
        is_active: !!monitor.is_active
      }
      this.showMonitorModal = true
    },
    closeMonitorModal () {
      this.showMonitorModal = false
      this.monitorDraft = this.createEmptyMonitorDraft()
    },
    async handleSaveMonitor () {
      if (!this.monitorDraft.market || !this.monitorDraft.symbol) {
        this.$message.warning(this.tt('aiAssetAnalysis.monitor.symbolRequired', 'Missing market or symbol'))
        return
      }
      if (!String(this.monitorDraft.name || '').trim()) {
        this.$message.warning(this.tt('aiAssetAnalysis.monitor.nameRequired', 'Task name is required'))
        return
      }

      this.savingMonitor = true
      try {
        const stock = {
          market: this.monitorDraft.market,
          symbol: this.monitorDraft.symbol
        }
        const matchedPositions = this.getMatchedPositions(stock)
        const payload = {
          name: String(this.monitorDraft.name).trim(),
          monitor_type: 'ai',
          position_ids: matchedPositions.map(position => position.id),
          config: {
            interval_minutes: Number(this.monitorDraft.interval_minutes || 60),
            prompt: this.monitorDraft.prompt || '',
            language: this.$store.getters.lang || 'en-US',
            market: this.monitorDraft.market,
            symbol: this.monitorDraft.symbol,
            name: this.monitorDraft.name || this.monitorDraft.symbol
          },
          notification_config: {
            channels: this.normalizeChannels(this.monitorDraft.channels),
            targets: this.buildNotificationTargets()
          },
          is_active: this.monitorDraft.is_active !== false
        }

        const res = this.monitorDraft.id
          ? await updateMonitor(this.monitorDraft.id, payload)
          : await addMonitor(payload)

        if (res?.code === 1) {
          this.$message.success(this.tt('aiAssetAnalysis.monitor.saveSuccess', 'Task saved'))
          this.closeMonitorModal()
          await this.loadMonitors()
        } else {
          this.$message.error(res?.msg || this.tt('aiAssetAnalysis.monitor.saveFailed', 'Failed to save task'))
        }
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.monitor.saveFailed', 'Failed to save task'))
      } finally {
        this.savingMonitor = false
      }
    },
    async toggleMonitorStatus (monitor, active) {
      try {
        const res = await updateMonitor(monitor.id, { is_active: active })
        if (res?.code === 1) {
          await this.loadMonitors()
        } else {
          this.$message.error(res?.msg || this.tt('aiAssetAnalysis.monitor.updateFailed', 'Failed to update task'))
        }
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.monitor.updateFailed', 'Failed to update task'))
      }
    },
    async toggleStockMonitor (stock) {
      const meta = this.getMonitorMeta(stock)
      if (!meta) {
        this.openMonitorModal(stock)
        return
      }

      const nextActive = meta.activeCount === 0
      try {
        await Promise.all(meta.list.map(item => updateMonitor(item.id, { is_active: nextActive })))
        this.$message.success(nextActive ? this.tt('aiAssetAnalysis.monitor.enabled', 'Task enabled') : this.tt('aiAssetAnalysis.monitor.disabled', 'Task paused'))
        await this.loadMonitors()
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.monitor.updateFailed', 'Failed to update task'))
      }
    },
    async runTaskNow (monitor) {
      this.runningMonitorId = monitor.id
      try {
        const res = await runMonitor(monitor.id, {
          language: this.$store.getters.lang || 'en-US',
          async: true
        })
        if (res?.code === 1) {
          this.$message.success(this.tt('aiAssetAnalysis.tasks.runQueued', 'Task queued'))
          await this.loadMonitors()
        } else {
          this.$message.error(res?.msg || this.tt('aiAssetAnalysis.tasks.runFailed', 'Failed to start task'))
        }
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.tasks.runFailed', 'Failed to start task'))
      } finally {
        this.runningMonitorId = null
      }
    },
    async deleteMonitorTask (monitor) {
      try {
        const res = await deleteMonitor(monitor.id)
        if (res?.code === 1) {
          this.$message.success(this.tt('aiAssetAnalysis.tasks.deleteSuccess', 'Task deleted'))
          await this.loadMonitors()
        } else {
          this.$message.error(res?.msg || this.tt('aiAssetAnalysis.tasks.deleteFailed', 'Failed to delete task'))
        }
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.tasks.deleteFailed', 'Failed to delete task'))
      }
    },
    toggleBatchMode () {
      this.batchMode = !this.batchMode
      if (!this.batchMode) {
        this.batchSelectedKeys = []
      }
    },
    onBatchItemToggle (stock, event) {
      const checked = !!event.target.checked
      const key = `${stock.market}:${stock.symbol}`
      if (checked) {
        if (!this.batchSelectedKeys.includes(key)) {
          this.batchSelectedKeys = [...this.batchSelectedKeys, key]
        }
      } else {
        this.batchSelectedKeys = this.batchSelectedKeys.filter(item => item !== key)
      }
    },
    onBatchSelectAll (event) {
      const checked = !!event.target.checked
      this.batchSelectedKeys = checked ? this.watchlist.map(item => `${item.market}:${item.symbol}`) : []
    },
    openBatchScheduleModal () {
      if (this.batchSelectedKeys.length === 0) {
        this.$message.warning(this.tt('aiAssetAnalysis.batch.noneSelected', 'Select at least one asset first'))
        return
      }
      this.batchScheduleDraft = this.createEmptyBatchDraft()
      this.showBatchScheduleModal = true
    },
    closeBatchScheduleModal () {
      this.showBatchScheduleModal = false
      this.batchScheduleDraft = this.createEmptyBatchDraft()
    },
    async handleBatchSchedule () {
      if (this.batchSelectedKeys.length === 0) {
        this.$message.warning(this.tt('aiAssetAnalysis.batch.noneSelected', 'Select at least one asset first'))
        return
      }

      this.savingBatchSchedule = true
      try {
        const selectedStocks = this.watchlist.filter(item => this.batchSelectedKeys.includes(`${item.market}:${item.symbol}`))
        for (const stock of selectedStocks) {
          const existing = this.getMonitorMeta(stock)?.first || null
          const payload = {
            name: `${stock.symbol} monitor`,
            monitor_type: 'ai',
            position_ids: this.getMatchedPositions(stock).map(position => position.id),
            config: {
              interval_minutes: Number(this.batchScheduleDraft.interval_minutes || 60),
              prompt: this.batchScheduleDraft.prompt || '',
              language: this.$store.getters.lang || 'en-US',
              market: stock.market,
              symbol: stock.symbol,
              name: stock.name || stock.symbol
            },
            notification_config: {
              channels: this.normalizeChannels(this.batchScheduleDraft.channels),
              targets: this.buildNotificationTargets()
            },
            is_active: true
          }

          if (existing) {
            await updateMonitor(existing.id, payload)
          } else {
            await addMonitor(payload)
          }
        }

        this.$message.success(this.tt('aiAssetAnalysis.batch.saveSuccess', 'Batch schedule saved'))
        this.closeBatchScheduleModal()
        this.batchMode = false
        this.batchSelectedKeys = []
        await this.loadMonitors()
      } catch (e) {
        this.$message.error(e?.response?.data?.msg || e?.message || this.tt('aiAssetAnalysis.batch.saveFailed', 'Failed to save batch schedule'))
      } finally {
        this.savingBatchSchedule = false
      }
    },
    async handleAddStock () {
      let market = ''
      let symbol = ''
      let name = ''

      if (this.selectedSymbolForAdd) {
        market = this.selectedSymbolForAdd.market
        symbol = this.selectedSymbolForAdd.symbol.toUpperCase()
        name = this.selectedSymbolForAdd.name || ''
      } else if (this.symbolSearchKeyword && this.symbolSearchKeyword.trim()) {
        if (!this.selectedMarketTab) {
          this.$message.warning(this.$t('dashboard.analysis.modal.addStock.pleaseSelectMarket'))
          return
        }
        market = this.selectedMarketTab
        symbol = this.symbolSearchKeyword.trim().toUpperCase()
        name = ''
      } else {
        this.$message.warning(this.$t('dashboard.analysis.modal.addStock.pleaseSelectOrEnterSymbol'))
        return
      }

      this.addingStock = true
      try {
        const res = await addWatchlist({
          userid: this.userId,
          market: market,
          symbol: symbol,
          name: name
        })
        if (res && res.code === 1) {
          this.$message.success(this.$t('dashboard.analysis.message.addStockSuccess'))
          this.handleCloseAddStockModal()
          await this.loadWatchlist()
        } else {
          this.$message.error(res?.msg || this.$t('dashboard.analysis.message.addStockFailed'))
        }
      } catch (error) {
        const errorMsg = error?.response?.data?.msg || error?.message || this.$t('dashboard.analysis.message.addStockFailed')
        this.$message.error(errorMsg)
      } finally {
        this.addingStock = false
      }
    },
    handleCloseAddStockModal () {
      this.showAddStockModal = false
      this.selectedSymbolForAdd = null
      this.symbolSearchKeyword = ''
      this.symbolSearchResults = []
      this.hasSearched = false
      this.selectedMarketTab = this.marketTypes.length > 0 ? this.marketTypes[0].value : ''
    },
    handleMarketTabChange (activeKey) {
      this.selectedMarketTab = activeKey
      this.symbolSearchKeyword = ''
      this.symbolSearchResults = []
      this.selectedSymbolForAdd = null
      this.hasSearched = false
      this.loadHotSymbols(activeKey)
    },
    handleSymbolSearchInput (e) {
      const keyword = e.target.value
      this.symbolSearchKeyword = keyword

      if (this.searchTimer) {
        clearTimeout(this.searchTimer)
      }

      if (!keyword || keyword.trim() === '') {
        this.symbolSearchResults = []
        this.hasSearched = false
        this.selectedSymbolForAdd = null
        return
      }

      this.searchTimer = setTimeout(() => {
        this.searchSymbolsInModal(keyword)
      }, 500)
    },
    handleSearchOrInput (keyword) {
      if (!keyword || !keyword.trim()) return

      if (!this.selectedMarketTab) {
        this.$message.warning(this.$t('dashboard.analysis.modal.addStock.pleaseSelectMarket'))
        return
      }

      if (this.symbolSearchResults.length > 0) return

      if (this.hasSearched && this.symbolSearchResults.length === 0) {
        this.handleDirectAdd()
      } else {
        this.searchSymbolsInModal(keyword)
      }
    },
    async searchSymbolsInModal (keyword) {
      if (!keyword || keyword.trim() === '') {
        this.symbolSearchResults = []
        this.hasSearched = false
        return
      }

      if (!this.selectedMarketTab) {
        this.$message.warning(this.$t('dashboard.analysis.modal.addStock.pleaseSelectMarket'))
        return
      }

      this.searchingSymbols = true
      this.hasSearched = true
      try {
        const res = await searchSymbols({
          market: this.selectedMarketTab,
          keyword: keyword.trim(),
          limit: 20
        })
        if (res && res.code === 1 && res.data && res.data.length > 0) {
          this.symbolSearchResults = res.data
        } else {
          this.symbolSearchResults = []
          this.selectedSymbolForAdd = {
            market: this.selectedMarketTab,
            symbol: keyword.trim().toUpperCase(),
            name: ''
          }
        }
      } catch (error) {
        this.symbolSearchResults = []
        this.selectedSymbolForAdd = {
          market: this.selectedMarketTab,
          symbol: keyword.trim().toUpperCase(),
          name: ''
        }
      } finally {
        this.searchingSymbols = false
      }
    },
    handleDirectAdd () {
      if (!this.symbolSearchKeyword || !this.symbolSearchKeyword.trim()) {
        this.$message.warning(this.$t('dashboard.analysis.modal.addStock.pleaseEnterSymbol'))
        return
      }

      if (!this.selectedMarketTab) {
        this.$message.warning(this.$t('dashboard.analysis.modal.addStock.pleaseSelectMarket'))
        return
      }

      this.selectedSymbolForAdd = {
        market: this.selectedMarketTab,
        symbol: this.symbolSearchKeyword.trim().toUpperCase(),
        name: ''
      }
    },
    selectSymbol (symbol) {
      this.selectedSymbolForAdd = {
        market: symbol.market,
        symbol: symbol.symbol,
        name: symbol.name || symbol.symbol
      }
    },
    async loadHotSymbols (market) {
      if (!market) {
        market = this.selectedMarketTab || (this.marketTypes.length > 0 ? this.marketTypes[0].value : '')
      }

      if (!market) return

      this.loadingHotSymbols = true
      try {
        const res = await getHotSymbols({
          market: market,
          limit: 10
        })
        if (res && res.code === 1 && res.data) {
          this.hotSymbols = res.data
        } else {
          this.hotSymbols = []
        }
      } catch (error) {
        this.hotSymbols = []
      } finally {
        this.loadingHotSymbols = false
      }
    },
    async removeFromWatchlist (stock) {
      if (!this.userId) return
      // Support either a stock object or separate symbol/market arguments.
      const symbol = typeof stock === 'object' ? stock.symbol : stock
      const market = typeof stock === 'object' ? stock.market : arguments[1]
      const removedKey = `${market}:${symbol}`
      try {
        const res = await removeWatchlist({
          userid: this.userId,
          symbol: symbol,
          market: market
        })
        if (res && res.code === 1) {
          this.$message.success(this.$t('dashboard.analysis.message.removeStockSuccess'))
          this.batchSelectedKeys = this.batchSelectedKeys.filter(item => item !== removedKey)
          if (this.selectedSymbol === removedKey) {
            this.selectedSymbol = undefined
            this.analysisResult = null
            this.analysisError = null
          }
          await this.loadWatchlist()
        } else {
          this.$message.error(res?.msg || this.$t('dashboard.analysis.message.removeStockFailed'))
        }
      } catch (error) {
        this.$message.error(this.$t('dashboard.analysis.message.removeStockFailed'))
      }
    },
    getMarketName (market) {
      return this.$t(`dashboard.analysis.market.${market}`) || market
    },
    formatNumber (num) {
      if (typeof num === 'string') return num
      return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    },
    async loadMarketTypes () {
      try {
        const res = await getMarketTypes()
        if (res && res.code === 1 && res.data && Array.isArray(res.data)) {
          this.marketTypes = res.data.map(item => ({
            value: item.value,
            i18nKey: item.i18nKey || `dashboard.analysis.market.${item.value}`
          }))
        } else {
          this.marketTypes = [
            { value: 'USStock', i18nKey: 'dashboard.analysis.market.USStock' },
            { value: 'Crypto', i18nKey: 'dashboard.analysis.market.Crypto' },
            { value: 'Forex', i18nKey: 'dashboard.analysis.market.Forex' },
            { value: 'Futures', i18nKey: 'dashboard.analysis.market.Futures' }
          ]
        }
      } catch (error) {
        this.marketTypes = [
          { value: 'USStock', i18nKey: 'dashboard.analysis.market.USStock' },
          { value: 'Crypto', i18nKey: 'dashboard.analysis.market.Crypto' },
          { value: 'Forex', i18nKey: 'dashboard.analysis.market.Forex' },
          { value: 'Futures', i18nKey: 'dashboard.analysis.market.Futures' }
        ]
      }

      if (this.marketTypes.length > 0 && !this.selectedMarketTab) {
        this.selectedMarketTab = this.marketTypes[0].value
      }
    }
  },
  watch: {
    selectedSymbol (newVal) {
      this.$emit('symbol-change', newVal)
    },
    presetSymbol (newVal) {
      if (newVal && newVal !== this.selectedSymbol) {
        this.selectedSymbol = newVal
        this.analysisResult = null
        this.analysisError = null
        this.analysisErrorTone = 'error'
      }
    },
    autoAnalyzeSignal (newVal) {
      if (!newVal) return
      if (this.presetSymbol && this.presetSymbol !== this.selectedSymbol) {
        this.selectedSymbol = this.presetSymbol
      }
      this.$nextTick(() => {
        this.startFastAnalysis()
      })
    },
    showAddStockModal (newVal) {
      if (newVal) {
        if (this.marketTypes.length > 0 && !this.selectedMarketTab) {
          this.selectedMarketTab = this.marketTypes[0].value
        }
        if (this.selectedMarketTab) {
          this.loadHotSymbols(this.selectedMarketTab)
        }
      } else {
        this.selectedSymbolForAdd = null
        this.symbolSearchKeyword = ''
        this.symbolSearchResults = []
        this.hasSearched = false
        if (this.searchTimer) {
          clearTimeout(this.searchTimer)
          this.searchTimer = null
        }
      }
    }
  }
}
</script>

<style lang="less" scoped>
.ai-analysis-container {
  display: flex;
  height: calc(100vh - 120px);
  background: #f0f2f5;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
}

.ai-analysis-container.embedded {
  height: auto;
  min-height: 700px;
  background: transparent;
}

.ai-analysis-container.embedded .main-content-full {
  box-shadow: none;
  border-radius: 0;
}

// Full-width main content
.main-content-full {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  border-radius: 12px;
  height: 100%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

// Top market index strip
.top-index-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-family: 'SF Mono', Monaco, Consolas, monospace;

  .indicator-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4px 10px;
    background: #fff;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
    min-width: 50px;

    .ind-label { font-size: 9px; color: #94a3b8; text-transform: uppercase; }
    .ind-value { font-size: 13px; font-weight: 700; color: #1e293b; }

    &.fear-greed.extreme-fear .ind-value { color: #dc2626; }
    &.fear-greed.fear .ind-value { color: #ea580c; }
    &.fear-greed.neutral .ind-value { color: #ca8a04; }
    &.fear-greed.greed .ind-value { color: #65a30d; }
    &.fear-greed.extreme-greed .ind-value { color: #16a34a; }
    &.vix.low .ind-value { color: #16a34a; }
    &.vix.medium .ind-value { color: #ca8a04; }
    &.vix.high .ind-value { color: #dc2626; }
    &.dxy .ind-value { color: #2563eb; }
  }

  .indices-marquee {
    flex: 1;
    overflow: hidden;
    min-width: 0;

    .marquee-track {
      display: flex;
      gap: 8px;
      animation: marquee 35s linear infinite;
      width: max-content;
      &:hover { animation-play-state: paused; }
    }

    .index-item {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      background: #fff;
      border-radius: 4px;
      border: 1px solid #e2e8f0;
      font-size: 11px;
      white-space: nowrap;

      .idx-flag { font-size: 11px; }
      .idx-symbol { color: #64748b; font-weight: 500; }
      .idx-price { color: #1e293b; font-weight: 600; }
      .idx-change {
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 1px;
        &.up { color: #16a34a; }
        &.down { color: #dc2626; }
      }
    }
  }

  @keyframes marquee {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }

  .refresh-btn {
    color: #94a3b8;
    flex-shrink: 0;
    &:hover { color: #1e293b; }
  }
}

// Main three-column layout
.main-body {
  flex: 1;
  display: flex;
  gap: 12px;
  padding: 12px;
  overflow: hidden;
  min-height: 0;
}

// Left panel: heatmap + economic calendar
.left-panel {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;

  .heatmap-box {
    background: #fff;
    border-radius: 8px;
    padding: 12px;
    border: 1px solid #e2e8f0;

    .box-header {
      margin-bottom: 10px;
      ::v-deep .ant-radio-group .ant-radio-button-wrapper {
        font-size: 10px;
        padding: 0 6px;
        height: 22px;
        line-height: 20px;
        &.ant-radio-button-wrapper-checked {
          background: var(--primary-color, #1890ff);
          border-color: var(--primary-color, #1890ff);
          color: #fff;
        }
      }
    }

    .heatmap-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 4px;

      .heat-cell {
        padding: 6px 4px;
        border-radius: 4px;
        text-align: center;
        font-size: 9px;
        .heat-name { display: block; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 1px; }
        .heat-price { display: block; font-size: 9px; opacity: 0.8; margin-bottom: 1px; }
        .heat-val { font-weight: 700; font-size: 10px; }
      }
    }
  }

  .calendar-box {
    flex: 1;
    background: #fff;
    border-radius: 8px;
    padding: 12px;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;

    .box-header {
      margin-bottom: 8px;
      .box-title {
        font-size: 12px;
        color: #64748b;
        font-weight: 600;
        .anticon { margin-right: 6px; color: var(--primary-color, #1890ff); }
      }
    }

    .calendar-list {
      flex: 1;
      overflow-y: auto;

      &::-webkit-scrollbar { width: 4px; }
      &::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }

      .cal-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 0;
        border-bottom: 1px solid #f1f5f9;
        font-size: 10px;
        &:last-child { border-bottom: none; }
        &.high { border-left: 3px solid #dc2626; padding-left: 8px; margin-left: -4px; }
        &.medium { border-left: 3px solid #ca8a04; padding-left: 8px; margin-left: -4px; }
        &.low { border-left: 3px solid #16a34a; padding-left: 8px; margin-left: -4px; }

        .cal-date {
          font-size: 9px;
          color: #94a3b8;
          min-width: 32px;
          font-weight: 500;
        }
        .cal-time { color: #64748b; min-width: 36px; font-weight: 500; }
        .cal-flag { font-size: 12px; }
        .cal-name { flex: 1; color: #334155; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cal-impact {
          font-weight: 600;
          font-size: 10px;
          display: flex;
          align-items: center;
          gap: 2px;
          &.bullish { color: #16a34a; }
          &.bearish { color: #dc2626; }
          &.neutral { color: #94a3b8; }
        }
      }
      .cal-empty { text-align: center; color: #94a3b8; padding: 20px 0; font-size: 12px; }
    }
  }
}

// Center panel: toolbar + analysis result
// Middle analysis panel
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;

  .analysis-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid #f1f5f9;
    background: #fafafa;
    border-radius: 8px 8px 0 0;

    .symbol-selector {
      flex: 1;
      max-width: 320px;
    }

    .analyze-button {
      background: var(--primary-color, #1890ff);
      border-color: var(--primary-color, #1890ff);
    }

    .history-button {
      border-color: #d9d9d9;
    }
  }

  .analysis-main {
    flex: 1;
    overflow: auto;
    padding: 16px;
    min-height: 0;

    .analysis-placeholder {
      min-height: 360px;

      .placeholder-hero {
        display: flex;
        gap: 20px;
        align-items: stretch;
        min-height: 360px;
        padding: 24px;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        background:
          radial-gradient(circle at top left, rgba(24, 144, 255, 0.12), transparent 36%),
          linear-gradient(145deg, #f8fbff 0%, #f7fafc 48%, #ffffff 100%);
      }

      .placeholder-mark {
        width: 120px;
        min-width: 120px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 20px;
        background: linear-gradient(160deg, rgba(24, 144, 255, 0.15), rgba(14, 165, 233, 0.06));
        color: var(--primary-color, #1890ff);
        font-size: 48px;
      }

      .hero-body {
        flex: 1;
        min-width: 0;
      }

      .hero-badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(24, 144, 255, 0.1);
        color: var(--primary-color, #1890ff);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
      }

      .hero-title {
        margin: 16px 0 10px;
        font-size: 28px;
        line-height: 1.2;
        color: #0f172a;
      }

      .hero-subtitle {
        max-width: 760px;
        margin: 0;
        font-size: 15px;
        line-height: 1.7;
        color: #64748b;
      }

      .hero-stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 22px;
      }

      .hstat {
        display: flex;
        gap: 10px;
        align-items: flex-start;
        padding: 14px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.82);
      }

      .hstat-icon {
        width: 36px;
        height: 36px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        background: rgba(24, 144, 255, 0.1);
        color: var(--primary-color, #1890ff);
      }

      .hstat-body {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
      }

      .hstat-val {
        font-size: 14px;
        font-weight: 600;
        color: #0f172a;
      }

      .hstat-label {
        font-size: 12px;
        line-height: 1.6;
        color: #64748b;
      }

      .hero-cta {
        display: flex;
        gap: 12px;
        margin-top: 22px;
      }

      .hero-hint {
        margin: 16px 0 0;
        font-size: 13px;
        color: #94a3b8;
      }
    }
  }
}

// Right watchlist panel
.watchlist-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-bottom: 1px solid #f1f5f9;
    background: #fafafa;

    .panel-title {
      font-size: 12px;
      font-weight: 600;
      color: #64748b;
      .anticon { color: #facc15; margin-right: 6px; }
    }

    .panel-header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .panel-header-icon {
      color: #94a3b8;
      cursor: pointer;
      transition: color 0.2s ease;

      &:hover {
        color: var(--primary-color, #1890ff);
      }
    }
  }

  .panel-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    padding: 10px 12px 0;
  }

  .summary-chip {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 10px;
    background: #f8fafc;
    border: 1px solid #eef2f7;

    .sc-num {
      font-size: 14px;
      font-weight: 700;
      color: #0f172a;

      &.up {
        color: #16a34a;
      }

      &.down {
        color: #dc2626;
      }
    }

    .sc-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #94a3b8;
    }
  }

  .batch-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px 0;

    .batch-all-cb {
      flex: 1;
      font-size: 12px;
      color: #64748b;
    }
  }

  .watchlist-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;

    &::-webkit-scrollbar { width: 4px; }
    &::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 2px; }

    .wl-card {
      position: relative;
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
      padding: 10px;
      border-radius: 12px;
      border: 1px solid #edf2f7;
      background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        border-color: #dbe7f5;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
      }

      &.active {
        border-color: #91d5ff;
        background: linear-gradient(180deg, #f0f7ff 0%, #e6f7ff 100%);
      }

      .wl-card-cb {
        margin-top: 2px;
      }

      .wl-card-body {
        flex: 1;
        min-width: 0;

        &.with-cb {
          padding-right: 4px;
        }
      }

      .wl-row-main {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .wl-symbol {
        font-size: 13px;
        font-weight: 700;
        color: #0f172a;
      }

      .wl-market {
        font-size: 11px;
        color: #64748b;
      }

      .wl-spacer {
        flex: 1;
      }

      .wl-price,
      .wl-change,
      .wl-pnl-qty,
      .wl-pnl-val,
      .wl-task-next {
        font-family: 'SF Mono', Monaco, monospace;
      }

      .wl-price {
        font-size: 11px;
        font-weight: 700;
        color: #0f172a;
      }

      .wl-change {
        font-size: 10px;
        font-weight: 700;
      }

      .wl-change.up,
      .wl-pnl-val.up {
        color: #16a34a;
      }

      .wl-change.down,
      .wl-pnl-val.down {
        color: #dc2626;
      }

      .wl-row-pnl,
      .wl-row-task {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-top: 8px;
      }

      .wl-pnl-qty {
        font-size: 10px;
        color: #64748b;
      }

      .wl-pnl-val {
        font-size: 10px;
        font-weight: 700;
      }

      .wl-task-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 10px;
        font-weight: 700;
        border: 1px solid transparent;
        transition: all 0.2s ease;

        &.active {
          color: #166534;
          background: rgba(34, 197, 94, 0.12);
          border-color: rgba(34, 197, 94, 0.18);
        }

        &.paused {
          color: #92400e;
          background: rgba(245, 158, 11, 0.12);
          border-color: rgba(245, 158, 11, 0.18);
        }
      }

      .wl-task-next {
        font-size: 10px;
        color: #94a3b8;
        text-align: right;
      }

      .wl-card-hover-actions {
        position: absolute;
        top: 8px;
        right: 8px;
        display: flex;
        gap: 6px;
        opacity: 0;
        transform: translateY(-2px);
        transition: all 0.2s ease;
      }

      .wl-hover-btn {
        width: 24px;
        height: 24px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.92);
        color: #64748b;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);

        &:hover {
          color: var(--primary-color, #1890ff);
        }

        &.danger:hover {
          color: #dc2626;
        }
      }

      &:hover .wl-card-hover-actions {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .watchlist-empty {
      text-align: center;
      padding: 24px 12px;
      color: #94a3b8;
      .we-icon {
        width: 52px;
        height: 52px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 16px;
        background: rgba(250, 204, 21, 0.12);
        color: #f59e0b;
        margin-bottom: 10px;
      }
      .anticon { font-size: 24px; display: block; }
      p { font-size: 12px; margin-bottom: 12px; }
    }
  }
}

.task-drawer-head {
  margin-bottom: 16px;
}

.task-drawer-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.task-drawer-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.task-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #edf2f7;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.task-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.task-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-card-meta {
  margin-top: 12px;
}

.task-meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  font-size: 12px;

  .label {
    color: #64748b;
  }

  .value {
    color: #0f172a;
    text-align: right;
  }
}

.task-card-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Responsive */
@media (max-width: 992px) {
  .ai-analysis-container {
    height: auto;
    min-height: calc(100vh - 64px);
    overflow-y: auto;
  }

  .main-content-full {
    height: auto;
    min-height: auto;
  }

  .top-index-bar {
    flex-wrap: wrap;
    padding: 8px;

    .indicator-box {
      min-width: 45px;
      padding: 3px 6px;
    }

    .indices-marquee {
      order: 10;
      width: 100%;
      margin-top: 8px;
    }
  }

  .main-body {
    flex-direction: column;
    padding: 12px;
  }

  .left-panel {
    width: 100%;
    flex-direction: row;
    gap: 12px;

    .heatmap-box, .calendar-box {
      flex: 1;
      min-width: 0;
    }

    .calendar-box {
      max-height: 200px;
    }
  }

  .right-panel {
    .analysis-toolbar {
      flex-wrap: wrap;
      .symbol-selector { width: 100% !important; max-width: none !important; }
      .analyze-button, .history-button { flex: 1; }
    }

    .analysis-main .analysis-placeholder .placeholder-hero {
      flex-direction: column;
    }

    .analysis-main .analysis-placeholder .placeholder-mark {
      width: 100%;
      min-width: 0;
      min-height: 96px;
    }

    .analysis-main .analysis-placeholder .hero-stats {
      grid-template-columns: 1fr;
    }

    .analysis-main .analysis-placeholder .hero-cta {
      flex-direction: column;
    }
  }

  .watchlist-panel {
    width: 100%;
    max-height: none;
    order: -1;

    .panel-summary {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .batch-bar {
      flex-wrap: wrap;
    }
  }

  .task-card-actions {
    flex-wrap: wrap;
  }
}

/* Dark Theme */
.ai-analysis-container.theme-dark {
  background: #131722;
  color: #d1d4dc;

  .main-content-full {
    background: #1e222d;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .top-index-bar {
    background: #1e222d;
    border-bottom-color: #363c4e;

    .indicator-box {
      background: #2a2e39;
      border-color: #363c4e;
      .ind-label { color: #868993; }
      .ind-value { color: #d1d4dc; }
    }

    .indices-marquee .index-item {
      background: #2a2e39;
      border-color: #363c4e;
      .idx-symbol { color: #868993; }
      .idx-price { color: #d1d4dc; }
    }

    .refresh-btn {
      color: #868993;
      &:hover { color: #d1d4dc; }
    }
  }

  .watchlist-panel {
    background: #2a2e39;
    border-color: #363c4e;

    .panel-header {
      background: #1e222d;
      border-bottom-color: #363c4e;
      .panel-title { color: #868993; }
      .panel-header-icon { color: #868993; }
    }

    .summary-chip {
      background: #1e222d;
      border-color: #363c4e;

      .sc-num {
        color: #d1d4dc;
      }

      .sc-label {
        color: #64748b;
      }
    }

    .batch-bar .batch-all-cb {
      color: #868993;
    }

    .watchlist-list {
      .wl-card {
        background: linear-gradient(180deg, #232833 0%, #1f2430 100%);
        border-color: #363c4e;

        &:hover {
          border-color: #475067;
          box-shadow: 0 10px 24px rgba(0, 0, 0, 0.24);
        }

        &.active {
          background: rgba(24, 144, 255, 0.12);
          border-color: #1890ff;
        }

        .wl-symbol,
        .wl-price {
          color: #d1d4dc;
        }

        .wl-market,
        .wl-pnl-qty,
        .wl-task-next {
          color: #868993;
        }

        .wl-task-badge.active {
          color: #86efac;
          background: rgba(34, 197, 94, 0.12);
          border-color: rgba(34, 197, 94, 0.18);
        }

        .wl-task-badge.paused {
          color: #fcd34d;
          background: rgba(245, 158, 11, 0.12);
          border-color: rgba(245, 158, 11, 0.18);
        }

        .wl-hover-btn {
          background: rgba(30, 34, 45, 0.95);
          color: #868993;

          &:hover {
            color: #d1d4dc;
          }
        }
      }

      .watchlist-empty { color: #64748b; }
    }
  }

  .watchlist-bar-legacy {
    background: #1e222d;
    border-bottom-color: #363c4e;

    .stock-chip {
      background: #2a2e39;
      border-color: #363c4e;
      &:hover, &.active { border-color: var(--primary-color, #1890ff); background: rgba(24, 144, 255, 0.1); }
      .chip-symbol { color: #d1d4dc; }
      .chip-price { color: #868993; }
    }
  }

  .left-panel {
    .heatmap-box {
      background: #2a2e39;
      border-color: #363c4e;

      ::v-deep .ant-radio-group .ant-radio-button-wrapper {
        background: #1e222d;
        border-color: #363c4e;
        color: #868993;
        &:hover { color: #d1d4dc; }
      }
    }

    .calendar-box {
      background: #2a2e39;
      border-color: #363c4e;

      .box-title { color: #868993; }
      .cal-item {
        border-bottom-color: #363c4e;
        .cal-date { color: #64748b; }
        .cal-time { color: #868993; }
        .cal-name { color: #d1d4dc; }
      }
      .cal-empty { color: #64748b; }
    }
  }

  .right-panel {
    background: #2a2e39;
    border-color: #363c4e;

    .analysis-toolbar {
      background: #1e222d;
      border-bottom-color: #363c4e;

      .history-button {
        background: #2a2e39;
        border-color: #363c4e;
        color: #d1d4dc;
      }
    }

    .analysis-main {
      .analysis-placeholder {
        .placeholder-hero {
          border-color: #363c4e;
          background:
            radial-gradient(circle at top left, rgba(24, 144, 255, 0.16), transparent 34%),
            linear-gradient(145deg, #1f2633 0%, #1b2230 48%, #1e222d 100%);
        }

        .placeholder-mark {
          background: rgba(24, 144, 255, 0.12);
        }

        .hero-title,
        .hstat-val {
          color: #d1d4dc;
        }

        .hero-subtitle,
        .hstat-label,
        .hero-hint {
          color: #868993;
        }

        .hstat {
          border-color: #363c4e;
          background: rgba(17, 24, 39, 0.52);
        }
      }
    }
  }

  // Legacy style compatibility
  .watchlist-bar-compat {
    background: #1e222d;
    border-top-color: #363c4e;

    .bar-label { color: #868993; }

    .stock-chip {
      background: #2a2e39;
      border-color: #363c4e;

      &:hover, &.active {
        border-color: var(--primary-color, #1890ff);
        background: rgba(24, 144, 255, 0.1);
      }

      .chip-symbol { color: #d1d4dc; }
      .chip-price { color: #868993; }
      .chip-remove { color: #64748b; }
    }
  }

  ::v-deep .symbol-selector {
    .ant-select-selection {
      background-color: #2a2e39;
      border-color: #363c4e;
      color: #d1d4dc;
    }
  }
}

.ai-analysis-container.theme-dark {
  .task-drawer-title {
    color: #d1d4dc;
  }

  .task-drawer-desc {
    color: #868993;
  }

  .task-card {
    background: linear-gradient(180deg, #232833 0%, #1f2430 100%);
    border-color: #363c4e;
  }

  .task-meta-row {
    .label {
      color: #868993;
    }

    .value {
      color: #d1d4dc;
    }
  }
}

/* Add Stock Modal */
.add-stock-modal-content {
  .market-tabs { margin-bottom: 16px; }
  .symbol-search-section { margin-bottom: 24px; }

  .search-results-section,
  .hot-symbols-section {
    margin-bottom: 24px;

    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #262626;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
    }
  }

  .symbol-list {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid #e8e8e8;
    border-radius: 4px;

    .symbol-list-item {
      cursor: pointer;
      padding: 8px 12px;
      transition: background-color 0.3s;

      &:hover { background-color: #f5f5f5; }

      .symbol-item-content {
        display: flex;
        align-items: center;
        gap: 8px;

        .symbol-code {
          font-weight: 600;
          color: #262626;
          min-width: 80px;
        }

        .symbol-name {
          color: #595959;
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
  }

  .selected-symbol-section {
    margin-top: 16px;

    .selected-symbol-info {
      display: flex;
      align-items: center;
    }
  }
}

/* Skeleton loading animation for progressive rendering */
.skeleton-box {
  .skeleton-text {
    display: block;
    height: 12px;
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
    border-radius: 4px;
    margin: 3px 0;

    &.short { width: 40px; height: 9px; }
  }
}

.skeleton-cell {
  background: #f8fafc !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;

  .skeleton-text {
    width: 80%;
    height: 10px;
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
    border-radius: 3px;
    margin: 2px 0;

    &.short { width: 50%; height: 8px; }
  }
}

.skeleton-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;

  .skeleton-text {
    height: 12px;
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: skeleton-pulse 1.5s ease-in-out infinite;
    border-radius: 4px;
    flex: 1;

    &.short { flex: none; width: 40px; }
  }
}

.indices-loading, .indices-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 11px;
  color: #94a3b8;
  padding: 4px 16px;
}

.indices-loading {
  .anticon { margin-right: 6px; }
}

.heatmap-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 20px;
  color: #94a3b8;
  font-size: 12px;
}

@keyframes skeleton-pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Dark-theme skeleton loading */
.theme-dark {
  .skeleton-box, .skeleton-cell, .skeleton-item {
    .skeleton-text {
      background: linear-gradient(90deg, #363c4e 25%, #424857 50%, #363c4e 75%);
      background-size: 200% 100%;
    }
  }

  .skeleton-cell {
    background: #2a2e39 !important;
  }

  .indices-loading, .indices-empty, .heatmap-empty {
    color: #64748b;
  }
}
</style>
