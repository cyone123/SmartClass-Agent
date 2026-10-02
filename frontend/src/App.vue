<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import { useUserStore } from '@/store/user'

const userStore = useUserStore()

const handleUnauthorized = () => {
  userStore.handleUnauthorized()
}

onMounted(async () => {
  window.addEventListener('smartclass-unauthorized', handleUnauthorized)
  if (userStore.accessToken) {
    try {
      await userStore.hydrateCurrentUser()
    } catch {
      userStore.handleUnauthorized()
    }
  } else {
    userStore.openAuthDialog('login')
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('smartclass-unauthorized', handleUnauthorized)
})
</script>

<template>
  <router-view></router-view>
</template>

<style>
/* 全局样式已在 main.js 中引入 src/assets/styles/index.css */
</style>
