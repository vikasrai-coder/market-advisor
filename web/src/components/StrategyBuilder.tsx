"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  addStrategyVersion,
  cloneStrategy,
  createStrategy,
  getStrategies,
  validateStrategy,
  type Strategy,
  type StrategyDefinition,
  type StrategyValidation,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

const INDICATORS = ["rsi", "ema", "sma", "macd", "supertrend", "bollinger_upper", "volume", "price"];
const OPERATORS = [">", ">=", "<", "<=", "=="];
const TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "1d"];

type BuilderState = {
  name: string;
  description: string;
  timeframe: string;
  market: string;
  symbols: string;
  entryIndicator: string;
  entryPeriod: number;
  entryOperator: string;
  entryValue: number;
  exitTargetPct: number;
  exitStopPct: number;
  trailingStopPct: number;
  riskPerTradePct: number;
  maxReentries: number;
};

const DEFAULT_STATE: BuilderState = {
  name: "RSI EMA Pullback",
  description: "No-code momentum strategy generated from the first platform builder.",
  timeframe: "5m",
  market: "NSE",
  symbols: "RELIANCE,TCS,HDFCBANK",
  entryIndicator: "rsi",
  entryPeriod: 14,
  entryOperator: "<",
  entryValue: 35,
  exitTargetPct: 2,
  exitStopPct: 1,
  trailingStopPct: 0.8,
  riskPerTradePct: 1,
  maxReentries: 1,
};

