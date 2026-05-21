import { SignalsPage } from "@/components/SignalsPage";

export default function SignalsRoute() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-3xl font-bold text-white">Buy & sell signals</h1>
      <p className="mt-2 text-slate-400">
        Signals are issued the day before the planned trade date so you can prepare entries and exits.
      </p>
      <div className="mt-8">
        <SignalsPage />
      </div>
    </div>
  );
}
