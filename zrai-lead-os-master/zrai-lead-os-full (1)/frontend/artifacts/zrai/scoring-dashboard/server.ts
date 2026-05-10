/**
 * ZRAI Scoring Dashboard Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const scoringDashboardDocumentHandler = createDocumentHandler<"scoring-dashboard">({
  kind: "scoring-dashboard",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-scoringDashboard",
      data: null,
      transient: true,
    });
    return JSON.stringify(null);
  },
  onUpdateDocument: async ({ document, dataStream }) => {
    let results = null;
    try {
      results = JSON.parse(document.content || "null");
    } catch {
      // Ignore parse errors
    }

    (dataStream as any).write({
      type: "data-scoringDashboard",
      data: results,
      transient: true,
    });

    return document.content || "null";
  },
});
