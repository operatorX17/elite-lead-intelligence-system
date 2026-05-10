import {
  customProvider,
  extractReasoningMiddleware,
  wrapLanguageModel,
} from "ai";
import { isTestEnvironment } from "../constants";
import { chatModels, DEFAULT_CHAT_MODEL } from "./models";
import { openrouter } from "./openrouter";

const THINKING_SUFFIX_REGEX = /-thinking$/;

export const myProvider = isTestEnvironment
  ? (() => {
      const {
        artifactModel,
        chatModel,
        reasoningModel,
        titleModel,
      } = require("./models.mock");
      return customProvider({
        languageModels: {
          "chat-model": chatModel,
          "chat-model-reasoning": reasoningModel,
          "title-model": titleModel,
          "artifact-model": artifactModel,
        },
      });
    })()
  : null;

export function getLanguageModel(modelId: string) {
  if (isTestEnvironment && myProvider) {
    return myProvider.languageModel(modelId);
  }

  // Validate model ID - fall back to default if invalid
  const isValidModel = chatModels.some(m => m.id === modelId) || 
                       modelId.includes("reasoning") || 
                       modelId.endsWith("-thinking");
  
  const effectiveModelId = isValidModel ? modelId : DEFAULT_CHAT_MODEL;
  
  if (!isValidModel) {
    console.warn(`[Providers] Invalid model ID "${modelId}", falling back to "${DEFAULT_CHAT_MODEL}"`);
  }

  const isReasoningModel =
    effectiveModelId.includes("reasoning") || effectiveModelId.endsWith("-thinking");

  if (isReasoningModel) {
    const openRouterModelId = effectiveModelId.replace(THINKING_SUFFIX_REGEX, "");

    return wrapLanguageModel({
      model: openrouter(openRouterModelId),
      middleware: extractReasoningMiddleware({ tagName: "thinking" }),
    });
  }

  // Use OpenRouter for all models
  return openrouter(effectiveModelId);
}

export function getTitleModel() {
  if (isTestEnvironment && myProvider) {
    return myProvider.languageModel("title-model");
  }
  // Use DeepSeek V3 - cheap and fast
  return openrouter("deepseek/deepseek-chat");
}

export function getArtifactModel() {
  if (isTestEnvironment && myProvider) {
    return myProvider.languageModel("artifact-model");
  }
  // Use DeepSeek V3 - cheap and capable
  return openrouter("deepseek/deepseek-chat");
}
