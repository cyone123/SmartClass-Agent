"use client"

import { motion } from "framer-motion"
import { Braces, DatabaseZap, FileCog, MonitorSmartphone } from "lucide-react"

import { SectionHeading } from "@/components/landing/SectionHeading"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { techStackGroups } from "@/lib/site-content"

const icons = [Braces, DatabaseZap, FileCog, MonitorSmartphone]

export function TechStackBoard() {
  return (
    <section id="tech-stack" className="px-4 pt-8 pb-2 h-full flex flex-col justify-center items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="Tech Stack"
          title="技术方案不是孤立技术点罗列，而是围绕教师工作流分工协同"
          description="项目现有主系统后端采用 FastAPI + LangGraph 体系，前端工作台采用 Vue 3"
        />

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <div className="grid gap-5 md:grid-cols-2">
            {techStackGroups.map((group, index) => {
              const Icon = icons[index % icons.length]

              return (
                <motion.div
                  key={group.title}
                  initial={{ opacity: 0, scale: 0.95, y: 30 }}
                  whileInView={{ opacity: 1, scale: 1, y: 0 }}
                  viewport={{ once: true, margin: "-50px" }}
                  transition={{ duration: 0.5, delay: (index % 2) * 0.15, ease: "easeOut" }}
                >
                  <Card className="h-full border-white/80 bg-white/84 p-6 sm:p-7">
                    <div className="flex items-start gap-4">
                      <div className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-100 to-white text-primary">
                        <Icon className="size-5" />
                      </div>
                      <div className="space-y-3">
                        <h3 className="font-heading text-2xl tracking-[-0.03em] text-slate-950">{group.title}</h3>
                        <p className="text-sm leading-7 text-slate-600">{group.description}</p>
                      </div>
                    </div>
                    <div className="mt-6 flex flex-wrap gap-3">
                      {group.stacks.map((stack) => (
                        <Badge key={stack} variant="secondary" className="tracking-normal normal-case">
                          {stack}
                        </Badge>
                      ))}
                    </div>
                  </Card>
                </motion.div>
              )
            })}
          </div>

          <motion.div
            initial={{ opacity: 0, x: 50 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
          >
            <Card className="h-full overflow-hidden border-white/80 bg-slate-950 p-6 text-white sm:p-7">
              <div className="space-y-6">
                <Badge className="w-fit border-white/15 bg-white/10 text-white">Showcase Layer</Badge>
                <div className="space-y-4">
                  <h3 className="font-heading text-3xl tracking-[-0.04em]">落地展示页的实现策略</h3>
                  <p className="text-sm leading-7 text-slate-300 sm:text-base">
                    本次展示页采用独立的 Next.js 单页叙事形态，强调架构、流程、协议与亮点。
                  </p>
                </div>

                <div className="grid gap-3">
                  {[
                    "Next.js App Router",
                    "TypeScript 类型化内容模型",
                    "Tailwind CSS 4 + shadcn 风格组件",
                    "浅色高端视觉系统与自然动效",
                  ].map((item) => (
                    <div
                      key={item}
                      className="rounded-[22px] border border-white/10 bg-white/6 px-4 py-3 text-sm text-slate-200"
                    >
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
