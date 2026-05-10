import { simulateReadableStream } from "ai";
import { MockLanguageModelV3 } from "ai/test";
import { getResponseChunksByPrompt } from "@/tests/prompts/utils";

// AI SDK v6 format per official documentation
export const chatModel = new MockLanguageModelV3({
  doGenerate: async () => ({
    finishReason: "stop" as const,
    usage: { inputTokens: 10, outputTokens: 20, totalTokens: 30 },
    content: [{ type: "text" as const, text: "Hello, world!" }],
    warnings: [],
  }),
  doStream: async ({ prompt }) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 500,
      initialDelayInMs: 1000,
      chunks: getResponseChunksByPrompt(prompt),
    }),
  }),
});

export const reasoningModel = new MockLanguageModelV3({
  doGenerate: async () => ({
    finishReason: "stop" as const,
    usage: { inputTokens: 10, outputTokens: 20, totalTokens: 30 },
    content: [{ type: "text" as const, text: "Hello, world!" }],
    warnings: [],
  }),
  doStream: async ({ prompt }) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 500,
      initialDelayInMs: 1000,
      chunks: getResponseChunksByPrompt(prompt, true),
    }),
  }),
});

export const titleModel = new MockLanguageModelV3({
  doGenerate: async () => ({
    finishReason: "stop" as const,
    usage: { inputTokens: 10, outputTokens: 20, totalTokens: 30 },
    content: [{ type: "text" as const, text: "This is a test title" }],
    warnings: [],
  }),
  doStream: async () => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 500,
      initialDelayInMs: 1000,
      chunks: [
        { type: "text-start" as const, id: "1" },
        { type: "text-delta" as const, id: "1", delta: "This is a test title" },
        { type: "text-end" as const, id: "1" },
        {
          type: "finish" as const,
          finishReason: "stop" as const,
          logprobs: undefined,
          usage: { inputTokens: 10, outputTokens: 20, totalTokens: 30 },
        },
      ],
    }),
  }),
});

export const artifactModel = new MockLanguageModelV3({
  doGenerate: async () => ({
    finishReason: "stop" as const,
    usage: { inputTokens: 10, outputTokens: 20, totalTokens: 30 },
    content: [{ type: "text" as const, text: "Hello, world!" }],
    warnings: [],
  }),
  doStream: async ({ prompt }) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 50,
      initialDelayInMs: 100,
      chunks: getResponseChunksByPrompt(prompt),
    }),
  }),
});
