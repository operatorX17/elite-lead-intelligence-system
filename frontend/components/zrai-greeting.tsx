/**
 * ZRAI Lead OS - Greeting Component
 *
 * Operator-first landing surface for chat-driven Lead OS workflows.
 */

"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ZRAI_GREETING } from "@/lib/zrai/constants";

type PipelineStats = {
  leads_discovered: number;
  outreach_sent: number;
  meetings_booked: number;
  leads_qualified: number;
};

type Alert = {
  type: "warning" | "error" | "info";
  message: string;
};

type HealthStatus = {
  status: string;
  service: string;
  agents: Record<string, boolean>;
};

export function ZRAIGreeting() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const hasMeaningfulPipelineStats = Boolean(
    stats &&
      (stats.leads_discovered > 0 ||
        stats.leads_qualified > 0 ||
        stats.outreach_sent > 0 ||
        stats.meetings_booked > 0)
  );

  useEffect(() => {
    async function fetchData() {
      try {
        const [healthRes, metricsRes, governanceRes] = await Promise.all([
          fetch("/api/zrai/health"),
          fetch("/api/zrai/metrics?period=daily"),
          fetch("/api/zrai/governance"),
        ]);

        if (healthRes.ok) {
          const healthData = await healthRes.json();
          if (healthData.success && healthData.data) {
            setHealth(healthData.data);
          }
        }

        if (metricsRes.ok) {
          const metricsData = await metricsRes.json();
          if (metricsData.success && metricsData.data) {
            setStats({
              leads_discovered: metricsData.data.leads_discovered || 0,
              outreach_sent: metricsData.data.outreach_sent || 0,
              meetings_booked: Math.round(
                (metricsData.data.meeting_rate || 0) *
                  (metricsData.data.outreach_sent || 0)
              ),
              leads_qualified: metricsData.data.leads_qualified || 0,
            });
          }
        }

        if (governanceRes.ok) {
          const governanceData = await governanceRes.json();

          if (governanceData.success && governanceData.data) {
            const nextAlerts: Alert[] = [];
            const { budgets, circuit_breakers } = governanceData.data;

            if (budgets?.llm_tokens?.limit) {
              const llmUsage =
                budgets.llm_tokens.used / budgets.llm_tokens.limit;
              if (llmUsage > 0.9) {
                nextAlerts.push({
                  type: "warning",
                  message: "LLM token budget is above 90 percent.",
                });
              }
            }

            if (budgets?.apify_runs?.limit) {
              const apifyUsage =
                budgets.apify_runs.used / budgets.apify_runs.limit;
              if (apifyUsage > 0.9) {
                nextAlerts.push({
                  type: "warning",
                  message: "Apify run budget is above 90 percent.",
                });
              }
            }

            if (budgets?.browser_sessions?.limit) {
              const browserUsage =
                budgets.browser_sessions.used / budgets.browser_sessions.limit;
              if (browserUsage > 0.9) {
                nextAlerts.push({
                  type: "warning",
                  message: "Browser session budget is above 90 percent.",
                });
              }
            }

            if (circuit_breakers) {
              const openCircuits = Object.entries(circuit_breakers)
                .filter(([, state]) => state === "open")
                .map(([name]) => name);

              if (openCircuits.length > 0) {
                nextAlerts.push({
                  type: "error",
                  message: `Open circuit breakers: ${openCircuits.join(", ")}`,
                });
              }
            }

            setAlerts(nextAlerts);
          }
        }
      } catch (error) {
        console.error("Failed to fetch ZRAI operator status:", error);
        setAlerts([
          {
            type: "info",
            message:
              "Backend status is unavailable. Check ZRAI_BACKEND_URL and the Python API server.",
          },
        ]);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  return (
    <div
      className="mx-auto mt-2 flex size-full max-w-5xl flex-col justify-center px-3 md:mt-10 md:px-6"
      key="zrai-greeting"
    >
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-[24px] border border-border/60 bg-[linear-gradient(180deg,rgba(10,10,10,0.98),rgba(18,18,18,0.98))] p-4 text-white shadow-xl shadow-black/10 md:rounded-[28px] md:p-8"
        exit={{ opacity: 0, y: 10 }}
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.2 }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.06),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.06),transparent_22%)]" />

        <div className="relative flex flex-col gap-4 md:gap-6">
          <div className="flex flex-wrap items-center gap-1.5 md:gap-2">
            <Badge className="border border-white/10 bg-white/5 text-white/85 backdrop-blur">
              {health ? `Backend ${health.status}` : "Backend pending"}
            </Badge>
            <Badge className="border border-white/10 bg-white/5 text-white/72 backdrop-blur">
              Operator workspace
            </Badge>
          </div>

          <div className="grid gap-3 md:gap-6 lg:grid-cols-[1.4fr_0.9fr]">
            <div className="space-y-3 md:space-y-4">
              <div>
                <h1 className="max-w-3xl font-semibold text-2xl tracking-tight sm:text-3xl md:text-4xl">
                  {ZRAI_GREETING.title}
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-white/80 sm:text-base md:text-lg">
                  {ZRAI_GREETING.subtitle}
                </p>
                <p className="mt-2 hidden max-w-2xl text-sm text-white/72 md:mt-4 md:block md:text-base">
                  {ZRAI_GREETING.description}
                </p>
              </div>

              {hasMeaningfulPipelineStats ? (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricCard
                    label="Leads discovered"
                    value={stats?.leads_discovered ?? 0}
                  />
                  <MetricCard
                    label="Qualified today"
                    value={stats?.leads_qualified ?? 0}
                  />
                  <MetricCard
                    label="Outreach sent"
                    value={stats?.outreach_sent ?? 0}
                  />
                  <MetricCard
                    label="Meetings projected"
                    value={stats?.meetings_booked ?? 0}
                  />
                </div>
              ) : (
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs text-white/68 md:px-4 md:py-3 md:text-sm">
                  No meaningful activity has been recorded for this session yet.
                  Start with one lead discovery or one lead analysis, then the
                  pipeline totals become useful.
                </div>
              )}
            </div>

            <div className="hidden rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-sm lg:block">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm text-white/80">
                    Current readiness
                  </div>
                  <div className="text-white/60 text-xs">
                    What is actually available right now
                  </div>
                </div>
                <HealthDot ok={health?.status === "healthy"} />
              </div>

              <div className="space-y-3">
                <CapabilityRow
                  active={Boolean(health?.agents?.discovery)}
                  label="Discovery and enrichment"
                />
                <CapabilityRow
                  active={Boolean(health?.agents?.scoring)}
                  label="Intent scoring and prioritization"
                />
                <CapabilityRow
                  active={Boolean(health?.agents?.enrichment)}
                  label="Proof and data enrichment"
                />
                <CapabilityRow
                  active={Boolean(health?.agents?.orchestrator)}
                  label="Full pipeline orchestration"
                />
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="mt-3 grid gap-3 md:mt-4 md:gap-4 lg:grid-cols-[1.15fr_0.85fr]"
        exit={{ opacity: 0, y: 10 }}
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.3 }}
      >
        <div className="rounded-3xl border border-border/60 bg-card/70 p-3 shadow-sm md:p-5">
          <div className="font-medium text-foreground text-xs md:text-sm">
            Good starting moves
          </div>
          <div className="mt-2 grid gap-2 md:mt-3 md:gap-3 md:grid-cols-3">
            <WorkflowCard
              description="Run one discovery and inspect one lead before scaling anything."
              title="1. Find one good clinic"
            />
            <WorkflowCard
              description="Analyze one lead deeply and verify truth, proof, and score all agree."
              title="2. Validate one lead"
            />
            <WorkflowCard
              description="Only draft outreach after the lead looks commercially worth your time."
              title="3. Draft one angle"
            />
          </div>
        </div>

        <div className="hidden rounded-3xl border border-border/60 bg-card/70 p-5 shadow-sm lg:block">
          <div className="font-medium text-foreground text-sm">
            Live status
          </div>

          {loading ? (
            <div className="mt-3 text-muted-foreground text-sm">
              Loading backend status...
            </div>
          ) : alerts.length > 0 ? (
            <div className="mt-3 space-y-2">
              {alerts.map((alert) => (
                <AlertBadge
                  key={`${alert.type}-${alert.message}`}
                  message={alert.message}
                  type={alert.type}
                />
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3 text-emerald-700 text-sm dark:text-emerald-300">
              No active governance blockers detected. The system looks ready for
              chat-driven testing.
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-sm">
      <div className="font-semibold text-2xl text-white md:text-3xl">
        {value.toLocaleString()}
      </div>
      <div className="mt-1 text-white/58 text-xs uppercase tracking-[0.18em]">
        {label}
      </div>
    </div>
  );
}

function AlertBadge({ type, message }: Alert) {
  const colors = {
    warning:
      "border-yellow-500/20 bg-yellow-500/10 text-yellow-800 dark:text-yellow-300",
    error: "border-red-500/20 bg-red-500/10 text-red-800 dark:text-red-300",
    info: "border-blue-500/20 bg-blue-500/10 text-blue-800 dark:text-blue-300",
  };

  const titles = {
    warning: "Warning",
    error: "Issue",
    info: "Info",
  };

  return (
    <div className={`rounded-2xl border px-3 py-2 text-sm ${colors[type]}`}>
      <span className="mr-2 font-medium">{titles[type]}</span>
      {message}
    </div>
  );
}

function WorkflowCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/80 p-3 md:p-4">
      <div className="font-medium text-[13px] text-foreground md:text-sm">{title}</div>
      <p className="mt-1 text-[11px] text-muted-foreground leading-5 md:mt-2 md:text-sm">
        {description}
      </p>
    </div>
  );
}

function CapabilityRow({ active, label }: { active: boolean; label: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.04] px-3 py-2">
      <span className="text-sm text-white/82">{label}</span>
      <span
        className={`rounded-full px-2 py-1 font-medium text-[11px] uppercase tracking-wide ${
          active
            ? "bg-emerald-400/14 text-emerald-200"
            : "bg-white/10 text-white/60"
        }`}
      >
        {active ? "ready" : "pending"}
      </span>
    </div>
  );
}

function HealthDot({ ok }: { ok: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`inline-flex size-2.5 rounded-full ${
          ok
            ? "bg-emerald-300 shadow-[0_0_14px_rgba(110,231,183,0.8)]"
            : "bg-amber-300"
        }`}
      />
      <span className="text-white/58 text-xs uppercase tracking-[0.2em]">
        {ok ? "stable" : "degraded"}
      </span>
    </div>
  );
}
