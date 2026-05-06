"use client";
import type { UseChatHelpers } from "@ai-sdk/react";
import equal from "fast-deep-equal";
import { memo, useEffect, useRef, useState } from "react";
import { useSWRConfig } from "swr";
import { useArtifact } from "@/hooks/use-artifact";
import type { Vote } from "@/lib/db/schema";
import type { ChatMessage, ZRAIActivityEvent } from "@/lib/types";
import {
  cn,
  getTextFromMessage,
  normalizeMessageParts,
  sanitizeText,
} from "@/lib/utils";
import { useDataStream } from "./data-stream-provider";
import { DocumentToolResult } from "./document";
import { DocumentPreview } from "./document-preview";
import { MessageContent } from "./elements/message";
import { Response } from "./elements/response";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "./elements/tool";
import { SparklesIcon } from "./icons";
import { MessageActions } from "./message-actions";
import { MessageEditor } from "./message-editor";
import { MessageReasoning } from "./message-reasoning";
import { PreviewAttachment } from "./preview-attachment";
import { Weather } from "./weather";

function hashArtifactSeed(input: string, seed: number) {
  let hash = seed >>> 0;

  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return hash >>> 0;
}

function buildStableArtifactDocumentId({
  chatId,
  kind,
  toolCallId,
}: {
  chatId?: string;
  kind: string;
  toolCallId: string;
}) {
  const seed = `${chatId || "global"}:${kind}:${toolCallId}`;
  const chunks = [
    hashArtifactSeed(`${seed}:0`, 0x811c9dc5),
    hashArtifactSeed(`${seed}:1`, 0x9e3779b9),
    hashArtifactSeed(`${seed}:2`, 0x85ebca6b),
    hashArtifactSeed(`${seed}:3`, 0xc2b2ae35),
  ];

  const hex = chunks
    .map((chunk) => chunk.toString(16).padStart(8, "0"))
    .join("");

  const versioned = `${hex.slice(0, 12)}4${hex.slice(13, 16)}${(
    (Number.parseInt(hex.slice(16, 18), 16) & 0x3f) |
    0x80
  )
    .toString(16)
    .padStart(2, "0")}${hex.slice(18)}`;

  return [
    versioned.slice(0, 8),
    versioned.slice(8, 12),
    versioned.slice(12, 16),
    versioned.slice(16, 20),
    versioned.slice(20, 32),
  ].join("-");
}

const artifactTitles: Record<string, string> = {
  "lead-list": "Lead List",
  "lead-card": "Lead Details",
  "proof-viewer": "Proof Viewer",
  "scoring-dashboard": "Scoring Dashboard",
  "outreach-draft": "Outreach Draft",
  "conversation-thread": "Conversation Thread",
  "metrics-dashboard": "Metrics Dashboard",
  "lead-sheet": "Lead Import Sheet",
};

const zraiToolTypes = new Set([
  "tool-dailyOperator",
  "tool-discoverLeads",
  "tool-enrichLead",
  "tool-analyzeIntent",
  "tool-generateProof",
  "tool-scoreLeads",
  "tool-draftOutreach",
  "tool-sendOutreach",
  "tool-handleConversation",
  "tool-approveEscalation",
  "tool-checkGovernance",
  "tool-manageABTest",
  "tool-runPipeline",
  "tool-importLeads",
  "tool-analyzeScreenshot",
]);

type ZRAIToolState =
  | "input-streaming"
  | "input-available"
  | "approval-requested"
  | "approval-responded"
  | "output-available"
  | "output-error"
  | "output-denied";

type ZRAIToolPart = {
  approval?: {
    approved?: boolean;
    id: string;
  };
  errorText?: string;
  input?: unknown;
  output?: {
    artifactTrigger?: {
      data?: unknown;
      kind: string;
    };
    error?: string;
    success?: boolean;
    suggestion?: string;
    summary?: string;
  };
  state: ZRAIToolState;
  toolCallId: string;
  type: string;
};

function isZRAIToolPart(part: unknown): part is ZRAIToolPart {
  if (!part || typeof part !== "object") {
    return false;
  }

  const type = (part as { type?: unknown }).type;

  return typeof type === "string" && zraiToolTypes.has(type);
}

function asZRAIToolPart(part: unknown) {
  return part as unknown as ZRAIToolPart;
}

function getMessageParts(message: ChatMessage) {
  return normalizeMessageParts(message.parts);
}

function hasRenderableText(text: string | undefined) {
  return Boolean(text && sanitizeText(text).trim().length > 0);
}

