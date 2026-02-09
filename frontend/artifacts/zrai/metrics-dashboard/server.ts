/**
 * ZRAI Metrics Dashboard Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const metricsDashboardDocumentHandler = createDocumentHandler<"metrics-dashboard">({
  kind: "metrics-dashboard",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-metricsDashboard",
      data: null,
      transient: true,
    });
    return JSON.stringify(null);
  },
  onUpdateDocument: async ({ document, dataStream }) => {
    let metrics = null;
    try {
      metrics = JSON.parse(document.content || "null");
    } catch {
      // Ignore parse errors
    }

    (dataStream as any).write({
      type: "data-metricsDashboard",
      data: metrics,
      transient: true,
    });

    return document.content || "null";
  },
});
