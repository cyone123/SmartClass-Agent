import { ArrowRight, Bot, Wrench, Network, Sparkles, FileSearchCorner } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { heroMetrics } from "@/lib/site-content"
import { cn } from "@/lib/utils"

const cues = [
  { label: "LangGraph 编排", icon: Network },
  { label: "多模态工作流", icon: Bot },
  { label: "RAG知识检索", icon: FileSearchCorner },
  { label: "Agent Skill能力", icon: Wrench },
]

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden px-4 pt-8 pb-2 h-full flex flex-col justify-center items-center">
      <div className="w-full max-w-7xl gap-8 grid lg:grid-cols-[minmax(0,1.12fr)_minmax(0,0.88fr)] lg:items-center">
        <div className="relative z-10 space-y-6">
          <Badge className="w-fit">Teacher-Facing AI System</Badge>

          <div className="space-y-6">
            <h1 className="hero-title max-w-4xl font-heading text-5xl leading-[1.05] font-semibold tracking-[-0.05em] text-slate-950 sm:text-6xl lg:text-7xl">
              系统架构设计与实现
              <span className="block text-primary">安全可控的Agent工作流</span>
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600 sm:text-xl">
              通过 LangGraph 将教学工作流显式化，通过 RAG 与多模态附件增强上下文，通过 Skill + Workspace 机制驱动真实产物生成，通过 SSE、审批卡片、产物追踪、OnlyOffice 等机制把整个过程完整呈现在前端。
            </p>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row">
            <a
              href="#architecture"
              className={cn(
                buttonVariants({ size: "lg" }),
                "rounded-full bg-slate-950 px-6 text-white shadow-[0_12px_32px_rgba(15,23,42,0.14)] hover:bg-slate-800"
              )}
            >
              查看架构设计
              <ArrowRight className="size-4" />
            </a>
            <a
              href="#workflow"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "rounded-full border-slate-200 bg-white/80 px-6 text-slate-700 hover:border-slate-300 hover:bg-white"
              )}
            >
              浏览业务流程
            </a>
          </div>

          <div className="flex flex-wrap gap-3">
            {cues.map(({ label, icon: Icon }) => (
              <div
                key={label}
                className="inline-flex items-center gap-2 rounded-full border border-white/80 bg-white/75 px-4 py-2 text-sm text-slate-600 shadow-[0_10px_25px_rgba(15,23,42,0.05)] backdrop-blur-sm"
              >
                <Icon className="size-4 text-primary" />
                {label}
              </div>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {heroMetrics.map((metric, index) => (
              <Card
                key={metric.label}
                className="metric-card animate-fade-up p-5"
                style={{ animationDelay: `${index * 120}ms` }}
              >
                <div className="text-3xl font-semibold tracking-[-0.05em] text-slate-950">{metric.value}</div>
                <div className="mt-2 text-sm font-medium text-slate-800">{metric.label}</div>
                <p className="mt-3 text-sm leading-6 text-slate-600">{metric.detail}</p>
              </Card>
            ))}
          </div>
        </div>

        <div className="relative z-10 lg:pl-6">
          <div className="absolute inset-x-8 top-8 h-48 rounded-full bg-[radial-gradient(circle,_rgba(125,211,252,0.34),_transparent_70%)] blur-3xl" />
          <Card className="relative overflow-hidden p-5 sm:p-6">
            <div className="grid gap-4">
              <div className="flex items-center justify-between gap-4 rounded-[24px] border border-sky-100 bg-gradient-to-r from-sky-50 to-white p-4">
                <div>
                  <div className="text-xs tracking-[0.18em] text-slate-500 uppercase">Live Workflow Story</div>
                  <div className="mt-2 font-heading text-2xl tracking-[-0.03em] text-slate-950">
                    从教学计划到课件生成
                  </div>
                </div>
                {/* <div className="relative hidden size-20 overflow-hidden rounded-[22px] border border-white/70 bg-white shadow-inner sm:block">
                  <Image
                    src="/logo360x360.png"
                    alt="SmartClass 项目标识"
                    fill
                    sizes="80px"
                    className="object-cover"
                  />
                </div> */}
              </div>

              <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
                <Card className="grid gap-4 border-slate-100 bg-[#fdfefe] p-5 shadow-none">
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-2xl bg-sky-100 text-primary">
                      <Sparkles className="size-5" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-900">编排主链路</div>
                      <div className="text-sm text-slate-500">Intent → Metadata → Review → RAG → Artifact</div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {[
                      "意图识别与结构化教学元数据抽取",
                      "信息不足时追问补全并中断等待",
                      "RAG 检索增强后生成教学设计方案",
                      "审批确认后选择性生成 PPT / DOCX / HTML",
                    ].map((item) => (
                      <div
                        key={item}
                        className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-600"
                      >
                        <span className="mt-1 size-2 rounded-full bg-sky-400" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </Card>

                <div className="grid gap-4">
                  <Card className="border-amber-100/80 bg-amber-50/80 p-5 shadow-none">
                    <div className="text-xs tracking-[0.18em] text-amber-700 uppercase">Artifact Revision</div>
                    <div className="mt-3 font-heading text-2xl tracking-[-0.03em] text-slate-950">项目亮点</div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      多Agent编排工作流，安全可控的Agent执行模型，可插拔的Skill能力，多模态统一抽象架构。
                    </p>
                  </Card>

                  <Card className="border-slate-100 bg-white p-5 shadow-none">
                    <div className="text-xs tracking-[0.18em] text-slate-500 uppercase">Key Word</div>
                    <div className="mt-3 grid gap-2">
                      {["资料管理与检索", "教学要素提取", "教学设计规划", "课件教案生成", "互动内容生成", "在线预览与修订"].map((item) => (
                        <div key={item} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-2 text-sm text-slate-600">
                          {item}
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </section>
  )
}
