<template>
  <div :class="['basic-layout-wrapper', settings.theme]">
    <pro-layout
      :menus="menus"
      :collapsed="collapsed"
      :mediaQuery="query"
      :isMobile="isMobile"
      :handleMediaQuery="handleMediaQuery"
      :handleCollapse="handleCollapse"
      :i18nRender="i18nRender"
      v-bind="settings"
    >

      <template #menuHeaderRender>
        <div>
          <img src="~@/assets/slogo.png" />
          <h1>{{ title }}</h1>
        </div>
      </template>
      <!-- pro-layout 1.0.0+ provides an API
          for customizing the left side of the header content area
    -->
      <template #headerContentRender>
        <div>
          <a-tooltip :title="$t('menu.header.refreshPage')">
            <a-icon type="reload" style="font-size: 18px;cursor: pointer;" @click="handleRefresh" />
          </a-tooltip>
        </div>
      </template>

      <!-- User agreement modal -->
      <a-modal :visible="showLegalModal" :footer="null" :title="$t('menu.footer.userAgreement')" @cancel="showLegalModal = false" :width="800">
        <div style="max-height: 60vh; overflow: auto; white-space: pre-wrap; line-height: 1.8; padding: 16px;">
          {{ menuFooterConfig.legal.user_agreement || $t('user.login.legal.content') }}
        </div>
        <div style="margin-top: 12px; text-align: right;">
          <a-button type="primary" @click="showLegalModal = false">OK</a-button>
        </div>
      </a-modal>

      <!-- Privacy policy modal -->
      <a-modal :visible="showPrivacyModal" :footer="null" :title="$t('menu.footer.privacyPolicy')" @cancel="showPrivacyModal = false" :width="800">
        <div style="max-height: 60vh; overflow: auto; white-space: pre-wrap; line-height: 1.8; padding: 16px;">
          {{ menuFooterConfig.legal.privacy_policy || $t('user.login.privacy.content') }}
        </div>
        <div style="margin-top: 12px; text-align: right;">
          <a-button type="primary" @click="showPrivacyModal = false">OK</a-button>
        </div>
      </a-modal>

      <setting-drawer ref="settingDrawer" :settings="settings" @change="handleSettingChange">
        <div style="margin: 12px 0;">
          This is SettingDrawer custom footer content.
        </div>
      </setting-drawer>
      <template #rightContentRender>
        <right-content :top-menu="settings.layout === 'topmenu'" :is-mobile="isMobile" :theme="settings.theme" />
      </template>
      <!-- custom footer removed -->
      <template #footerRender>
        <div style="display: none;"></div>
      </template>
      <router-view :key="refreshKey" />
    </pro-layout>

    <!-- Menu footer at the bottom, rendered directly without slots -->
    <div class="custom-menu-footer" :class="{ 'collapsed': collapsed, 'drawer-open': isMobile && isDrawerOpen, 'drawer-animating': isMobile && isDrawerAnimating }">
      <div v-if="!collapsed" class="menu-footer-content">
        <!-- Contact us -->
        <div class="footer-section">
          <div class="section-title">{{ $t('menu.footer.contactUs') }}</div>
          <div class="section-links">
            <a :href="menuFooterConfig.contact.support_url" target="_blank">{{ $t('menu.footer.support') }}</a>
            <span class="separator">|</span>
            <a :href="menuFooterConfig.contact.feature_request_url" target="_blank">{{ $t('menu.footer.featureRequest') }}</a>
          </div>
        </div>

        <!-- Get support -->
        <div class="footer-section">
          <div class="section-title">{{ $t('menu.footer.getSupport') }}</div>
          <div class="section-links">
            <a :href="'mailto:' + menuFooterConfig.contact.email">{{ $t('menu.footer.email') }}</a>
            <span class="separator">|</span>
            <a :href="menuFooterConfig.contact.live_chat_url" target="_blank">{{ $t('menu.footer.liveChat') }}</a>
          </div>
        </div>

        <!-- Social accounts -->
        <div class="footer-section" v-if="menuFooterConfig.social_accounts && menuFooterConfig.social_accounts.length > 0">
          <div class="section-title">{{ $t('menu.footer.socialAccounts') }}</div>
          <div class="social-icons">
            <a
              v-for="(account, index) in menuFooterConfig.social_accounts"
              :key="index"
              :href="account.url"
              target="_blank"
              rel="noopener noreferrer"
              :title="account.name"
              class="social-icon"
            >
              <Icon :icon="`simple-icons:${account.icon}`" class="social-icon-svg" />
            </a>
          </div>
        </div>

        <!-- User agreement and privacy policy -->
        <div class="footer-section">
          <div class="section-links">
            <a @click="showLegalModal = true">{{ $t('menu.footer.userAgreement') }}</a>
            <span class="separator">&</span>
            <a @click="showPrivacyModal = true">{{ $t('menu.footer.privacyPolicy') }}</a>
          </div>
        </div>

        <!-- Copyright information -->
        <div class="footer-section copyright">
          {{ menuFooterConfig.copyright }}
        </div>
        <!-- Version number -->
        <div class="footer-section version">
          V2.2.1
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { updateTheme } from '@/components/SettingDrawer/settingConfig'
import { i18nRender } from '@/locales'
import { mapState } from 'vuex'
import {
  CONTENT_WIDTH_TYPE,
  SIDEBAR_TYPE,
  TOGGLE_MOBILE_TYPE,
  TOGGLE_NAV_THEME,
  TOGGLE_LAYOUT,
  TOGGLE_FIXED_HEADER,
  TOGGLE_FIXED_SIDEBAR,
  TOGGLE_CONTENT_WIDTH,
  TOGGLE_HIDE_HEADER,
  TOGGLE_COLOR,
  TOGGLE_WEAK,
  TOGGLE_MULTI_TAB
} from '@/store/mutation-types'

