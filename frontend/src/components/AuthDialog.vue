<template>
  <Teleport to="body">
    <Transition name="auth-fade">
      <div v-if="authDialogVisible" class="auth-overlay">
        <div class="auth-panel">
          <div class="auth-header">
            <div>
              <h2>{{ isRegisterMode ? "创建教师账户" : "登录 SmartClass" }}</h2>
              <p>{{ isRegisterMode ? "注册后即可拥有独立的教学计划和资料空间。" : "请输入用户名和密码继续使用。" }}</p>
            </div>
          </div>

          <form class="auth-form" @submit.prevent="submitAuth">
            <label class="auth-field">
              <span>用户名</span>
              <input v-model.trim="form.username" type="text" autocomplete="username" />
            </label>

            <label v-if="isRegisterMode" class="auth-field">
              <span>显示名称</span>
              <input v-model.trim="form.displayName" type="text" autocomplete="name" />
            </label>

            <label class="auth-field">
              <span>密码</span>
              <input
                v-model="form.password"
                type="password"
                :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
              />
            </label>

            <button type="submit" class="auth-submit" :disabled="isSubmitting">
              <Loader2 v-if="isSubmitting" class="auth-spin" />
              <span>{{ isRegisterMode ? "注册并登录" : "登录" }}</span>
            </button>
          </form>

          <div class="auth-switch">
            <span>{{ isRegisterMode ? "已有账户？" : "还没有账户？" }}</span>
            <button type="button" @click="toggleMode">
              {{ isRegisterMode ? "去登录" : "注册新账户" }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue"
import { storeToRefs } from "pinia"
import { ElMessage } from "element-plus"
import { Loader2 } from "lucide-vue-next"

import { useUserStore } from "@/store/user"

const userStore = useUserStore()
const { authDialogVisible, authDialogMode } = storeToRefs(userStore)

const isSubmitting = ref(false)
const form = reactive({
  username: "",
  displayName: "",
  password: "",
})

const isRegisterMode = computed(() => authDialogMode.value === "register")

watch(authDialogMode, () => {
  form.password = ""
})

const toggleMode = () => {
  userStore.setAuthDialogMode(isRegisterMode.value ? "login" : "register")
}

const validateForm = () => {
  if (!form.username) {
    ElMessage.warning("请输入用户名")
    return false
  }
  if (isRegisterMode.value && !form.displayName) {
    ElMessage.warning("请输入显示名称")
    return false
  }
  if (!form.password || form.password.length < (isRegisterMode.value ? 8 : 1)) {
    ElMessage.warning(isRegisterMode.value ? "密码至少 8 位" : "请输入密码")
    return false
  }
  return true
}

const submitAuth = async () => {
  if (!validateForm() || isSubmitting.value) {
    return
  }

  isSubmitting.value = true
  try {
    if (isRegisterMode.value) {
      await userStore.register({
        username: form.username,
        display_name: form.displayName,
        password: form.password,
      })
    }
    await userStore.login({
      username: form.username,
      password: form.password,
    })
    userStore.closeAuthDialog()
    ElMessage.success(isRegisterMode.value ? "注册并登录成功" : "登录成功")
  } catch (error) {
    const message = error.response?.data?.detail || error.response?.data?.message || "认证失败"
    ElMessage.error(message)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(5px);
}

.auth-panel {
  width: min(420px, calc(100vw - 32px));
  padding: 28px;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.22);
}

.auth-header h2 {
  margin: 0;
  color: var(--text-main);
  font-size: 22px;
  font-weight: 700;
}

.auth-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.auth-form {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}

.auth-field {
  display: grid;
  gap: 8px;
}

.auth-field span {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.auth-field input {
  width: 100%;
  height: 40px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0 12px;
  color: var(--text-main);
  font-size: 14px;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.auth-field input:focus {
  border-color: rgba(79, 70, 229, 0.55);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.auth-submit {
  height: 42px;
  border: none;
  border-radius: 8px;
  background: var(--primary-color);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.auth-submit:hover:not(:disabled) {
  background: var(--primary-hover);
}

.auth-submit:disabled {
  cursor: not-allowed;
  opacity: 0.66;
}

.auth-spin {
  width: 16px;
  height: 16px;
  animation: auth-spin 1s linear infinite;
}

.auth-switch {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
  color: var(--text-secondary);
  font-size: 13px;
}

.auth-switch button {
  border: none;
  background: transparent;
  color: var(--primary-color);
  font-weight: 700;
  cursor: pointer;
}

.auth-fade-enter-active,
.auth-fade-leave-active {
  transition: opacity 0.2s ease;
}

.auth-fade-enter-from,
.auth-fade-leave-to {
  opacity: 0;
}

@keyframes auth-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
