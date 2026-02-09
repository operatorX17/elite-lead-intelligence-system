/**
 * ZRAI Conversation Thread Artifact - Server Component
 */

import { createDocumentHandler } from "@/lib/artifacts/server";

export const conversationThreadDocumentHandler = createDocumentHandler<"conversation-thread">({
  kind: "conversation-thread",
  onCreateDocument: async ({ dataStream }) => {
    (dataStream as any).write({
      type: "data-conversationThread",
      data: { messages: [], leadId: null, status: 'active' },
      transient: true,
    });
    return JSON.stringify({ messages: [], leadId: null, status: 'active' });
  },
  onUpdateDocument: async ({ document, dataStream }) => {
    let data = { messages: [], leadId: null, status: 'active' };
    try {
      data = JSON.parse(document.content || "{}");
    } catch {
      // Ignore parse errors
    }

    (dataStream as any).write({
      type: "data-conversationThread",
      data,
      transient: true,
    });

    return document.content || JSON.stringify(data);
  },
});