function hasZRAIArtifactTrigger(part: ChatMessage["parts"][number]) {
  if (!isZRAIToolPart(part)) {
    return false;
  }

  const candidate = asZRAIToolPart(part);

  return (
    candidate.state === "output-available" &&
    Boolean(candidate.output?.artifactTrigger?.kind)
  );
}

function shouldRenderZRAIToolPart(part: ChatMessage["parts"][number]) {
  if (!isZRAIToolPart(part)) {
    return false;
  }

  const candidate = asZRAIToolPart(part);

  if (
    candidate.state === "input-streaming" ||
    candidate.state === "input-available" ||
    candidate.state === "approval-requested" ||
    candidate.state === "approval-responded" ||
    candidate.state === "output-error" ||
    candidate.state === "output-denied"
  ) {
    return true;
  }

  if (candidate.state !== "output-available") {
    return false;
  }

  if (candidate.output?.success === false || candidate.output?.error) {
    return true;
  }

  return !candidate.output?.artifactTrigger;
}

function getZRAIArtifactToolPart(message: ChatMessage) {
  const artifactParts = getMessageParts(message).filter((part) => {
    if (!hasZRAIArtifactTrigger(part)) {
      return false;
    }

    const candidate = asZRAIToolPart(part);

    return candidate.state === "output-available";
  });

  return (
    [...artifactParts]
      .reverse()
      .find(
        (part) =>
          asZRAIToolPart(part).output?.artifactTrigger?.kind === "lead-list"
      ) ?? artifactParts.at(-1)
  ) as
    | {
        toolCallId: string;
        output: {
          artifactTrigger: { kind: string; data?: unknown };
          summary?: string;
        };
      }
    | undefined;
}

function getArtifactTitle(kind: string, data: unknown) {
  if (!data || typeof data !== "object") {
    return artifactTitles[kind] ?? "Artifact";
  }

  if (
    kind === "lead-card" &&
    "lead" in data &&
    data.lead &&
    typeof data.lead === "object" &&
    "company_name" in data.lead &&
    typeof data.lead.company_name === "string"
  ) {
    return data.lead.company_name;
  }

  if (
    kind === "outreach-draft" &&
    "channel" in data &&
    typeof data.channel === "string"
  ) {
    return `${data.channel.toUpperCase()} Outreach Draft`;
  }

  if (
    kind === "lead-list" &&
    "niche" in data &&
    typeof data.niche === "string"
  ) {
    return `${data.niche} Lead List`;
  }

  return artifactTitles[kind] ?? "Artifact";
}

function getDefaultBoundingBox() {
  if (typeof window === "undefined") {
    return {
      top: 96,
      left: 0,
      width: 360,
      height: 520,
    };
  }

  const width = Math.min(420, Math.max(window.innerWidth * 0.3, 320));
  const height = Math.max(window.innerHeight - 144, 420);

  return {
    top: 88,
    left: Math.max(window.innerWidth - width - 32, 0),
    width,
    height,
  };
}

function getArtifactMetadataPayload(kind: string, data: unknown) {
  if (kind === "lead-list") {
    const payload =
      data && typeof data === "object" ? (data as Record<string, unknown>) : {};

    return {
      leads: Array.isArray(payload.leads) ? payload.leads : [],
      loading: false,
      sortBy: "score",
      sortOrder: "desc" as const,
      filter: "",
      ...payload,
    };
  }

  return data ?? null;
}