import defaultSettings from '@/config/defaultSettings'
import RightContent from '@/components/GlobalHeader/RightContent'
import SettingDrawer from '@/components/SettingDrawer/SettingDrawer'
import { Icon } from '@iconify/vue2'

export default {
  name: 'BasicLayout',
  components: {
    SettingDrawer,
    RightContent,
    Icon
    // GlobalFooter,
    // Ads
  },
  data () {
    return {
      // preview.pro.antdv.com only use.
      isProPreviewSite: process.env.VUE_APP_PREVIEW === 'true' && process.env.NODE_ENV !== 'development',
      // end
      isDev: process.env.NODE_ENV === 'development' || process.env.VUE_APP_PREVIEW === 'true',

      // base - menus moved to computed property
      // Sidebar collapsed state
      collapsed: false,
      title: defaultSettings.title,
      settings: {
        // Layout type
        layout: defaultSettings.layout, // 'sidemenu', 'topmenu'
        // CONTENT_WIDTH_TYPE
        contentWidth: defaultSettings.layout === 'sidemenu' ? CONTENT_WIDTH_TYPE.Fluid : defaultSettings.contentWidth,
        // Theme: 'dark' | 'light'
        theme: defaultSettings.navTheme,
        // Primary color
        primaryColor: defaultSettings.primaryColor,
        fixedHeader: defaultSettings.fixedHeader,
        fixSiderbar: defaultSettings.fixSiderbar,
        colorWeak: defaultSettings.colorWeak,

        hideHintAlert: false,
        hideCopyButton: false
      },
      // Media query
      query: {},

      // Whether mobile mode is active
      isMobile: false,
      // Legal disclaimer modal visibility state
      showLegalModal: false,
      showPrivacyModal: false,
      // Key used to refresh the content area
      refreshKey: 0,
      // Whether the drawer is open on mobile
      isDrawerOpen: false,
      // Whether the drawer is animating on mobile
      isDrawerAnimating: false,
      // Static footer config (local OSS build)
      menuFooterConfig: {
        contact: {
          support_url: 'https://t.me/quantdinger',
          feature_request_url: 'https://github.com/brokermr810/QuantDinger/issues',
          email: 'brokermr810@gmail.com',
          live_chat_url: 'https://t.me/quantdinger'
        },
        social_accounts: [
          { name: 'GitHub', icon: 'github', url: 'https://github.com/brokermr810/QuantDinger' },
          { name: 'X', icon: 'x', url: 'https://x.com/HenryCryption' },
          { name: 'Discord', icon: 'discord', url: 'https://discord.gg/cn6HVE2KC' },
          { name: 'Telegram', icon: 'telegram', url: 'https://t.me/quantdinger' },
          { name: 'YouTube', icon: 'youtube', url: 'https://youtube.com/@quantdinger' }
        ],
        legal: {
          user_agreement: '',
          privacy_policy: ''
        },
        copyright: '© 2025-2026 QuantDinger. All rights reserved.'
      },
      // Whether this is the first theme-color initialization, used to decide whether to show the "switching theme" notice
      isInitialThemeColorLoad: true
    }
  },
  computed: {
    ...mapState({
      // Dynamic main routes
      mainMenu: state => state.permission.addRouters
    }),
    // Responsive menu - update dynamically based on addRouters
    menus () {
      const routes = this.mainMenu.find(item => item.path === '/')
      return (routes && routes.children) || []
    }
  },
  created () {
    // menus is now a computed property - no need to set here
    // Sync theme settings from the store, restoring them from localStorage
    this.settings.theme = this.$store.state.app.theme
    this.settings.primaryColor = this.$store.state.app.color || defaultSettings.primaryColor
    // Handle sidebar collapse state
    this.$watch('collapsed', () => {
      this.$store.commit(SIDEBAR_TYPE, this.collapsed)
    })
    this.$watch('isMobile', () => {
      this.$store.commit(TOGGLE_MOBILE_TYPE, this.isMobile)
    })
    // Watch theme changes in the store and sync them to settings and body classes
    this.$watch('$store.state.app.theme', (val) => {
      this.settings.theme = val
      if (val === 'dark' || val === 'realdark') {
        document.body.classList.add('dark')
        document.body.classList.remove('light')
      } else {
        document.body.classList.remove('dark')
        document.body.classList.add('light')
      }
    }, { immediate: true })
    // Watch theme-color changes in the store and sync them to settings
    this.$watch('$store.state.app.color', (val) => {
      if (val) {
        this.settings.primaryColor = val
        // Apply the theme color
        if (process.env.NODE_ENV !== 'production' || process.env.VUE_APP_PREVIEW === 'true') {
          // Update silently on first load without showing the "switching theme" notice
          updateTheme(val, this.isInitialThemeColorLoad)
          // Clear the first-call flag after the first update
          if (this.isInitialThemeColorLoad) {
            this.isInitialThemeColorLoad = false
          }
        }
      }
    }, { immediate: true })
    // Watch settings.theme and sync body classes as an extra safeguard
    this.$watch('settings.theme', (val) => {
      if (val === 'dark' || val === 'realdark') {
        document.body.classList.add('dark')
        document.body.classList.remove('light')
      } else {
        document.body.classList.remove('dark')
        document.body.classList.add('light')
      }
    }, { immediate: true })
  },
  mounted () {
    const userAgent = navigator.userAgent
    if (userAgent.indexOf('Edge') > -1) {
      this.$nextTick(() => {
        this.collapsed = !this.collapsed
        setTimeout(() => {
          this.collapsed = !this.collapsed
        }, 16)
      })
    }

    // first update color
    // TIPS: THEME COLOR HANDLER!! PLEASE CHECK THAT!!
    // Theme-color updates are already handled by the watch in created(); do not call them again here
    // to avoid showing the "switching theme" notice twice

    // Listen for the event that opens the settings drawer
    this.$root.$on('show-setting-drawer', () => {
      if (this.$refs.settingDrawer) {
        this.$refs.settingDrawer.showDrawer()
      }
    })

    // Footer config is static for local OSS build

    // Update the footer position after a delay so the DOM has finished rendering
    this.$nextTick(() => {
      setTimeout(() => {
        this.updateMenuFooterPosition()
      }, 200)
    })

    // Listen for window size changes
    window.addEventListener('resize', this.updateMenuFooterPosition)

    // Desktop: periodically check and update the footer position to keep it visible
    if (!this.isMobile) {
      this._desktopFooterInterval = setInterval(() => {
        this.updateMenuFooterPosition()
      }, 1000)
    }

    // Listen for opening and closing of the mobile menu drawer
    // Use MutationObserver to watch drawer visibility changes
    const observer = new MutationObserver(() => {
      if (this.isMobile) {
        // Check whether the drawer is open
        const drawer = document.querySelector('.ant-drawer.ant-drawer-open')
        const wasOpen = this.isDrawerOpen
        const isOpen = !!drawer

        this.isDrawerOpen = isOpen

        // Update the footer position when the state changes
        if (wasOpen !== this.isDrawerOpen) {
          if (this.isDrawerOpen) {
            // The drawer just opened; mark it as animating and delay footer visibility
            this.isDrawerAnimating = true
            // Wait for the drawer animation to complete; Ant Design Drawer uses 0.3s
            setTimeout(() => {
              this.isDrawerAnimating = false
              this.updateMenuFooterPosition()
            }, 300)
          } else {
            // The drawer closed; hide the footer immediately
            this.isDrawerAnimating = false
            this.updateMenuFooterPosition()
          }
        }
      }
    })

    // Observe body changes to detect drawer insertion, removal, and class changes
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class']
    })

    // Store the observer for cleanup
    this._menuFooterObserver = observer

    // Periodic check as a fallback to keep the footer position correct
    this._menuFooterInterval = setInterval(() => {
      if (this.isMobile) {
        const drawer = document.querySelector('.ant-drawer.ant-drawer-open')
        const currentState = !!drawer
        if (this.isDrawerOpen !== currentState) {
          this.isDrawerOpen = currentState
          // Mark the drawer as animating if it just opened
          if (currentState) {
            this.isDrawerAnimating = true
            setTimeout(() => {
              this.isDrawerAnimating = false
              this.updateMenuFooterPosition()
            }, 300)
          } else {
            this.isDrawerAnimating = false
            this.updateMenuFooterPosition()
          }
        } else if (currentState && !this.isDrawerAnimating) {
          // If the drawer is open and no longer animating, update the position to avoid drift
          this.updateMenuFooterPosition()
        }
      }
    }, 200)
  },
  beforeDestroy () {
    // Remove event listeners
    this.$root.$off('show-setting-drawer')
    window.removeEventListener('resize', this.updateMenuFooterPosition)

    // Clean up the MutationObserver
    if (this._menuFooterObserver) {
      this._menuFooterObserver.disconnect()
    }

    // Clean up timers
    if (this._menuFooterInterval) {
      clearInterval(this._menuFooterInterval)
    }

    // Clean up desktop timers
    if (this._desktopFooterInterval) {
      clearInterval(this._desktopFooterInterval)
    }
  },
  methods: {
    i18nRender,
    updateMenuFooterPosition () {
      this.$nextTick(() => {
        // Use requestAnimationFrame to update before the next repaint and avoid interrupting CSS transitions
        requestAnimationFrame(() => {
          const menuFooter = this.$el?.querySelector('.custom-menu-footer')
          if (!menuFooter) return

          // Mobile: find the drawer menu container
          if (this.isMobile) {
            const drawer = document.querySelector('.ant-drawer.ant-drawer-open')
            this.isDrawerOpen = !!drawer

            if (drawer && !this.isDrawerAnimating) {
              // const drawerRect = drawer.getBoundingClientRect()
              menuFooter.style.position = 'fixed'
              // menuFooter.style.left = `${drawerRect.left}px`
              // Width is controlled by the CSS .collapsed class, so do not set it here
              menuFooter.style.bottom = '0px'
              menuFooter.style.zIndex = '1001'
              menuFooter.style.display = 'block'
              menuFooter.style.opacity = '1'

              // Compute the footer height dynamically and apply drawer body padding
              const footerHeight = menuFooter.offsetHeight || 280
              const drawerBody = drawer.querySelector('.ant-drawer-body')
              if (drawerBody) {
                // Set a CSS variable for styles to consume
                drawer.style.setProperty('--footer-height', `${footerHeight}px`)
                // Set padding-bottom directly so menu content is not obscured
                drawerBody.style.paddingBottom = `${footerHeight + 10}px`
                // Ensure the drawer body can scroll
                drawerBody.style.overflowY = 'auto'
                drawerBody.style.overflowX = 'hidden'
                drawerBody.style.webkitOverflowScrolling = 'touch'
              }

              return
            } else if (drawer && this.isDrawerAnimating) {
              // While the drawer is animating, the footer should be hidden or transparent
              menuFooter.style.opacity = '0'
              menuFooter.style.display = 'block'
              return
            } else {
              menuFooter.style.display = 'none'
              menuFooter.style.opacity = '0'
              // Clear the drawer body padding
              const drawer = document.querySelector('.ant-drawer')
              if (drawer) {
                const drawerBody = drawer.querySelector('.ant-drawer-body')
                if (drawerBody) {
                  drawerBody.style.paddingBottom = ''
                  drawerBody.style.overflowY = ''
                  drawerBody.style.overflowX = ''
                }
              }
              return
            }
          }

          // Desktop: find the regular menu container
          const sider = this.$el?.querySelector('.ant-pro-sider') || document.querySelector('.ant-pro-sider')
          if (sider) {
            const siderRect = sider.getBoundingClientRect()
          const footerHeight = menuFooter.offsetHeight || 220
            menuFooter.style.position = 'fixed'
            menuFooter.style.left = `${siderRect.left}px`
            // Width is controlled by the CSS .collapsed class, so do not set it here
            menuFooter.style.bottom = '0px'
            menuFooter.style.zIndex = '100'
            menuFooter.style.display = 'block'
          // Write the footer height to a CSS variable for use in styles
          sider.style.setProperty('--menu-footer-height', `${footerHeight}px`)
          // Reserve footer height in the sidebar body and allow scrolling
          const siderChildren = sider.querySelector('.ant-layout-sider-children')
          if (siderChildren) {
            siderChildren.style.paddingBottom = `${footerHeight + 12}px`
            siderChildren.style.overflowY = 'auto'
            siderChildren.style.overflowX = 'hidden'
            siderChildren.style.webkitOverflowScrolling = 'touch'
          }
          // Further restrict menu area height so the footer does not cover it
          const menuScroll = sider.querySelector('.ant-pro-sider-menu') ||
            sider.querySelector('.ant-menu-root') ||
            sider.querySelector('.ant-menu')
          if (menuScroll) {
            const availableHeight = Math.max(siderRect.height - footerHeight - 12, 120)
            menuScroll.style.maxHeight = `${availableHeight}px`
            menuScroll.style.overflowY = 'auto'
            menuScroll.style.overflowX = 'hidden'
            menuScroll.style.webkitOverflowScrolling = 'touch'
          }
          } else {
            // Fall back to the default position if the menu cannot be found
            menuFooter.style.position = 'fixed'
            menuFooter.style.left = '0px'
            // Width is controlled by the CSS .collapsed class
            menuFooter.style.bottom = '0px'
            menuFooter.style.zIndex = '100'
            menuFooter.style.display = 'block'
          }
        })
      })
    },
    handleRefresh () {
      // Refresh only the content area by changing the key and forcing router-view to re-render
      this.refreshKey += 1
    },
    handleMediaQuery (val) {
      this.query = val
      if (this.isMobile && !val['screen-xs']) {
        this.isMobile = false
        this.$nextTick(() => {
          this.updateMenuFooterPosition()
        })
        return
      }
      if (!this.isMobile && val['screen-xs']) {
        this.isMobile = true
        this.collapsed = false
        this.settings.contentWidth = CONTENT_WIDTH_TYPE.Fluid
        // this.settings.fixSiderbar = false
        this.$nextTick(() => {
          this.updateMenuFooterPosition()
        })
      }
    },
    handleCollapse (val) {
      this.collapsed = val
      // Update the footer position when the menu collapse state changes
      // CSS transitions handle smooth width and position changes automatically
      this.$nextTick(() => {
        this.updateMenuFooterPosition()
      })
    },
    handleMobileMenuToggle () {
      // Listen for mobile menu open and close changes
      this.$nextTick(() => {
        setTimeout(() => {
          this.updateMenuFooterPosition()
        }, 300) // Wait for the drawer animation to complete
      })
    },
    handleSettingChange ({ type, value }) {
      type && (this.settings[type] = value)
      switch (type) {
        case 'theme':
          this.$store.commit(TOGGLE_NAV_THEME, value)
          break
        case 'primaryColor':
          this.$store.commit(TOGGLE_COLOR, value)
          break
        case 'layout':
          this.$store.commit(TOGGLE_LAYOUT, value)
          if (value === 'sidemenu') {
            this.settings.contentWidth = CONTENT_WIDTH_TYPE.Fluid
          } else {
            this.settings.fixSiderbar = false
            this.settings.contentWidth = CONTENT_WIDTH_TYPE.Fixed
          }
          break
        case 'contentWidth':
          this.settings[type] = value
          this.$store.commit(TOGGLE_CONTENT_WIDTH, value)
          break
        case 'fixedHeader':
          this.$store.commit(TOGGLE_FIXED_HEADER, value)
          break
        case 'autoHideHeader':
          this.$store.commit(TOGGLE_HIDE_HEADER, value)
          break
        case 'fixSiderbar':
          this.$store.commit(TOGGLE_FIXED_SIDEBAR, value)
          break
        case 'colorWeak':
          this.$store.commit(TOGGLE_WEAK, value)
          break
        case 'multiTab':
          this.$store.commit(TOGGLE_MULTI_TAB, value)
          break
      }
    }
  }
}
</script>

