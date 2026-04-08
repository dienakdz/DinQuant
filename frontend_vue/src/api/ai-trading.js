import request from '@/utils/request'

const api = {
  strategies: '/addons/quantdinger/strategy/strategies',
  createAIStrategy: '/addons/quantdinger/strategy/aiCreate',
  updateAIStrategy: '/addons/quantdinger/strategy/aiUpdate',
  deleteStrategy: '/addons/quantdinger/strategy/delete',
  startStrategy: '/addons/quantdinger/strategy/start',
  stopStrategy: '/addons/quantdinger/strategy/stop',
  testConnection: '/addons/quantdinger/strategy/testConnection',
  aiDecisions: '/addons/quantdinger/strategy/aiDecisions',
  getCryptoSymbols: '/addons/quantdinger/strategy/getCryptoSymbols'
}

/**
 * Get AI trading strategy list
 */
export function getStrategies () {
  return request({
    url: api.strategies,
    method: 'get'
  })
}

/**
 * Create AI trading strategy
 */
export function createAIStrategy (data) {
  return request({
    url: api.createAIStrategy,
    method: 'post',
    data
  })
}

/**
 * Update AI trading strategy
 */
export function updateAIStrategy (data) {
  return request({
    url: api.updateAIStrategy,
    method: 'post',
    data
  })
}

/**
 * Delete strategy
 */
export function deleteStrategy (strategyId) {
  return request({
    url: api.deleteStrategy,
    method: 'delete',
    params: { id: strategyId }
  })
}

/**
 * Start strategy
 */
export function startStrategy (strategyId) {
  return request({
    url: api.startStrategy,
    method: 'post',
    params: { id: strategyId }
  })
}

/**
 * Stop strategy
 */
export function stopStrategy (strategyId) {
  return request({
    url: api.stopStrategy,
    method: 'post',
    params: { id: strategyId }
  })
}

/**
 * Test exchange connection
 */
export function testConnection (data) {
  return request({
    url: api.testConnection,
    method: 'post',
    data
  })
}

/**
 * Get AI decision records
 */
export function getAIDecisions (strategyId, params) {
  return request({
    url: api.aiDecisions,
    method: 'get',
    params: {
      strategy_id: strategyId,
      ...params
    }
  })
}

/**
 * Get supported trading pairs
 */
export function getCryptoSymbols () {
  return request({
    url: api.getCryptoSymbols,
    method: 'get'
  })
}
