import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type SectionHeadingProps = {
  eyebrow: string
  title: string
  description: string
  align?: "left" | "center"
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
}: SectionHeadingProps) {
  return (
    <div className={cn("flex flex-col gap-5", align === "center" && "items-center text-center")}>
      <Badge variant="secondary" className="w-fit">
        {eyebrow}
      </Badge>
      <div className="space-y-4">
        <h2 className="font-heading text-3xl leading-tight font-semibold tracking-[-0.03em] text-slate-950 sm:text-4xl">
          {title}
        </h2>
        <p className="max-w-3xl text-base leading-8 text-slate-600 sm:text-lg">{description}</p>
      </div>
    </div>
  )
}
