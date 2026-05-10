/**
 * ZRAI File Upload Hook
 * 
 * Handles ZRAI-specific file uploads (CSV imports, screenshots).
 */

'use client';

import { useCallback, useState } from 'react';
import { toast } from 'sonner';
import {
  categorizeFile,
  validateFile,
  validateFileSize,
  processCSVFile,
  isSupportedImageType,
  type ZRAIFileCategory,
} from '@/lib/zrai/file-handlers';
import type { Attachment } from '@/lib/types';

export type ZRAIFileType = 'csv' | 'image' | 'document' | 'unknown';

export interface ZRAIFileUploadResult {
  file: File;
  type: ZRAIFileType;
  attachment?: Attachment;
  suggestedAction?: string;
  previewData?: unknown;
}

export function useZRAIFileUpload() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingFiles, setProcessingFiles] = useState<string[]>([]);

  /**
   * Detect the ZRAI file type based on MIME type and extension.
   */
  const detectFileType = useCallback((file: File): ZRAIFileType => {
    const category = categorizeFile(file);
    switch (category) {
      case 'lead_import':
        return 'csv';
      case 'screenshot_analysis':
        return 'image';
      case 'document':
        return 'document';
      default:
        return 'unknown';
    }
  }, []);

  /**
   * Get suggested action based on file type.
   */
  const getSuggestedAction = useCallback((type: ZRAIFileType, fileName: string): string => {
    switch (type) {
      case 'csv':
        return `Import leads from ${fileName}`;
      case 'image':
        return `Analyze this screenshot for intent signals`;
      case 'document':
        return `Process document ${fileName}`;
      default:
        return '';
    }
  }, []);

  /**
   * Process a file for ZRAI-specific handling.
   */
  const processFile = useCallback(async (file: File): Promise<ZRAIFileUploadResult | null> => {
    const type = detectFileType(file);

    // Validate file
    const validation = validateFile(file);
    if (!validation.success) {
      toast.error(validation.error || 'Invalid file');
      return null;
    }

    // Validate file size
    const sizeValidation = validateFileSize(file);
    if (!sizeValidation.valid) {
      toast.error(sizeValidation.error || 'File too large');
      return null;
    }

    const result: ZRAIFileUploadResult = {
      file,
      type,
      suggestedAction: getSuggestedAction(type, file.name),
    };

    // For CSV files, parse and preview
    if (type === 'csv') {
      try {
        const parseResult = await processCSVFile(file);
        if (parseResult.success) {
          result.previewData = {
            rowCount: parseResult.leads?.length || 0,
            columns: parseResult.leads?.[0] ? Object.keys(parseResult.leads[0]) : [],
            preview: parseResult.leads?.slice(0, 3),
          };
          toast.success(`CSV loaded: ${parseResult.leads?.length || 0} rows found`);
        } else {
          toast.warning(`CSV parsing issues: ${parseResult.errors?.length || 0} errors`);
        }
      } catch (error) {
        console.error('Error parsing CSV:', error);
      }
    }

    return result;
  }, [detectFileType, getSuggestedAction]);

  /**
   * Process multiple files.
   */
  const processFiles = useCallback(async (files: File[]): Promise<ZRAIFileUploadResult[]> => {
    setIsProcessing(true);
    setProcessingFiles(files.map(f => f.name));

    const results: ZRAIFileUploadResult[] = [];

    for (const file of files) {
      const result = await processFile(file);
      if (result) {
        results.push(result);
      }
    }

    setIsProcessing(false);
    setProcessingFiles([]);

    return results;
  }, [processFile]);

  /**
   * Check if a file is a ZRAI-specific type that should trigger special handling.
   */
  const isZRAIFile = useCallback((file: File): boolean => {
    const type = detectFileType(file);
    return type === 'csv' || type === 'image';
  }, [detectFileType]);

  /**
   * Get the appropriate tool name for a file type.
   */
  const getToolForFileType = useCallback((type: ZRAIFileType): string | null => {
    switch (type) {
      case 'csv':
        return 'importLeads';
      case 'image':
        return 'analyzeScreenshot';
      default:
        return null;
    }
  }, []);

  return {
    isProcessing,
    processingFiles,
    detectFileType,
    processFile,
    processFiles,
    isZRAIFile,
    getToolForFileType,
    getSuggestedAction,
  };
}