<style lang="less">
@import "./BasicLayout.less";
.ant-pro-sider-menu-sider.light .ant-menu-light {
  height: 60vh!important;
}
/* Fully hide all footers */
.basic-layout-wrapper {
  .ant-layout-footer {
    display: none !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
  }
}

/* Menu footer styles - positioned directly at the bottom of the menu */
.basic-layout-wrapper {
  position: relative;

  /* Custom menu footer - positioned in the menu area via CSS selectors */
  .custom-menu-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    z-index: 100;
    width: 256px; /* Unified fixed width: 256px */
    background: #001529; /* Default dark background */
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    /* Sync with the menu drawer animation by using the same timing and easing */
    /* Ant Design Vue Drawer uses 0.3s and cubic-bezier(0.78, 0.14, 0.15, 0.86) */
    transition: left 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86),
                width 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86),
                max-width 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86),
                opacity 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86);
    max-width: 256px;
    display: block; /* Visible by default */
    opacity: 1;

    &.collapsed {
      width: 80px; /* Menu width when collapsed */
      max-width: 80px;
    }

    /* Mobile: use a higher z-index when the menu is inside the drawer */
    @media (max-width: 768px) {
      z-index: 1001; /* The drawer z-index is usually 1000 */

      /* Hide the footer while the drawer is closed */
      &:not(.drawer-open) {
        display: none !important;
        opacity: 0;
      }

      /* While the drawer is animating, keep the footer transparent until the animation completes */
      &.drawer-animating {
        opacity: 0;
        transition: opacity 0.1s ease-out;
      }

      /* Show the footer only after the drawer is fully open and no longer animating */
      &.drawer-open:not(.drawer-animating) {
        opacity: 1;
        transition: left 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86),
                    width 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86),
                    max-width 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86),
                    opacity 0.3s cubic-bezier(0.78, 0.14, 0.15, 0.86) 0.1s; /* Delay visibility by 0.1s so the drawer appears first */
      }
    }

    /* Light theme */
    body.light &,
    .ant-pro-layout.light & {
      background: #fff;
      border-top-color: #e8e8e8;
      color: rgba(0, 0, 0, 0.85);

      .menu-footer-content {
        .footer-section {
          .section-links a {
            color: rgba(0, 0, 0, 0.65);
          }
        }
        .social-icon {
          background: rgba(0, 0, 0, 0.05);
          color: rgba(0, 0, 0, 0.65);
          &:hover {
            background: rgba(0, 0, 0, 0.1);
            color: rgba(0, 0, 0, 0.85);
          }
          .social-icon-svg {
            color: currentColor;
          }
        }
      }
    }

    /* Dark theme */
    body.dark &,
    body.realdark &,
    .ant-pro-layout.dark &,
    .ant-pro-layout.realdark & {
      background: #001529;
      border-top-color: rgba(255, 255, 255, 0.1);
      color: rgba(255, 255, 255, 0.65);

      .menu-footer-content {
        .footer-section {
          .section-links a {
            color: rgba(255, 255, 255, 0.65);
          }
        }
        .social-icon {
          background: rgba(255, 255, 255, 0.05);
          color: rgba(255, 255, 255, 0.65);
          &:hover {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.85);
          }
          .social-icon-svg {
            color: currentColor;
          }
        }
      }
    }

    .menu-footer-content {
      padding: 12px 16px;
      font-size: 11px;
      color: inherit;
      max-height: 30vh;
      overflow-y: auto;
      overflow-x: hidden;

      /* Hide scrollbars while preserving scrolling */
      scrollbar-width: thin;
      scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
      &::-webkit-scrollbar {
        width: 4px;
      }
      &::-webkit-scrollbar-track {
        background: transparent;
      }
      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
      }

      .footer-section {
        margin-bottom: 12px;
        text-align: center;

        &:last-child {
          margin-bottom: 0;
        }

        .section-title {
          font-size: 11px;
          font-weight: 500;
          margin-bottom: 6px;
          opacity: 0.8;
          color: inherit;
        }

        .section-links {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          flex-wrap: wrap;
          font-size: 10px;
          opacity: 0.7;

          a {
            cursor: pointer;
            color: inherit;
            text-decoration: underline;
            transition: opacity 0.2s;

            &:hover {
              opacity: 1;
            }
          }

          .separator {
            opacity: 0.5;
            margin: 0 2px;
          }
        }

        .social-icons {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 8px;
          margin-top: 6px;

          .social-icon {
            width: 15px;
            height: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
            cursor: pointer;
            opacity: 0.7;
            transition: all 0.2s;
            background: rgba(255, 255, 255, 0.05);
            text-decoration: none;
            overflow: hidden;

            &:hover {
              opacity: 1;
              background: rgba(255, 255, 255, 0.1);
              transform: translateY(-2px);
            }

            .social-icon-svg {
              width: 15x;
              height: 15px;
              color: currentColor;
            }

            .anticon {
              font-size: 16px;
            }

            .social-logo {
              width: 15px;
              height: 15px;
              object-fit: contain;
            }

            .social-icon-text {
              font-size: 10px;
              font-weight: bold;
            }
          }
        }

        &.copyright {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          opacity: 0.6;
          font-size: 10px;
        }

        &.version {
          margin-top: 4px;
          font-size: 9px;
          opacity: 0.4;
          text-align: center;
          letter-spacing: 1px;
        }
      }
    }

    .menu-footer-content-collapsed {
      text-align: center;
      padding: 16px;
      font-size: 12px;
      opacity: 0.6;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;

      .anticon {
        font-size: 16px;
      }

      &:hover {
        opacity: 1;
      }
    }
  }

  /* Watch menu collapse state and adjust width dynamically */
  ::v-deep .ant-pro-layout {
    &.ant-pro-sider-collapsed ~ .custom-menu-footer,
    .ant-pro-sider-collapsed ~ .custom-menu-footer {
      width: 80px;
    }
  }
}

