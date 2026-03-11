// AI SDK v6 format per official documentation
export function getResponseChunksByPrompt(
  _prompt: unknown,
  includeReasoning = false
) {
  const chunks: Array<
    | { type: "reasoning-start"; id: string }
    | { type: "reasoning-delta"; id: string; delta: string }
    | { type: "reasoning-end"; id: string }
    | { type: "text-start"; id: string }
    | { type: "text-delta"; id: string; delta: string }
    | { type: "text-end"; id: string }
    | {
        type: "finish";
        finishReason: "stop";
        logprobs: undefined;
        usage: { inputTokens: number; outputTokens: number; totalTokens: number };
      }
  > = [];

  if (includeReasoning) {
    chunks.push(
      { type: "reasoning-start" as const, id: "r1" },
      { type: "reasoning-delta" as const, id: "r1", delta: "Let me think about this." },
      { type: "reasoning-end" as const, id: "r1" }
    );
  }

  chunks.push(
    { type: "text-start" as const, id: "t1" },
    { type: "text-delta" as const, id: "t1", delta: "Hello, world!" },
    { type: "text-end" as const, id: "t1" },
    {
      type: "finish" as const,
      finishReason: "stop" as const,
      logprobs: undefined,
      usage: { inputTokens: 10, outputTokens: 20, totalTokens: 30 },
    }
  );

  return chunks;
}
