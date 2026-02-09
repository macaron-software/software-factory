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
          <div className="flex min-h-screen bg-bg-2">
            <Sidebar />
            <main className="flex-1 overflow-auto">
              <div className="max-w-[1080px] mx-auto px-6 py-6 lg:px-10 lg:py-8">
                {children}
              </div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
