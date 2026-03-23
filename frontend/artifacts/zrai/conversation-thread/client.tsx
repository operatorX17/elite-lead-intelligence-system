"use client";

/**
 * ZRAI Conversation Thread Artifact - Client Component
 * 
 * Displays conversation history with lead.
 */

import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import { formatArtifactPayloadForClipboard } from "@/lib/zrai/clipboard";
import type { ConversationMessage } from "@/lib/zrai/types";

type ConversationThreadMetadata = {
  messages: ConversationMessage[];
  leadId: string | null;
  status: 'active' | 'qualified' | 'escalated' | 'closed';
  loading: boolean;
};

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isAI = message.sender === 'ai';
  
  return (
    <div className={`flex ${isAI ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[80%] rounded-lg p-3 ${
        isAI 
          ? 'bg-zinc-100 dark:bg-zinc-800' 
          : 'bg-blue-500 text-white'
      }`}>
        <div className="text-sm">{message.content}</div>
        <div className={`mt-1 flex items-center gap-2 text-xs ${
          isAI ? 'text-zinc-500' : 'text-blue-100'
        }`}>
          <span>{message.channel}</span>
          <span>•</span>
          <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
        </div>
        
        {/* Qualification signals */}
        {message.qualification_signals && message.qualification_signals.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.qualification_signals.map((signal, idx) => (
              <span 
                key={idx}
                className={`rounded-full px-2 py-0.5 text-xs ${
                  signal.type === 'positive' 
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                    : signal.type === 'negative'
                    ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                    : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                }`}
              >
                {signal.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationThreadContent({ 
  content, 
  metadata,
}: { 
  content: string; 
  metadata: ConversationThreadMetadata;
}) {
  let messages: ConversationMessage[] = metadata?.messages || [];
  let status = metadata?.status || 'active';
  
  if (messages.length === 0 && content) {
    try {
      const parsed = JSON.parse(content);
      messages = parsed.messages || parsed;
      status = parsed.status || status;
    } catch {
      // Content might not be JSON
    }
  }

  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No conversation yet</div>
          <div className="text-sm">Messages will appear here when the lead responds</div>
        </div>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    active: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    qualified: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    escalated: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    closed: 'bg-zinc-100 text-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400',
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 p-4 dark:border-zinc-700">
        <div>
          <div className="font-medium">Conversation Thread</div>
          <div className="text-xs text-zinc-500">
            {messages.length} messages • Lead: {metadata?.leadId || 'Unknown'}
          </div>
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusColors[status]}`}>
          {status}
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-auto p-4">
        {messages.map((message, idx) => (
          <MessageBubble key={idx} message={message} />
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
        <div className="flex items-center justify-between text-sm text-zinc-500">
          <span>
            Last activity: {messages.length > 0 
              ? new Date(messages[messages.length - 1].timestamp).toLocaleString()
              : 'N/A'
            }
          </span>
          {status === 'escalated' && (
            <span className="text-yellow-600">⚠️ Awaiting human review</span>
          )}
        </div>
      </div>
    </div>
  );
}

export const conversationThreadArtifact = new Artifact<"conversation-thread", ConversationThreadMetadata>({
  kind: "conversation-thread",
  description: "Display conversation history with lead including qualification signals",
  initialize: ({ setMetadata }) => {
    setMetadata({
      messages: [],
      leadId: null,
      status: 'active',
      loading: false,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-conversationThread") {
      const data = (streamPart as any).data as { messages: ConversationMessage[]; leadId: string; status: string };
      setMetadata((prev) => ({
        ...prev,
        messages: data.messages,
        leadId: data.leadId,
        status: data.status as any,
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
    <ConversationThreadContent 
      content={props.content} 
      metadata={props.metadata}
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
      description: "Copy conversation",
      onClick: ({ content }) => {
        try {
          const data = JSON.parse(content);
          const text = formatArtifactPayloadForClipboard(
            "conversation-thread",
            data
          );
          navigator.clipboard.writeText(text);
          toast.success("Conversation copied!");
        } catch {
          navigator.clipboard.writeText(content);
          toast.success("Copied!");
        }
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">💬</span>,
      description: "Reply to lead",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Draft a reply to this conversation" }],
        });
      },
    },
    {
      icon: <span className="text-xs">🚨</span>,
      description: "Escalate to human",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Escalate this conversation to a human" }],
        });
      },
    },
  ],
});
