/**
 * ZRAI Lead OS - Tools Index
 * 
 * Exports all ZRAI tools for registration in the chat route.
 */

// Discovery & Enrichment
export { discoverLeads } from './discover-leads';
export { enrichLead } from './enrich-lead';
export { analyzeIntent } from './analyze-intent';

// Proof Generation
export { generateProof } from './generate-proof';

// Scoring
export { scoreLeads } from './score-leads';

// Outreach (draft-outreach does NOT require approval)
export { draftOutreach } from './draft-outreach';

// Outreach (send-outreach REQUIRES approval)
export { sendOutreach } from './send-outreach';

// Conversation
export { handleConversation } from './handle-conversation';

// Escalation (REQUIRES approval)
export { approveEscalation } from './approve-escalation';

// Governance & Metrics
export { checkGovernance } from './check-governance';
export { manageABTest } from './manage-ab-test';

// Pipeline
export { runPipeline } from './run-pipeline';

// Import & Analysis
export { importLeads } from './import-leads';
export { analyzeScreenshot } from './analyze-screenshot';

/**
 * All ZRAI tools grouped for easy registration.
 */
export const zraiTools = {
  // Discovery & Enrichment
  discoverLeads: require('./discover-leads').discoverLeads,
  enrichLead: require('./enrich-lead').enrichLead,
  analyzeIntent: require('./analyze-intent').analyzeIntent,
  
  // Proof
  generateProof: require('./generate-proof').generateProof,
  
  // Scoring
  scoreLeads: require('./score-leads').scoreLeads,
  
  // Outreach
  draftOutreach: require('./draft-outreach').draftOutreach,
  sendOutreach: require('./send-outreach').sendOutreach, // needsApproval: true
  
  // Conversation
  handleConversation: require('./handle-conversation').handleConversation,
  approveEscalation: require('./approve-escalation').approveEscalation, // needsApproval: true
  
  // Governance
  checkGovernance: require('./check-governance').checkGovernance,
  manageABTest: require('./manage-ab-test').manageABTest,
  
  // Pipeline
  runPipeline: require('./run-pipeline').runPipeline,
  
  // Import
  importLeads: require('./import-leads').importLeads,
  analyzeScreenshot: require('./analyze-screenshot').analyzeScreenshot,
} as const;

/**
 * List of tool names that require user approval before execution.
 */
export const APPROVAL_REQUIRED_TOOLS = [
  'sendOutreach',
  'approveEscalation',
] as const;

/**
 * List of all ZRAI tool names for experimental_activeTools.
 */
export const ZRAI_TOOL_NAMES = [
  'discoverLeads',
  'enrichLead',
  'analyzeIntent',
  'generateProof',
  'scoreLeads',
  'draftOutreach',
  'sendOutreach',
  'handleConversation',
  'approveEscalation',
  'checkGovernance',
  'manageABTest',
  'runPipeline',
  'importLeads',
  'analyzeScreenshot',
] as const;

export type ZRAIToolName = typeof ZRAI_TOOL_NAMES[number];
