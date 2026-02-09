/**
 * ZRAI Lead OS - Greeting Component
 * 
 * Custom greeting for ZRAI Lead OS with branding and pipeline stats.
 */

'use client';

import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { ZRAI_GREETING } from '@/lib/zrai/constants';

interface PipelineStats {
  leads_discovered: number;
  outreach_sent: number;
  meetings_booked: number;
}

interface Alert {
  type: 'warning' | 'error' | 'info';
  message: string;
}

export function ZRAIGreeting() {
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch pipeline stats and alerts
    async function fetchData() {
      try {
        const [metricsRes, governanceRes] = await Promise.all([
          fetch('/api/zrai/metrics?period=daily'),
          fetch('/api/zrai/governance'),
        ]);

        if (metricsRes.ok) {
          const metricsData = await metricsRes.json();
          if (metricsData.success && metricsData.data) {
            setStats({
              leads_discovered: metricsData.data.leads_discovered || 0,
              outreach_sent: metricsData.data.outreach_sent || 0,
              meetings_booked: Math.round((metricsData.data.meeting_rate || 0) * (metricsData.data.outreach_sent || 0)),
            });
          }
        }

        if (governanceRes.ok) {
          const govData = await governanceRes.json();
          if (govData.success && govData.data) {
            const newAlerts: Alert[] = [];

            // Check for budget warnings
            const { budgets, circuit_breakers } = govData.data;
            if (budgets) {
              if (budgets.llm_tokens.used / budgets.llm_tokens.limit > 0.9) {
                newAlerts.push({ type: 'warning', message: 'LLM token budget nearly exhausted' });
              }
              if (budgets.apify_runs.used / budgets.apify_runs.limit > 0.9) {
                newAlerts.push({ type: 'warning', message: 'Apify run budget nearly exhausted' });
              }
              if (budgets.browser_sessions.used / budgets.browser_sessions.limit > 0.9) {
                newAlerts.push({ type: 'warning', message: 'Browser session budget nearly exhausted' });
              }
            }

            // Check for open circuit breakers
            if (circuit_breakers) {
              const openCircuits = Object.entries(circuit_breakers)
                .filter(([_, state]) => state === 'open')
                .map(([name]) => name);
              if (openCircuits.length > 0) {
                newAlerts.push({
                  type: 'error',
                  message: `Circuit breakers open: ${openCircuits.join(', ')}`,
                });
              }
            }

            setAlerts(newAlerts);
          }
        }
      } catch (error) {
        console.error('Failed to fetch ZRAI stats:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  return (
    <div
      className="mx-auto mt-4 flex size-full max-w-3xl flex-col justify-center px-4 md:mt-16 md:px-8"
      key="zrai-greeting"
    >
      {/* Title */}
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="font-semibold text-xl md:text-2xl"
        exit={{ opacity: 0, y: 10 }}
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.3 }}
      >
        {ZRAI_GREETING.title}
      </motion.div>

      {/* Subtitle */}
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="text-lg text-zinc-500 md:text-xl"
        exit={{ opacity: 0, y: 10 }}
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.4 }}
      >
        {ZRAI_GREETING.subtitle}
      </motion.div>

      {/* Description */}
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 text-sm text-zinc-400 md:text-base"
        exit={{ opacity: 0, y: 10 }}
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.5 }}
      >
        {ZRAI_GREETING.description}
      </motion.div>

      {/* Pipeline Stats */}
      {!loading && stats && (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 grid grid-cols-3 gap-4"
          exit={{ opacity: 0, y: 10 }}
          initial={{ opacity: 0, y: 10 }}
          transition={{ delay: 0.6 }}
        >
          <StatCard label="Leads Discovered" value={stats.leads_discovered} />
          <StatCard label="Outreach Sent" value={stats.outreach_sent} />
          <StatCard label="Meetings Booked" value={stats.meetings_booked} />
        </motion.div>
      )}

      {/* Alerts */}
      {!loading && alerts.length > 0 && (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 space-y-2"
          exit={{ opacity: 0, y: 10 }}
          initial={{ opacity: 0, y: 10 }}
          transition={{ delay: 0.7 }}
        >
          {alerts.map((alert, index) => (
            <AlertBadge key={index} type={alert.type} message={alert.message} />
          ))}
        </motion.div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        {value.toLocaleString()}
      </div>
      <div className="text-xs text-zinc-500">{label}</div>
    </div>
  );
}

function AlertBadge({ type, message }: Alert) {
  const colors = {
    warning: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    error: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    info: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  };

  const icons = {
    warning: '⚠️',
    error: '🔴',
    info: 'ℹ️',
  };

  return (
    <div className={`rounded-md px-3 py-2 text-sm ${colors[type]}`}>
      <span className="mr-2">{icons[type]}</span>
      {message}
    </div>
  );
}
