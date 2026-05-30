import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "台灣旅遊 AI 助理",
  description: "用 AI 串接 TDX 與氣象資料，規劃你的台灣之旅",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
