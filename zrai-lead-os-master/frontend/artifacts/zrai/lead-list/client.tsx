"use client";

/**
 * ZRAI Lead List Artifact - Client Component
 * 
 * Displays a list of leads with filtering and sorting.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import type { Lead } from "@/lib/zrai/types";

type LeadListMetadata = {
  leads: Lead[];
  loading: boolean;
  sortBy: string;
  sortOrder: "asc" | "desc";
  filter: string;
};

function LeadRow({ lead, onClick }: { lead: Lead; onClick: () => void }) {
  const scoreColor = (lead.score || 0) >= 80 ? 'text-green-600' : 
                     (lead.score || 0) >= 60 ? 'text-yellow-600' : 'text-red-600';

  return (
    <tr 
      className="cursor-pointer border-b border-zinc-200 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
      onClick={onClick}
    >
      <td className="p-3">
        <div className="font-medium">{lead.company_name}</div>
        <div className="text-xs text-zinc-500">{lead.domain}</div>
      </td>
      <td className="p-3 text-sm">{lead.niche}</td>
      <td className="p-3 text-sm">{lead.geo}</td>
      <td className={`p-3 text-sm font-bold ${scoreColor}`}>
        {lead.score ?? '-'}
      </td>
      <td className="p-3">
        <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800">
          {lead.status.replace('_', ' ')}
        </span>
      </td>
      <td className="p-3 text-sm text-zinc-500">
        {lead.contacts?.length || 0}
      </td>
    </tr>
  );
}

function LeadListContent({ 
  content, 
  metadata, 
  setMetadata 
}: { 
  content: string; 
  metadata: LeadListMetadata;
  setMetadata: (fn: (prev: LeadListMetadata) => LeadListMetadata) => void;
}) {
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  
  // Parse leads from content or metadata
  let leads: Lead[] = metadata?.leads || [];
  
  if (leads.length === 0 && content) {
    try {
      const parsed = JSON.parse(content);
      leads = Array.isArray(parsed) ? parsed : parsed.leads || [];
    } catch {
      // Content might not be JSON
    }
  }

  // Apply filter
  const filter = metadata?.filter || "";
  const filteredLeads = filter 
    ? leads.filter(l => 
        l.company_name.toLowerCase().includes(filter.toLowerCase()) ||
        l.domain.toLowerCase().includes(filter.toLowerCase()) ||
        l.niche.toLowerCase().includes(filter.toLowerCase())
      )
    : leads;

  // Apply sort
  const sortBy = metadata?.sortBy || "score";
  const sortOrder = metadata?.sortOrder || "desc";
  const sortedLeads = [...filteredLeads].sort((a, b) => {
    let aVal: any = a[sortBy as keyof Lead];
    let bVal: any = b[sortBy as keyof Lead];
    
    if (typeof aVal === 'string') aVal = aVal.toLowerCase();
    if (typeof bVal === 'string') bVal = bVal.toLowerCase();
    
    if (aVal < bVal) return sortOrder === "asc" ? -1 : 1;
    if (aVal > bVal) return sortOrder === "asc" ? 1 : -1;
    return 0;
  });

  if (leads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No leads found</div>
          <div className="text-sm">Use the discover tool to find leads</div>
        </div>
      </div>
    );
  }

  const handleSort = (column: string) => {
    setMetadata((prev) => ({
      ...prev,
      sortBy: column,
      sortOrder: prev.sortBy === column && prev.sortOrder === "desc" ? "asc" : "desc",
    }));
  };

  return (
    <div className="flex h-full flex-col">
      {/* Filter */}
      <div className="border-b border-zinc-200 p-3 dark:border-zinc-700">
        <input
          type="text"
          placeholder="Filter leads..."
          className="w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-600"
          value={filter}
          onChange={(e) => setMetadata((prev) => ({ ...prev, filter: e.target.value }))}
        />
      </div>

      {/* Stats */}
      <div className="flex gap-4 border-b border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
        <span>Total: {leads.length}</span>
        <span>Filtered: {filteredLeads.length}</span>
        <span>Avg Score: {Math.round(leads.reduce((sum, l) => sum + (l.score || 0), 0) / leads.length) || 0}</span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-900">
            <tr>
              <th 
                className="cursor-pointer p-3 text-left text-sm font-medium"
                onClick={() => handleSort("company_name")}
              >
                Company {sortBy === "company_name" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th 
                className="cursor-pointer p-3 text-left text-sm font-medium"
                onClick={() => handleSort("niche")}
              >
                Niche {sortBy === "niche" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th 
                className="cursor-pointer p-3 text-left text-sm font-medium"
                onClick={() => handleSort("geo")}
              >
                Geo {sortBy === "geo" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th 
                className="cursor-pointer p-3 text-left text-sm font-medium"
                onClick={() => handleSort("score")}
              >
                Score {sortBy === "score" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th 
                className="cursor-pointer p-3 text-left text-sm font-medium"
                onClick={() => handleSort("status")}
              >
                Status {sortBy === "status" && (sortOrder === "asc" ? "↑" : "↓")}
              </th>
              <th className="p-3 text-left text-sm font-medium">Contacts</th>
            </tr>
          </thead>
          <tbody>
            {sortedLeads.map((lead) => (
              <LeadRow 
                key={lead.id} 
                lead={lead} 
                onClick={() => setSelectedLead(lead)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Selected Lead Preview */}
      {selectedLead && (
        <div className="border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-800">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-bold">{selectedLead.company_name}</div>
              <div className="text-sm text-zinc-500">{selectedLead.domain}</div>
            </div>
            <button 
              className="text-sm text-blue-500 hover:underline"
              onClick={() => setSelectedLead(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export const leadListArtifact = new Artifact<"lead-list", LeadListMetadata>({
  kind: "lead-list",
  description: "Display a list of leads with filtering and sorting capabilities",
  initialize: ({ setMetadata }) => {
    setMetadata({
      leads: [],
      loading: false,
      sortBy: "score",
      sortOrder: "desc",
      filter: "",
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-leadList") {
      const data = (streamPart as any).data as Lead[];
      setMetadata((prev) => ({
        ...prev,
        leads: data,
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
    <LeadListContent 
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
      description: "Copy as CSV",
      onClick: ({ content }) => {
        try {
          const leads = JSON.parse(content);
          const csv = [
            "Company,Domain,Niche,Geo,Score,Status",
            ...leads.map((l: Lead) => 
              `"${l.company_name}","${l.domain}","${l.niche}","${l.geo}",${l.score || ''},"${l.status}"`
            )
          ].join("\n");
          navigator.clipboard.writeText(csv);
          toast.success("Copied as CSV!");
        } catch {
          navigator.clipboard.writeText(content);
          toast.success("Copied!");
        }
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">🔍</span>,
      description: "Enrich all leads",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Enrich all leads in this list" }],
        });
      },
    },
    {
      icon: <span className="text-xs">📊</span>,
      description: "Score all leads",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Score all leads in this list" }],
        });
      },
    },
  ],
});
