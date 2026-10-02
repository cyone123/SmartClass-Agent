<template>
  <div class="sidebar">
    <div class="logo-area">
      <span class="logo-text">智课伴侣</span>
      <PanelLeftClose class="collapse-btn"/>
    </div>

    <div class="plan-actions">
      <button type="button" class="new-plan-btn" @click="handleNewPlan">
        <Plus class="btn-icon" />
        新建教学计划
      </button>

      <div class="plan-search-shell">
        <Search class="search-icon" />
        <input
          v-model="planSearchKeyword"
          type="text"
          class="plan-search-input"
          placeholder="搜索教学计划或会话"
        />
      </div>
    </div>

    <div class="menu-container">
        <div v-for="plan in plans" :key="plan.id" class="plan-group">
          <div class="plan-row" :class="{ 'is-editing': plan.isEditing }">
          <div class="plan-header" @click="handlePlanHeaderClick(plan)">
            <ChevronRight class="toggle-icon" :class="{ 'is-open': openPlans.includes(plan.id) }" />
            <FolderClosed v-if="!openPlans.includes(plan.id)" class="plan-icon" />
            <FolderOpen v-else class="plan-icon" />

            <input
              v-if="plan.isEditing"
              v-model="plan.tempName"
              v-focus
              class="edit-input"
              type="text"
              @click.stop
              @keyup.enter="saveNewPlan(plan)"
              @keyup.esc="cancelPlanEdit(plan)"
            />

            <span v-else class="plan-name" :title="plan.name">{{ plan.name }}</span>
          </div>

          <div v-if="plan.isEditing" class="item-actions editing-actions">
            <button
              type="button"
              class="action-btn confirm-btn"
              title="保存"
              @click.stop.prevent="saveNewPlan(plan)"
            >
              <Check class="action-icon" />
            </button>
            <button type="button" class="action-btn" title="取消" @click.stop.prevent="cancelPlanEdit(plan)">
              <X class="action-icon" />
            </button>
          </div>

          <div v-else class="item-actions plan-item-actions">
            <button type="button" class="action-btn" title="重命名" @click.stop.prevent="startEditPlan(plan)">
              <Pencil class="action-icon" />
            </button>
            <button
              type="button"
              class="action-btn delete-btn"
              title="删除"
              @click.stop.prevent="removePlan(plan)"
            >
              <Trash2 class="action-icon" />
            </button>
          </div>
        </div>

        <div v-show="openPlans.includes(plan.id)" class="session-list">
          <div
            v-for="session in plan.sessions"
            :key="session.id"
            class="session-row"
            :class="{ 'is-active': activeSessionId === session.id.toString(), 'is-editing': session.isEditing }"
          >
            <div class="session-item" @click="handleSessionItemClick(plan, session)">
              <MessageSquare class="session-icon" />

              <input
                v-if="session.isEditing"
                v-model="session.tempName"
                v-focus
                class="edit-input"
                type="text"
                @click.stop
                @keyup.enter="saveNewSession(plan, session)"
                @keyup.esc="cancelSessionEdit(plan, session)"
              />

              <span v-else class="session-name">{{ session.name }}</span>
            </div>

            <div v-if="session.isEditing" class="item-actions editing-actions">
              <button
                type="button"
                class="action-btn confirm-btn"
                title="保存"
                @click.stop.prevent="saveNewSession(plan, session)"
              >
                <Check class="action-icon" />
              </button>
              <button
                type="button"
                class="action-btn"
                title="取消"
                @click.stop.prevent="cancelSessionEdit(plan, session)"
              >
                <X class="action-icon" />
              </button>
            </div>

            <div v-else class="item-actions session-item-actions">
              <button
                type="button"
                class="action-btn"
                title="重命名"
                @click.stop.prevent="startEditSession(session)"
              >
                <Pencil class="action-icon" />
              </button>
              <button
                type="button"
                class="action-btn delete-btn"
                title="删除"
                @click.stop.prevent="removeSession(plan, session)"
              >
                <Trash2 class="action-icon" />
              </button>
            </div>
          </div>

          <div class="session-item new-session-item" @click="handleSelectSession(`new_session_${plan.id}`, plan.id)">
            <PlusCircle class="session-icon" />
            <span>新建会话</span>
          </div>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <Transition name="account-sheet">
        <div v-if="isAccountDrawerVisible" class="account-drawer">
          <div class="drawer-header">
            <span>切换账户</span>
            <span class="drawer-caption"><LogOut class="log-out"/></span>
          </div>

          <div class="account-row current-account-row">
            <div class="account-avatar" :style="{ background: currentAccount.avatarGradient }">
              {{ getAccountInitials(currentAccount.name) }}
            </div>
            <div class="account-meta">
              <div class="account-name-line">
                <span class="account-name">{{ currentAccount.name }}</span>
                <span class="active-pill">当前</span>
              </div>
              <div class="account-subtitle">{{ currentAccount.email }}</div>
            </div>
          </div>

          <button v-if="currentUser" type="button" class="add-account-btn" @click="logout">
            <LogOut class="drawer-icon" />
            退出登录
          </button>
          <button v-else type="button" class="add-account-btn" @click="openLoginDialog">
            <UserPlus class="drawer-icon" />
            立即登录
          </button>
        </div>
      </Transition>

      <div class="user-bar">
        <button type="button" class="user-entry" @click="toggleAccountDrawer">
          <div class="user-avatar" :style="{ background: currentAccount.avatarGradient }">
            {{ getAccountInitials(currentAccount.name) }}
          </div>
          <div class="user-meta">
            <span class="user-name">{{ currentAccount.name }}</span>
            <span class="user-role">{{ currentAccount.role }}</span>
          </div>
          <ChevronUp class="user-chevron" :class="{ 'is-open': isAccountDrawerVisible }" />
        </button>

        <button type="button" class="settings-trigger" title="设置" @click.stop="openSettingsPanel">
          <Settings2 class="settings-icon" />
        </button>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="isSettingsVisible" class="settings-overlay" @click.self="closeSettingsPanel">
          <div class="settings-modal">
            <div class="settings-header">
              <div>
                <h3>系统设置</h3>
                <p>以下内容为前端 mock 展示，用于预览后续设置面板形态。</p>
              </div>
              <button type="button" class="settings-close-btn" @click="closeSettingsPanel">
                <X class="settings-close-icon" />
              </button>
            </div>

            <div class="settings-body">
              <aside class="settings-nav">
                <button
                  type="button"
                  v-for="section in settingsSections"
                  :key="section.key"
                  class="settings-nav-item"
                  :class="{ 'is-active': activeSettingsSection === section.key }"
                  @click="activeSettingsSection = section.key"
                >
                  <component :is="section.icon" class="settings-nav-icon" />
                  <span>{{ section.label }}</span>
                </button>
              </aside>

              <section class="settings-content">
                <template v-if="activeSettingsSection === 'account'">
                  <div class="settings-card hero-card">
                    <div>
                      <div class="card-eyebrow">账户与安全</div>
                      <h4>{{ currentAccount.name }}</h4>
                      <p>这里展示当前登录账户、会话状态与退出入口。</p>
                    </div>
                    <div class="hero-badge">已登录</div>
                  </div>

                  <div class="settings-grid">
                    <div class="settings-card">
                      <h5>当前登录账户</h5>
                      <p>{{ currentAccount.email }}</p>
                      <span class="card-note">角色：{{ currentAccount.role }}</span>
                    </div>
                    <div class="settings-card">
                      <h5>登录状态</h5>
                      <p>当前会话已绑定 JWT access token。</p>
                      <span class="card-note">可随时退出并重新登录。</span>
                    </div>
                    <div class="settings-card">
                      <h5>认证说明</h5>
                      <p>所有计划、会话、文件与产物都按当前用户隔离。</p>
                    </div>
                  </div>
                </template>

                <template v-else-if="activeSettingsSection === 'memory'">
                  <div class="settings-card hero-card memory-hero-card">
                    <div>
                      <div class="card-eyebrow">长期记忆</div>
                      <h4>{{ currentAccount.name }}</h4>
                      <p>这些记忆会跨会话影响助手的回答方式、偏好理解与可复用教学经验。</p>
                    </div>
                    <button type="button" class="memory-refresh-btn" :disabled="isMemoryLoading" @click="refreshMemories">
                      <RefreshCw class="memory-action-icon" />
                      刷新
                    </button>
                  </div>

                  <div class="memory-toolbar">
                    <div class="memory-tabs">
                      <button
                        type="button"
                        class="memory-tab"
                        :class="{ 'is-active': activeMemoryKind === 'profile' }"
                        @click="activeMemoryKind = 'profile'"
                      >
                        画像偏好
                      </button>
                      <button
                        type="button"
                        class="memory-tab"
                        :class="{ 'is-active': activeMemoryKind === 'experience' }"
                        @click="activeMemoryKind = 'experience'"
                      >
                        经验记忆
                      </button>
                    </div>
                    <div class="memory-search">
                      <Search class="memory-search-icon" />
                      <input v-model="memorySearchKeyword" type="text" placeholder="搜索记忆" />
                    </div>
                  </div>

                  <div class="memory-list">
                    <div v-if="isMemoryLoading" class="memory-empty">正在加载长期记忆...</div>
                    <div v-else-if="filteredMemoryItems.length === 0" class="memory-empty">暂无匹配的长期记忆</div>
                    <template v-else>
                    <div v-for="memory in filteredMemoryItems" :key="memory.id" class="memory-card">
                      <template v-if="editingMemoryId === memory.id">
                        <input v-model="editingMemoryDraft.title" class="memory-input" type="text" placeholder="标题" />
                        <input v-model="editingMemoryDraft.summary" class="memory-input" type="text" placeholder="摘要" />
                        <textarea v-model="editingMemoryDraft.content" class="memory-textarea" rows="4" placeholder="完整内容"></textarea>
                        <input v-model="editingMemoryDraft.tagsText" class="memory-input" type="text" placeholder="标签，用英文逗号分隔" />
                        <div class="memory-card-actions">
                          <button type="button" class="memory-icon-btn primary" title="保存" @click="saveMemory(memory)">
                            <Save class="memory-action-icon" />
                          </button>
                          <button type="button" class="memory-icon-btn" title="取消" @click="cancelEditMemory">
                            <X class="memory-action-icon" />
                          </button>
                        </div>
                      </template>
                      <template v-else>
                        <div class="memory-card-head">
                          <div>
                            <h5>{{ memory.title }}</h5>
                            <p>{{ memory.summary }}</p>
                          </div>
                          <div class="memory-card-actions">
                            <button type="button" class="memory-icon-btn" title="编辑" @click="startEditMemory(memory)">
                              <Pencil class="memory-action-icon" />
                            </button>
                            <button type="button" class="memory-icon-btn danger" title="删除" @click="removeMemory(memory)">
                              <Trash2 class="memory-action-icon" />
                            </button>
                          </div>
                        </div>
                        <div v-if="memory.tags?.length" class="memory-tags">
                          <span v-for="tag in memory.tags" :key="tag" class="memory-tag">{{ tag }}</span>
                        </div>
                        <div class="memory-meta">{{ memory.updated_at || memory.created_at || "未记录时间" }}</div>
                      </template>
                    </div>
                    </template>
                  </div>
                </template>

                <template v-else-if="activeSettingsSection === 'privacy'">
                  <div class="settings-card hero-card soft-card">
                    <div>
                      <div class="card-eyebrow">隐私政策</div>
                      <h4>数据使用说明</h4>
                      <p>这里预留隐私政策、数据保留时长、导出与删除说明等内容展示位。</p>
                    </div>
                  </div>

                  <div class="settings-stack">
                    <div class="settings-card">
                      <h5>数据授权范围</h5>
                      <p>展示课堂资料、会话记录、产物与多模态附件的处理授权说明。</p>
                    </div>
                    <div class="settings-card">
                      <h5>导出与删除</h5>
                      <p>后续可放置导出教学计划、清理历史会话、知识库删除等入口。</p>
                    </div>
                  </div>
                </template>

                <template v-else-if="activeSettingsSection === 'appearance'">
                  <div class="settings-card hero-card warm-card">
                    <div>
                      <div class="card-eyebrow">外观设置</div>
                      <h4>界面主题与布局</h4>
                      <p>用于演示主题切换、字号、边栏宽度与消息显示偏好的设置区块。</p>
                    </div>
                  </div>

                  <div class="settings-grid">
                    <div class="settings-card option-card">
                      <span class="option-label">主题模式</span>
                      <div class="option-pills">
                        <span class="option-pill is-active">浅色</span>
                        <span class="option-pill">深色</span>
                        <span class="option-pill">跟随系统</span>
                      </div>
                    </div>
                    <div class="settings-card option-card">
                      <span class="option-label">阅读密度</span>
                      <div class="option-pills">
                        <span class="option-pill">紧凑</span>
                        <span class="option-pill is-active">舒适</span>
                        <span class="option-pill">宽松</span>
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else-if="activeSettingsSection === 'models'">
                  <div class="settings-card hero-card tech-card">
                    <div>
                      <div class="card-eyebrow">大模型配置</div>
                      <h4>教学智能体模型编排</h4>
                      <p>这里预留对话模型、Embedding、视觉模型、语音模型等配置项。</p>
                    </div>
                    <div class="hero-badge">实验性</div>
                  </div>

                  <div class="settings-stack">
                    <div class="settings-card">
                      <h5>对话模型</h5>
                      <p>GPT-4.1 / GPT-4o / 自定义 OpenAI 兼容接口</p>
                      <span class="card-note">后续接入真实配置表单与环境校验。</span>
                    </div>
                    <div class="settings-card">
                      <h5>检索与嵌入</h5>
                      <p>Embedding 模型、向量维度、召回数量与重排策略。</p>
                    </div>
                    <div class="settings-card">
                      <h5>多模态能力</h5>
                      <p>视频理解、语音转写、文档生成与技能路由等高级配置入口。</p>
                    </div>
                  </div>
                </template>
              </section>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import {
  Bot,
  Brain,
  Check,
  LogOut,
  ChevronRight,
  ChevronUp,
  PanelLeftClose,
  FileLock2,
  FolderClosed,
  FolderOpen,
  MessageSquare,
  Palette,
  Pencil,
  Plus,
  PlusCircle,
  Search,
  Settings2,
  ShieldCheck,
  RefreshCw,
  Save,
  Trash2,
  UserPlus,
  X,
} from "lucide-vue-next"
import { ElMessage, ElMessageBox } from "element-plus"

