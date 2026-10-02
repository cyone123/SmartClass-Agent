"use client"

import { motion } from "framer-motion"
import { SectionHeading } from "@/components/landing/SectionHeading"
import { AccordionItem } from "@/components/ui/accordion"
import { faqItems } from "@/lib/site-content"

export function FAQSection() {
  return (
    <section id="faq" className="px-4 pt-8 pb-2 h-full flex flex-col justify-center items-center">
      <div className="w-full max-w-7xl space-y-6">
        <SectionHeading
          eyebrow="FAQ"
          title="把你可能追问的问题，转化为清晰、可验证的回答"
          description="FAQ 不是补充信息，而是帮助观众快速理解 SmartClass 为什么不是普通 AI Demo，以及它的工程价值到底落在哪里。"
        />

        <div className="grid gap-4">
          {faqItems.map((item, index) => (
            <motion.div
              key={item.question}
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: "easeOut" }}
            >
              <AccordionItem question={item.question} answer={item.answer} />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