export default function StrategyBuilder() {
  const [userId, setUserId] = useState("");
  const [state, setState] = useState<BuilderState>(DEFAULT_STATE);
  const [jsonDraft, setJsonDraft] = useState("");
  const [useJsonDraft, setUseJsonDraft] = useState(false);
  const [validation, setValidation] = useState<StrategyValidation | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const definition = useMemo(() => buildDefinition(state), [state]);
  const displayedJson = useJsonDraft ? jsonDraft : JSON.stringify(definition, null, 2);

  useEffect(() => {
    async function loadUser() {
      const offlineId = localStorage.getItem("offline_user_id");
      if (offlineId) {
        setUserId(offlineId);
        return;
      }
      const supabase = createClient();
      const { data } = await supabase.auth.getUser();
      if (data.user?.id) setUserId(data.user.id);
    }
    void loadUser();
  }, []);

  const refreshStrategies = useCallback(async (id = userId) => {
    try {
      const res = await getStrategies(id);
      setStrategies(res.strategies);
      if (!selectedStrategyId && res.strategies[0]) setSelectedStrategyId(res.strategies[0].id);
    } catch (err) {
      console.error(err);
    }
  }, [selectedStrategyId, userId]);

  useEffect(() => {
    if (!userId) return;
    // Initial strategy hydration reads API state for the current user.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshStrategies(userId);
  }, [refreshStrategies, userId]);

  function getWorkingDefinition(): StrategyDefinition {
    if (!useJsonDraft) return definition;
    return JSON.parse(jsonDraft) as StrategyDefinition;
  }

  async function handleValidate() {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const result = await validateStrategy(getWorkingDefinition());
      setValidation(result);
      setMessage(result.valid ? "Strategy validates. Ready to save as an immutable version." : "Strategy needs fixes.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveNew() {
    if (!userId) {
      setError("User session not loaded.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const res = await createStrategy({
        user_id: userId,
        name: state.name,
        description: state.description,
        visibility: "private",
        status: "draft",
        definition: getWorkingDefinition(),
      });
      setSelectedStrategyId(res.strategy.id);
      setMessage("Strategy saved with v1.");
      await refreshStrategies();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveVersion() {
    if (!selectedStrategyId) {
      setError("Select a strategy first.");
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await addStrategyVersion(selectedStrategyId, {
        user_id: userId,
        definition: getWorkingDefinition(),
        notes: "Saved from no-code builder",
      });
      setMessage("New immutable version saved.");
      await refreshStrategies();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Version save failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleClone(strategy: Strategy) {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const res = await cloneStrategy(strategy.id, userId, `${strategy.name} Copy`);
      setSelectedStrategyId(res.strategy.id);
      setMessage("Strategy cloned as a private draft.");
      await refreshStrategies();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clone failed.");
    } finally {
      setLoading(false);
    }
  }

  function loadStrategy(strategy: Strategy) {
    const current = strategy.current_version;
    if (!current) return;
    const next = stateFromDefinition(current.definition, strategy);
    setState(next);
    setSelectedStrategyId(strategy.id);
    setUseJsonDraft(false);
    setValidation(null);
    setMessage(`Loaded ${strategy.name} ${current.version_label}.`);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <section className="min-w-0">
        <div className="mb-6">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-300">Strategy Builder</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white">No-code algo strategy lab</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Create validated, versioned strategy definitions. Execution and broker deployment stay locked until risk controls land.
          </p>
        </div>

        <div className="grid gap-4">
          <Panel title="Strategy">
            <div className="grid gap-3 sm:grid-cols-2">
              <TextInput label="Name" value={state.name} onChange={(name) => setState((s) => ({ ...s, name }))} />
              <SelectInput label="Timeframe" value={state.timeframe} options={TIMEFRAMES} onChange={(timeframe) => setState((s) => ({ ...s, timeframe }))} />
              <TextInput label="Market" value={state.market} onChange={(market) => setState((s) => ({ ...s, market: market.toUpperCase() }))} />
              <TextInput label="Symbols" value={state.symbols} onChange={(symbols) => setState((s) => ({ ...s, symbols }))} />
              <div className="sm:col-span-2">
                <TextInput label="Description" value={state.description} onChange={(description) => setState((s) => ({ ...s, description }))} />
              </div>
            </div>
          </Panel>

          <Panel title="Entry Rules">
            <div className="grid gap-3 sm:grid-cols-4">
              <SelectInput label="Indicator" value={state.entryIndicator} options={INDICATORS} onChange={(entryIndicator) => setState((s) => ({ ...s, entryIndicator }))} />
              <NumberInput label="Period" value={state.entryPeriod} onChange={(entryPeriod) => setState((s) => ({ ...s, entryPeriod }))} />
              <SelectInput label="Operator" value={state.entryOperator} options={OPERATORS} onChange={(entryOperator) => setState((s) => ({ ...s, entryOperator }))} />
              <NumberInput label="Value" value={state.entryValue} onChange={(entryValue) => setState((s) => ({ ...s, entryValue }))} />
            </div>
          </Panel>

          <Panel title="Exit And Risk">
            <div className="grid gap-3 sm:grid-cols-5">
              <NumberInput label="Target %" value={state.exitTargetPct} onChange={(exitTargetPct) => setState((s) => ({ ...s, exitTargetPct }))} />
              <NumberInput label="Stop %" value={state.exitStopPct} onChange={(exitStopPct) => setState((s) => ({ ...s, exitStopPct }))} />
              <NumberInput label="Trail %" value={state.trailingStopPct} onChange={(trailingStopPct) => setState((s) => ({ ...s, trailingStopPct }))} />
              <NumberInput label="Risk %" value={state.riskPerTradePct} onChange={(riskPerTradePct) => setState((s) => ({ ...s, riskPerTradePct }))} />
              <NumberInput label="Re-entries" value={state.maxReentries} onChange={(maxReentries) => setState((s) => ({ ...s, maxReentries }))} />
            </div>
          </Panel>

          <Panel
            title="JSON Preview"
            action={
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                <input
                  type="checkbox"
                  checked={useJsonDraft}
                  onChange={(event) => {
                    setUseJsonDraft(event.target.checked);
                    if (event.target.checked) setJsonDraft(JSON.stringify(definition, null, 2));
                  }}
                  className="h-4 w-4 accent-emerald-400"
                />
                Use edited JSON
              </label>
            }
          >
            <textarea
              value={displayedJson}
              onChange={(event) => setJsonDraft(event.target.value)}
              readOnly={!useJsonDraft}
              className="h-80 w-full resize-y rounded-md border border-slate-800 bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200 outline-none focus:border-emerald-400"
              spellCheck={false}
            />
          </Panel>

          <div className="flex flex-wrap gap-2">
            <ActionButton onClick={handleValidate} disabled={loading}>Validate</ActionButton>
            <ActionButton onClick={handleSaveNew} disabled={loading || !userId}>Save New</ActionButton>
            <ActionButton onClick={handleSaveVersion} disabled={loading || !selectedStrategyId || !userId}>Save Version</ActionButton>
          </div>

          {message && <Notice tone="ok">{message}</Notice>}
          {error && <Notice tone="bad">{error}</Notice>}
          {validation && (
            <Notice tone={validation.valid ? "ok" : "bad"}>
              {validation.valid ? "Valid definition" : validation.errors.join(" ")}
              {validation.warnings.length ? ` Warnings: ${validation.warnings.join(" ")}` : ""}
            </Notice>
          )}
        </div>
      </section>

      <aside className="lg:sticky lg:top-24 lg:self-start">
        <Panel title="Saved Strategies">
          {!userId ? (
            <p className="text-sm text-slate-500">Loading session...</p>
          ) : strategies.length === 0 ? (
            <p className="text-sm text-slate-500">No strategies yet. Save first version to begin.</p>
          ) : (
            <div className="grid gap-3">
              {strategies.map((strategy) => (
                <div
                  key={strategy.id}
                  className={`rounded-md border p-3 ${
                    selectedStrategyId === strategy.id
                      ? "border-emerald-400/70 bg-emerald-950/20"
                      : "border-slate-800 bg-slate-950/60"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-white">{strategy.name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {strategy.current_version?.version_label || "No version"} · {strategy.status} · {strategy.visibility}
                      </p>
                    </div>
                    <span className="rounded border border-slate-700 px-2 py-1 text-[10px] font-bold uppercase text-slate-400">
                      {strategy.current_version?.validation_status || "draft"}
                    </span>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => loadStrategy(strategy)}
                      className="rounded border border-slate-700 px-2.5 py-1.5 text-xs font-semibold text-slate-200 hover:border-emerald-400 hover:text-emerald-200"
                    >
                      Load
                    </button>
                    <button
                      type="button"
                      onClick={() => handleClone(strategy)}
                      className="rounded border border-slate-700 px-2.5 py-1.5 text-xs font-semibold text-slate-200 hover:border-sky-400 hover:text-sky-200"
                    >
                      Clone
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </aside>
    </div>
  );
}

function buildDefinition(state: BuilderState): StrategyDefinition {
  const symbols = state.symbols
    .split(",")
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);

  return {
    meta: { name: state.name, market: state.market.toUpperCase(), timeframe: state.timeframe },
    universe: { type: "watchlist", symbols },
    entry: {
      all: [
        {
          indicator: state.entryIndicator,
          period: state.entryPeriod,
          operator: state.entryOperator,
          value: state.entryValue,
        },
      ],
    },
    exit: {
      any: [
        { target_pct: state.exitTargetPct },
        { stop_loss_pct: state.exitStopPct },
        { trailing_stop_pct: state.trailingStopPct },
      ],
    },
    position: { sizing: "fixed_risk", risk_per_trade_pct: state.riskPerTradePct },
    reentry: {
      enabled: state.maxReentries > 0,
      max_count: state.maxReentries,
      cooldown_candles: 3,
    },
    risk: {
      max_daily_loss_pct: 3,
      max_open_positions: 3,
      require_deployment_confirmation: true,
    },
  };
}

function stateFromDefinition(definition: StrategyDefinition, strategy: Strategy): BuilderState {
  const entry = Array.isArray((definition.entry as { all?: unknown[] }).all)
    ? ((definition.entry as { all: Record<string, unknown>[] }).all[0] ?? {})
    : {};
  const exits = Array.isArray((definition.exit as { any?: unknown[] }).any)
    ? (definition.exit as { any: Record<string, number>[] }).any
    : [];
  return {
    ...DEFAULT_STATE,
    name: strategy.name,
    description: strategy.description || "",
    timeframe: definition.meta?.timeframe || DEFAULT_STATE.timeframe,
    market: definition.meta?.market || DEFAULT_STATE.market,
    symbols: definition.universe?.symbols?.join(",") || DEFAULT_STATE.symbols,
    entryIndicator: String(entry.indicator || DEFAULT_STATE.entryIndicator),
    entryPeriod: Number(entry.period || DEFAULT_STATE.entryPeriod),
    entryOperator: String(entry.operator || DEFAULT_STATE.entryOperator),
    entryValue: Number(entry.value || DEFAULT_STATE.entryValue),
    exitTargetPct: Number(exits.find((item) => item.target_pct)?.target_pct || DEFAULT_STATE.exitTargetPct),
    exitStopPct: Number(exits.find((item) => item.stop_loss_pct)?.stop_loss_pct || DEFAULT_STATE.exitStopPct),
    trailingStopPct: Number(exits.find((item) => item.trailing_stop_pct)?.trailing_stop_pct || DEFAULT_STATE.trailingStopPct),
    riskPerTradePct: Number((definition.position as { risk_per_trade_pct?: number })?.risk_per_trade_pct || DEFAULT_STATE.riskPerTradePct),
    maxReentries: Number((definition.reentry as { max_count?: number })?.max_count || DEFAULT_STATE.maxReentries),
  };
}

function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/35 p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-slate-200">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold text-slate-400">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-400"
      />
    </label>
  );
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold text-slate-400">
      {label}
      <input
        type="number"
        step="0.1"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-400"
      />
    </label>
  );
}

function SelectInput({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold text-slate-400">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-400"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function ActionButton({ children, disabled, onClick }: { children: ReactNode; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-md border border-emerald-400/50 bg-emerald-500 px-4 py-2 text-sm font-bold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-800 disabled:text-slate-500"
    >
      {children}
    </button>
  );
}

function Notice({ tone, children }: { tone: "ok" | "bad"; children: ReactNode }) {
  return (
    <div
      className={`rounded-md border px-4 py-3 text-sm ${
        tone === "ok"
          ? "border-emerald-400/30 bg-emerald-950/30 text-emerald-100"
          : "border-red-400/30 bg-red-950/30 text-red-100"
      }`}
    >
      {children}
    </div>
  );
}
