import request from '@/utils/request'

const api = {
  placeOrder: '/api/quick-trade/place-order',
  balance: '/api/quick-trade/balance',
  position: '/api/quick-trade/position',
  history: '/api/quick-trade/history',
  closePosition: '/api/quick-trade/close-position'
}

export function placeQuickTradeOrder (data) {
  return request({
    url: api.placeOrder,
    method: 'post',
    data
  })
}

export function getQuickTradeBalance (params) {
  return request({
    url: api.balance,
    method: 'get',
    params
  })
}

export function getQuickTradePosition (params) {
  return request({
    url: api.position,
    method: 'get',
    params
  })
}

export function getQuickTradeHistory (params) {
  return request({
    url: api.history,
    method: 'get',
    params
  })
}

export function closeQuickTradePosition (data) {
  return request({
    url: api.closePosition,
    method: 'post',
    data
  })
}
