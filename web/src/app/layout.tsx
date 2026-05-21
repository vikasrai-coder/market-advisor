import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthHeader } from "@/components/AuthHeader";
import { createClient } from "@/lib/supabase/server";
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
  title: "Market Advisor — Indian Stock Picks (NSE)",
  description: "10 daily NSE buy recommendations via Yahoo Finance, Hugging Face AI, and Supabase",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">
        {user ? <AuthHeader email={user.email} /> : null}
        <main className="flex-1">{children}</main>
        {user ? (
          <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-600">
            Not financial advice. For research and education only.
          </footer>
        ) : null}
      </body>
    </html>
  );
}
