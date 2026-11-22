import type { ReactNode } from "react";
import "../theme/tokens.css";

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="ko"><body>{children}</body></html>;
}
