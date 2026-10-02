import { ArrowRight, FileText, Presentation, Shapes } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

const outputs = [
  { label: "课件 PPT", icon: Presentation },
  { label: "DOCX 教案", icon: FileText },
  { label: "HTML 互动内容", icon: Shapes },
]

export function FinalCTA() {
  return (
    <section id="final-cta" className="px-4 pb-16 pt-10 sm:px-6 sm:pb-20 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <Card className="overflow-hidden border-white/80 bg-[linear-gradient(135deg,rgba(15,23,42,1),rgba(30,41,59,0.96),rgba(8,47,73,0.92))] p-8 text-white shadow-[0_30px_80px_rgba(15,23,42,0.24)] sm:p-10 lg:p-12">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-end">
            <div className="space-y-6">
              <Badge className="w-fit border-white/15 bg-white/10 text-white">Final Statement</Badge>
              <div className="space-y-4">
                <h2 className="font-heading text-4xl leading-tight font-semibold tracking-[-0.04em] sm:text-5xl">
                  智课伴侣 的价值，不在于“生成了一份内容”，而在于把教师备课真正做成了可协作的智能流程。
                </h2>
                <p className="max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
                  它把教学对话、RAG、多模态输入、审批确认、产物生成、差量修订与在线预览贯穿为一个稳定工作台，推动人工智能从“能回答”走向“能支撑教学任务落地”。
                </p>
              </div>

              {/* <div className="flex flex-col gap-4 sm:flex-row">
                <a
                  href="#top"
                  className={cn(
                    buttonVariants({ size: "lg" }),
                    "rounded-full bg-white px-6 text-slate-950 hover:bg-slate-100"
                  )}
                >
                  回到顶部
                  <ArrowRight className="size-4" />
                </a>
                <a
                  href="#workflow"
                  className={cn(
                    buttonVariants({ variant: "outline", size: "lg" }),
                    "rounded-full border-white/15 bg-white/5 px-6 text-white hover:bg-white/10"
                  )}
                >
                  再看业务流程
                </a>
              </div> */}
            </div>

            <div className="grid gap-4">
              {outputs.map(({ label, icon: Icon }) => (
                <div
                  key={label}
                  className="flex items-center gap-4 rounded-[24px] border border-white/10 bg-white/6 px-5 py-4 text-sm text-slate-200"
                >
                  <div className="flex size-11 items-center justify-center rounded-2xl bg-white/10 text-white">
                    <Icon className="size-5" />
                  </div>
                  <div>
                    <div className="font-medium text-white">{label}</div>
                    <div className="mt-1 text-xs tracking-[0.16em] text-slate-400 uppercase">Generation + Revision</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </section>
  )
}
