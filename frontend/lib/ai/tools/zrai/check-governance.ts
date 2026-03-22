/**
 * ZRAI Lead OS - Check Governance Tool
 *
 * Checks current governance status including rate limits, budgets, and circuit breakers.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { toSystemMetrics } from "@/lib/zrai/transformers";
import { createZRAIProgressReporter } from "./progress";

export const checkGovernance = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Check the current governance status of the ZRAI system.
Use this tool to see rate limits, budget consumption, circuit breaker states, and agent health.
Helpful for understanding system capacity and any active restrictions.`,
    inputSchema: z.object({}),
    execute: async (_input: Record<string, never>) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "checkGovernance",
        title: "Checking system governance",
        stages: ["Inspect limits", "Read health signals", "Prepare dashboard"],
      });
      progress.start("Collecting budgets, circuit breakers, and agent health.");

      try {
        progress.advance(
          1,
          "Loading live governance and health metrics from the backend."
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.governance, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(
            1,
            data.error?.message || "Failed to fetch governance status",
            { status: response.status }
          );
          return {
            success: false,
            error: data.error?.message || "Failed to fetch governance status",
            suggestion: "Try again later.",
          };
        }

        const {
          rate_limits,
          budgets,
          circuit_breakers,
          agent_health,
          kill_switches,
        } = data;

        const openCircuits = Object.entries(circuit_breakers).filter(
          ([, state]) => state === "open"
        );
        const degradedAgents = agent_health.filter(
          (agent: any) => agent.status !== "healthy"
        );
        const budgetWarnings: string[] = [];

        if (budgets.llm_tokens.used / budgets.llm_tokens.limit > 0.8) {
          budgetWarnings.push("LLM tokens");
        }
        if (budgets.apify_runs.used / budgets.apify_runs.limit > 0.8) {
          budgetWarnings.push("Apify runs");
        }
        if (
          budgets.browser_sessions.used / budgets.browser_sessions.limit >
          0.8
        ) {
          budgetWarnings.push("Browser sessions");
        }

        progress.advance(2, "Preparing the governance dashboard for review.", {
          degradedAgents: degradedAgents.length,
          openCircuits: openCircuits.length,
        });
        progress.success("Governance snapshot is ready.");

        return {
          success: true,
          rate_limits,
          budgets,
          circuit_breakers,
          agent_health,
          kill_switches,
          summary: `System status: ${
            openCircuits.length > 0
              ? `${openCircuits.length} circuit(s) open`
              : "All circuits closed"
          }. ${
            degradedAgents.length > 0
              ? `${degradedAgents.length} agent(s) degraded.`
              : "All agents healthy."
          } ${
            budgetWarnings.length > 0
              ? `Budget warnings: ${budgetWarnings.join(", ")}.`
              : "Budgets OK."
          }`,
          artifactTrigger: {
            kind: "metrics-dashboard" as const,
            data: toSystemMetrics(data),
          },
        };
      } catch (error) {
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error"
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion: "Please check your connection and try again.",
        };
      }
    },
  });
