import { ChevronDown } from "lucide-react"

import { cn } from "@/lib/utils"

type AccordionItemProps = {
  question: string
  answer: string
  className?: string
}

function AccordionItem({ question, answer, className }: AccordionItemProps) {
  return (
    <details
      className={cn(
        "group rounded-[24px] border border-slate-200/80 bg-white/90 p-6 shadow-[0_14px_40px_rgba(15,23,42,0.05)] transition-colors open:border-primary/30",
        className
      )}
    >
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 text-left">
        <span className="pr-2 font-medium text-slate-900">{question}</span>
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500 transition duration-300 group-open:rotate-180 group-open:border-primary/30 group-open:bg-primary/10 group-open:text-primary">
          <ChevronDown className="size-4" />
        </span>
      </summary>
      <p className="pt-4 text-sm leading-7 text-slate-600">{answer}</p>
    </details>
  )
}

export { AccordionItem }
