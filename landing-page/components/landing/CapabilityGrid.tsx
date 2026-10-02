"use client"

import { motion } from "framer-motion"
import { Binary, BookOpenText, Boxes, FileStack, Mic, Route, ScanSearch, Sparkles } from "lucide-react"

import { SectionHeading } from "@/components/landing/SectionHeading"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { capabilityItems } from "@/lib/site-content"
import { cn } from "@/lib/utils"

const accentStyles = {
  blue: "from-sky-50 via-white to-slate-50 text-primary",
  teal: "from-teal-50 via-white to-slate-50 text-teal-700",
  amber: "from-amber-50 via-white to-slate-50 text-amber-700",
} as const

const icons = [Route, Binary, ScanSearch, FileStack, Mic, Sparkles, Boxes, BookOpenText]

export function CapabilityGrid() {
  return (
    <section id="overview" className="px-4 pt-8 pb-2 h-full flex flex-col justify-center items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="System Overview"
          title="以教师备课与教学设计为核心，而不是通用聊天机器人"
          description="“教学对话 + RAG + 多模态附件分析 + 教学设计 + 可编辑产物生成与修订”的教师智能工作台"
        />

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {capabilityItems.map((item, index) => {
            const Icon = icons[index % icons.length]
            return (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay: (index % 4) * 0.15, ease: "easeOut" }}
                className="h-full"
              >
                <Card className="group h-full overflow-hidden border-white/80 bg-white/82 transition duration-300 hover:-translate-y-1 hover:shadow-[0_22px_50px_rgba(15,23,42,0.1)]">
                  <CardHeader>
                    <div
                      className={cn(
                        "flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br",
                        accentStyles[item.accent]
                      )}
                    >
                      <Icon className="size-5" />
                    </div>
                    <CardTitle>{item.title}</CardTitle>
                    <CardDescription>{item.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-2">
                    {item.tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="tracking-normal normal-case">
                        {tag}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
