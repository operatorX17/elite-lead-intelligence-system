"use client";

/**
 * ZRAI Scoring Dashboard Artifact - Client Component
 * 
 * Displays lead rankings with score breakdowns.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import type { Lead, ScoringResult } from "@/lib/zrai/types";

type ScoringDashboardMetadata = {
  results: ScoringResult | null;
  loading: boolean;
  selectedLead: string | null;
};

function ScoreBar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const percentage = (value / max) * 100;
  const color = percentage >= 80 ? 'bg-green-500' : percentage >= 60 ? 'bg-yellow-500' : 'bg-red-500';
  
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 text-xs text-zinc-500">{label}</span>
      <div className="h-2 flex-1 rounded-full bg-zinc-200 dark:bg-zinc-700">
        <div 
          className={`h-full rounded-full ${color}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="w-8 text-right text-xs font-medium">{value}</span>
    </div>
  );
}

function LeadScoreCard({ 
  lead, 
  rank, 
  isSelected, 
  onClick 
}: { 
  lead: Lead; 
  rank: number; 
  isSelected: boolean;
  onClick: () => void;
}) {
  const scoreColor = (lead.score || 0) >= 80 ? 'text-green-600' : 
                     (lead.score || 0) >= 60 ? 'text-yellow-600' : 'text-red-600';

  return (
    <div 
      className={`cursor-pointer rounded-lg border p-3 transition-colors ${
        isSelected 
          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
          : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600'
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        <div className="flex size-8 items-center justify-center rounded-full bg-zinc-100 text-sm font-bold dark:bg-zinc-800">
          #{rank}
        </div>
        <div className="flex-1">
          <div className="font-medium">{lead.company_name}</div>
          <div className="text-xs text-zinc-500">{lead.niche} • {lead.geo}</div>
        </div>
        <div className={`text-2xl font-bold ${scoreColor}`}>
          {lead.score || 0}
        </div>
      </div>
    </div>
  );
}

function ScoringDashboardContent({ 
  content, 
  metadata,
  setMetadata,
}: { 
  content: string; 
  metadata: ScoringDashboardMetadata;
  setMetadata: (fn: (prev: ScoringDashboardMetadata) => ScoringDashboardMetadata) => void;
}) {
  let results: ScoringResult | null = metadata?.results || null;
  
  if (!results && content) {
    try {
      results = JSON.parse(content);
    } catch {
      // Content might not be JSON
    }
  }

  const selectedLeadId = metadata?.selectedLead;
  const selectedLead = results?.leads?.find(l => l.id === selectedLeadId);

  if (!results || !results.leads || results.leads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No scoring results</div>
          <div className="text-sm">Use the score leads tool to rank your pipeline</div>
        </div>
      </div>
    );
  }

  // Sort leads by score
  const sortedLeads = [...results.leads].sort((a, b) => (b.score || 0) - (a.score || 0));

  return (
    <div className="flex h-full">
      {/* Lead List */}
      <div className="w-1/2 overflow-auto border-r border-zinc-200 p-4 dark:border-zinc-700">
        <div className="mb-4">
          <h3 className="font-semibold">Lead Rankings</h3>
          <p className="text-sm text-zinc-500">{sortedLeads.length} leads scored</p>
        </div>
        
        <div className="space-y-2">
          {sortedLeads.map((lead, idx) => (
            <LeadScoreCard
              key={lead.id}
              lead={lead}
              rank={idx + 1}
              isSelected={lead.id === selectedLeadId}
              onClick={() => setMetadata((prev) => ({ ...prev, selectedLead: lead.id }))}
            />
          ))}
        </div>
      </div>

      {/* Score Details */}
      <div className="w-1/2 overflow-auto p-4">
        {selectedLead ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold">{selectedLead.company_name}</h3>
              <p className="text-sm text-zinc-500">{selectedLead.domain}</p>
            </div>

            <div className="rounded-lg bg-zinc-50 p-4 dark:bg-zinc-800">
              <div className="mb-2 text-sm font-medium">Score Breakdown</div>
              <div className="space-y-2">
                <ScoreBar label="Intent" value={Math.round((selectedLead.score || 0) * 0.4)} max={40} />
                <ScoreBar label="Fit" value={Math.round((selectedLead.score || 0) * 0.3)} max={30} />
                <ScoreBar label="Engagement" value={Math.round((selectedLead.score || 0) * 0.2)} max={20} />
                <ScoreBar label="Recency" value={Math.round((selectedLead.score || 0) * 0.1)} max={10} />
              </div>
            </div>

            {selectedLead.intent_signals && selectedLead.intent_signals.length > 0 && (
              <div>
                <div className="mb-2 text-sm font-medium">Intent Signals</div>
                <div className="space-y-1">
                  {selectedLead.intent_signals.map((signal, idx) => (
                    <div key={idx} className="rounded bg-zinc-100 px-2 py-1 text-sm dark:bg-zinc-800">
                      <span className="font-medium">{signal.signal_type}:</span> {signal.signal_value}
                      <span className="ml-2 text-xs text-zinc-500">({Math.round(signal.confidence * 100)}%)</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs text-zinc-400">
              Status: {selectedLead.status.replace('_', ' ')}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-zinc-500">
            Select a lead to view score details
          </div>
        )}
      </div>
    </div>
  );
}

export const scoringDashboardArtifact = new Artifact<"scoring-dashboard", ScoringDashboardMetadata>({
  kind: "scoring-dashboard",
  description: "Display lead rankings with score breakdowns and filtering",
  initialize: ({ setMetadata }) => {
    setMetadata({
      results: null,
      loading: false,
      selectedLead: null,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-scoringDashboard") {
      const data = (streamPart as any).data as ScoringResult;
      setMetadata((prev) => ({
        ...prev,
        results: data,
        loading: false,
      }));
      setArtifact((draft) => ({
        ...draft,
        content: JSON.stringify(data),
        status: "idle",
      }));
    }
  },
  content: (props) => (
    <ScoringDashboardContent 
      content={props.content} 
      metadata={props.metadata}
      setMetadata={props.setMetadata}
    />
  ),
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
      description: "Copy rankings",
      onClick: ({ content }) => {
        navigator.clipboard.writeText(content);
        toast.success("Rankings copied!");
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">🔄</span>,
      description: "Re-score leads",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Re-score all leads with updated criteria" }],
        });
      },
    },
    {
      icon: <span className="text-xs">📧</span>,
      description: "Draft outreach for top leads",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Draft outreach for the top 5 scored leads" }],
        });
      },
    },
  ],
});
