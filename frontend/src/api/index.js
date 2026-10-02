import axios from 'axios'

// 创建 axios 实例
const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('smartclass_access_token') : ''
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem('smartclass_access_token')
        window.localStorage.removeItem('smartclass_current_user')
        window.dispatchEvent(new Event('smartclass-unauthorized'))
      }
    }
    return Promise.reject(error)
  }
)

export default request