/* Sidebar menu scrolling and reserved space for the custom footer */
.basic-layout-wrapper {
  .ant-layout-sider-children {
    padding-bottom: calc(var(--menu-footer-height, 220px) + 12px);
    overflow-y: auto;
    overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.15) transparent;

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.15);
      border-radius: 3px;
    }

    body.dark &,
    body.realdark &,
    .ant-pro-layout.dark &,
    .ant-pro-layout.realdark & {
      scrollbar-color: rgba(255, 255, 255, 0.25) transparent;

      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.25);
      }
    }
  }

  /* Force the sidebar and menu area to scroll so the footer does not cover them */
  .ant-pro-sider {
    height: 100vh;
    display: flex;
    flex-direction: column;

    .ant-layout-sider-children {
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }

    .ant-pro-sider-menu,
    .ant-menu-root,
    .ant-menu {
      flex: 1 1 auto;
      min-height: 0;
      max-height: calc(100vh - var(--menu-footer-height, 220px) - 24px);
      overflow-y: auto !important;
      overflow-x: hidden;
      -webkit-overflow-scrolling: touch;
    }
  }
}

/* Dark theme styles */
.basic-layout-wrapper.dark,
.basic-layout-wrapper.realdark {
  /* Header adaptation */
  .ant-pro-global-header {
    background: #001529 !important;
    color: rgba(255, 255, 255, 0.85) !important;

    .ant-pro-global-header-trigger {
      color: rgba(255, 255, 255, 0.85) !important;
      &:hover {
        background: rgba(255, 255, 255, 0.03) !important;
      }
    }

    .action {
      color: rgba(255, 255, 255, 0.85) !important;
      &:hover {
        background: rgba(255, 255, 255, 0.03) !important;
      }
    }
  }

  /* Content adaptation */
  .ant-pro-basicLayout-content {
    background-color: #141414 !important;
  }

  /* Ensure the layout itself is also dark */
  .ant-layout {
    background-color: #141414 !important;
  }
}

/* Mobile: fix the footer covering the menu */
@media (max-width: 768px) {
  /* Let the drawer body scroll and add bottom padding so the footer does not cover it */
  .ant-drawer.ant-drawer-open {
    /* Ensure the drawer container can render correctly */
    .ant-drawer-content-wrapper {
      overflow: visible;
    }

    .ant-drawer-content {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: visible;
    }

    .ant-drawer-wrapper-body {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: visible;
    }

    .ant-drawer-body {
      /* Let the menu content scroll */
      overflow-y: auto !important;
      overflow-x: hidden !important;
      /* Add bottom padding equal to the footer height, set dynamically by JS */
      /* Use 280px as the fallback default */
      padding-bottom: var(--footer-height, 280px) !important;
      /* Keep scrolling smooth */
      -webkit-overflow-scrolling: touch;
      /* Hide scrollbars while preserving scrolling */
      scrollbar-width: thin;
      scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
      &::-webkit-scrollbar {
        width: 4px;
      }
      &::-webkit-scrollbar-track {
        background: transparent;
      }
      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
        &:hover {
          background: rgba(255, 255, 255, 0.3);
        }
      }
      /* Ensure the menu content area has enough height */
      min-height: 0;
      flex: 1;
    }
  }
}

</style>