import {
  deleteMemoryAPI,
  getMemoryListAPI,
  updateMemoryAPI,
} from "@/api/memory"
import {
  addPlanAPI,
  addSessionAPI,
  deletePlanAPI,
  deleteSessionAPI,
  getPlanAndSessionListAPI,
  updatePlanAPI,
  updateSessionAPI,
} from "@/api/session"
import { useSessionStore } from "@/store/session"
import { useUserStore } from "@/store/user"
import { storeToRefs } from "pinia"

const vFocus = {
  mounted: (el) => {
    requestAnimationFrame(() => {
      if (!document.contains(el)) {
        return
      }
      el.focus()
      if (typeof el.select === "function") {
        el.select()
      }
    })
  },
}

const settingsSections = [
  { key: "account", label: "账户与安全", icon: ShieldCheck },
  { key: "memory", label: "长期记忆", icon: Brain },
  { key: "privacy", label: "隐私政策", icon: FileLock2 },
  { key: "appearance", label: "外观设置", icon: Palette },
  { key: "models", label: "大模型配置", icon: Bot },
]

const plans = ref([])
const planSearchKeyword = ref("")
const openPlans = ref([1])
const isAccountDrawerVisible = ref(false)
const isSettingsVisible = ref(false)
const activeSettingsSection = ref("account")
const activeMemoryKind = ref("profile")
const memorySearchKeyword = ref("")
const memoryItems = ref([])
const isMemoryLoading = ref(false)
const editingMemoryId = ref("")
const editingMemoryDraft = ref({
  title: "",
  summary: "",
  content: "",
  tagsText: "",
})

