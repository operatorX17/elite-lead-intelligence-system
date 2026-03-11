/**
 * ZRAI Lead OS - Authentication Utilities
 * 
 * Authentication and authorization helpers for ZRAI operations.
 */

// Session type from next-auth
interface Session {
  user?: {
    id?: string;
    email?: string | null;
    name?: string | null;
  };
}

/**
 * ZRAI permission levels.
 */
export type ZRAIPermission =
  | 'read:leads'
  | 'write:leads'
  | 'read:outreach'
  | 'write:outreach'
  | 'send:outreach'
  | 'read:governance'
  | 'write:governance'
  | 'read:metrics'
  | 'admin';

/**
 * ZRAI role definitions with associated permissions.
 */
export const ZRAI_ROLES: Record<string, ZRAIPermission[]> = {
  viewer: ['read:leads', 'read:outreach', 'read:governance', 'read:metrics'],
  operator: [
    'read:leads',
    'write:leads',
    'read:outreach',
    'write:outreach',
    'read:governance',
    'read:metrics',
  ],
  sender: [
    'read:leads',
    'write:leads',
    'read:outreach',
    'write:outreach',
    'send:outreach',
    'read:governance',
    'read:metrics',
  ],
  admin: [
    'read:leads',
    'write:leads',
    'read:outreach',
    'write:outreach',
    'send:outreach',
    'read:governance',
    'write:governance',
    'read:metrics',
    'admin',
  ],
};

/**
 * Default role for authenticated users.
 */
export const DEFAULT_ROLE = 'operator';

/**
 * Get user's ZRAI role from session.
 */
export function getUserRole(session: Session | null): string {
  if (!session?.user) return 'viewer';
  // In a real implementation, this would come from the user's profile or JWT claims
  return (session.user as any).zraiRole || DEFAULT_ROLE;
}

/**
 * Get user's permissions based on their role.
 */
export function getUserPermissions(session: Session | null): ZRAIPermission[] {
  const role = getUserRole(session);
  return ZRAI_ROLES[role] || ZRAI_ROLES.viewer;
}

/**
 * Check if user has a specific permission.
 */
export function hasPermission(session: Session | null, permission: ZRAIPermission): boolean {
  const permissions = getUserPermissions(session);
  return permissions.includes(permission) || permissions.includes('admin');
}

/**
 * Check if user can perform a specific ZRAI action.
 */
export function canPerformAction(
  session: Session | null,
  action: 'discover' | 'enrich' | 'score' | 'draft' | 'send' | 'escalate' | 'governance'
): boolean {
  const actionPermissions: Record<string, ZRAIPermission> = {
    discover: 'write:leads',
    enrich: 'write:leads',
    score: 'write:leads',
    draft: 'write:outreach',
    send: 'send:outreach',
    escalate: 'send:outreach',
    governance: 'read:governance',
  };

  return hasPermission(session, actionPermissions[action]);
}

/**
 * Create authorization headers for ZRAI backend requests.
 */
export function createAuthHeaders(session: Session | null): Record<string, string> {
  if (!session?.user) {
    return {};
  }

  return {
    'X-User-ID': session.user.id || '',
    'X-User-Email': session.user.email || '',
    'X-User-Role': getUserRole(session),
  };
}

/**
 * Audit log entry for ZRAI operations.
 */
export interface AuditLogEntry {
  timestamp: string;
  user_id: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  parameters?: Record<string, unknown>;
  result: 'success' | 'failure' | 'denied';
  error_message?: string;
  ip_address?: string;
  user_agent?: string;
}

/**
 * Create an audit log entry for a ZRAI operation.
 */
export function createAuditLogEntry(
  session: Session | null,
  action: string,
  resourceType: string,
  options: {
    resourceId?: string;
    parameters?: Record<string, unknown>;
    result: 'success' | 'failure' | 'denied';
    errorMessage?: string;
    request?: Request;
  }
): AuditLogEntry {
  return {
    timestamp: new Date().toISOString(),
    user_id: session?.user?.id || 'anonymous',
    user_email: session?.user?.email || 'anonymous',
    action,
    resource_type: resourceType,
    resource_id: options.resourceId,
    parameters: options.parameters,
    result: options.result,
    error_message: options.errorMessage,
    ip_address: options.request?.headers.get('x-forwarded-for') || undefined,
    user_agent: options.request?.headers.get('user-agent') || undefined,
  };
}

/**
 * Log an audit entry (in production, this would send to a logging service).
 */
export async function logAuditEntry(entry: AuditLogEntry): Promise<void> {
  // In production, send to audit logging service
  console.log('[ZRAI:Audit]', JSON.stringify(entry));
  
  // Could also send to backend for persistent storage
  // await fetch(`${ZRAI_BACKEND_URL}/api/v1/audit`, {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify(entry),
  // });
}

/**
 * Middleware helper to check authentication and authorization.
 */
export async function requireAuth(
  session: Session | null,
  permission?: ZRAIPermission
): Promise<{ authorized: boolean; error?: string }> {
  if (!session?.user) {
    return { authorized: false, error: 'Authentication required' };
  }

  if (permission && !hasPermission(session, permission)) {
    return { authorized: false, error: `Permission denied: ${permission}` };
  }

  return { authorized: true };
}
