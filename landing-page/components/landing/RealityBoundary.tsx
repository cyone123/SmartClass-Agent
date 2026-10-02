"use client"

import { motion } from "framer-motion"
import { CircleAlert, CircleCheckBig } from "lucide-react"

import { SectionHeading } from "@/components/landing/SectionHeading"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { boundaryItems } from "@/lib/site-content"

export function RealityBoundary() {
  return (
    <section id="reality-boundary" className="px-4 pt-8 pb-2 h-full flex flex-col justify-center items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="Reality Boundary"
          title="展示当前真实边界，让项目介绍既有想象力，也有可信度"
          description="SmartClass 已经打通主链路，但它不是把未来规划包装成既成事实。清晰说明边界，本身就是工程成熟度的一部分。"
        />

        <div className="grid gap-5 lg:grid-cols-2">
          {boundaryItems.map((item, index) => {
            const isReady = item.status === "已实现"
            const Icon = isReady ? CircleCheckBig : CircleAlert

            return (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.5, delay: (index % 2) * 0.15, ease: "easeOut" }}
              >
                <Card className="border-white/80 bg-white/84 p-6 sm:p-7">
                  <div className="flex items-start gap-4">
                    <div
                      className={`flex size-12 shrink-0 items-center justify-center rounded-2xl ${
                        isReady ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      <Icon className="size-5" />
                    </div>
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="font-heading text-2xl tracking-[-0.03em] text-slate-950">{item.title}</h3>
                        <Badge variant={isReady ? "secondary" : "warm"} className="tracking-normal">
                          {item.status}
                        </Badge>
                      </div>
                      <p className="text-sm leading-7 text-slate-600 sm:text-base">{item.description}</p>
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
