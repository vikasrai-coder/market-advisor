import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Market Advisor — AI Stock Picks",
  description: "10 daily buy recommendations powered by Hugging Face AI, trends, and news",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">
        <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-50">
          <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
            <Link href="/" className="text-lg font-bold tracking-tight text-white">
              Market <span className="text-emerald-400">Advisor</span>
            </Link>
            <div className="flex gap-6 text-sm font-medium text-slate-400">
              <Link href="/" className="hover:text-white">
                Top 10 Buys
              </Link>
              <Link href="/signals" className="hover:text-white">
                Buy / Sell Signals
              </Link>
            </div>
          </nav>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-600">
          Not financial advice. For research and education only.
        </footer>
      </body>
    </html>
  );
}
