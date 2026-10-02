export type HeroMetric = {
  value: string
  label: string
  detail: string
}

export type CapabilityItem = {
  title: string
  description: string
  tags: string[]
  accent: "blue" | "teal" | "amber"
}

export type ArchitectureLayer = {
  name: string
  summary: string
  items: string[]
  signal: string
}

export type WorkflowLane = {
  title: string
  description: string
  steps: string[]
  emphasis: string
}

export type HighlightCard = {
  title: string
  description: string
  badge: string
}

export type TechStackGroup = {
  title: string
  description: string
  stacks: string[]
}

export type BoundaryItem = {
  title: string
  status: "已实现" | "持续完善"
  description: string
}

export type FaqItem = {
  question: string
  answer: string
}

export const navigationItems = [
  { label: "系统全貌", href: "#overview" },
  { label: "架构设计", href: "#architecture" },
  { label: "业务流程", href: "#workflow" },
  { label: "亮点特色", href: "#highlights" },
  { label: "技术方案", href: "#tech-stack" },
] as const

export const heroMetrics: HeroMetric[] = [
  {
    value: "9 类",
    label: "流式事件协议",
    detail: "metadata、progress、token、artifact、approval 等事件驱动前端实时协作。",
  },
  {
    value: "3 类",
    label: "核心产物闭环",
    detail: "课件 PPT、DOCX 教案、HTML 互动内容均已进入生成与修订链路。",
  },
  {
    value: "2 条",
    label: "文件处理主链路",
    detail: "知识库文件服务于 RAG，会话附件服务于当前轮上下文分析，职责清晰分离。",
  },
  {
    value: "4 层",
    label: "总体架构分层",
    detail: "交互层、编排层、能力层、数据与存储层共同组成教师智能工作台。",
  },
] as const

export const capabilityItems: CapabilityItem[] = [
  {
    title: "教学对话与会话管理",
    description: "围绕教学计划建立多轮备课会话，不是一次性问答。",
    tags: ["计划 CRUD", "Session", "多轮状态"],
    accent: "blue",
  },
  {
    title: "结构化教学要素抽取",
    description: "自动提取学科、年级、主题、课时、重点难点与目标，并在信息不足时追问补全。",
    tags: ["JSON Schema", "Metadata", "追问中断"],
    accent: "teal",
  },
  {
    title: "知识库 RAG 检索",
    description: "知识库文件支持异步入库、文本切分与向量检索，为教学设计生成提供检索增强。",
    tags: ["PGVector", "PDF/DOCX/TXT", "异步入库"],
    accent: "blue",
  },
  {
    title: "会话附件智能分析",
    description: "文档附件与视频附件先摘要和转述，再统一折叠为可注入上下文进入图流程。",
    tags: ["attachments", "上下文注入", "分析摘要"],
    accent: "amber",
  },
  {
    title: "语音输入与视频理解",
    description: "语音可直接转写回填输入框，视频可抽音频、转写、提关键帧生成画面摘要。",
    tags: ["voice transcribe", "FFmpeg", "video summary"],
    accent: "teal",
  },
  {
    title: "教学设计与审批协作",
    description: "关键节点通过审批卡片等待教师确认，支持选择性生成产物，保持人机共创。",
    tags: ["approval", "progress", "selective generation"],
    accent: "blue",
  },
  {
    title: "产物生成与版本管理",
    description: "生成结果统一抽象为 artifact，具备状态、归属、预览、版本链等工程属性。",
    tags: ["artifact", "版本链", "预览"],
    accent: "amber",
  },
  {
    title: "产物差量修改",
    description: "支持围绕既有 PPT、DOCX、HTML 产物执行定向修订，而非每次从零重生成。",
    tags: ["revision", "workspace", "delta edit"],
    accent: "teal",
  },
] as const

