/**
 * ZRAI Lead Sheet Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const leadSheetDocumentHandler = createDocumentHandler<"lead-sheet">({
  kind: "lead-sheet",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-leadSheet",
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
      type: "data-leadSheet",
      data: leads,
      transient: true,
    });

    return document.content || "[]";
  },
});
