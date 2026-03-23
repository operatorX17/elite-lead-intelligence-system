"use client";

/**
 * ZRAI Lead Sheet Artifact - Client Component
 * 
 * Spreadsheet-style view for bulk lead management.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import { formatArtifactPayloadForClipboard } from "@/lib/zrai/clipboard";
import type { Lead } from "@/lib/zrai/types";

type LeadSheetMetadata = {
  leads: Lead[];
  selectedRows: Set<string>;
  editingCell: { rowId: string; column: string } | null;
  loading: boolean;
};

function LeadSheetContent({ 
  content, 
  metadata,
  setMetadata,
  onSaveContent,
}: { 
  content: string; 
  metadata: LeadSheetMetadata;
  setMetadata: (fn: (prev: LeadSheetMetadata) => LeadSheetMetadata) => void;
  onSaveContent: (content: string, debounce: boolean) => void;
}) {
  const [sortColumn, setSortColumn] = useState<string>('score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  
  let leads: Lead[] = metadata?.leads || [];
  
  if (leads.length === 0 && content) {
    try {
      const parsed = JSON.parse(content);
      leads = Array.isArray(parsed) ? parsed : parsed.leads || [];
    } catch {
      // Content might not be JSON
    }
  }

  const selectedRows = metadata?.selectedRows || new Set<string>();
  const editingCell = metadata?.editingCell;

  if (leads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No leads in sheet</div>
          <div className="text-sm">Import leads or use the discover tool</div>
        </div>
      </div>
    );
  }

  // Sort leads
  const sortedLeads = [...leads].sort((a, b) => {
    const aVal = a[sortColumn as keyof Lead];
    const bVal = b[sortColumn as keyof Lead];
    
    if (aVal === undefined) return 1;
    if (bVal === undefined) return -1;
    
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      return sortOrder === 'asc' 
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    }
    
    return sortOrder === 'asc' 
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortOrder('desc');
    }
  };

  const toggleRowSelection = (id: string) => {
    setMetadata((prev) => {
      const newSelected = new Set(prev.selectedRows);
      if (newSelected.has(id)) {
        newSelected.delete(id);
      } else {
        newSelected.add(id);
      }
      return { ...prev, selectedRows: newSelected };
    });
  };

  const toggleAllSelection = () => {
    setMetadata((prev) => {
      if (prev.selectedRows.size === leads.length) {
        return { ...prev, selectedRows: new Set() };
      }
      return { ...prev, selectedRows: new Set(leads.map(l => l.id)) };
    });
  };

  const handleCellEdit = (rowId: string, column: string, value: string) => {
    const updatedLeads = leads.map(lead => {
      if (lead.id === rowId) {
        return { ...lead, [column]: value };
      }
      return lead;
    });
    
    setMetadata((prev) => ({ ...prev, leads: updatedLeads, editingCell: null }));
    onSaveContent(JSON.stringify(updatedLeads), true);
  };

  const exportCSV = () => {
    const headers = ['Company', 'Domain', 'Niche', 'Geo', 'Score', 'Status', 'Contacts'];
    const rows = sortedLeads.map(l => [
      l.company_name,
      l.domain,
      l.niche,
      l.geo,
      l.score?.toString() || '',
      l.status,
      l.contacts?.length.toString() || '0',
    ]);
    
    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'leads.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toast.success('CSV exported!');
  };

  const columns = [
    { key: 'company_name', label: 'Company', width: 'w-48' },
    { key: 'domain', label: 'Domain', width: 'w-40' },
    { key: 'niche', label: 'Niche', width: 'w-32' },
    { key: 'geo', label: 'Geo', width: 'w-24' },
    { key: 'score', label: 'Score', width: 'w-20' },
    { key: 'status', label: 'Status', width: 'w-28' },
  ];

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-700 dark:bg-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-500">
            {selectedRows.size > 0 
              ? `${selectedRows.size} selected`
              : `${leads.length} leads`
            }
          </span>
          {selectedRows.size > 0 && (
            <button
              className="rounded bg-blue-500 px-2 py-1 text-xs text-white hover:bg-blue-600"
              onClick={() => {
                toast.info(`Bulk action on ${selectedRows.size} leads`);
              }}
            >
              Bulk Action
            </button>
          )}
        </div>
        <button
          className="rounded bg-zinc-200 px-3 py-1 text-sm hover:bg-zinc-300 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          onClick={exportCSV}
        >
          Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-900">
            <tr>
              <th className="w-10 border-b border-zinc-200 p-2 dark:border-zinc-700">
                <input
                  type="checkbox"
                  checked={selectedRows.size === leads.length}
                  onChange={toggleAllSelection}
                  className="rounded"
                />
              </th>
              {columns.map(col => (
                <th
                  key={col.key}
                  className={`${col.width} cursor-pointer border-b border-zinc-200 p-2 text-left text-sm font-medium hover:bg-zinc-200 dark:border-zinc-700 dark:hover:bg-zinc-800`}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {sortColumn === col.key && (
                    <span className="ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedLeads.map((lead) => (
              <tr 
                key={lead.id}
                className={`border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/50 ${
                  selectedRows.has(lead.id) ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                }`}
              >
                <td className="p-2">
                  <input
                    type="checkbox"
                    checked={selectedRows.has(lead.id)}
                    onChange={() => toggleRowSelection(lead.id)}
                    className="rounded"
                  />
                </td>
                {columns.map(col => {
                  const isEditing = editingCell?.rowId === lead.id && editingCell?.column === col.key;
                  const value = lead[col.key as keyof Lead];
                  
                  return (
                    <td 
                      key={col.key}
                      className={`${col.width} p-2 text-sm`}
                      onDoubleClick={() => {
                        if (col.key !== 'score') {
                          setMetadata((prev) => ({ 
                            ...prev, 
                            editingCell: { rowId: lead.id, column: col.key } 
                          }));
                        }
                      }}
                    >
                      {isEditing ? (
                        <input
                          type="text"
                          defaultValue={String(value || '')}
                          className="w-full rounded border border-blue-500 bg-white px-1 py-0.5 text-sm dark:bg-zinc-900"
                          autoFocus
                          onBlur={(e) => handleCellEdit(lead.id, col.key, e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleCellEdit(lead.id, col.key, e.currentTarget.value);
                            } else if (e.key === 'Escape') {
                              setMetadata((prev) => ({ ...prev, editingCell: null }));
                            }
                          }}
                        />
                      ) : col.key === 'score' ? (
                        <span className={`font-medium ${
                          typeof value === 'number' && value >= 80 ? 'text-green-600' :
                          typeof value === 'number' && value >= 60 ? 'text-yellow-600' : 'text-red-600'
                        }`}>
                          {typeof value === 'number' ? value : '-'}
                        </span>
                      ) : col.key === 'status' ? (
                        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                          {String(value || '').replace('_', ' ')}
                        </span>
                      ) : (
                        <span className="truncate">{String(value || '')}</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export const leadSheetArtifact = new Artifact<"lead-sheet", LeadSheetMetadata>({
  kind: "lead-sheet",
  description: "Spreadsheet view for bulk lead management with sorting, filtering, and inline editing",
  initialize: ({ setMetadata }) => {
    setMetadata({
      leads: [],
      selectedRows: new Set(),
      editingCell: null,
      loading: false,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-leadSheet") {
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
    <LeadSheetContent 
      content={props.content} 
      metadata={props.metadata}
      setMetadata={props.setMetadata}
      onSaveContent={props.onSaveContent}
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
      description: "Copy lead sheet",
      onClick: ({ content }) => {
        try {
          const parsed = JSON.parse(content);
          navigator.clipboard.writeText(
            formatArtifactPayloadForClipboard("lead-sheet", parsed)
          );
          toast.success("Lead sheet copied!");
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
      description: "Enrich selected",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Enrich the selected leads" }],
        });
      },
    },
    {
      icon: <span className="text-xs">📊</span>,
      description: "Score selected",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Score the selected leads" }],
        });
      },
    },
    {
      icon: <span className="text-xs">📧</span>,
      description: "Draft outreach for selected",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Draft outreach for the selected leads" }],
        });
      },
    },
  ],
});
