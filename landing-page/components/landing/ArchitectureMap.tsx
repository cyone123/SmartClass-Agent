"use client"

import { motion } from "framer-motion"
import { Database, Layers3, ServerCog, Workflow } from "lucide-react"

import { SectionHeading } from "@/components/landing/SectionHeading"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { architectureLayers } from "@/lib/site-content"

const icons = [Layers3, Workflow, ServerCog, Database]

export function ArchitectureMap({ part = 1 }: { part?: 1 | 2 }) {
  const currentLayers = part === 1 ? architectureLayers.slice(0, 2) : architectureLayers.slice(2, 4);

  return (
    <section id={`architecture-part${part}`} className="px-4 pt-10 pb-4 h-full flex flex-col items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="Architecture"
          title="以四层结构组织能力，让教师工作流、Agent 能力与数据契约保持一致"
          description="项目的稳定性并不只来自模型能力，而来自交互、编排、能力与存储四个层面的边界清晰。这样的结构也让后续扩展多模态输入与产物类型时，不必重写整条链路。"
        />

        <div className="relative grid gap-5">
          <div className="absolute left-7 top-10 hidden h-[calc(100%-5rem)] w-px bg-gradient-to-b from-sky-200 via-slate-200 to-amber-200 lg:block" />
          {currentLayers.map((layer, idx) => {
            const index = part === 1 ? idx : idx + 2;
            const Icon = icons[index % icons.length]

            return (
              <motion.div
                key={layer.name}
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay: index * 0.2, ease: "easeOut" }}
              >
                <Card
                  className="relative overflow-hidden border-white/80 bg-white/84 p-1"
                >
                  <div className="grid gap-5 rounded-[26px] border border-slate-100/80 bg-gradient-to-r from-white via-white to-slate-50/60 p-6 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-start lg:p-7">
                    <div className="flex items-start gap-4">
                      <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-[0_12px_30px_rgba(15,23,42,0.16)]">
                        <Icon className="size-6" />
                      </div>
                      <div className="space-y-3">
                        <Badge className="w-fit">Layer {index + 1}</Badge>
                        <CardTitle className="text-2xl">{layer.name}</CardTitle>
                      </div>
                    </div>

                    <div className="grid gap-5">
                      <CardHeader className="p-0">
                        <p className="text-sm leading-7 text-slate-600 sm:text-base">{layer.summary}</p>
                      </CardHeader>
                      <CardContent className="grid gap-4 p-0">
                        <div className="flex flex-wrap gap-3">
                          {layer.items.map((item) => (
                            <span
                              key={item}
                              className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600"
                            >
                              {item}
                            </span>
                          ))}
                        </div>
                        <div className="rounded-[22px] border border-sky-100 bg-sky-50/70 px-5 py-4 text-sm leading-7 text-slate-700">
                          <span className="font-medium text-slate-900">这一层的设计价值：</span> {layer.signal}
                        </div>
                      </CardContent>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
