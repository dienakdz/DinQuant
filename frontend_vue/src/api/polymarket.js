import request from '@/utils/request'

const api = {
  analyze: '/api/polymarket/analyze',
  history: '/api/polymarket/history'
}

export function analyzePolymarket (data) {
  return request({
    url: api.analyze,
    method: 'post',
    data,
    timeout: 120000
  })
}

export function getPolymarketHistory (params) {
  return request({
    url: api.history,
    method: 'get',
    params
  })
}
