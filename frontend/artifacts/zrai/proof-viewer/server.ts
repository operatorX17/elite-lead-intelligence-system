/**
 * ZRAI Proof Viewer Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const proofViewerDocumentHandler = createDocumentHandler<"proof-viewer">({
  kind: "proof-viewer",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-proofViewer",
      data: null,
      transient: true,
    });
    return JSON.stringify(null);
  },
  onUpdateDocument: async ({ document, dataStream }) => {
    let proof = null;
    try {
      proof = JSON.parse(document.content || "null");
    } catch {
      // Ignore parse errors
    }

    (dataStream as any).write({
      type: "data-proofViewer",
      data: proof,
      transient: true,
    });

    return document.content || "null";
  },
});