function mergeLeadListWithLeadCard(
  currentContent: string,
  leadCardData: unknown
) {
  let currentParsed: unknown = {};

  try {
    currentParsed = currentContent ? JSON.parse(currentContent) : {};
  } catch {
    currentParsed = {};
  }

  const currentPayload = Array.isArray(currentParsed)
    ? { leads: currentParsed }
    : currentParsed && typeof currentParsed === "object"
      ? (currentParsed as Record<string, unknown>)
      : {};
  const nextCardPayload =
    leadCardData && typeof leadCardData === "object"
      ? (leadCardData as Record<string, unknown>)
      : {};
  const nextLead =
    nextCardPayload.lead && typeof nextCardPayload.lead === "object"
      ? (nextCardPayload.lead as Record<string, unknown>)
      : null;

  if (!nextLead || typeof nextLead.id !== "string") {
    return null;
  }

  const currentLeads = Array.isArray(currentPayload.leads)
    ? (currentPayload.leads as Array<Record<string, unknown>>)
    : [];
  const currentProcessedDetails =
    currentPayload.processedDetails &&
    typeof currentPayload.processedDetails === "object"
      ? (currentPayload.processedDetails as Record<string, unknown>)
      : currentPayload.processed_details &&
          typeof currentPayload.processed_details === "object"
        ? (currentPayload.processed_details as Record<string, unknown>)
        : {};

  const mergedLeads = [
    nextLead,
    ...currentLeads.filter(
      (lead) =>
        !lead ||
        typeof lead !== "object" ||
        String(lead.id || "") !== String(nextLead.id)
    ),
  ];

  const mergedProcessedDetails = {
    ...currentProcessedDetails,
    ...(nextCardPayload.processed_details &&
    typeof nextCardPayload.processed_details === "object"
      ? { [nextLead.id]: nextCardPayload.processed_details }
      : {}),
  };

  return {
    autoAnalyzeCompletedToken:
      currentPayload.autoAnalyzeCompletedToken || null,
    autoAnalyzeEnabled: currentPayload.autoAnalyzeEnabled ?? true,
    filter: typeof currentPayload.filter === "string" ? currentPayload.filter : "",
    leads: mergedLeads,
    processedDetails: mergedProcessedDetails,
    selectedLeadId: nextLead.id,
    sortBy: typeof currentPayload.sortBy === "string" ? currentPayload.sortBy : "score",
    sortOrder: currentPayload.sortOrder === "asc" ? "asc" : "desc",
  };
}

function normalizeLeadCardArtifactTrigger(artifactTrigger: {
  data?: unknown;
  kind: string;
}) {
  if (artifactTrigger.kind !== "lead-card") {
    return artifactTrigger;
  }

  const leadListPayload = mergeLeadListWithLeadCard("", artifactTrigger.data);

  if (!leadListPayload) {
    return artifactTrigger;
  }

  return {
    data: leadListPayload,
    kind: "lead-list",
  };
}

function openZRAIArtifact({
  artifactTrigger,
  chatId,
  mutate,
  setArtifact,
  toolCallId,
}: {
  artifactTrigger: { data?: unknown; kind: string };
  chatId?: string;
  mutate: ReturnType<typeof useSWRConfig>["mutate"];
  setArtifact: ReturnType<typeof useArtifact>["setArtifact"];
  toolCallId?: string;
}) {
  const effectiveArtifactTrigger =
    normalizeLeadCardArtifactTrigger(artifactTrigger);
  const resolvedToolCallId =
    toolCallId ||
    artifactTrigger &&
    artifactTrigger.data &&
    typeof artifactTrigger.data === "object" &&
    "toolCallId" in artifactTrigger.data &&
    typeof (artifactTrigger.data as { toolCallId?: unknown }).toolCallId === "string"
      ? String((artifactTrigger.data as { toolCallId: string }).toolCallId)
      : "manual";
  const artifactId = buildStableArtifactDocumentId({
    chatId,
    kind: effectiveArtifactTrigger.kind,
    toolCallId: resolvedToolCallId,
  });

  mutate(
    `artifact-metadata-${artifactId}`,
    getArtifactMetadataPayload(
      effectiveArtifactTrigger.kind,
      effectiveArtifactTrigger.data
    ),
    {
      revalidate: false,
    }
  );

  setArtifact((currentArtifact) => ({
    ...(() => {
      if (
        currentArtifact.kind === "lead-list" &&
        artifactTrigger.kind === "lead-card"
      ) {
        const mergedLeadListPayload = mergeLeadListWithLeadCard(
          currentArtifact.content || "",
          artifactTrigger.data
        );

        if (mergedLeadListPayload) {
          if (currentArtifact.documentId) {
            mutate(
              `artifact-metadata-${currentArtifact.documentId}`,
              mergedLeadListPayload,
              {
                revalidate: false,
              }
            );
          }

          return {
            ...currentArtifact,
            content: JSON.stringify(mergedLeadListPayload),
            isVisible: true,
            status: "idle",
          };
        }
      }

      return {
        ...currentArtifact,
        documentId: artifactId,
        title: getArtifactTitle(
          effectiveArtifactTrigger.kind,
          effectiveArtifactTrigger.data
        ),
        kind: effectiveArtifactTrigger.kind as any,
        content: JSON.stringify(effectiveArtifactTrigger.data ?? null),
        isVisible: true,
        status: "idle",
        boundingBox:
          currentArtifact.boundingBox.width > 0
            ? currentArtifact.boundingBox
            : getDefaultBoundingBox(),
      };
    })(),
  }));
}

