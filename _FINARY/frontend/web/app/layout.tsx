import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Finary — Patrimoine",
  description: "Gestion de patrimoine personnel",
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
          <div className="min-h-screen bg-gray-50">
            <nav className="bg-white border-b border-gray-200 px-6 py-3">
              <div className="flex items-center justify-between max-w-7xl mx-auto">
                <h1 className="text-xl font-bold text-gray-900">💰 Finary</h1>
                <div className="flex gap-6 text-sm font-medium">
                  <a href="/" className="text-gray-700 hover:text-emerald-600">
                    Patrimoine
                  </a>
                  <a
                    href="/portfolio"
                    className="text-gray-700 hover:text-emerald-600"
                  >
                    Portfolio
                  </a>
                  <a
                    href="/accounts"
                    className="text-gray-700 hover:text-emerald-600"
                  >
                    Comptes
                  </a>
                  <a
                    href="/budget"
                    className="text-gray-700 hover:text-emerald-600"
                  >
                    Budget
                  </a>
                </div>
              </div>
            </nav>
            <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