const sessionStore = useSessionStore()
const userStore = useUserStore()
const { activeSessionId } = storeToRefs(sessionStore)
const { currentUser } = storeToRefs(userStore)

const currentAccount = computed(() => {
  const user = currentUser.value
  if (!user) {
    return {
      name: "未登录",
      role: "访客",
      email: "请先登录",
      avatarGradient: "linear-gradient(135deg, #64748b 0%, #94a3b8 100%)",
    }
  }
  return {
    name: user.display_name || user.username,
    role: user.role === "admin" ? "系统管理员" : "教师",
    email: user.username,
    avatarGradient: user.role === "admin"
      ? "linear-gradient(135deg, #f97316 0%, #ef4444 100%)"
      : "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
  }
})

const filteredMemoryItems = computed(() => {
  const keyword = memorySearchKeyword.value.trim().toLowerCase()
  const items = memoryItems.value.filter((item) => item.kind === activeMemoryKind.value)
  if (!keyword) {
    return items
  }
  return items.filter((item) => {
    const searchable = `${item.title || ""} ${item.summary || ""} ${item.content || ""}`.toLowerCase()
    return searchable.includes(keyword)
  })
})

watch(isSettingsVisible, (visible) => {
  document.body.style.overflow = visible ? "hidden" : ""
  if (visible) {
    isAccountDrawerVisible.value = false
    if (activeSettingsSection.value === "memory") {
      refreshMemories()
    }
  }
})