export const architectureLayers: ArchitectureLayer[] = [
  {
    name: "交互层",
    summary: "面向教师的工作台界面，承接计划管理、对话、文件上传、审批与产物预览。",
    items: ["Vue 3 + Vite", "Element Plus + Pinia", "SSE 流式消息", "OnlyOffice 文档预览"],
    signal: "把工作流结果完整可视化，而不是只显示一段 AI 回复。",
  },
  {
    name: "编排层",
    summary: "以 LangGraph 对教学流程进行显式编排，支持状态恢复、中断等待与节点式路由。",
    items: ["意图识别", "教学元数据抽取", "追问补全", "RAG 检索", "教学设计规划", "产物修订路由"],
    signal: "把教师备课流程拆成可验证、可恢复、可插入审批的真实工作流。",
  },
  {
    name: "能力层",
    summary: "RAG、附件分析、Skill Registry、Workspace Agent工作区、语音转写、视频理解、产物 Agent 共同提供能力。",
    items: ["Skill Registry", "Attachment Agent", "Speech Runtime", "Video Runtime", "Artifact Agent", "Workspace Tools"],
    signal: "采用统一抽象与模块化编排机制，系统能够持续接入更多模态理解与教学产物生成能力，实现从“单点功能叠加”到“平台化智能扩展”的跃升。",
  },
  {
    name: "数据与存储层",
    summary: "业务数据库、图状态、文件存储与向量存储共同支撑计划、会话、文件和产物生命周期。",
    items: ["PostgreSQL", "SQLAlchemy", "LangGraph Checkpoint", "Local Storage", "PGVector 向量检索"],
    signal: "保证计划、会话、知识库文件、附件与 artifact 都有清晰归属与持久化语义。",
  },
] as const

export const workflowLanes: WorkflowLane[] = [
  {
    title: "对话主链路",
    description: "从 `/api/chat/stream` 发起，进入 LangGraph，按意图在普通聊天、教学规划、产物修订之间分流。",
    steps: [
      "前端发送消息、thread_id 与附件引用",
      "后端定位会话与 plan_id，并预处理附件上下文",
      "LangGraph 执行意图识别、元数据抽取、追问补全或规划生成",
      "通过 SSE 推送 metadata、progress、token、artifact、approval 等事件",
    ],
    emphasis: "事件驱动前端，而不是一条 message 贯穿全程。",
  },
  {
    title: "知识库文件链路",
    description: "知识库文件面向 RAG，不混用会话附件链路。",
    steps: [
      "上传到 knowledge_files 并写入本地存储",
      "异步入队，由 FileIngestionRuntime 后台消费",
      "完成文本切分、元数据附加与向量入库",
      "在教学设计阶段按 plan_id 检索增强",
    ],
    emphasis: "知识库属于可复用资料层，为后续多轮备课提供稳定支撑。",
  },
  {
    title: "会话附件链路",
    description: "会话附件服务于当前轮或当前线程的上下文增强，强调即时分析而非长期检索。",
    steps: [
      "附件按 plan_id + thread_id 存储归属",
      "文档交给 skill 分析，视频走音频转写与关键帧摘要",
      "生成 attachment_text 统一注入图输入",
      "前端同步展示上传、分析与引用状态",
    ],
    emphasis: "多模态输入最终收敛为可注入上下文。",
  },
  {
    title: "产物修订链路",
    description: "针对当前线程已有 artifact 判断修改目标、准备工作区并执行定向修订。",
    steps: [
      "识别 artifact_revision 意图并推断修订对象",
      "目标不清晰时进入审批卡片等待澄清",
      "复制源文件到 workspace，生成 source summary 与 revision request",
      "产物 Agent 完成修订并通过 artifact / artifact_trace 事件回推",
    ],
    emphasis: "从“重新生成”升级为“基于现有成果做差量更新”。",
  },
] as const

export const highlightCards: HighlightCard[] = [
  {
    title: "LangGraph 显式编排",
    description: "把教师备课流程拆分为可恢复、可中断、可插入审批的人机协作图，而不是单 prompt 黑盒。",
    badge: "Workflow Core",
  },
  {
    title: "SSE 多事件协议",
    description: "前端不只接收文本，而是同时理解 progress、approval、artifact、artifact_trace 等结构化事件。",
    badge: "Streaming UX",
  },
  {
    title: "审批卡片机制",
    description: "教学要素确认、教学设计确认、产物修订澄清都通过统一审批协议落到前端界面。",
    badge: "Human in the Loop",
  },
  {
    title: "Artifact 差量修订",
    description: "围绕已有 PPT、DOCX、HTML 产物建立版本链和修订工作区，支持面向目标的局部更新。",
    badge: "Revision Engine",
  },
  {
    title: "Skill + Workspace 治理",
    description: "Agent 具备真实文件处理能力，但能力边界通过 skill 元数据与受控 workspace 明确收束。",
    badge: "Governed Agent",
  },
  {
    title: "OnlyOffice 回写闭环",
    description: "AI 生成后仍可由教师在线编辑，系统接住回写并回收更新，实现 AI + 人工协同编辑。",
    badge: "Editable Output",
  },
] as const

