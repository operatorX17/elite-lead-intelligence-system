"use client";

/**
 * ZRAI Outreach Draft Artifact - Client Component
 * 
 * Displays and edits outreach messages with 4-part structure.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import type { OutreachMessage } from "@/lib/zrai/types";

type OutreachDraftMetadata = {
  message: OutreachMessage | null;
  isEditing: boolean;
  loading: boolean;
};

function StructureSection({ 
  label, 
  content, 
  color,
  isEditing,
  onChange,
}: { 
  label: string; 
  content: string; 
  color: string;
  isEditing: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className={`rounded-lg border-l-4 ${color} bg-zinc-50 p-3 dark:bg-zinc-800`}>
      <div className="mb-1 text-xs font-semibold uppercase text-zinc-500">{label}</div>
      {isEditing ? (
        <textarea
          className="w-full resize-none rounded border border-zinc-300 bg-white p-2 text-sm dark:border-zinc-600 dark:bg-zinc-900"
          value={content}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
        />
      ) : (
        <div className="text-sm">{content}</div>
      )}
    </div>
  );
}

function OutreachDraftContent({ 
  content, 
  metadata,
  setMetadata,
  onSaveContent,
}: { 
  content: string; 
  metadata: OutreachDraftMetadata;
  setMetadata: (fn: (prev: OutreachDraftMetadata) => OutreachDraftMetadata) => void;
  onSaveContent: (content: string, debounce: boolean) => void;
}) {
  const [editedMessage, setEditedMessage] = useState<OutreachMessage | null>(null);
  
  let message: OutreachMessage | null = metadata?.message || null;
  
  if (!message && content) {
    try {
      message = JSON.parse(content);
    } catch {
      // Content might not be JSON
    }
  }

  const isEditing = metadata?.isEditing || false;
  const displayMessage = isEditing && editedMessage ? editedMessage : message;

  if (!displayMessage) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No outreach draft</div>
          <div className="text-sm">Use the draft outreach tool to create a message</div>
        </div>
      </div>
    );
  }

  const handleEdit = () => {
    setEditedMessage(message);
    setMetadata((prev) => ({ ...prev, isEditing: true }));
  };

  const handleSave = () => {
    if (editedMessage) {
      onSaveContent(JSON.stringify(editedMessage), false);
      setMetadata((prev) => ({ ...prev, message: editedMessage, isEditing: false }));
    }
  };

  const handleCancel = () => {
    setEditedMessage(null);
    setMetadata((prev) => ({ ...prev, isEditing: false }));
  };

  const updateStructure = (key: keyof OutreachMessage['structure'], value: string) => {
    if (editedMessage) {
      setEditedMessage({
        ...editedMessage,
        structure: { ...editedMessage.structure, [key]: value },
      });
    }
  };

  const channelIcons: Record<string, string> = {
    email: '📧',
    linkedin: '💼',
    sms: '📱',
  };

  const charLimit = displayMessage.channel === 'sms' ? 160 : 
                    displayMessage.channel === 'linkedin' ? 300 : 
                    2000;
  
  const totalChars = Object.values(displayMessage.structure || {}).join(' ').length;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 p-4 dark:border-zinc-700">
        <div className="flex items-center gap-2">
          <span className="text-xl">{channelIcons[displayMessage.channel] || '📧'}</span>
          <div>
            <div className="font-medium">
              {displayMessage.channel.charAt(0).toUpperCase() + displayMessage.channel.slice(1)} Outreach
            </div>
            <div className="text-xs text-zinc-500">
              Lead ID: {displayMessage.lead_id}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <button
                className="rounded bg-zinc-200 px-3 py-1 text-sm hover:bg-zinc-300 dark:bg-zinc-700 dark:hover:bg-zinc-600"
                onClick={handleCancel}
              >
                Cancel
              </button>
              <button
                className="rounded bg-blue-500 px-3 py-1 text-sm text-white hover:bg-blue-600"
                onClick={handleSave}
              >
                Save
              </button>
            </>
          ) : (
            <button
              className="rounded bg-zinc-200 px-3 py-1 text-sm hover:bg-zinc-300 dark:bg-zinc-700 dark:hover:bg-zinc-600"
              onClick={handleEdit}
            >
              Edit
            </button>
          )}
        </div>
      </div>

      {/* Subject (for email) */}
      {displayMessage.channel === 'email' && displayMessage.subject && (
        <div className="border-b border-zinc-200 p-4 dark:border-zinc-700">
          <div className="text-xs text-zinc-500">Subject</div>
          <div className="font-medium">{displayMessage.subject}</div>
        </div>
      )}

      {/* Message Structure */}
      <div className="flex-1 space-y-3 overflow-auto p-4">
        <StructureSection
          label="Observation"
          content={displayMessage.structure?.observation || ''}
          color="border-l-blue-500"
          isEditing={isEditing}
          onChange={(v) => updateStructure('observation', v)}
        />
        <StructureSection
          label="Impact"
          content={displayMessage.structure?.impact || ''}
          color="border-l-yellow-500"
          isEditing={isEditing}
          onChange={(v) => updateStructure('impact', v)}
        />
        <StructureSection
          label="Offer"
          content={displayMessage.structure?.offer || ''}
          color="border-l-green-500"
          isEditing={isEditing}
          onChange={(v) => updateStructure('offer', v)}
        />
        <StructureSection
          label="Call to Action"
          content={displayMessage.structure?.cta || ''}
          color="border-l-purple-500"
          isEditing={isEditing}
          onChange={(v) => updateStructure('cta', v)}
        />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
        <div className="text-sm text-zinc-500">
          {totalChars} / {charLimit} characters
          {totalChars > charLimit && (
            <span className="ml-2 text-red-500">⚠️ Over limit</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-1 text-xs ${
            displayMessage.status === 'draft' ? 'bg-yellow-100 text-yellow-800' :
            displayMessage.status === 'sent' ? 'bg-green-100 text-green-800' :
            'bg-zinc-100 text-zinc-800'
          }`}>
            {displayMessage.status}
          </span>
        </div>
      </div>
    </div>
  );
}

export const outreachDraftArtifact = new Artifact<"outreach-draft", OutreachDraftMetadata>({
  kind: "outreach-draft",
  description: "Display and edit outreach messages with 4-part structure",
  initialize: ({ setMetadata }) => {
    setMetadata({
      message: null,
      isEditing: false,
      loading: false,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-outreachDraft") {
      const data = (streamPart as any).data as OutreachMessage;
      setMetadata((prev) => ({
        ...prev,
        message: data,
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
    <OutreachDraftContent 
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
      description: "Copy message",
      onClick: ({ content }) => {
        try {
          const msg = JSON.parse(content);
          const text = Object.values(msg.structure || {}).join('\n\n');
          navigator.clipboard.writeText(text);
          toast.success("Message copied!");
        } catch {
          navigator.clipboard.writeText(content);
          toast.success("Copied!");
        }
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">📤</span>,
      description: "Send message",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Send this outreach message" }],
        });
      },
    },
    {
      icon: <span className="text-xs">🔄</span>,
      description: "Regenerate",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Regenerate this outreach message with a different approach" }],
        });
      },
    },
  ],
});
