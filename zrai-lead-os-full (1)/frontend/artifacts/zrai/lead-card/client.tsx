"use client";

/**
 * ZRAI Lead Card Artifact - Client Component
 * 
 * Displays detailed lead information with quick actions.
 */

import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import {
  CopyIcon,
  RedoIcon,
  UndoIcon,
} from "@/components/icons";
import type { Lead, IntentSignal } from "@/lib/zrai/types";

type LeadCardMetadata = {
  lead: Lead | null;
  loading: boolean;
};

function LeadStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    discovered: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    enriched: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
    scored: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    outreach_pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    outreach_sent: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
    replied: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400',
    qualified: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
    escalated: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    disqualified: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
  };

  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${colors[status] || colors.discovered}`}>
      {status.replace('_', ' ')}
    </span>
  );
}

function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined) return null;
  
  const color = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600';
  
  return (
    <div className={`text-2xl font-bold ${color}`}>
      {score}
    </div>
  );
}

function IntentSignalItem({ signal }: { signal: IntentSignal }) {
  // Map confidence to strength for display
  const strength = signal.confidence >= 0.7 ? 'high' : signal.confidence >= 0.4 ? 'medium' : 'low';
  const strengthColors: Record<string, string> = {
    high: 'border-l-green-500',
    medium: 'border-l-yellow-500',
    low: 'border-l-gray-500',
  };

  return (
    <div className={`border-l-4 ${strengthColors[strength]} bg-zinc-50 p-2 dark:bg-zinc-800`}>
      <div className="text-sm font-medium">{signal.signal_type}</div>
      <div className="text-xs text-zinc-500">{signal.signal_value}</div>
      <div className="text-xs text-zinc-400">Source: {signal.source} | Confidence: {Math.round(signal.confidence * 100)}%</div>
    </div>
  );
}

function LeadCardContent({ content, metadata }: { content: string; metadata: LeadCardMetadata }) {
  // Parse lead data from content or metadata
  let lead: Lead | null = metadata?.lead || null;
  
  if (!lead && content) {
    try {
      lead = JSON.parse(content);
    } catch {
      // Content might not be JSON
    }
  }

  if (!lead) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No lead data available</div>
          <div className="text-sm">Use the discover or enrich tools to load lead data</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold">{lead.company_name}</h2>
          <a 
            href={`https://${lead.domain}`} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-sm text-blue-500 hover:underline"
          >
            {lead.domain}
          </a>
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={lead.score} />
          <LeadStatusBadge status={lead.status} />
        </div>
      </div>

      {/* Details */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-zinc-500">Niche</div>
          <div className="font-medium">{lead.niche}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Geography</div>
          <div className="font-medium">{lead.geo}</div>
        </div>
      </div>

      {/* Contacts */}
      {lead.contacts && lead.contacts.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Contacts</h3>
          <div className="space-y-2">
            {lead.contacts.map((contact, idx) => (
              <div key={idx} className="rounded-lg border border-zinc-200 p-2 dark:border-zinc-700">
                <div className="font-medium">{contact.name}</div>
                <div className="text-sm text-zinc-500">{contact.title}</div>
                {contact.email && (
                  <a href={`mailto:${contact.email}`} className="text-sm text-blue-500 hover:underline">
                    {contact.email}
                  </a>
                )}
                {contact.linkedin_url && (
                  <a 
                    href={contact.linkedin_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="ml-2 text-sm text-blue-500 hover:underline"
                  >
                    LinkedIn
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Intent Signals */}
      {lead.intent_signals && lead.intent_signals.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Intent Signals</h3>
          <div className="space-y-2">
            {lead.intent_signals.map((signal, idx) => (
              <IntentSignalItem key={idx} signal={signal} />
            ))}
          </div>
        </div>
      )}

      {/* Timestamps */}
      <div className="border-t border-zinc-200 pt-2 text-xs text-zinc-400 dark:border-zinc-700">
        <div>Created: {new Date(lead.created_at).toLocaleString()}</div>
        <div>Updated: {new Date(lead.updated_at).toLocaleString()}</div>
      </div>
    </div>
  );
}

export const leadCardArtifact = new Artifact<"lead-card", LeadCardMetadata>({
  kind: "lead-card",
  description: "Display detailed lead information with contacts, scores, and intent signals",
  initialize: ({ setMetadata }) => {
    setMetadata({
      lead: null,
      loading: false,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-leadCard") {
      const data = (streamPart as any).data as Lead;
      setMetadata((prev) => ({
        ...prev,
        lead: data,
        loading: false,
      }));
      setArtifact((draft) => ({
        ...draft,
        content: JSON.stringify(data),
        status: "idle",
      }));
    }
  },
  content: (props) => <LeadCardContent content={props.content} metadata={props.metadata} />,
  actions: [
    {
      icon: <UndoIcon size={18} />,
      description: "View Previous version",
      onClick: ({ handleVersionChange }) => handleVersionChange("prev"),
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
    },
    {
      icon: <RedoIcon size={18} />,
      description: "View Next version",
      onClick: ({ handleVersionChange }) => handleVersionChange("next"),
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
    },
    {
      icon: <CopyIcon size={18} />,
      description: "Copy lead data",
      onClick: ({ content }) => {
        navigator.clipboard.writeText(content);
        toast.success("Lead data copied!");
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">📧</span>,
      description: "Draft outreach",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Draft an outreach message for this lead" }],
        });
      },
    },
    {
      icon: <span className="text-xs">🔍</span>,
      description: "Enrich lead",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Enrich this lead with more contact information" }],
        });
      },
    },
    {
      icon: <span className="text-xs">📊</span>,
      description: "Score lead",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Score this lead" }],
        });
      },
    },
  ],
});
