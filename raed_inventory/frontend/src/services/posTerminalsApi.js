import api from './api'

const BASE = '/audit/pos-terminals'

export const posTerminalsApi = {
  list(params) {
    return api.get(BASE, { params })
  },
  create(body) {
    return api.post(BASE, body)
  },
  update(id, body) {
    return api.patch(`${BASE}/${id}`, body)
  },
}
