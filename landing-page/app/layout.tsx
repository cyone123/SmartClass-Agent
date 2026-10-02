import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartClass | 多模态教学智能体比赛展示",
  description:
    "SmartClass 是面向教师场景的多模态教学智能体系统，围绕教学设计、知识库、附件分析、产物生成与差量修订构建完整工作流闭环。",
  keywords: [
    "SmartClass",
    "教学智能体",
    "LangGraph",
    "RAG",
    "多模态",
    "教育 AI",
    "产物差量修改",
  ],
  openGraph: {
    title: "SmartClass | 多模态教学智能体比赛展示",
    description:
      "围绕教师真实备课流程构建的智能工作台，展示教学对话、RAG、多模态附件分析、产物生成与修订闭环。",
  },
  twitter: {
    card: "summary_large_image",
    title: "SmartClass | 多模态教学智能体比赛展示",
    description:
      "面向教师真实备课流程的多模态智能工作台。",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full scroll-smooth antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
