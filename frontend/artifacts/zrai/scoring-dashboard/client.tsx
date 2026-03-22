"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import type { Lead, ScoringResult } from "@/lib/zrai/types";

type ScoringDashboardData = {
  count: number;
  results: ScoringResult[];
  scored_at: string;
};

type ScoringDashboardMetadata = {
  count: number;
  loading: boolean;
  results: ScoringResult[];
  scored_at: string | null;
  selectedLeadId: string | null;
};

function parseScoringPayload(content: string): ScoringDashboardData | null {
  if (!content) {
    return null;
  }

  try {
    const parsed = JSON.parse(content) as Partial<ScoringDashboardData>;
    return {
      count: typeof parsed.count === "number" ? parsed.count : 0,
      results: Array.isArray(parsed.results) ? parsed.results : [],
      scored_at: typeof parsed.scored_at === "string" ? parsed.scored_at : "",
    };
  } catch {
    return null;
  }
}

function scoreValue(result: ScoringResult) {
  return result.score_breakdown?.total_score ?? result.lead?.score ?? 0;
}

function ScoreBar({
  label,
  max = 100,
  value,
}: {
  label: string;
  max?: number;
  value: number;
}) {
  const percentage = Math.max(0, Math.min(100, (value / max) * 100));
  const color =
    percentage >= 80
      ? "bg-green-500"
      : percentage >= 60
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <span className="w-24 text-xs text-zinc-500">{label}</span>
      <div className="h-2 flex-1 rounded-full bg-zinc-200 dark:bg-zinc-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-medium">{value}</span>
    </div>
  );
}

function LeadScoreCard({
  isSelected,
  onClick,
  rank,
  result,
}: {
  isSelected: boolean;
  onClick: () => void;
  rank: number;
  result: ScoringResult;
}) {
  const lead = result.lead;

  if (!lead) {
    return null;
  }

  const score = scoreValue(result);
  const scoreColor =
    score >= 80 ? "text-green-600" : score >= 60 ? "text-yellow-600" : "text-red-600";

  return (
    <div
      className={`cursor-pointer rounded-lg border p-3 transition-colors ${
        isSelected
          ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
          : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        <div className="flex size-8 items-center justify-center rounded-full bg-zinc-100 text-sm font-bold dark:bg-zinc-800">
          #{rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium">{lead.company_name}</div>
          <div className="text-xs text-zinc-500">
            {lead.niche} • {lead.geo}
          </div>
        </div>
        <div className={`text-2xl font-bold ${scoreColor}`}>{score}</div>
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
  const payload = parseScoringPayload(content);
  const results = metadata?.results?.length ? metadata.results : payload?.results || [];
  const count = metadata?.count || payload?.count || results.length;
  const scoredAt = metadata?.scored_at || payload?.scored_at || null;

  const sortedResults = useMemo(
    () => [...results].sort((a, b) => scoreValue(b) - scoreValue(a)),
    [results]
  );

  const selectedLeadId =
    metadata?.selectedLeadId || sortedResults.find((result) => result.lead)?.lead?.id || null;
  const selectedResult =
    sortedResults.find((result) => result.lead?.id === selectedLeadId) || sortedResults[0] || null;
  const selectedLead = selectedResult?.lead || null;
  const breakdown = selectedResult?.score_breakdown;

  if (!sortedResults.length) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No scoring results</div>
          <div className="text-sm">Use a deterministic score action to rank the current leads.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="w-1/2 overflow-auto border-zinc-200 border-r p-4 dark:border-zinc-700">
        <div className="mb-4">
          <h3 className="font-semibold">Lead Rankings</h3>
          <p className="text-sm text-zinc-500">
            {count} scored lead{count === 1 ? "" : "s"}
            {scoredAt ? ` • ${new Date(scoredAt).toLocaleString()}` : ""}
          </p>
        </div>

        <div className="space-y-2">
          {sortedResults.map((result, idx) => (
            <LeadScoreCard
              isSelected={result.lead?.id === selectedLeadId}
              key={result.lead?.id || `${result.lead_id || "result"}-${idx}`}
              onClick={() =>
                setMetadata((prev) => ({
                  ...prev,
                  selectedLeadId: result.lead?.id || null,
                }))
              }
              rank={idx + 1}
              result={result}
            />
          ))}
        </div>
      </div>

      <div className="w-1/2 overflow-auto p-4">
        {selectedLead && selectedResult ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold">{selectedLead.company_name}</h3>
              <p className="text-sm text-zinc-500">{selectedLead.domain}</p>
            </div>

            <div className="rounded-lg bg-zinc-50 p-4 dark:bg-zinc-800">
              <div className="mb-2 text-sm font-medium">Score Breakdown</div>
              <div className="space-y-2">
                <ScoreBar label="Intent" value={breakdown?.intent_score ?? 0} />
                <ScoreBar label="Fit" value={breakdown?.fit_score ?? 0} />
                <ScoreBar label="Engagement" value={breakdown?.engagement_score ?? 0} />
                <ScoreBar label="Recency" value={breakdown?.recency_score ?? 0} />
                <ScoreBar label="Total" value={breakdown?.total_score ?? scoreValue(selectedResult)} />
              </div>
            </div>

            <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
              <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">Status</div>
              <div className="mt-2">{selectedLead.status.replace(/_/g, " ")}</div>
              {selectedResult.disqualified && (
                <div className="mt-2 text-sm text-red-400">
                  Disqualified: {selectedResult.disqualification_reason || "No reason provided"}
                </div>
              )}
            </div>

            {!!selectedLead.intent_signals?.length && (
              <div>
                <div className="mb-2 text-sm font-medium">Intent Signals</div>
                <div className="space-y-1">
                  {selectedLead.intent_signals.map((signal, idx) => (
                    <div
                      className="rounded bg-zinc-100 px-2 py-1 text-sm dark:bg-zinc-800"
                      key={`${selectedLead.id}-signal-${idx}`}
                    >
                      <span className="font-medium">{signal.signal_type}:</span> {signal.signal_value}
                      <span className="ml-2 text-xs text-zinc-500">
                        ({Math.round(signal.confidence * 100)}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
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

export const scoringDashboardArtifact = new Artifact<
  "scoring-dashboard",
  ScoringDashboardMetadata
>({
  kind: "scoring-dashboard",
  description: "Display lead rankings with real scoring breakdowns.",
  initialize: ({ setMetadata }) => {
    setMetadata({
      count: 0,
      loading: false,
      results: [],
      scored_at: null,
      selectedLeadId: null,
    });
  },
  onStreamPart: ({ setArtifact, setMetadata, streamPart }) => {
    if ((streamPart as any).type === "data-scoringDashboard") {
      const data = (streamPart as any).data as ScoringDashboardData;
      setMetadata((prev) => ({
        ...prev,
        count: data.count,
        loading: false,
        results: data.results || [],
        scored_at: data.scored_at || null,
        selectedLeadId: data.results?.[0]?.lead?.id || prev.selectedLeadId,
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
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
      onClick: ({ handleVersionChange }) => handleVersionChange("prev"),
    },
    {
      icon: <RedoIcon size={18} />,
      description: "View Next version",
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
      onClick: ({ handleVersionChange }) => handleVersionChange("next"),
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
  toolbar: [],
});
