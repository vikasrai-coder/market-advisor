import "@ant-design/v5-patch-for-react-19";
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
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    shortcut: "/favicon.ico",
    apple: "/icon.png",
  },
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
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                const originalError = console.error;
                console.error = function(...args) {
                  if (args[0] && typeof args[0] === 'string' && (args[0].includes('[antd: compatible]') || args[0].includes('[antd: message]') || args[0].includes('[antd: Modal]'))) {
                    return;
                  }
                  originalError.apply(console, args);
                };
              })();
            `
          }}
        />
      </head>
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
