// OpenRouter provider using official OpenAI adapter
// OpenRouter is fully OpenAI-compatible

import { createOpenAI } from "@ai-sdk/openai";

const OPENROUTER_API_URL = "https://openrouter.ai/api/v1";

// Create OpenRouter provider using OpenAI adapter
const openrouterProvider = createOpenAI({
  apiKey: process.env.OPENROUTER_API_KEY || "",
  baseURL: OPENROUTER_API_URL,
  headers: {
    "HTTP-Referer": process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
    "X-Title": "ZRAI Lead OS",
  },
});

// Export as a function that creates models
export function openrouter(modelId: string) {
  return openrouterProvider(modelId);
}

// Alternative factory for custom configs
export function createOpenRouter(config: { apiKey?: string; baseURL?: string } = {}) {
  const provider = createOpenAI({
    apiKey: config.apiKey || process.env.OPENROUTER_API_KEY || "",
    baseURL: config.baseURL || OPENROUTER_API_URL,
    headers: {
      "HTTP-Referer": process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
      "X-Title": "ZRAI Lead OS",
    },
  });
  
  return (modelId: string) => provider(modelId);
}
