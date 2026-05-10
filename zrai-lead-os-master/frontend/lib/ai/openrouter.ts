// Official OpenRouter provider for Vercel AI SDK
// Using @openrouter/ai-sdk-provider - the official community package
// Documentation: https://openrouter.ai/docs/guides/community/vercel-ai-sdk

import { createOpenRouter } from "@openrouter/ai-sdk-provider";

// Create OpenRouter provider using the official package
const openrouterProvider = createOpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY || "",
});

// Wrapper that logs model calls and returns a chat model
export const openrouter = (modelId: string) => {
  console.log(`[OpenRouter] Creating model: ${modelId}`);
  if (!process.env.OPENROUTER_API_KEY) {
    console.error("[OpenRouter] ERROR: OPENROUTER_API_KEY is not set!");
  }
  return openrouterProvider(modelId);
};

// Factory function for creating custom OpenRouter instances with different API keys
export function createCustomOpenRouter(config: { apiKey?: string } = {}) {
  const provider = createOpenRouter({
    apiKey: config.apiKey || process.env.OPENROUTER_API_KEY || "",
  });
  
  return (modelId: string) => {
    console.log(`[OpenRouter Custom] Creating model: ${modelId}`);
    return provider(modelId);
  };
}
