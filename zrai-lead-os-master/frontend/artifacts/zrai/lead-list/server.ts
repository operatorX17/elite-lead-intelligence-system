/**
 * ZRAI Lead List Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const leadListDocumentHandler = createDocumentHandler<"lead-list">({
  kind: "lead-list",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-leadList",
      data: [],
      transient: true,
    });
    return JSON.stringify([]);
  },
  onUpdateDocument: async ({ document, dataStream }) => {
    let leads = [];
    try {
      leads = JSON.parse(document.content || "[]");
    } catch {
      // Ignore parse errors
    }

    (dataStream as any).write({
      type: "data-leadList",
      data: leads,
      transient: true,
    });

    return document.content || "[]";
  },
});
