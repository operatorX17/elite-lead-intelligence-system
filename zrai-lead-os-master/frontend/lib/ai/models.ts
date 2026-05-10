// Curated list of models available via OpenRouter
// Prioritizing cheap Chinese models that are excellent at tool calling

// DeepSeek V3 is the best value: cheap, fast, excellent tool calling
export const DEFAULT_CHAT_MODEL = "deepseek/deepseek-chat";

export type ChatModel = {
  id: string;
  name: string;
  provider: string;
  description: string;
  supportsTools: boolean; // Whether the model properly supports function calling
  pricing?: string; // Approximate pricing info
};

export const chatModels: ChatModel[] = [
  // ============================================
  // RECOMMENDED: Cheap Chinese Models with Tool Support
  // ============================================
  
  // DeepSeek - Best value, excellent tool calling
  {
    id: "deepseek/deepseek-chat",
    name: "DeepSeek V3 ⭐",
    provider: "deepseek",
    description: "Best value! Cheap, fast, excellent tool calling",
    supportsTools: true,
    pricing: "$0.14/M in, $0.28/M out",
  },
  {
    id: "deepseek/deepseek-chat-v3-0324:free",
    name: "DeepSeek V3 (Free)",
    provider: "deepseek",
    description: "Free tier with rate limits",
    supportsTools: true,
    pricing: "Free",
  },
  {
    id: "deepseek/deepseek-r1-distill-qwen-32b",
    name: "DeepSeek R1 Distill 32B",
    provider: "deepseek",
    description: "Reasoning model, great for complex tasks",
    supportsTools: true,
    pricing: "$0.12/M in, $0.18/M out",
  },
  
  // Qwen - Alibaba's excellent models
  {
    id: "qwen/qwen-2.5-72b-instruct",
    name: "Qwen 2.5 72B",
    provider: "qwen",
    description: "Powerful, great multilingual tool calling",
    supportsTools: true,
    pricing: "$0.35/M in, $0.40/M out",
  },
  {
    id: "qwen/qwen-2.5-coder-32b-instruct",
    name: "Qwen 2.5 Coder 32B",
    provider: "qwen",
    description: "Optimized for coding and tool use",
    supportsTools: true,
    pricing: "$0.07/M in, $0.16/M out",
  },
  {
    id: "qwen/qwen-2.5-7b-instruct:free",
    name: "Qwen 2.5 7B (Free)",
    provider: "qwen",
    description: "Free, good for simple tasks",
    supportsTools: true,
    pricing: "Free",
  },
  
  // GLM - Zhipu AI models
  {
    id: "z-ai/glm-4.7",
    name: "GLM 4.7",
    provider: "zhipu",
    description: "Latest GLM, strong tool calling",
    supportsTools: true,
    pricing: "$0.10/M in, $0.10/M out",
  },
  {
    id: "thudm/glm-4-9b-chat:free",
    name: "GLM-4 9B (Free)",
    provider: "zhipu",
    description: "Free GLM model",
    supportsTools: true,
    pricing: "Free",
  },
  
  // MiniMax - Good for agents
  {
    id: "minimax/minimax-01",
    name: "MiniMax 01",
    provider: "minimax",
    description: "Good for agentic tasks",
    supportsTools: true,
    pricing: "$0.20/M in, $0.60/M out",
  },
  
  // ============================================
  // Premium Models (More Expensive)
  // ============================================
  
  // Anthropic
  {
    id: "anthropic/claude-3.5-sonnet",
    name: "Claude 3.5 Sonnet",
    provider: "anthropic",
    description: "Best overall quality, more expensive",
    supportsTools: true,
    pricing: "$3/M in, $15/M out",
  },
  {
    id: "anthropic/claude-3-haiku",
    name: "Claude 3 Haiku",
    provider: "anthropic",
    description: "Fast but limited tool support",
    supportsTools: false, // Struggles with function calling
    pricing: "$0.25/M in, $1.25/M out",
  },
  
  // OpenAI
  {
    id: "openai/gpt-4o",
    name: "GPT-4o",
    provider: "openai",
    description: "OpenAI's flagship, excellent tools",
    supportsTools: true,
    pricing: "$2.50/M in, $10/M out",
  },
  {
    id: "openai/gpt-4o-mini",
    name: "GPT-4o Mini",
    provider: "openai",
    description: "Cheaper GPT-4, good tool support",
    supportsTools: true,
    pricing: "$0.15/M in, $0.60/M out",
  },
  
  // Google
  {
    id: "google/gemini-2.0-flash-001",
    name: "Gemini 2.0 Flash",
    provider: "google",
    description: "Fast Google model with tools",
    supportsTools: true,
    pricing: "$0.10/M in, $0.40/M out",
  },
  {
    id: "google/gemini-2.0-flash-lite-001",
    name: "Gemini 2.0 Flash Lite",
    provider: "google",
    description: "Ultra cheap but NO tool support",
    supportsTools: false, // Causes infinite loops with tools
    pricing: "$0.075/M in, $0.30/M out",
  },
  
  // ============================================
  // Free Models (Limited)
  // ============================================
  {
    id: "meta-llama/llama-3.1-70b-instruct:free",
    name: "Llama 3.1 70B (Free)",
    provider: "meta",
    description: "Free, powerful open model",
    supportsTools: true,
    pricing: "Free",
  },
  {
    id: "meta-llama/llama-3.2-3b-instruct:free",
    name: "Llama 3.2 3B (Free)",
    provider: "meta",
    description: "Free but too small for tools",
    supportsTools: false,
    pricing: "Free",
  },
  {
    id: "mistralai/mistral-7b-instruct:free",
    name: "Mistral 7B (Free)",
    provider: "mistral",
    description: "Free but limited tool support",
    supportsTools: false,
    pricing: "Free",
  },
];

// Helper function to check if a model supports tool calling
export function modelSupportsTools(modelId: string): boolean {
  const model = chatModels.find(m => m.id === modelId);
  
  // If model found, use its supportsTools flag
  if (model) {
    return model.supportsTools;
  }
  
  // For unknown models, check if it's a known problematic pattern
  const noToolPatterns = [
    'lite', 'mini', '3b', '7b-instruct', 'haiku',
    'gemini-2.0-flash-lite', 'llama-3.2-3b'
  ];
  
  const lowerModelId = modelId.toLowerCase();
  for (const pattern of noToolPatterns) {
    if (lowerModelId.includes(pattern)) {
      return false;
    }
  }
  
  // Default to true for unknown models (optimistic)
  return true;
}

// Get recommended models for tool calling
export function getToolCapableModels(): ChatModel[] {
  return chatModels.filter(m => m.supportsTools);
}

// Get the best available model for tool calling (cheap + good)
export function getBestToolModel(): string {
  return "deepseek/deepseek-chat"; // Best value
}

// Get free models that support tools
export function getFreeToolModels(): ChatModel[] {
  return chatModels.filter(m => m.supportsTools && m.pricing === "Free");
}

// Group models by provider for UI
export const modelsByProvider = chatModels.reduce(
  (acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  },
  {} as Record<string, ChatModel[]>
);
