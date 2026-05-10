/**
 * ZRAI Lead OS - Analyze Screenshot Tool
 * 
 * Analyzes uploaded screenshots for intent signals.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const analyzeScreenshot = tool({
  description: `Analyze an uploaded screenshot for intent signals and lead information.
Use this tool when the user uploads an image of a website, landing page, or business profile.
The AI will extract relevant information and identify potential intent signals.`,
  inputSchema: z.object({
    image_base64: z
      .string()
      .describe('Base64-encoded image data'),
    mime_type: z
      .string()
      .describe('MIME type of the image (e.g., "image/png", "image/jpeg")'),
    context: z
      .string()
      .optional()
      .describe('Optional context about what to look for in the image'),
  }),
  execute: async ({ image_base64, mime_type, context }) => {
    try {
      const response = await fetch(`${ZRAI_ENDPOINTS.intent}/screenshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64, mime_type, context }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to analyze screenshot',
          suggestion: 'Make sure the image is clear and try again.',
        };
      }

      const { intent_signals, extracted_text, confidence } = data.data;
      const signalCount = intent_signals?.length || 0;

      return {
        success: true,
        intent_signals,
        extracted_text,
        confidence,
        summary: `Analyzed screenshot with ${(confidence * 100).toFixed(0)}% confidence. Found ${signalCount} intent signal(s). ${
          extracted_text
            ? `Extracted text: "${extracted_text.substring(0, 100)}${extracted_text.length > 100 ? '...' : ''}"`
            : 'No text extracted.'
        }`,
        artifactTrigger: {
          kind: 'proof-viewer' as const,
          data: { 
            proof: {
              proof_type: 'screenshot',
              metadata: { extracted_text },
            },
            intent_signals,
          },
        },
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        suggestion: 'Please check your connection and try again.',
      };
    }
  },
});
