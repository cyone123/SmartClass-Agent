import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getCurrentUserAPI, loginAPI, registerAPI } from '@/api/auth'

const TOKEN_STORAGE_KEY = 'smartclass_access_token'
const USER_STORAGE_KEY = 'smartclass_current_user'

const readStoredJSON = (key) => {
  if (typeof window === 'undefined') {
    return null
  }
  const raw = window.localStorage.getItem(key)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

const writeStoredJSON = (key, value) => {
  if (typeof window === 'undefined') {
    return
  }
  if (value == null) {
    window.localStorage.removeItem(key)
    return
  }
  window.localStorage.setItem(key, JSON.stringify(value))
}

export const useUserStore = defineStore('user', () => {
  const accessToken = ref(typeof window !== 'undefined' ? window.localStorage.getItem(TOKEN_STORAGE_KEY) || '' : '')
  const currentUser = ref(readStoredJSON(USER_STORAGE_KEY))
  const authDialogVisible = ref(false)
  const authDialogMode = ref('login')

  const isLoggedIn = computed(() => Boolean(accessToken.value && currentUser.value))

  const persistSession = (token, user) => {
    accessToken.value = token || ''
    currentUser.value = user || null
    if (typeof window !== 'undefined') {
      if (token) {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
      } else {
        window.localStorage.removeItem(TOKEN_STORAGE_KEY)
      }
    }
    writeStoredJSON(USER_STORAGE_KEY, user || null)
  }

  const openAuthDialog = (mode = 'login') => {
    authDialogMode.value = mode
    authDialogVisible.value = true
  }

  const closeAuthDialog = () => {
    authDialogVisible.value = false
  }

  const setAuthDialogMode = (mode) => {
    authDialogMode.value = mode
  }

  const setSession = (token, user) => {
    persistSession(token, user)
  }

  const hydrateCurrentUser = async () => {
    if (!accessToken.value) {
      return null
    }
    const response = await getCurrentUserAPI()
    const user = response.data || response
    currentUser.value = user
    writeStoredJSON(USER_STORAGE_KEY, user)
    return user
  }

  const login = async (payload) => {
    const response = await loginAPI(payload)
    const data = response.data || response
    persistSession(data.access_token, data.user)
    return data
  }

  const register = async (payload) => {
    const response = await registerAPI(payload)
    return response.data || response
  }

  const logout = () => {
    persistSession('', null)
    authDialogVisible.value = false
  }

  const handleUnauthorized = () => {
    logout()
    openAuthDialog('login')
  }

  return {
    accessToken,
    currentUser,
    authDialogVisible,
    authDialogMode,
    isLoggedIn,
    openAuthDialog,
    closeAuthDialog,
    setAuthDialogMode,
    setSession,
    hydrateCurrentUser,
    login,
    register,
    logout,
    handleUnauthorized,
  }
})
