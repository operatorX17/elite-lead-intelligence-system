/**
 * ZRAI Lead OS - Import Leads Tool
 * 
 * Imports leads from CSV or other sources.
 */

import { tool } from 'ai';
import { z } from 'zod';
import { ZRAI_ENDPOINTS } from '@/lib/zrai/constants';

export const importLeads = tool({
  description: `Import leads from a structured data source.
Use this tool when the user has uploaded a CSV file or wants to bulk import leads.
The leads will be validated and added to the pipeline for processing.`,
  inputSchema: z.object({
    leads: z
      .array(z.object({
        company_name: z.string().describe('Company name'),
        domain: z.string().describe('Company domain (e.g., "example.com")'),
        niche: z.string().optional().describe('Industry niche'),
        geo: z.string().optional().describe('Geographic region'),
        contacts: z.array(z.object({
          name: z.string().optional(),
          email: z.string().optional(),
          phone: z.string().optional(),
          linkedin_url: z.string().optional(),
          title: z.string().optional(),
        })).optional().describe('Contact information'),
      }))
      .min(1)
      .describe('Array of leads to import'),
    source: z
      .string()
      .describe('Source of the leads (e.g., "csv_upload", "manual_entry", "api_import")'),
  }),
  execute: async ({ leads, source }) => {
    try {
      const response = await fetch(ZRAI_ENDPOINTS.import, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ leads, source }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        return {
          success: false,
          error: data.error?.message || 'Failed to import leads',
          suggestion: data.error?.code === 'rate_limit'
            ? 'Rate limit exceeded. Try importing fewer leads.'
            : 'Check your data format and try again.',
        };
      }

      const result = data.data;

      return {
        success: true,
        result,
        summary: `Imported ${result.imported} of ${result.total_rows} lead(s) from ${source}. ${
          result.failed > 0
            ? `${result.failed} failed: ${result.errors.slice(0, 3).map((e: any) => e.error).join('; ')}${result.errors.length > 3 ? '...' : ''}`
            : 'All leads imported successfully.'
        }`,
        artifactTrigger: {
          kind: 'lead-sheet' as const,
          data: { leads: result.leads, importResult: result },
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
