import type { Metadata } from "next";
import { Shell } from "../components/Shell";
import "./globals.css";

export const metadata: Metadata = { title: "CA Workbench · Kosh AI", description: "Multi-client compliance exception console — sandbox" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <Shell>{children}</Shell>
  </body></html>;
}