watch(activeSettingsSection, (section) => {
  if (section === "memory" && isSettingsVisible.value) {
    refreshMemories()
  }
})

watch(
  currentUser,
  async (user, previousUser) => {
    if (user?.id === previousUser?.id) {
      return
    }

    plans.value = []
    openPlans.value = []
    sessionStore.resetActiveSession()

    if (user) {
      await getPlanAndSessionList()
      if (isSettingsVisible.value && activeSettingsSection.value === "memory") {
        refreshMemories()
      }
    } else {
      memoryItems.value = []
    }
  }
)

onMounted(() => {
  if (currentUser.value) {
    getPlanAndSessionList()
  }
})

onBeforeUnmount(() => {
  document.body.style.overflow = ""
})

const togglePlan = (id) => {
  const index = openPlans.value.indexOf(id)
  if (index > -1) {
    openPlans.value.splice(index, 1)
    return
  }
  openPlans.value.push(id)
}

const isTempPlan = (plan) => typeof plan.id === "string" && plan.id.startsWith("temp_")

const isTempSession = (session) => typeof session.id === "string" && session.id.startsWith("temp_")

const handlePlanHeaderClick = (plan) => {
  if (plan.isEditing) {
    return
  }
  togglePlan(plan.id)
}

const startEditPlan = (plan) => {
  plan.tempName = plan.name
  plan.isEditing = true
}

const cancelPlanEdit = (plan) => {
  if (!plan.isEditing) {
    return
  }

  if (isTempPlan(plan)) {
    const planIndex = plans.value.findIndex((item) => item.id === plan.id)
    if (planIndex > -1) {
      plans.value.splice(planIndex, 1)
    }

    const openIndex = openPlans.value.indexOf(plan.id)
    if (openIndex > -1) {
      openPlans.value.splice(openIndex, 1)
    }
    return
  }

  plan.tempName = plan.name
  plan.isEditing = false
}

const startEditSession = (session) => {
  session.tempName = session.name
  session.isEditing = true
}

const cancelSessionEdit = (plan, session) => {
  if (!session.isEditing) {
    return
  }

  if (isTempSession(session)) {
    const sessionIndex = plan.sessions.findIndex((item) => item.id === session.id)
    if (sessionIndex > -1) {
      plan.sessions.splice(sessionIndex, 1)
    }
    return
  }

  session.tempName = session.name
  session.isEditing = false
}

const removePlan = async (plan) => {
  const confirmed = window.confirm("确定要删除该教学计划吗？同时会删除其所有会话内容。")
  if (!confirmed) {
    return
  }

  try {
    await deletePlanAPI(plan.id)
    const index = plans.value.findIndex((item) => item.id === plan.id)
    if (index > -1) {
      plans.value.splice(index, 1)
    }
    ElMessage.success("删除成功")
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除计划失败", error)
    }
  }
}

