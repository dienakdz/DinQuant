/**
 * Default project settings
 * primaryColor - default theme color. If changes do not apply, clear localStorage
 * navTheme - sidebar theme ['dark', 'light'] with two theme options
 * colorWeak - color weak mode
 * layout - overall layout mode ['sidemenu', 'topmenu'] with two layout options
 * fixedHeader - fixed Header : boolean
 * fixSiderbar - fixed left sidebar : boolean
 * contentWidth - content layout: fluid | fixed
 *
 * storageOptions: {} - Vue-ls plugin options (localStorage/sessionStorage)
 *
 */

export const PYTHON_API_BASE_URL = process.env.VUE_APP_PYTHON_API_BASE_URL || 'http://localhost:5000'

export default {
  navTheme: 'light', // theme for nav menu
  primaryColor: '#13C2C2', // '#F5222D', // primary color of ant design
  layout: 'sidemenu', // nav menu position: `sidemenu` or `topmenu`
  contentWidth: 'Fluid', // layout of content: `Fluid` or `Fixed`, only works when layout is topmenu
  fixedHeader: true, // sticky header - pin the top navigation
  fixSiderbar: true, // sticky siderbar - pin the left sidebar
  colorWeak: false,
  menu: {
    locale: true
  },
  title: 'QuantDinger',
  pwa: false,
  iconfontUrl: '',
  production: process.env.NODE_ENV === 'production' && process.env.VUE_APP_PREVIEW !== 'true'

}
