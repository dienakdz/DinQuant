import { isIE } from '@/utils/util'

// Local development already has a complete backend API, so mock is disabled
// to avoid intercepting real requests. Set this to true if you need mock data.
const ENABLE_MOCK = false

// Load mock services only outside production, or when preview mode is enabled.
if (ENABLE_MOCK && (process.env.NODE_ENV !== 'production' || process.env.VUE_APP_PREVIEW === 'true')) {
  if (isIE()) {
  }
  // Use synchronous loading so the mock layer is ready before Vuex requests
  // run. This prevents early GetInfo calls from bypassing mocked responses.
  const Mock = require('mockjs2')
  require('./services/auth')
  require('./services/user')
  require('./services/manage')
  require('./services/other')
  require('./services/tagCloud')
  require('./services/article')

  Mock.setup({
    timeout: 800 // setter delay time
  })
}
