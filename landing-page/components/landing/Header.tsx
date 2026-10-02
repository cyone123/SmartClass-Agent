import Image from "next/image"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { navigationItems } from "@/lib/site-content"
import { cn } from "@/lib/utils"

export function Header() {
  return (
    <header className="sticky top-0 z-50 px-4 pt-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 rounded-full border border-white/75 bg-white/80 px-4 py-3 shadow-[0_16px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:px-6">
        <a href="#top" className="flex min-w-0 items-center gap-3">
          <div className="relative flex size-11 items-center justify-center overflow-hidden rounded-full border border-sky-100 bg-sky-50 shadow-inner">
            <Image src="/logo360x360.png" alt="SmartClass 标识" width={44} height={44} priority />
          </div>
          <div className="min-w-0">
            <div className="font-heading text-lg font-semibold tracking-[-0.03em] text-slate-950">SmartClass</div>
            <div className="text-xs tracking-[0.18em] text-slate-500 uppercase">Teaching Intelligence Workspace</div>
          </div>
        </a>

        <nav className="hidden items-center gap-6 lg:flex">
          {navigationItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm text-slate-600 transition hover:text-slate-950"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {/* <Badge className="hidden md:inline-flex">比赛展示版</Badge> */}
          <a
            href="#final-cta"
            className={cn(
              buttonVariants({ size: "sm" }),
              "rounded-full bg-slate-950 px-4 text-white hover:bg-slate-800"
            )}
          >
            查看亮点总结
          </a>
        </div>
      </div>
    </header>
  )
}
