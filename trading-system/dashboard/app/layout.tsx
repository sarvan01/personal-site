import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Trading Cockpit",
  description: "Two-sleeve trading system dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
