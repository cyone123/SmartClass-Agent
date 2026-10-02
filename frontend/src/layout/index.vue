<template>
  <div class="app-layout">
    <Sidebar class="sidebar-container" />
    <div class="main-container">
      <ChatPanel class="chat-panel" />
      <ContextPanel class="context-panel" />
    </div>
    <AuthDialog />
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
import ChatPanel from '@/components/ChatPanel/index.vue'
import ContextPanel from '@/components/ContextPanel/index.vue'
import AuthDialog from '@/components/AuthDialog.vue'
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: var(--bg-main);
}
.sidebar-container {
  width: var(--sidebar-width);
  height: 100%;
  border-right: 1px solid var(--border-color);
  background-color: var(--bg-sidebar);
}

.main-container {
  flex: 1;
  display: flex;
  height: 100%;
  overflow: hidden;
}

.chat-panel {
  flex: 1;
  height: 100%;
  position: relative;
}

.context-panel {
  width: var(--context-width);
  height: 100%;
  border-left: 1px solid var(--border-color);
  background-color: var(--bg-context);
}
</style>