export const techStackGroups: TechStackGroup[] = [
  {
    title: "后端工作流栈",
    description: "负责 API、编排、状态推进与结构化调用。",
    stacks: ["FastAPI", "LangChain", "LangGraph", "ChatOpenAI Compatible API", "Pydantic"],
  },
  {
    title: "知识与数据层",
    description: "负责计划、会话、文件、artifact 与向量化知识管理。",
    stacks: ["PostgreSQL", "SQLAlchemy", "PGVector Style Retrieval", "LangGraph Checkpoint", "Local Storage"],
  },
  {
    title: "智能能力与文件处理",
    description: "负责技能加载、附件理解、音视频分析与产物执行环境。",
    stacks: ["Skill Registry", "Workspace Runtime", "FFmpeg", "Speech Runtime", "Video Vision Runtime", "OnlyOffice Callback"],
  },
  {
    title: "当前产品前端",
    description: "项目现有工作台前端并非 Next.js，而是已成型的教学操作界面。",
    stacks: ["Vue 3", "Vite", "Element Plus", "Pinia", "SSE Stream Rendering", "OnlyOffice Preview"],
  },
] as const

export const boundaryItems: BoundaryItem[] = [
  {
    title: "教学对话、RAG、附件分析主链路",
    status: "已实现",
    description: "对话、知识库、附件摘要与教学设计规划已经形成真实可运行主流程。",
  },
  {
    title: "语音输入与视频附件理解",
    status: "已实现",
    description: "语音可转写回填输入框，视频可抽音频、提关键帧并生成组合摘要。",
  },
  {
    title: "产物生成与选择性生成",
    status: "已实现",
    description: "教师可在审批节点选择是否生成 PPT、DOCX 与 HTML 互动内容。",
  },
  {
    title: "产物差量修改能力",
    status: "已实现",
    description: "系统已进入基于既有产物的修订阶段，不再停留在一次性生成。",
  },
  {
    title: "持续完善的重点方向",
    status: "持续完善",
    description: "当前仍处于主流程骨架持续补强阶段，后续重点是统一协议、增强稳定性和拓展多模态深度。",
  },
] as const

export const faqItems: FaqItem[] = [
  {
    question: "SmartClass 和普通教学聊天机器人有什么本质区别？",
    answer:
      "核心区别在于它不是把模型直接包装成问答框，而是围绕教师真实备课流程设计工作流、审批节点、文件链路和产物闭环，因此更接近可落地的教师智能工作台。",
  },
  {
    question: "为什么强调 knowledge_files 和 attachments 必须分开？",
    answer:
      "因为前者服务于知识库与长期检索，后者服务于当前对话上下文增强，两条链路的归属、时效性和处理方式都不同，混用会造成检索和权限语义混乱。",
  },
  {
    question: "项目为什么要用 LangGraph，而不是把所有逻辑写进一个 prompt？",
    answer:
      "因为教学设计、追问补全、审批确认、产物生成与修订都需要状态推进与中断恢复。LangGraph 让这些节点变得显式、可追踪，也更容易扩展。",
  },
  {
    question: "产物修订为什么是这个项目最值得展示的点之一？",
    answer:
      "真实教学场景里教师往往不是每次都重做课件和教案，而是基于现有版本持续修改。系统支持围绕已有 artifact 做差量更新，更贴近实际生产过程。",
  },
  {
    question: "这次落地页展示的是不是项目现有前端？",
    answer:
      "不是。当前产品前端仍然是 Vue 3 工作台，而这个落地页是为比赛展示额外构建的 Next.js 单页，用来更清晰地讲述项目能力与技术方案。",
  },
] as const