const removeSession = async (plan, session) => {
  try {
    await ElMessageBox.confirm(
      "确定要删除该教学计划吗？同时会删除其所有会话内容。",
      "删除确认",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    )


    await deleteSessionAPI(session.id)
    const index = plan.sessions.findIndex((item) => item.id === session.id)
    if (index > -1) {
      plan.sessions.splice(index, 1)
    }

    if (activeSessionId.value === session.id.toString()) {
      sessionStore.setActiveSession("", "", plan.id)
    }
    ElMessage.success("删除成功")
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除会话失败", error)
    }
  }
}

const handleNewPlan = () => {
  const newPlan = {
    id: `temp_plan_${Date.now()}`,
    name: "新计划",
    tempName: "新计划",
    sessions: [],
    isEditing: true,
  }
  plans.value.unshift(newPlan)
  if (!openPlans.value.includes(newPlan.id)) {
    openPlans.value.push(newPlan.id)
  }
}

const saveNewPlan = async (plan) => {
  if (!plan.isEditing) {
    return
  }

  const newName = plan.tempName?.trim()
  if (!newName) {
    ElMessage.warning("教学计划名称不能为空")
    return
  }

  const isNew = isTempPlan(plan)
  if (!isNew && newName === plan.name) {
    plan.isEditing = false
    return
  }

  if (isNew) {
    const oldId = plan.id
    try {
      const res = await addPlanAPI({ name: newName })
      if (res.data?.id) {
        plan.id = res.data.id
      }

      plan.name = newName
      plan.tempName = newName
      plan.isEditing = false

      const openIndex = openPlans.value.indexOf(oldId)
      if (openIndex > -1) {
        openPlans.value[openIndex] = plan.id
      }
    } catch (error) {
      console.error("新建教学计划失败", error)
      ElMessage.error("新建教学计划失败")
    }
    return
  }

  try {
    await updatePlanAPI({ id: plan.id, name: newName })
    plan.name = newName
    plan.tempName = newName
    plan.isEditing = false
    ElMessage.success("重命名成功")
  } catch (error) {
    console.error("重命名计划失败", error)
    ElMessage.error("重命名计划失败")
  }
}

const handleSelectSession = (index, planId) => {
  if (index?.startsWith("new_session_")) {
    handleNewSession(planId)
    return
  }

  let targetThreadId = ""
  for (const plan of plans.value) {
    if (!plan.sessions) {
      continue
    }
    const session = plan.sessions.find((item) => item.id.toString() === index.toString())
    if (session) {
      targetThreadId = session.thread_id || ""
      break
    }
  }

  sessionStore.setActiveSession(index, targetThreadId, planId)
}

const handleNewSession = (planId) => {
  const targetPlan = plans.value.find((plan) => plan.id === planId)
  if (!targetPlan) {
    return
  }

  const newSession = {
    id: `temp_session_${Date.now()}`,
    name: "新会话",
    tempName: "新会话",
    isEditing: true,
  }

  if (!targetPlan.sessions) {
    targetPlan.sessions = []
  }
  targetPlan.sessions.unshift(newSession)
}

const handleSessionItemClick = (plan, session) => {
  if (session.isEditing) {
    return
  }
  handleSelectSession(session.id.toString(), plan.id)
}

const saveNewSession = async (plan, session) => {
  if (!session.isEditing) {
    return
  }

  const newName = session.tempName?.trim()
  if (!newName) {
    ElMessage.warning("会话名称不能为空")
    return
  }

  const isNew = isTempSession(session)
  if (!isNew && newName === session.name) {
    session.isEditing = false
    return
  }

  if (isNew) {
    try {
      const res = await addSessionAPI({ plan_id: plan.id, name: newName })
      if (res.data?.id) {
        session.id = res.data.id
      }
      if (res.data?.thread_id) {
        session.thread_id = res.data.thread_id
      }
      session.name = newName
      session.tempName = newName
      session.isEditing = false
      sessionStore.setActiveSession(session.id.toString(), session.thread_id || "", plan.id)
    } catch (error) {
      console.error("新建会话失败", error)
      ElMessage.error("新建会话失败")
    }
    return
  }

  try {
    await updateSessionAPI({ ...session, name: newName })
    session.name = newName
    session.tempName = newName
    session.isEditing = false
    ElMessage.success("重命名成功")
  } catch (error) {
    console.error("重命名会话失败", error)
    ElMessage.error("重命名会话失败")
  }
}

const getPlanAndSessionList = async () => {
  try {
    const res = await getPlanAndSessionListAPI()
    if (res.data) {
      plans.value = res.data

      if (!activeSessionId.value && res.data.length > 0 && res.data[0].sessions?.length > 0) {
        const firstSession = res.data[0].sessions[0]
        sessionStore.setActiveSession(
          firstSession.id.toString(),
          firstSession.thread_id || "",
          res.data[0].id
        )
        if (!openPlans.value.includes(res.data[0].id)) {
          openPlans.value.push(res.data[0].id)
        }
      } else if (activeSessionId.value) {
        let targetThreadId = ""
        let targetPlanId = ""
        for (const plan of plans.value) {
          if (!plan.sessions) {
            continue
          }
          const session = plan.sessions.find(
            (item) => item.id.toString() === activeSessionId.value.toString()
          )
          if (session) {
            targetThreadId = session.thread_id || ""
            targetPlanId = plan.id
            break
          }
        }
        sessionStore.setActiveSession(activeSessionId.value, targetThreadId, targetPlanId)
      }
    }
  } catch (error) {
    console.error("获取教学计划和会话列表失败", error)
  }
}

