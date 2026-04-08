import request from '@/utils/request'

/**
 * Get setting schema definitions
 */
export function getSettingsSchema () {
  return request({
    url: '/api/settings/schema',
    method: 'get'
  })
}

/**
 * Get current setting values
 */
export function getSettingsValues () {
  return request({
    url: '/api/settings/values',
    method: 'get'
  })
}

/**
 * Save settings
 * @param {Object} data - settings data
 */
export function saveSettings (data) {
  return request({
    url: '/api/settings/save',
    method: 'post',
    data
  })
}

/**
 * Test API connection
 * @param {string} service - service name (openrouter, finnhub, etc.)
 * @param {Object} params - extra parameters
 */
export function testConnection (service, params = {}) {
  return request({
    url: '/api/settings/test-connection',
    method: 'post',
    data: { service, ...params }
  })
}

/**
 * Query OpenRouter account balance
 */
export function getOpenRouterBalance () {
  return request({
    url: '/api/settings/openrouter-balance',
    method: 'get'
  })
}
