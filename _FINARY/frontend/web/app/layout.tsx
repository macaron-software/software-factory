import type { Metadata } from "next";
import { Providers } from "./providers";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Finary",
  description: "Gestion de patrimoine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <body>
        <Providers>
          <div className="flex min-h-screen" style={{ background: "var(--bg-2)" }}>
            <Sidebar />
            <main className="flex-1 overflow-auto">
              <div className="max-w-[960px] mx-auto px-8 py-8">
                {children}
              </div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