const getAccountInitials = (name) => {
  return (name || "用户").trim().slice(0, 2).toUpperCase()
}

const refreshMemories = async () => {
  isMemoryLoading.value = true
  try {
    const res = await getMemoryListAPI()
    memoryItems.value = res.data?.items || []
  } catch (error) {
    console.error("加载长期记忆失败", error)
    ElMessage.error("加载长期记忆失败")
  } finally {
    isMemoryLoading.value = false
  }
}

const startEditMemory = (memory) => {
  editingMemoryId.value = memory.id
  editingMemoryDraft.value = {
    title: memory.title || "",
    summary: memory.summary || "",
    content: memory.content || "",
    tagsText: (memory.tags || []).join(", "),
  }
}

const cancelEditMemory = () => {
  editingMemoryId.value = ""
  editingMemoryDraft.value = {
    title: "",
    summary: "",
    content: "",
    tagsText: "",
  }
}

const saveMemory = async (memory) => {
  const draft = editingMemoryDraft.value
  const title = draft.title.trim()
  const content = draft.content.trim()
  if (!title || !content) {
    ElMessage.warning("标题和内容不能为空")
    return
  }
  try {
    await updateMemoryAPI(memory.kind, memory.id, {
      title,
      summary: draft.summary.trim() || content.slice(0, 120),
      content,
      tags: draft.tagsText
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    })
    cancelEditMemory()
    await refreshMemories()
    ElMessage.success("长期记忆已保存")
  } catch (error) {
    console.error("保存长期记忆失败", error)
    ElMessage.error("保存长期记忆失败")
  }
}

const removeMemory = async (memory) => {
  try {
    await ElMessageBox.confirm(
      "确定删除这条长期记忆吗？删除后不会再参与后续会话。",
      "删除长期记忆",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      }
    )
    await deleteMemoryAPI(memory.kind, memory.id)
    await refreshMemories()
    ElMessage.success("长期记忆已删除")
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除长期记忆失败", error)
      ElMessage.error("删除长期记忆失败")
    }
  }
}

const toggleAccountDrawer = () => {
  isAccountDrawerVisible.value = !isAccountDrawerVisible.value
}

const openLoginDialog = () => {
  isAccountDrawerVisible.value = false
  userStore.openAuthDialog("login")
}

const logout = () => {
  userStore.logout()
  isAccountDrawerVisible.value = false
  ElMessage.success("已退出登录")
}

const openSettingsPanel = () => {
  activeSettingsSection.value = "account"
  isSettingsVisible.value = true
}

const closeSettingsPanel = () => {
  isSettingsVisible.value = false
}
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.logo-area {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
  border-bottom: 1px solid var(--border-color);
}

.logo-text {
  letter-spacing: 0.02em;
}

.collapse-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 6px;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.collapse-btn:hover {
  background-color: #f1f5f9;
  color: var(--text-main);
}

.plan-actions {
  padding: 16px 20px;
}

.new-plan-btn {
  width: 100%;
  border-radius: 80px;/*var(--border-radius);*/
  background-color: var(--primary-color);
  color: white;
  border: none;
  padding: 10px 0;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: var(--shadow-sm);
}

.new-plan-btn:hover {
  background-color: var(--primary-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.btn-icon {
  width: 16px;
  height: 16px;
  margin-right: 6px;
}

.plan-search-shell {
  position: relative;
  margin-top: 12px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  width: 14px;
  height: 14px;
  color: var(--text-disabled);
  transform: translateY(-50%);
  pointer-events: none;
}

.plan-search-input {
  width: 100%;
  height: 32px;
  padding: 0 12px 0 36px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-main);
  font-size: 12px;
  outline: none;
  transition: all 0.2s ease;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.03);
}

.plan-search-input::placeholder {
  color: var(--text-disabled);
}

.plan-search-input:focus {
  border-color: rgba(79, 70, 229, 0.35);
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.08);
}

.menu-container {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 12px;

  /* &::-webkit-scrollbar {
    width: 10px;
    background: rgba(245,245,245,0.8);
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(73, 61, 206,0.6);
    border: 2px solid #fff;
    border-radius: 5px;
    background-clip: padding-box;
  } */
}

.plan-group {
  margin-bottom: 4px;
}

.plan-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.plan-header {
  display: flex;
  align-items: center;
  height: 36px;
  flex: 1;
  min-width: 0;
  padding: 0 8px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-main);
  font-weight: 500;
  font-size: 13px;
  transition: background-color 0.15s ease;
}

.plan-header:hover {
  background-color: rgba(226, 232, 240, 0.5);
}

.toggle-icon {
  width: 14px;
  height: 14px;
  margin-right: 6px;
  color: var(--text-disabled);
  transition: transform 0.2s ease;
}

.toggle-icon.is-open {
  transform: rotate(90deg);
}

.plan-icon {
  width: 16px;
  height: 16px;
  margin-right: 8px;
  color: var(--text-secondary);
}

