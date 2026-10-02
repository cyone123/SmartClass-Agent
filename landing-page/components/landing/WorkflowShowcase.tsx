"use client"

import { motion } from "framer-motion"
import { ArrowRight } from "lucide-react"

import { SectionHeading } from "@/components/landing/SectionHeading"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { workflowLanes } from "@/lib/site-content"

export function WorkflowShowcase({ part = 1 }: { part?: 1 | 2 }) {
  const currentLanes = part === 1 ? workflowLanes.slice(0, 2) : workflowLanes.slice(2, 4);

  return (
    <section id={`workflow-part${part}`} className="px-4 pt-10 pb-4 h-full flex flex-col items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="Workflow"
          title="用业务流程而不是抽象口号，说明系统如何从输入流到产物流真正跑起来"
          description="比赛展示最有说服力的部分不是“能做什么”，而是“怎么做到”。下方四条泳道对应当前系统里最核心、也最真实的执行链路。"
        />

        <div className="grid gap-5 xl:grid-cols-2">
          {currentLanes.map((lane, idx) => {
            const laneIndex = part === 1 ? idx : idx + 2;
            return (
            <motion.div
              key={lane.title}
              initial={{ opacity: 0, x: laneIndex % 2 === 0 ? -40 : 40 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.7, delay: 0.1, ease: "easeOut" }}
            >
              <Card
                className="overflow-hidden border-white/80 bg-white/84 p-6 transition duration-300 hover:-translate-y-1 hover:shadow-[0_22px_48px_rgba(15,23,42,0.08)] sm:p-7"
              >
                <div className="flex flex-col gap-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-3">
                      <Badge variant={laneIndex % 2 === 0 ? "default" : "warm"} className="w-fit">
                        Lane {laneIndex + 1}
                      </Badge>
                      <h3 className="font-heading text-2xl tracking-[-0.03em] text-slate-950">{lane.title}</h3>
                      <p className="max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">{lane.description}</p>
                    </div>
                    <div className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs tracking-[0.16em] text-slate-500 uppercase">
                      {lane.emphasis}
                    </div>
                  </div>

                  <ol className="grid gap-4">
                    {lane.steps.map((step, stepIndex) => (
                      <motion.li 
                        key={step} 
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: "-50px" }}
                        transition={{ duration: 0.5, delay: 0.2 + stepIndex * 0.15 }}
                        className="grid gap-4 sm:grid-cols-[44px_minmax(0,1fr)] sm:items-start"
                      >
                        <div className="flex items-center gap-3 sm:flex-col sm:gap-2">
                          <div className="flex size-11 items-center justify-center rounded-2xl bg-slate-950 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(15,23,42,0.14)]">
                            {stepIndex + 1}
                          </div>
                          {stepIndex < lane.steps.length - 1 ? (
                            <div className="hidden h-10 w-px bg-gradient-to-b from-slate-300 to-slate-100 sm:block" />
                          ) : null}
                        </div>

                        <div className="rounded-[22px] border border-slate-100 bg-slate-50/80 px-5 py-4 text-sm leading-7 text-slate-700">
                          {step}
                        </div>
                      </motion.li>
                    ))}
                  </ol>

                  <div className="flex items-center gap-3 rounded-[22px] border border-sky-100 bg-sky-50/80 px-5 py-4 text-sm text-slate-700">
                    <ArrowRight className="size-4 shrink-0 text-primary" />
                    <span>{lane.emphasis}</span>
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
