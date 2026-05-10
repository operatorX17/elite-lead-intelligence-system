"use client";

/**
 * ZRAI Metrics Dashboard Artifact - Client Component
 * 
 * Displays system metrics, budgets, and agent health.
 */

import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import type { SystemMetrics, AgentHealth } from "@/lib/zrai/types";

type MetricsDashboardMetadata = {
  metrics: SystemMetrics | null;
  loading: boolean;
};

function MetricCard({ 
  label, 
  value, 
  trend, 
  format = 'number' 
}: { 
  label: string; 
  value: number; 
  trend?: number;
  format?: 'number' | 'percent' | 'currency';
}) {
  const formattedValue = format === 'percent' 
    ? `${(value * 100).toFixed(1)}%`
    : format === 'currency'
    ? `$${value.toFixed(2)}`
    : value.toLocaleString();

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-800">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-bold">{formattedValue}</div>
      {trend !== undefined && (
        <div className={`mt-1 text-xs ${trend >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
        </div>
      )}
    </div>
  );
}

function BudgetBar({ 
  label, 
  used, 
  limit 
}: { 
  label: string; 
  used: number; 
  limit: number;
}) {
  const percentage = (used / limit) * 100;
  const color = percentage >= 90 ? 'bg-red-500' : percentage >= 70 ? 'bg-yellow-500' : 'bg-green-500';
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className="text-zinc-500">{used.toLocaleString()} / {limit.toLocaleString()}</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700">
        <div 
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}

function AgentHealthCard({ name, health }: { name: string; health: AgentHealth }) {
  const statusColors: Record<string, string> = {
    healthy: 'bg-green-500',
    degraded: 'bg-yellow-500',
    down: 'bg-red-500',
  };

  const circuitColors: Record<string, string> = {
    closed: 'text-green-600',
    half_open: 'text-yellow-600',
    open: 'text-red-600',
  };

  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`size-2 rounded-full ${statusColors[health.status]}`} />
          <span className="font-medium capitalize">{name.replace('_', ' ')}</span>
        </div>
        <span className={`text-xs ${circuitColors[health.circuit_breaker]}`}>
          {health.circuit_breaker}
        </span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-zinc-500">
        <div>Latency: {health.avg_latency_ms}ms</div>
        <div>Success: {(health.success_rate * 100).toFixed(0)}%</div>
      </div>
      {health.last_error && (
        <div className="mt-2 truncate text-xs text-red-500" title={health.last_error}>
          {health.last_error}
        </div>
      )}
    </div>
  );
}

function MetricsDashboardContent({ 
  content, 
  metadata,
}: { 
  content: string; 
  metadata: MetricsDashboardMetadata;
}) {
  let metrics: SystemMetrics | null = metadata?.metrics || null;
  
  if (!metrics && content) {
    try {
      metrics = JSON.parse(content);
    } catch {
      // Content might not be JSON
    }
  }

  if (!metrics) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No metrics available</div>
          <div className="text-sm">Use the check governance tool to load metrics</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      {/* Header */}
      <div className="border-b border-zinc-200 p-4 dark:border-zinc-700">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-semibold">System Metrics</div>
            <div className="text-xs text-zinc-500">
              Period: {metrics.period} • Last updated: {new Date().toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="border-b border-zinc-200 p-4 dark:border-zinc-700">
        <div className="mb-3 text-sm font-medium">Performance</div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Reply Rate" value={metrics.reply_rate} format="percent" />
          <MetricCard label="Meeting Rate" value={metrics.meeting_rate} format="percent" />
          <MetricCard label="Cost/Meeting" value={metrics.cost_per_meeting} format="currency" />
          <MetricCard label="Leads Discovered" value={metrics.leads_discovered} />
        </div>
      </div>

      {/* Pipeline Stats */}
      <div className="border-b border-zinc-200 p-4 dark:border-zinc-700">
        <div className="mb-3 text-sm font-medium">Pipeline</div>
        <div className="grid grid-cols-3 gap-3">
          <MetricCard label="Qualified" value={metrics.leads_qualified} />
          <MetricCard label="Outreach Sent" value={metrics.outreach_sent} />
          <MetricCard label="Conversion" value={metrics.leads_qualified / Math.max(metrics.leads_discovered, 1)} format="percent" />
        </div>
      </div>

      {/* Budget Consumption */}
      <div className="border-b border-zinc-200 p-4 dark:border-zinc-700">
        <div className="mb-3 text-sm font-medium">Budget Consumption</div>
        <div className="space-y-3">
          <BudgetBar 
            label="LLM Tokens" 
            used={metrics.budget.llm_tokens.used} 
            limit={metrics.budget.llm_tokens.limit} 
          />
          <BudgetBar 
            label="Apify Runs" 
            used={metrics.budget.apify_runs.used} 
            limit={metrics.budget.apify_runs.limit} 
          />
          <BudgetBar 
            label="Browser Sessions" 
            used={metrics.budget.browser_sessions.used} 
            limit={metrics.budget.browser_sessions.limit} 
          />
        </div>
      </div>

      {/* Agent Health */}
      <div className="p-4">
        <div className="mb-3 text-sm font-medium">Agent Health</div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {Object.entries(metrics.agent_health).map(([name, health]) => (
            <AgentHealthCard key={name} name={name} health={health} />
          ))}
        </div>
      </div>
    </div>
  );
}

export const metricsDashboardArtifact = new Artifact<"metrics-dashboard", MetricsDashboardMetadata>({
  kind: "metrics-dashboard",
  description: "Display system metrics, budgets, and agent health status",
  initialize: ({ setMetadata }) => {
    setMetadata({
      metrics: null,
      loading: false,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-metricsDashboard") {
      const data = (streamPart as any).data as SystemMetrics;
      setMetadata((prev) => ({
        ...prev,
        metrics: data,
        loading: false,
      }));
      setArtifact((draft) => ({
        ...draft,
        content: JSON.stringify(data),
        status: "idle",
      }));
    }
  },
  content: (props) => (
    <MetricsDashboardContent 
      content={props.content} 
      metadata={props.metadata}
    />
  ),
  actions: [
    {
      icon: <UndoIcon size={18} />,
      description: "View Previous version",
      onClick: ({ handleVersionChange }) => handleVersionChange("prev"),
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
    },
    {
      icon: <RedoIcon size={18} />,
      description: "View Next version",
      onClick: ({ handleVersionChange }) => handleVersionChange("next"),
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
    },
    {
      icon: <CopyIcon size={18} />,
      description: "Copy metrics",
      onClick: ({ content }) => {
        navigator.clipboard.writeText(content);
        toast.success("Metrics copied!");
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">🔄</span>,
      description: "Refresh metrics",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Refresh the governance and metrics data" }],
        });
      },
    },
  ],
});