.plan-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edit-input {
  flex: 1;
  width: 100%;
  height: 24px;
  background-color: var(--bg-main);
  border: 1px solid var(--primary-color);
  border-radius: 4px;
  padding: 0 6px;
  font-size: 13px;
  color: var(--text-main);
  outline: none;
  font-family: inherit;
}

.edit-input:focus {
  border-color: var(--primary-hover);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.session-list {
  padding-left: 22px;
  margin-top: 2px;
  margin-bottom: 8px;
}

.session-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.session-item {
  display: flex;
  align-items: center;
  height: 34px;
  flex: 1;
  min-width: 0;
  padding: 0 10px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 13px;
  margin-bottom: 2px;
  transition: all 0.15s ease;
}

.session-icon {
  width: 14px;
  height: 14px;
  margin-right: 8px;
  opacity: 0.7;
}

.session-item:hover {
  background-color: rgba(226, 232, 240, 0.5);
  color: var(--text-main);
}

.session-row.is-active .session-item {
  background-color: #e0e7ff;
  color: var(--primary-hover);
  font-weight: 500;
}

.session-row.is-active .session-icon {
  opacity: 1;
  color: var(--primary-color);
}

.session-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity 0.2s ease, transform 0.2s ease;
  position: relative;
  z-index: 1;
}

.plan-row:hover .item-actions,
.session-row:hover .item-actions {
  opacity: 1;
  transform: translateX(-1px);
}

.plan-row.is-editing .item-actions,
.session-row.is-editing .item-actions {
  opacity: 1;
  transform: none;
}

.editing-actions {
  gap: 4px;
}

.action-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.confirm-btn {
  color: #0f766e;
}

.confirm-btn:hover {
  background-color: #ccfbf1;
  color: #0f766e;
}

.action-btn:hover {
  background-color: #e2e8f0;
  color: var(--primary-color);
}

.action-btn.delete-btn:hover {
  background-color: #fee2e2;
  color: #ef4444;
}

.action-icon {
  width: 14px;
  height: 14px;
}

.new-session-item {
  color: var(--text-disabled);
}

.new-session-item:hover {
  color: var(--primary-color);
  background-color: transparent;
}

.new-session-item .session-icon {
  opacity: 1;
}

.sidebar-footer {
  position: relative;
  padding: 12px 14px 14px;
  /* border-top: 1px solid rgba(226, 232, 240, 0.9); */
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.2) 0%, rgba(255, 255, 255, 0.96) 28%),
    var(--bg-sidebar);
}

.user-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.95);
  box-shadow: 0 10px 18px -16px rgba(15, 23, 42, 0.45);
}

.user-entry {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px;
  cursor: pointer;
  text-align: left;
}

.user-avatar,
.account-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 10px 16px -12px rgba(15, 23, 42, 0.5);
}

.user-avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  flex-shrink: 0;
}

.user-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-chevron {
  width: 16px;
  height: 16px;
  color: var(--text-disabled);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.user-chevron.is-open {
  transform: rotate(180deg);
}

.settings-trigger {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: #f8fafc;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.settings-trigger:hover {
  background: #eef2ff;
  color: var(--primary-color);
  border-color: rgba(165, 180, 252, 0.9);
}

.settings-icon {
  width: 17px;
  height: 17px;
}

.account-drawer {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: calc(100% + 10px);
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 22px 40px -28px rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(12px);
  z-index: 4;
}

.drawer-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  color: var(--text-main);
  font-size: 13px;
  font-weight: 600;
}

.drawer-caption {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-disabled);
}

.log-out {
  width: 17px;
  height: 17px;
}

.account-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  margin-bottom: 6px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.account-row:hover {
  border-color: rgba(199, 210, 254, 0.95);
  background: #eef2ff;
}

