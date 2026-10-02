"use client"

import { motion } from "framer-motion"
import { Cpu, FileSearch2, GitBranchPlus, MessageSquareShare, PencilRuler, ShieldCheck } from "lucide-react"

import { SectionHeading } from "@/components/landing/SectionHeading"
import { Badge } from "@/components/ui/badge"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { highlightCards } from "@/lib/site-content"

const icons = [GitBranchPlus, MessageSquareShare, ShieldCheck, PencilRuler, Cpu, FileSearch2]

export function Highlights() {
  return (
    <section id="highlights" className="px-4 pt-8 pb-2 h-full flex flex-col justify-center items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="Highlights"
          title="不是“能生成”，而是“能稳定协作、能持续修订、能工程落地”"
          description="这些亮点不是概念包装，而是当前项目在代码和协议层面已经形成的实现方向。它们共同决定了 智课伴侣 更像一套可用的教学智能系统，而不是一个漂亮的聊天 Demo。"
        />

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {highlightCards.map((item, index) => {
            const Icon = icons[index % icons.length]

            return (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, scale: 0.9, y: 30 }}
                whileInView={{ opacity: 1, scale: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.5, delay: (index % 3) * 0.15, ease: "easeOut" }}
                className="h-full"
              >
                <Card className="h-full border-white/80 bg-white/85 p-6 sm:p-7">
                  <CardHeader className="p-0">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex size-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
                        <Icon className="size-5" />
                      </div>
                      <Badge variant="secondary" className="tracking-[0.14em]">
                        {item.badge}
                      </Badge>
                    </div>
                    <CardTitle className="pt-6">{item.title}</CardTitle>
                    <CardDescription className="text-sm leading-7 sm:text-base">{item.description}</CardDescription>
                  </CardHeader>
                </Card>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