function getLatestZRAIEvent(
  events: ZRAIActivityEvent[],
  tool?: string
): ZRAIActivityEvent | null {
  const scopedEvents = tool
    ? events.filter((event) => event.tool === tool)
    : events;

  return scopedEvents.at(-1) ?? null;
}

function ActivityTimeline({
  events,
  fallbackDetail,
  fallbackTitle,
}: {
  events: ZRAIActivityEvent[];
  fallbackDetail: string;
  fallbackTitle: string;
}) {
  const latestEvent = getLatestZRAIEvent(events);
  const stages = latestEvent?.stages ?? [
    { label: "Parse intent", state: "complete" as const },
    { label: "Run tools", state: "active" as const },
    { label: "Stream results", state: "pending" as const },
  ];
  const recentEvents = events.slice(-3);

  return (
    <>
      <div className="space-y-1">
        <div className="font-medium text-foreground text-sm">
          {latestEvent?.title ?? fallbackTitle}
        </div>
        <div className="text-muted-foreground text-sm">
          {latestEvent?.detail ?? fallbackDetail}
        </div>
      </div>

      <div className="grid gap-2 text-xs md:grid-cols-3">
        {stages.map((stage) => (
          <div
            className={cn(
              "rounded-xl border px-3 py-2 transition-colors",
              stage.state === "active" &&
                "border-emerald-500/20 bg-emerald-500/8 text-emerald-300",
              stage.state === "complete" &&
                "border-sky-500/20 bg-sky-500/8 text-sky-200",
              stage.state === "pending" &&
                "border-border/60 bg-background/60 text-muted-foreground",
              stage.state === "error" &&
                "border-red-500/20 bg-red-500/8 text-red-300"
            )}
            key={`${stage.label}-${stage.state}`}
          >
            {stage.label}
          </div>
        ))}
      </div>

      {recentEvents.length > 0 && (
        <div className="space-y-2 rounded-xl border border-border/60 bg-background/50 px-3 py-3">
          <div className="font-medium text-[11px] text-muted-foreground uppercase tracking-[0.18em]">
            Latest updates
          </div>
          <div className="space-y-2">
            {recentEvents.map((event) => (
              <div
                className="flex items-start gap-2 text-sm"
                key={`${event.tool}-${event.timestamp}-${event.detail}`}
              >
                <span
                  className={cn(
                    "mt-1 inline-flex size-2 shrink-0 rounded-full",
                    event.status === "running" &&
                      "animate-pulse bg-emerald-400",
                    event.status === "complete" && "bg-sky-400",
                    event.status === "error" && "bg-red-400"
                  )}
                />
                <div className="text-muted-foreground">{event.detail}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function ZRAIArtifactBridge({
  chatId,
  isLatestMessage,
  message,
}: {
  chatId: string;
  isLatestMessage: boolean;
  message: ChatMessage;
}) {
  const handledArtifactIdRef = useRef<string | null>(null);
  const { mutate } = useSWRConfig();
  const { setArtifact } = useArtifact();

  useEffect(() => {
    if (!isLatestMessage || message.role !== "assistant") {
      return;
    }

    const toolPartWithArtifact = getZRAIArtifactToolPart(message);

    if (!toolPartWithArtifact) {
      return;
    }

    const {
      toolCallId,
      output: { artifactTrigger },
    } = toolPartWithArtifact;
    const artifactId = buildStableArtifactDocumentId({
      chatId,
      kind: artifactTrigger.kind,
      toolCallId,
    });

    if (handledArtifactIdRef.current === artifactId) {
      return;
    }

    handledArtifactIdRef.current = artifactId;
    openZRAIArtifact({
      artifactTrigger,
      chatId,
      mutate,
      setArtifact,
      toolCallId,
    });
  }, [chatId, isLatestMessage, message, mutate, setArtifact]);

  return null;
}

const PurePreviewMessage = ({
  addToolApprovalResponse,
  chatId,
  message,
  vote,
  isLoading,
  setMessages,
  regenerate,
  isReadonly,
  requiresScrollPadding: _requiresScrollPadding,
  isLatestMessage,
}: {
  addToolApprovalResponse: UseChatHelpers<ChatMessage>["addToolApprovalResponse"];
  chatId: string;
  message: ChatMessage;
  vote: Vote | undefined;
  isLoading: boolean;
  setMessages: UseChatHelpers<ChatMessage>["setMessages"];
  regenerate: UseChatHelpers<ChatMessage>["regenerate"];
  isReadonly: boolean;
  requiresScrollPadding: boolean;
  isLatestMessage: boolean;
}) => {
  const [mode, setMode] = useState<"view" | "edit">("view");
  const { mutate } = useSWRConfig();
  const { setArtifact } = useArtifact();
  const messageParts = getMessageParts(message);
  const latestUserPrompt = getTextFromMessage(message);

  const attachmentsFromMessage = messageParts.filter(
    (part) => part.type === "file"
  );
  const hasArtifactOutput =
    message.role === "assistant" && !!getZRAIArtifactToolPart(message);
  const artifactToolPart =
    message.role === "assistant" ? getZRAIArtifactToolPart(message) : undefined;
  const hasRenderableZRAITool = messageParts.some((part) =>
    shouldRenderZRAIToolPart(part)
  );
  const hasVisibleReasoning = messageParts.some(
    (part) => part.type === "reasoning" && part.text?.trim().length > 0
  );
  const hasRenderableBuiltInTool = messageParts.some(
    (part) =>
      part.type === "tool-getWeather" ||
      part.type === "tool-createDocument" ||
      part.type === "tool-updateDocument" ||
      part.type === "tool-requestSuggestions"
  );
  const shouldHideAssistantText =
    mode === "view" && message.role === "assistant" && hasArtifactOutput;
  const hasVisibleText = messageParts.some(
    (part) =>
      part.type === "text" &&
      hasRenderableText(part.text) &&
      !(shouldHideAssistantText && message.role === "assistant")
  );
  const shouldShowArtifactShell =
    mode === "view" &&
    message.role === "assistant" &&
    !!artifactToolPart &&
    !hasVisibleText &&
    !hasVisibleReasoning &&
    !hasRenderableZRAITool &&
    !hasRenderableBuiltInTool &&
    attachmentsFromMessage.length === 0;
  const shouldShowLoadingActivity =
    message.role === "assistant" &&
    isLoading &&
    !hasVisibleText &&
    !hasVisibleReasoning &&
    !hasRenderableZRAITool &&
    !hasRenderableBuiltInTool &&
    attachmentsFromMessage.length === 0;

  const { zraiActivityEvents } = useDataStream();

  if (shouldShowLoadingActivity) {
    return (
      <ThinkingMessage
        detail="Selecting tools, opening the pipeline, and waiting for the first live update."
        events={zraiActivityEvents}
        title={
          latestUserPrompt.trim().length > 0
            ? `Working on: ${latestUserPrompt}`
            : "Running your ZRAI pipeline"
        }
      />
    );
  }

  if (shouldShowArtifactShell && artifactToolPart) {
    return (
      <div
        className="group/message fade-in w-full animate-in duration-200"
        data-role={message.role}
        data-testid="message-assistant-artifact-shell"
      >
        <ZRAIArtifactBridge
          chatId={chatId}
          isLatestMessage={isLatestMessage}
          message={message}
        />
        <div className="flex items-start justify-start gap-3">
          <div className="-mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
            <SparklesIcon size={14} />
          </div>
          <div className="flex w-full max-w-2xl flex-col gap-3 rounded-2xl border border-border/70 bg-card/70 px-4 py-3 shadow-sm backdrop-blur-sm md:px-5 md:py-4">
            <div className="space-y-1">
              <div className="font-medium text-sm text-foreground">
                {getArtifactTitle(
                  artifactToolPart.output.artifactTrigger.kind,
                  artifactToolPart.output.artifactTrigger.data
                )}
              </div>
              {artifactToolPart.output.summary ? (
                <div className="text-sm text-muted-foreground">
                  {artifactToolPart.output.summary}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Artifact ready. Open it again anytime from this message.
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                className="rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
                onClick={() => {
                  openZRAIArtifact({
                    artifactTrigger: artifactToolPart.output.artifactTrigger,
                    chatId,
                    mutate,
                    setArtifact,
                    toolCallId: artifactToolPart.toolCallId,
                  });
                }}
                type="button"
              >
                {isLatestMessage ? "View canvas" : "Reopen canvas"}
              </button>
              <MessageActions
                chatId={chatId}
                isLoading={isLoading}
                key={`action-${message.id}`}
                message={message}
                setMode={setMode}
                vote={vote}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="group/message fade-in w-full animate-in duration-200"
      data-role={message.role}
      data-testid={`message-${message.role}`}
    >
      <ZRAIArtifactBridge
        chatId={chatId}
        isLatestMessage={isLatestMessage}
        message={message}
      />

      <div
        className={cn("flex w-full items-start gap-2 md:gap-3", {
          "justify-end": message.role === "user" && mode !== "edit",
          "justify-start": message.role === "assistant",
        })}
      >
        {message.role === "assistant" && (
          <div className="-mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
            <SparklesIcon size={14} />
          </div>
        )}

        <div
          className={cn("flex flex-col", {
            "gap-2 md:gap-4": hasVisibleText,
            "w-full":
              (message.role === "assistant" &&
                (hasVisibleText ||
                  messageParts.some(
                    (p) =>
                      typeof p.type === "string" && p.type.startsWith("tool-")
                  ))) ||
              mode === "edit",
            "max-w-[calc(100%-2.5rem)] sm:max-w-[min(fit-content,80%)]":
              message.role === "user" && mode !== "edit",
          })}
        >
          {attachmentsFromMessage.length > 0 && (
            <div
              className="flex flex-row justify-end gap-2"
              data-testid={"message-attachments"}
            >
              {attachmentsFromMessage.map((attachment) => (
                <PreviewAttachment
                  attachment={{
                    name: attachment.filename ?? "file",
                    contentType: attachment.mediaType,
                    url: attachment.url,
                  }}
                  key={attachment.url}
                />
              ))}
            </div>
          )}

          {messageParts.map((part, index) => {
            const { type } = part;
            const key = `message-${message.id}-part-${index}`;

            if (type === "reasoning" && part.text?.trim().length > 0) {
              return (
                <MessageReasoning
                  isLoading={isLoading}
                  key={key}
                  reasoning={part.text}
                />
              );
            }

            if (type === "text") {
              const sanitizedText = sanitizeText(part.text);

              if (!sanitizedText) {
                return null;
              }

              if (shouldHideAssistantText && message.role === "assistant") {
                return null;
              }

              if (mode === "view") {
                return (
                  <div key={key}>
                    <MessageContent
                      className={cn({
                        "wrap-break-word w-fit rounded-2xl px-3 py-2 text-right text-white":
                          message.role === "user",
                        "bg-transparent px-0 py-0 text-left":
                          message.role === "assistant",
                      })}
                      data-testid="message-content"
                      style={
                        message.role === "user"
                          ? { backgroundColor: "#006cff" }
                          : undefined
                      }
                    >
                      <Response>{sanitizedText}</Response>
                    </MessageContent>
                  </div>
                );
              }

              if (mode === "edit") {
                return (
                  <div
                    className="flex w-full flex-row items-start gap-3"
                    key={key}
                  >
                    <div className="size-8" />
                    <div className="min-w-0 flex-1">
                      <MessageEditor
                        key={message.id}
                        message={message}
                        regenerate={regenerate}
                        setMessages={setMessages}
                        setMode={setMode}
                      />
                    </div>
                  </div>
                );
              }
            }

            if (type === "tool-getWeather") {
              const { toolCallId, state } = part;
              const approvalId = (part as { approval?: { id: string } })
                .approval?.id;
              const isDenied =
                state === "output-denied" ||
                (state === "approval-responded" &&
                  (part as { approval?: { approved?: boolean } }).approval
                    ?.approved === false);
              const widthClass = "w-[min(100%,450px)]";

              if (state === "output-available") {
                return (
                  <div className={widthClass} key={toolCallId}>
                    <Weather weatherAtLocation={part.output} />
                  </div>
                );
              }

              if (isDenied) {
                return (
                  <div className={widthClass} key={toolCallId}>
                    <Tool className="w-full" defaultOpen={true}>
                      <ToolHeader
                        state="output-denied"
                        type="tool-getWeather"
                      />
                      <ToolContent>
                        <div className="px-4 py-3 text-muted-foreground text-sm">
                          Weather lookup was denied.
                        </div>
                      </ToolContent>
                    </Tool>
                  </div>
                );
              }

              if (state === "approval-responded") {
                return (
                  <div className={widthClass} key={toolCallId}>
                    <Tool className="w-full" defaultOpen={true}>
                      <ToolHeader state={state} type="tool-getWeather" />
                      <ToolContent>
                        <ToolInput input={part.input} />
                      </ToolContent>
                    </Tool>
                  </div>
                );
              }

              return (
                <div className={widthClass} key={toolCallId}>
                  <Tool className="w-full" defaultOpen={true}>
                    <ToolHeader state={state} type="tool-getWeather" />
                    <ToolContent>
                      {(state === "input-available" ||
                        state === "approval-requested") && (
                        <ToolInput input={part.input} />
                      )}
                      {state === "approval-requested" && approvalId && (
                        <div className="flex items-center justify-end gap-2 border-t px-4 py-3">
                          <button
                            className="rounded-md px-3 py-1.5 text-muted-foreground text-sm transition-colors hover:bg-muted hover:text-foreground"
                            onClick={() => {
                              addToolApprovalResponse({
                                id: approvalId,
                                approved: false,
                                reason: "User denied weather lookup",
                              });
                            }}
                            type="button"
                          >
                            Deny
                          </button>
                          <button
                            className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground text-sm transition-colors hover:bg-primary/90"
                            onClick={() => {
                              addToolApprovalResponse({
                                id: approvalId,
                                approved: true,
                              });
                            }}
                            type="button"
                          >
                            Allow
                          </button>
                        </div>
                      )}
                    </ToolContent>
                  </Tool>
                </div>
              );
            }

            if (type === "tool-createDocument") {
              const { toolCallId } = part;

              if (part.output && "error" in part.output) {
                return (
                  <div
                    className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-500 dark:bg-red-950/50"
                    key={toolCallId}
                  >
                    Error creating document: {String(part.output.error)}
                  </div>
                );
              }

              return (
                <DocumentPreview
                  isReadonly={isReadonly}
                  key={toolCallId}
                  result={part.output}
                />
              );
            }

            if (type === "tool-updateDocument") {
              const { toolCallId } = part;

              if (part.output && "error" in part.output) {
                return (
                  <div
                    className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-500 dark:bg-red-950/50"
                    key={toolCallId}
                  >
                    Error updating document: {String(part.output.error)}
                  </div>
                );
              }

              return (
                <div className="relative" key={toolCallId}>
                  <DocumentPreview
                    args={{ ...part.output, isUpdate: true }}
                    isReadonly={isReadonly}
                    result={part.output}
                  />
                </div>
              );
            }

            if (type === "tool-requestSuggestions") {
              const { toolCallId, state } = part;

              return (
                <Tool defaultOpen={true} key={toolCallId}>
                  <ToolHeader state={state} type="tool-requestSuggestions" />
                  <ToolContent>
                    {state === "input-available" && (
                      <ToolInput input={part.input} />
                    )}
                    {state === "output-available" && (
                      <ToolOutput
                        errorText={undefined}
                        output={
                          "error" in part.output ? (
                            <div className="rounded border p-2 text-red-500">
                              Error: {String(part.output.error)}
                            </div>
                          ) : (
                            <DocumentToolResult
                              isReadonly={isReadonly}
                              result={part.output}
                              type="request-suggestions"
                            />
                          )
                        }
                      />
                    )}
                  </ToolContent>
                </Tool>
              );
            }

            if (isZRAIToolPart(part)) {
              const {
                approval,
                errorText,
                input,
                output,
                state,
                toolCallId,
                type: toolType,
              } = asZRAIToolPart(part);
              const normalizedState =
                state === "approval-responded" && approval?.approved === false
                  ? "output-denied"
                  : state;
              const hasArtifactTrigger = Boolean(output?.artifactTrigger);
              const shouldRender = shouldRenderZRAIToolPart(part);
              const liveEvent = getLatestZRAIEvent(
                zraiActivityEvents,
                toolType.replace("tool-", "")
              );

              if (!shouldRender) {
                return null;
              }

              const resultLines = [
                output?.summary,
                output?.suggestion ? `Next step: ${output.suggestion}` : null,
              ].filter(Boolean) as string[];

              return (
                <Tool
                  className="w-full"
                  defaultOpen={normalizedState !== "output-available"}
                  key={toolCallId}
                >
                  <ToolHeader
                    state={normalizedState}
                    type={toolType as "tool-getWeather"}
                  />
                  <ToolContent>
                    {(normalizedState === "input-streaming" ||
                      normalizedState === "input-available") &&
                      liveEvent && (
                        <div className="border-b px-4 py-4">
                          <ActivityTimeline
                            events={zraiActivityEvents.filter(
                              (event) =>
                                event.tool === toolType.replace("tool-", "")
                            )}
                            fallbackDetail="Dispatching the tool and waiting for the next backend update."
                            fallbackTitle="Running tool"
                          />
                        </div>
                      )}

                    {(normalizedState === "input-streaming" ||
                      normalizedState === "input-available" ||
                      normalizedState === "approval-requested" ||
                      normalizedState === "approval-responded") &&
                    input !== undefined &&
                    input !== null ? (
                      <ToolInput input={input as never} />
                    ) : null}

                    {normalizedState === "approval-requested" &&
                      approval?.id && (
                        <div className="flex items-center justify-end gap-2 border-t px-4 py-3">
                          <button
                            className="rounded-md px-3 py-1.5 text-muted-foreground text-sm transition-colors hover:bg-muted hover:text-foreground"
                            onClick={() => {
                              addToolApprovalResponse({
                                id: approval.id,
                                approved: false,
                                reason: "User denied ZRAI tool execution",
                              });
                            }}
                            type="button"
                          >
                            Deny
                          </button>
                          <button
                            className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground text-sm transition-colors hover:bg-primary/90"
                            onClick={() => {
                              addToolApprovalResponse({
                                id: approval.id,
                                approved: true,
                              });
                            }}
                            type="button"
                          >
                            Allow
                          </button>
                        </div>
                      )}

                    {(normalizedState === "output-error" ||
                      normalizedState === "output-denied" ||
                      (normalizedState === "output-available" &&
                        !hasArtifactTrigger)) && (
                      <ToolOutput
                        errorText={
                          normalizedState === "output-denied"
                            ? "Execution denied."
                            : normalizedState === "output-error" ||
                                output?.success === false
                              ? errorText || output?.error || "Tool failed."
                              : undefined
                        }
                        output={
                          resultLines.length > 0 ? (
                            <div className="space-y-2 p-3 text-sm">
                              {resultLines.map((line) => (
                                <div key={line}>{line}</div>
                              ))}
                            </div>
                          ) : null
                        }
                      />
                    )}
                  </ToolContent>
                </Tool>
              );
            }

            return null;
          })}

          <div className="flex items-center gap-2">
            {artifactToolPart && (
              <button
                className="rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
                onClick={() => {
                  openZRAIArtifact({
                    artifactTrigger: artifactToolPart.output.artifactTrigger,
                    chatId,
                    mutate,
                    setArtifact,
                    toolCallId: artifactToolPart.toolCallId,
                  });
                }}
                type="button"
              >
                {isLatestMessage ? "View canvas" : "Reopen canvas"}
              </button>
            )}
            {!isReadonly && (
              <MessageActions
                chatId={chatId}
                isLoading={isLoading}
                key={`action-${message.id}`}
                message={message}
                setMode={setMode}
                vote={vote}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export const PreviewMessage = memo(
  PurePreviewMessage,
  (prevProps, nextProps) => {
    if (
      prevProps.isLoading === nextProps.isLoading &&
      prevProps.isLatestMessage === nextProps.isLatestMessage &&
      prevProps.isReadonly === nextProps.isReadonly &&
      prevProps.message.id === nextProps.message.id &&
      prevProps.requiresScrollPadding === nextProps.requiresScrollPadding &&
      equal(prevProps.message.parts, nextProps.message.parts) &&
      equal(prevProps.vote, nextProps.vote)
    ) {
      return true;
    }
    return false;
  }
);

export const ThinkingMessage = ({
  title = "ZRAI is working on your request",
  detail = "Analyzing the brief, selecting the right tools, and preparing the first live update.",
  events = [],
}: {
  title?: string;
  detail?: string;
  events?: ZRAIActivityEvent[];
}) => {
  return (
    <div
      className="group/message fade-in w-full animate-in duration-300"
      data-role="assistant"
      data-testid="message-assistant-loading"
    >
      <div className="flex items-start justify-start gap-3">
        <div className="-mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
          <div className="animate-pulse">
            <SparklesIcon size={14} />
          </div>
        </div>

        <div className="flex w-full max-w-2xl flex-col gap-3 rounded-2xl border border-border/70 bg-card/70 px-4 py-3 shadow-sm backdrop-blur-sm md:gap-4 md:px-5 md:py-4">
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 font-medium text-[11px] text-emerald-300 uppercase tracking-[0.18em]">
              Live run
            </span>
            <div className="flex items-center gap-1 text-muted-foreground text-sm">
              <span className="animate-pulse">Processing</span>
              <span className="inline-flex">
                <span className="animate-bounce [animation-delay:0ms]">.</span>
                <span className="animate-bounce [animation-delay:150ms]">
                  .
                </span>
                <span className="animate-bounce [animation-delay:300ms]">
                  .
                </span>
              </span>
            </div>
          </div>

          <ActivityTimeline
            events={events}
            fallbackDetail={detail}
            fallbackTitle={title}
          />
        </div>
      </div>
    </div>
  );
};
