/**
 * ZRAI Lead OS - File Upload Handlers
 * 
 * Handles file uploads for CSV imports, image analysis, and document processing.
 */

import {
  MAX_FILE_SIZES,
  SUPPORTED_DOCUMENT_TYPES,
  SUPPORTED_IMAGE_TYPES,
} from './constants';
import type {
  CSVImportResult,
  FileUploadResult,
  ImageAnalysisResult,
  Lead,
  SupportedDocumentType,
  SupportedImageType,
} from './types';

// ============================================================================
// File Validation
// ============================================================================

/**
 * Validates if a file type is a supported image type.
 */
export function isSupportedImageType(mimeType: string): mimeType is SupportedImageType {
  return SUPPORTED_IMAGE_TYPES.includes(mimeType as SupportedImageType);
}

/**
 * Validates if a file type is a supported document type.
 */
export function isSupportedDocumentType(mimeType: string): mimeType is SupportedDocumentType {
  return SUPPORTED_DOCUMENT_TYPES.includes(mimeType as SupportedDocumentType);
}

/**
 * Validates file size against limits.
 */
export function validateFileSize(file: File): { valid: boolean; error?: string } {
  const isImage = isSupportedImageType(file.type);
  const isCSV = file.type === 'text/csv';
  const isDocument = isSupportedDocumentType(file.type);

  if (isImage && file.size > MAX_FILE_SIZES.image) {
    return {
      valid: false,
      error: `Image file too large. Maximum size is ${MAX_FILE_SIZES.image / 1024 / 1024}MB`,
    };
  }

  if (isCSV && file.size > MAX_FILE_SIZES.csv) {
    return {
      valid: false,
      error: `CSV file too large. Maximum size is ${MAX_FILE_SIZES.csv / 1024 / 1024}MB`,
    };
  }

  if (isDocument && file.size > MAX_FILE_SIZES.document) {
    return {
      valid: false,
      error: `Document file too large. Maximum size is ${MAX_FILE_SIZES.document / 1024 / 1024}MB`,
    };
  }

  return { valid: true };
}

/**
 * Validates a file for ZRAI upload.
 */
export function validateFile(file: File): FileUploadResult {
  const isImage = isSupportedImageType(file.type);
  const isDocument = isSupportedDocumentType(file.type);

  if (!isImage && !isDocument) {
    return {
      success: false,
      file_type: file.type,
      file_name: file.name,
      size_bytes: file.size,
      error: `Unsupported file type: ${file.type}. Supported types: images (PNG, JPG, GIF, WebP), documents (PDF, CSV, Excel)`,
    };
  }

  const sizeValidation = validateFileSize(file);
  if (!sizeValidation.valid) {
    return {
      success: false,
      file_type: file.type,
      file_name: file.name,
      size_bytes: file.size,
      error: sizeValidation.error,
    };
  }

  return {
    success: true,
    file_type: file.type,
    file_name: file.name,
    size_bytes: file.size,
  };
}

// ============================================================================
// CSV Parsing
// ============================================================================

/**
 * Required columns for lead CSV import.
 */
const REQUIRED_CSV_COLUMNS = ['company_name', 'domain'] as const;

/**
 * Optional columns for lead CSV import.
 */
const OPTIONAL_CSV_COLUMNS = [
  'niche',
  'geo',
  'contact_name',
  'contact_email',
  'contact_phone',
  'contact_linkedin',
  'contact_title',
] as const;

type CSVRow = Record<string, string>;

/**
 * Parses CSV content into rows.
 */
export function parseCSV(content: string): CSVRow[] {
  const lines = content.trim().split('\n');
  if (lines.length < 2) {
    return [];
  }

  const headers = lines[0].split(',').map((h) => h.trim().toLowerCase().replace(/\s+/g, '_'));
  const rows: CSVRow[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length !== headers.length) {
      continue; // Skip malformed rows
    }

    const row: CSVRow = {};
    headers.forEach((header, index) => {
      row[header] = values[index].trim();
    });
    rows.push(row);
  }

  return rows;
}

/**
 * Parses a single CSV line, handling quoted values.
 */
function parseCSVLine(line: string): string[] {
  const values: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      values.push(current);
      current = '';
    } else {
      current += char;
    }
  }

  values.push(current);
  return values;
}

/**
 * Validates CSV headers for lead import.
 */
export function validateCSVHeaders(headers: string[]): { valid: boolean; missing: string[] } {
  const normalizedHeaders = headers.map((h) => h.toLowerCase().replace(/\s+/g, '_'));
  const missing = REQUIRED_CSV_COLUMNS.filter((col) => !normalizedHeaders.includes(col));

  return {
    valid: missing.length === 0,
    missing,
  };
}

