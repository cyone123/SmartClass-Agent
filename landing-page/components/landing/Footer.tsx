import { navigationItems } from "@/lib/site-content"

export function Footer() {
  return (
    <footer className="px-4 pb-8 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 rounded-[28px] border border-white/70 bg-white/78 px-6 py-6 text-sm text-slate-500 shadow-[0_18px_48px_rgba(15,23,42,0.05)] backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <div className="font-heading text-lg tracking-[-0.03em] text-slate-950">SmartClass Showcase</div>
          <p className="max-w-2xl leading-7">
            比赛展示页基于当前仓库真实实现整理，聚焦教师智能工作台的功能闭环与技术方案。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {navigationItems.map((item) => (
            <a key={item.href} href={item.href} className="transition hover:text-slate-900">
              {item.label}
            </a>
          ))}
          <span className="text-slate-400">2026 SmartClass</span>
        </div>
      </div>
    </footer>
  )
}
