import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import "../theme/tokens.css";
export const metadata: Metadata = {
  title: "Goldnam Sachs · 개인 리서치",
  description:
    "순위, 타이밍, 리스크를 과거 근거와 함께 확인하는 개인 리서치 워크스페이스",
  robots: { index: false, follow: false },
  manifest: "/manifest-personal.webmanifest",
  icons: { icon: "/icons/personal-192.png", apple: "/icons/personal-180.png" },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Goldnam Sachs",
  },
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#181818",
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
