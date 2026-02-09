/**
 * ZRAI Outreach Draft Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const outreachDraftDocumentHandler = createDocumentHandler<"outreach-draft">({
  kind: "outreach-draft",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-outreachDraft",
      data: null,
      transient: true,
    });
    return JSON.stringify(null);
  },
  onUpdateDocument: async ({ document, dataStream }) => {
    let message = null;
    try {
      message = JSON.parse(document.content || "null");
    } catch {
      // Ignore parse errors
    }

    (dataStream as any).write({
      type: "data-outreachDraft",
      data: message,
      transient: true,
    });

    return document.content || "null";
  },
});