.account-row.is-active {
  border-color: rgba(129, 140, 248, 0.9);
  background: linear-gradient(180deg, #eef2ff 0%, #e8edff 100%);
}

.account-avatar {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  flex-shrink: 0;
}

.account-meta {
  min-width: 0;
  flex: 1;
}

.account-name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.account-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-subtitle {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.active-pill {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.12);
  color: var(--primary-color);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.add-account-btn {
  width: 100%;
  margin-top: 4px;
  height: 38px;
  border: 1px dashed rgba(148, 163, 184, 0.65);
  border-radius: 12px;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.add-account-btn:hover {
  border-color: rgba(79, 70, 229, 0.4);
  color: var(--primary-color);
  background: rgba(238, 242, 255, 0.65);
}

.drawer-icon {
  width: 15px;
  height: 15px;
}

.settings-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.settings-modal {
  width: min(1100px, 92vw);
  height: min(760px, 90vh);
  background: #ffffff;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}

.settings-header {
  min-height: 68px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background-color: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.settings-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}

.settings-header p {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.settings-close-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.settings-close-btn:hover {
  background: #e2e8f0;
  color: #ef4444;
}

.settings-close-icon {
  width: 18px;
  height: 18px;
}

.settings-body {
  flex: 1;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 0;
  background: linear-gradient(180deg, #fbfcff 0%, #f8fafc 100%);
}

.settings-nav {
  padding: 18px 14px;
  border-right: 1px solid var(--border-color);
  background: rgba(248, 250, 252, 0.9);
}

.settings-nav-item {
  width: 100%;
  border: none;
  background: transparent;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: all 0.18s ease;
}

.settings-nav-item:hover {
  background: rgba(226, 232, 240, 0.65);
  color: var(--text-main);
}

.settings-nav-item.is-active {
  background: linear-gradient(180deg, #eef2ff 0%, #e5eaff 100%);
  color: var(--primary-color);
  box-shadow: inset 0 0 0 1px rgba(129, 140, 248, 0.25);
}

.settings-nav-icon {
  width: 16px;
  height: 16px;
}

.settings-content {
  overflow-y: auto;
  padding: 22px;
}

.settings-card {
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.95);
  padding: 18px;
  box-shadow: 0 10px 18px -18px rgba(15, 23, 42, 0.5);
}

.settings-card h4,
.settings-card h5 {
  margin: 0;
  color: var(--text-main);
}

.settings-card h4 {
  font-size: 18px;
  font-weight: 700;
}

.settings-card h5 {
  font-size: 14px;
  font-weight: 600;
}

.settings-card p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.card-eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--primary-color);
  margin-bottom: 10px;
}

.hero-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  background: linear-gradient(135deg, #f6f8ff 0%, #ffffff 100%);
}

.soft-card {
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
}

.warm-card {
  background: linear-gradient(135deg, #fff8ef 0%, #ffffff 100%);
}

.tech-card {
  background: linear-gradient(135deg, #eef6ff 0%, #ffffff 100%);
}

.hero-badge {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.12);
  color: var(--primary-color);
  font-size: 11px;
  font-weight: 700;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.settings-stack {
  display: grid;
  gap: 14px;
}

.card-note {
  display: inline-block;
  margin-top: 10px;
  font-size: 11px;
  color: var(--text-disabled);
}

.option-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.option-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.option-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-pill {
  padding: 7px 10px;
  border-radius: 999px;
  background: #f1f5f9;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.option-pill.is-active {
  background: rgba(79, 70, 229, 0.12);
  color: var(--primary-color);
}

.memory-hero-card {
  align-items: center;
}

.memory-refresh-btn,
.memory-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: #ffffff;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.memory-refresh-btn {
  gap: 8px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
}

.memory-refresh-btn:hover,
.memory-icon-btn:hover {
  color: var(--primary-color);
  border-color: rgba(79, 70, 229, 0.35);
  background: rgba(79, 70, 229, 0.06);
}

.memory-refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.memory-action-icon,
.memory-search-icon {
  width: 16px;
  height: 16px;
}

.memory-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.memory-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: 8px;
  background: #f1f5f9;
}

.memory-tab {
  min-height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.memory-tab.is-active {
  background: #ffffff;
  color: var(--primary-color);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.memory-search {
  min-width: 220px;
  height: 36px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 8px;
  background: #ffffff;
  color: var(--text-disabled);
}

.memory-search input {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-main);
  font-size: 13px;
}

.memory-list {
  display: grid;
  gap: 12px;
}

.memory-empty {
  padding: 24px;
  border: 1px dashed rgba(148, 163, 184, 0.7);
  border-radius: 8px;
  background: #f8fafc;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}

.memory-card {
  padding: 14px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 8px;
  background: #ffffff;
}

.memory-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.memory-card-head h5 {
  margin: 0;
  font-size: 14px;
  color: var(--text-main);
}

.memory-card-head p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.memory-card-actions {
  display: inline-flex;
  gap: 6px;
  flex-shrink: 0;
}

.memory-icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.memory-icon-btn.primary {
  color: var(--primary-color);
}

.memory-icon-btn.danger:hover {
  color: #dc2626;
  border-color: rgba(220, 38, 38, 0.35);
  background: rgba(220, 38, 38, 0.06);
}

.memory-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.memory-tag {
  padding: 4px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
}

.memory-meta {
  margin-top: 10px;
  color: var(--text-disabled);
  font-size: 11px;
}

.memory-input,
.memory-textarea {
  width: 100%;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 8px;
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: border-color 0.18s ease;
}

.memory-input {
  height: 36px;
  padding: 0 10px;
  margin-bottom: 8px;
}

.memory-textarea {
  resize: vertical;
  min-height: 96px;
  padding: 10px;
  margin-bottom: 8px;
  line-height: 1.5;
}

.memory-input:focus,
.memory-textarea:focus {
  border-color: rgba(79, 70, 229, 0.55);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-active .settings-modal,
.fade-leave-active .settings-modal {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.fade-enter-from .settings-modal,
.fade-leave-to .settings-modal {
  transform: scale(0.98) translateY(10px);
}

.account-sheet-enter-active,
.account-sheet-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.account-sheet-enter-from,
.account-sheet-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

@media (max-width: 960px) {
  .settings-body {
    grid-template-columns: 1fr;
  }

  .settings-nav {
    border-right: none;
    border-bottom: 1px solid var(--border-color);
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .settings-nav-item {
    margin-bottom: 0;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .memory-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .memory-search {
    min-width: 0;
    width: 100%;
  }
}
</style>