/**
 * Converts a CSV row to a partial Lead object.
 */
export function csvRowToLead(row: CSVRow, index: number): Partial<Lead> | { error: string } {
  // Validate required fields
  if (!row.company_name || !row.domain) {
    return { error: `Row ${index + 1}: Missing required fields (company_name, domain)` };
  }

  // Validate domain format
  const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}$/;
  if (!domainRegex.test(row.domain)) {
    return { error: `Row ${index + 1}: Invalid domain format: ${row.domain}` };
  }

  const lead: Partial<Lead> = {
    company_name: row.company_name,
    domain: row.domain.toLowerCase(),
    niche: row.niche || 'unknown',
    geo: row.geo || 'unknown',
    status: 'discovered',
    contacts: [],
    intent_signals: [],
  };

  // Add contact if provided
  if (row.contact_name || row.contact_email) {
    lead.contacts = [
      {
        id: `temp-${index}`,
        lead_id: '',
        name: row.contact_name || 'Unknown',
        email: row.contact_email,
        phone: row.contact_phone,
        linkedin_url: row.contact_linkedin,
        title: row.contact_title,
        is_primary: true,
        created_at: new Date().toISOString(),
      },
    ];
  }

  return lead;
}

/**
 * Processes a CSV file for lead import.
 */
export async function processCSVFile(file: File): Promise<CSVImportResult> {
  try {
    const content = await file.text();
    const rows = parseCSV(content);

    if (rows.length === 0) {
      return {
        success: false,
        total_rows: 0,
        imported: 0,
        failed: 0,
        errors: [{ row: 0, error: 'CSV file is empty or has no data rows' }],
      };
    }

    // Validate headers
    const headers = Object.keys(rows[0]);
    const headerValidation = validateCSVHeaders(headers);
    if (!headerValidation.valid) {
      return {
        success: false,
        total_rows: rows.length,
        imported: 0,
        failed: rows.length,
        errors: [
          {
            row: 0,
            error: `Missing required columns: ${headerValidation.missing.join(', ')}`,
          },
        ],
      };
    }

    // Process rows
    const leads: Lead[] = [];
    const errors: Array<{ row: number; error: string }> = [];

    rows.forEach((row, index) => {
      const result = csvRowToLead(row, index);
      if ('error' in result) {
        errors.push({ row: index + 2, error: result.error }); // +2 for header row and 0-index
      } else {
        leads.push(result as Lead);
      }
    });

    return {
      success: errors.length === 0,
      total_rows: rows.length,
      imported: leads.length,
      failed: errors.length,
      errors,
      leads,
    };
  } catch (error) {
    return {
      success: false,
      total_rows: 0,
      imported: 0,
      failed: 0,
      errors: [
        {
          row: 0,
          error: `Failed to parse CSV: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
    };
  }
}

// ============================================================================
// Image Processing
// ============================================================================

/**
 * Converts a File to base64 string.
 */
export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data URL prefix (e.g., "data:image/png;base64,")
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

/**
 * Gets image dimensions from a File.
 */
export async function getImageDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      resolve({ width: img.width, height: img.height });
    };
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = URL.createObjectURL(file);
  });
}

/**
 * Prepares an image file for analysis.
 */
export async function prepareImageForAnalysis(file: File): Promise<{
  base64: string;
  mimeType: string;
  dimensions: { width: number; height: number };
}> {
  const [base64, dimensions] = await Promise.all([
    fileToBase64(file),
    getImageDimensions(file),
  ]);

  return {
    base64,
    mimeType: file.type,
    dimensions,
  };
}

// ============================================================================
// File Type Detection
// ============================================================================

/**
 * Determines the ZRAI file category for routing.
 */
export type ZRAIFileCategory = 'lead_import' | 'screenshot_analysis' | 'document' | 'unsupported';

export function categorizeFile(file: File): ZRAIFileCategory {
  if (file.type === 'text/csv') {
    return 'lead_import';
  }

  if (isSupportedImageType(file.type)) {
    return 'screenshot_analysis';
  }

  if (isSupportedDocumentType(file.type)) {
    return 'document';
  }

  return 'unsupported';
}

/**
 * Gets a human-readable description of the file category.
 */
export function getFileCategoryDescription(category: ZRAIFileCategory): string {
  switch (category) {
    case 'lead_import':
      return 'Lead Import (CSV)';
    case 'screenshot_analysis':
      return 'Screenshot Analysis';
    case 'document':
      return 'Document';
    case 'unsupported':
      return 'Unsupported File Type';
  }
}
