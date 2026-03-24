// Official OpenRouter provider for Vercel AI SDK
// Using @openrouter/ai-sdk-provider - the official community package
// Documentation: https://openrouter.ai/docs/guides/community/vercel-ai-sdk

import { createOpenRouter } from "@openrouter/ai-sdk-provider";

function cleanEnvValue(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  return value
    .trim()
    .replace(/^"|"$/g, "")
    .replace(/\\r\\n/g, "")
    .replace(/\\n/g, "")
    .trim();
}

function createRuntimeOpenRouterProvider() {
  return createOpenRouter({
    apiKey: cleanEnvValue(process.env.OPENROUTER_API_KEY),
  });
}

// Wrapper that logs model calls and returns a chat model
export const openrouter = (modelId: string) => {
  const apiKey = cleanEnvValue(process.env.OPENROUTER_API_KEY);
  console.log(`[OpenRouter] Creating model: ${modelId}`);
  if (!apiKey) {
    console.error("[OpenRouter] ERROR: OPENROUTER_API_KEY is not set!");
  }
  return createRuntimeOpenRouterProvider()(modelId);
};

// Factory function for creating custom OpenRouter instances with different API keys
export function createCustomOpenRouter(config: { apiKey?: string } = {}) {
  const provider = createOpenRouter({
    apiKey: cleanEnvValue(config.apiKey || process.env.OPENROUTER_API_KEY),
  });
  
  return (modelId: string) => {
    console.log(`[OpenRouter Custom] Creating model: ${modelId}`);
    return provider(modelId);
  };
}
