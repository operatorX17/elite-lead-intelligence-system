/**
 * ZRAI Lead OS - Run Pipeline Tool
 *
 * Triggers pipeline runs for lead processing.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

export const runPipeline = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Trigger a pipeline run to process leads through the ZRAI system.
Supports different modes:
- full: Run the complete pipeline on all eligible leads
- dry_run: Simulate the pipeline without making external changes
- replay: Re-run a previous pipeline run with the same configuration
- resume: Resume a failed pipeline run from where it stopped`,
    inputSchema: z.object({
      mode: z
        .enum(["full", "dry_run", "replay", "resume"])
        .describe("Pipeline run mode"),
      run_id: z
        .string()
        .uuid()
        .optional()
        .describe("Run ID (required for replay and resume modes)"),
      limit: z
        .number()
        .min(1)
        .max(1000)
        .optional()
        .describe("Maximum leads to process (useful for dry_run mode)"),
      config: z
        .record(z.unknown())
        .optional()
        .describe("Optional configuration overrides"),
    }),
    execute: async ({ mode, run_id, limit, config }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "runPipeline",
        title: "Starting pipeline run",
        stages: ["Validate request", "Dispatch run", "Prepare run summary"],
      });
      progress.start(`Preparing the ${mode} pipeline run.`, {
        limit: limit ?? null,
        mode,
        runId: run_id ?? null,
      });
      try {
        if ((mode === "replay" || mode === "resume") && !run_id) {
          progress.error(0, `${mode} mode requires a run_id`, { mode });
          return {
            success: false,
            error: `${mode} mode requires a run_id`,
            suggestion:
              "Provide the run_id of the pipeline run to replay or resume.",
          };
        }

        progress.advance(
          1,
          "Dispatching the pipeline request to the orchestration backend."
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.run, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode, run_id, limit, config }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(
            1,
            data.error?.message || "Failed to start pipeline run",
            { status: response.status }
          );
          return {
            success: false,
            error: data.error?.message || "Failed to start pipeline run",
            suggestion:
              data.error?.code === "not_found"
                ? "Run not found. Check the run_id."
                : data.error?.code === "budget_exceeded"
                  ? "Budget exceeded. Try again tomorrow."
                  : "Check your parameters and try again.",
          };
        }

        const run = {
          id: data.run_id,
          mode,
          status: "completed",
          config_snapshot: config ?? {},
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          stats: {
            leads_processed: data.processed ?? 0,
            leads_succeeded: data.processed ?? 0,
            leads_failed: 0,
            errors: [],
          },
        };
        const modeDescriptions: Record<string, string> = {
          full: "Full pipeline run",
          dry_run: "Dry run (no external changes)",
          replay: "Replay of previous run",
          resume: "Resuming failed run",
        };
        progress.advance(
          2,
          `Run ${run.id} created with status ${run.status}. Preparing the summary.`,
          { runId: run.id, status: run.status }
        );
        progress.success("Pipeline run accepted by the backend.", {
          runId: run.id,
          status: run.status,
        });

        return {
          success: true,
          run,
          summary: `${modeDescriptions[mode]} started. Run ID: ${run.id}. Status: ${run.status}. ${
            run.stats
              ? `Processed: ${run.stats.leads_processed}, Succeeded: ${run.stats.leads_succeeded}, Failed: ${run.stats.leads_failed}`
              : "Processing..."
          }`,
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
