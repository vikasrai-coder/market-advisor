"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export function AuthHeader({
  email,
  showNav = true,
}: {
  email?: string | null;
  showNav?: boolean;
}) {
  const router = useRouter();

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur sticky top-0 z-50">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-lg font-bold tracking-tight text-white">
          Market <span className="text-emerald-400">Advisor</span>
        </Link>
        {showNav && (
          <div className="flex items-center gap-6 text-sm font-medium text-slate-400">
            <Link href="/" className="hover:text-white">
              Top 10 Buys
            </Link>
            <Link href="/signals" className="hover:text-white">
              Buy / Sell Signals
            </Link>
            {email && <span className="hidden text-slate-500 sm:inline">{email}</span>}
            <button
              type="button"
              onClick={signOut}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 hover:border-slate-500 hover:text-white"
            >
              Sign out
            </button>
          </div>
        )}
      </nav>
    </header>
  );
}
