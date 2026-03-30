"use client";

import { format, formatDistanceToNowStrict, isToday } from "date-fns";
import {
  Bot,
  BrainCircuit,
  Link2,
  Mail,
  MessageCircleMore,
  Phone,
  Plus,
  RefreshCcw,
  Search,
  SendHorizontal,
  Sparkles,
  UserRound,
  Webhook,
} from "lucide-react";
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import { SidebarToggle } from "@/components/sidebar-toggle";
import { WhatsAppCampaignSheet } from "@/components/whatsapp-campaign-sheet";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type {
  WhatsAppConversation,
  WhatsAppMessage,
} from "@/lib/db/schema";
import type { WhatsAppPublicConfig } from "@/lib/whatsapp/config";
import { normalizeWhatsAppAgentState } from "@/lib/whatsapp/state";

type SerializedConversation = Omit<
  WhatsAppConversation,
  "createdAt" | "updatedAt" | "lastMessageAt"
> & { createdAt: string | Date; updatedAt: string | Date; lastMessageAt: string | Date };

type SerializedMessage = Omit<WhatsAppMessage, "createdAt"> & {
  createdAt: string | Date;
};

function hydrateConversation(input: SerializedConversation): WhatsAppConversation {
  return {
    ...input,
    createdAt: new Date(input.createdAt),
    updatedAt: new Date(input.updatedAt),
    lastMessageAt: new Date(input.lastMessageAt),
    agentState: normalizeWhatsAppAgentState(input.agentState),
  };
}

function hydrateMessage(input: SerializedMessage): WhatsAppMessage {
  return { ...input, createdAt: new Date(input.createdAt) };
}

function formatThreadTime(date: Date) {
  return isToday(date) ? format(date, "p") : format(date, "MMM d");
}

function apiTone(priority: string) {
  if (priority === "high") return "border-amber-300/20 bg-amber-500/10 text-amber-100";
  if (priority === "medium") return "border-sky-300/20 bg-sky-500/10 text-sky-100";
  return "border-white/10 bg-white/5 text-slate-300";
}

async function apiRequest<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.error?.formErrors?.[0] ?? payload?.error ?? "Request failed");
  }
  return payload as T;
}

export function WhatsAppInbox({
  initialConversations,
  initialMessages,
  initialConversationId,
  currentOperatorLabel,
  publicConfig,
}: {
  initialConversations: SerializedConversation[];
  initialMessages: SerializedMessage[];
  initialConversationId: string | null;
  currentOperatorLabel: string;
  publicConfig: WhatsAppPublicConfig;
}) {
  const [conversations, setConversations] = useState(
    initialConversations.map(hydrateConversation)
  );
  const [messagesByConversation, setMessagesByConversation] = useState<
    Record<string, WhatsAppMessage[]>
  >(
    initialConversationId
      ? { [initialConversationId]: initialMessages.map(hydrateMessage) }
      : {}
  );
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(
    initialConversationId
  );
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "needs-human" | "bot" | "unread"
  >("all");
  const [draft, setDraft] = useState("");
  const [isLoadingThread, setIsLoadingThread] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDraftingAi, setIsDraftingAi] = useState(false);
  const [threadsOpen, setThreadsOpen] = useState(false);
  const [assistOpen, setAssistOpen] = useState(false);
  const [newContactName, setNewContactName] = useState("");
  const [newContactPhone, setNewContactPhone] = useState("");
  const [startInHumanMode, setStartInHumanMode] = useState(false);
  const tailRef = useRef<HTMLDivElement | null>(null);
  const deferredQuery = useDeferredValue(query);

  const selectedConversation =
    conversations.find((item) => item.id === selectedConversationId) ?? null;
  const selectedMessages = selectedConversationId
    ? messagesByConversation[selectedConversationId] ?? []
    : [];
  const selectedState = normalizeWhatsAppAgentState(selectedConversation?.agentState);
  const selectedLeadContext = selectedConversation?.leadContext ?? null;
  const selectedSummary =
    selectedState.summary ||
    (selectedLeadContext
      ? [
          `${selectedLeadContext.companyName} is linked to this thread`,
          selectedLeadContext.topIssue
            ? `top issue: ${selectedLeadContext.topIssue}`
            : null,
          selectedLeadContext.decisionMakerName
            ? `decision maker: ${selectedLeadContext.decisionMakerName}`
            : null,
        ]
          .filter(Boolean)
          .join(" | ")
      : null) ||
    "No AI summary yet. The thread summary will sharpen as replies come in.";

  const filteredConversations = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    return conversations.filter((conversation) => {
      const matchesQuery =
        !normalizedQuery ||
        conversation.contactName.toLowerCase().includes(normalizedQuery) ||
        conversation.contactPhone.toLowerCase().includes(normalizedQuery) ||
        conversation.lastMessagePreview.toLowerCase().includes(normalizedQuery);

      if (!matchesQuery) return false;
      if (statusFilter === "needs-human") {
        return (
          conversation.mode === "human" ||
          conversation.status === "attention" ||
          conversation.agentState.handoffRecommended
        );
      }
      if (statusFilter === "bot") return conversation.mode === "bot";
      if (statusFilter === "unread") return conversation.unreadCount > 0;
      return true;
    });
  }, [conversations, deferredQuery, statusFilter]);

  const unreadCount = conversations.reduce((total, item) => total + item.unreadCount, 0);
  const humanAttentionCount = conversations.filter(
    (item) =>
      item.mode === "human" ||
      item.status === "attention" ||
      item.agentState.handoffRecommended
  ).length;
  const botManagedCount = conversations.filter((item) => item.mode === "bot").length;

  useEffect(() => {
    if (!selectedConversationId && conversations.length > 0) {
      setSelectedConversationId(conversations[0].id);
    }
  }, [conversations, selectedConversationId]);

  useEffect(() => {
    if (!selectedConversationId) return;
    void loadConversation(selectedConversationId);
  }, [selectedConversationId]);

  useEffect(() => {
    if (!selectedConversationId) return;
    const interval = setInterval(() => {
      void refreshInbox(true);
      void loadConversation(selectedConversationId, { silent: true });
    }, 8000);
    return () => clearInterval(interval);
  }, [selectedConversationId]);

  useEffect(() => {
    tailRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [selectedConversationId, selectedMessages.length]);

  function upsertConversation(nextConversation: WhatsAppConversation) {
    setConversations((current) =>
      [...current.filter((item) => item.id !== nextConversation.id), nextConversation].sort(
        (a, b) => b.lastMessageAt.getTime() - a.lastMessageAt.getTime()
      )
    );
  }

  async function refreshInbox(silent = false) {
    if (!silent) setIsRefreshing(true);
    try {
      const payload = await apiRequest<{ conversations: SerializedConversation[] }>(
        "/api/whatsapp/conversations"
      );
      setConversations(
        payload.conversations
          .map(hydrateConversation)
          .sort((a, b) => b.lastMessageAt.getTime() - a.lastMessageAt.getTime())
      );
    } catch (error) {
      if (!silent) {
        toast.error(error instanceof Error ? error.message : "Failed to refresh inbox");
      }
    } finally {
      if (!silent) setIsRefreshing(false);
    }
  }

  async function loadConversation(conversationId: string, options?: { silent?: boolean }) {
    if (!options?.silent) setIsLoadingThread(true);
    try {
      const payload = await apiRequest<{
        conversation: SerializedConversation;
        messages: SerializedMessage[];
      }>(`/api/whatsapp/conversations/${conversationId}/messages`);
      const nextConversation = hydrateConversation(payload.conversation);
      upsertConversation(nextConversation);
      setMessagesByConversation((current) => ({
        ...current,
        [conversationId]: payload.messages.map(hydrateMessage),
      }));
      if (nextConversation.unreadCount > 0) {
        const readPayload = await apiRequest<{ conversation: SerializedConversation }>(
          `/api/whatsapp/conversations/${conversationId}/read`,
          { method: "POST" }
        );
        upsertConversation(hydrateConversation(readPayload.conversation));
      }
    } catch (error) {
      if (!options?.silent) {
        toast.error(error instanceof Error ? error.message : "Failed to load thread");
      }
    } finally {
      if (!options?.silent) setIsLoadingThread(false);
    }
  }

  async function handleCreateConversation() {
    if (!newContactName.trim() || !newContactPhone.trim()) {
      toast.error("Enter a contact name and phone number");
      return;
    }
    try {
      const payload = await apiRequest<{ conversation: SerializedConversation }>(
        "/api/whatsapp/conversations",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contactName: newContactName,
            contactPhone: newContactPhone,
            startInHumanMode,
          }),
        }
      );
      const nextConversation = hydrateConversation(payload.conversation);
      upsertConversation(nextConversation);
      setSelectedConversationId(nextConversation.id);
      setNewContactName("");
      setNewContactPhone("");
      setStartInHumanMode(false);
      setIsCreateOpen(false);
      setThreadsOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create conversation");
    }
  }

  async function handleSendMessage() {
    if (!selectedConversation || !draft.trim()) return;
    setIsSending(true);
    try {
      const payload = await apiRequest<{ message: SerializedMessage }>(
        `/api/whatsapp/conversations/${selectedConversation.id}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: draft }),
        }
      );
      const nextMessage = hydrateMessage(payload.message);
      setMessagesByConversation((current) => ({
        ...current,
        [selectedConversation.id]: [...(current[selectedConversation.id] ?? []), nextMessage],
      }));
      setDraft("");
      await loadConversation(selectedConversation.id, { silent: true });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to send message");
    } finally {
      setIsSending(false);
    }
  }

  async function handleToggleMode() {
    if (!selectedConversation) return;
    const nextMode = selectedConversation.mode === "bot" ? "human" : "bot";
    try {
      const payload = await apiRequest<{ conversation: SerializedConversation }>(
        `/api/whatsapp/conversations/${selectedConversation.id}/mode`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: nextMode }),
        }
      );
      upsertConversation(hydrateConversation(payload.conversation));
      await loadConversation(selectedConversation.id, { silent: true });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to switch mode");
    }
  }

  async function handleDraftAiReply() {
    if (!selectedConversation) return;
    setIsDraftingAi(true);
    try {
      const payload = await apiRequest<{
        conversation: SerializedConversation;
        suggestedReply: string;
      }>(`/api/whatsapp/conversations/${selectedConversation.id}/ai-draft`, {
        method: "POST",
      });
      upsertConversation(hydrateConversation(payload.conversation));
      setDraft(payload.suggestedReply);
      toast.success("AI draft added to composer");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to draft AI reply");
    } finally {
      setIsDraftingAi(false);
    }
  }

  const threadList = (
    <Card className="min-h-0 border-white/8 bg-[#111722] text-slate-100">
      <CardHeader className="gap-3 border-b border-white/6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base text-white">Threads</CardTitle>
            <div className="mt-1 text-xs text-slate-400">
              {conversations.length} active | {humanAttentionCount} need human | {unreadCount} unread
            </div>
          </div>
          <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" onClick={() => setIsCreateOpen((current) => !current)} size="icon-sm" variant="outline">
            <Plus className="size-4" />
          </Button>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
          <Input className="border-white/10 bg-white/5 pl-9 text-slate-100 placeholder:text-slate-500" onChange={(event) => setQuery(event.target.value)} placeholder="Search threads" value={query} />
        </div>
        <div className="flex flex-wrap gap-2">
          {[
            { key: "all", label: "All" },
            { key: "needs-human", label: "Needs human" },
            { key: "bot", label: "AI active" },
            { key: "unread", label: "Unread" },
          ].map((filter) => (
            <Button className={cn("h-8 rounded-full border-white/10 px-3 text-xs", statusFilter === filter.key ? "bg-emerald-500/15 text-emerald-100" : "bg-white/5 text-slate-300 hover:bg-white/10")} key={filter.key} onClick={() => setStatusFilter(filter.key as "all" | "needs-human" | "bot" | "unread")} size="sm" variant="outline">
              {filter.label}
            </Button>
          ))}
        </div>
        {isCreateOpen ? (
          <div className="grid gap-2 rounded-2xl border border-white/8 bg-white/5 p-3">
            <Input className="border-white/10 bg-[#0b1019] text-slate-100 placeholder:text-slate-500" onChange={(event) => setNewContactName(event.target.value)} placeholder="Clinic or contact" value={newContactName} />
            <Input className="border-white/10 bg-[#0b1019] text-slate-100 placeholder:text-slate-500" onChange={(event) => setNewContactPhone(event.target.value)} placeholder="WhatsApp number" value={newContactPhone} />
            <Button className={cn("justify-start border-white/10", startInHumanMode ? "bg-amber-500/15 text-amber-100" : "bg-white/5 text-slate-300")} onClick={() => setStartInHumanMode((current) => !current)} type="button" variant="outline">
              {startInHumanMode ? "Starts with human" : "Starts with AI"}
            </Button>
            <Button className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" onClick={() => void handleCreateConversation()}>
              Create thread
            </Button>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="min-h-0 px-0 pb-0">
        <ScrollArea className="h-[calc(100dvh-22rem)]">
          <div className="space-y-2 px-3 pb-3">
            {filteredConversations.map((conversation) => {
              const state = normalizeWhatsAppAgentState(conversation.agentState);
              return (
                <button className={cn("w-full rounded-2xl border px-3 py-3 text-left transition", selectedConversationId === conversation.id ? "border-emerald-400/20 bg-emerald-500/10" : "border-white/6 bg-white/4 hover:bg-white/8")} key={conversation.id} onClick={() => { startTransition(() => { setSelectedConversationId(conversation.id); setThreadsOpen(false); }); }} type="button">
                  <div className="flex items-start gap-3">
                    <Avatar className="size-11 border border-white/10">
                      <AvatarFallback className="bg-emerald-500/15 font-semibold text-emerald-100">{conversation.contactName.slice(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <div className="truncate font-medium text-sm text-white">{conversation.contactName}</div>
                        <Badge className={cn("border text-[10px]", apiTone(state.priority))}>{state.priority}</Badge>
                        {conversation.unreadCount > 0 ? <Badge className="ml-auto bg-emerald-500 text-slate-950">{conversation.unreadCount}</Badge> : null}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge className="border border-white/10 bg-white/5 text-[10px] text-slate-300">{state.stage.toLowerCase().replace(/_/g, " ")}</Badge>
                        <Badge className="border border-white/10 bg-white/5 text-[10px] text-slate-300">{conversation.mode === "bot" ? "AI active" : "Human active"}</Badge>
                      </div>
                      <div className="mt-2 truncate text-xs text-slate-400">{state.summary || conversation.lastMessagePreview || conversation.contactPhone}</div>
                      <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                        <span>{conversation.contactPhone}</span>
                        <span>{formatThreadTime(conversation.lastMessageAt)}</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
            {filteredConversations.length === 0 ? <div className="rounded-2xl border border-dashed border-white/10 p-5 text-center text-sm text-slate-500">No matching threads.</div> : null}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );

  const assistCard = selectedConversation ? (
    <Card className="border-white/8 bg-[#111722] text-slate-100">
      <CardHeader className="border-b border-white/6">
        <div className="flex items-center gap-2">
          <BrainCircuit className="size-4 text-emerald-300" />
          <CardTitle className="text-sm text-white">AI assist</CardTitle>
        </div>
        <div className="text-xs text-slate-400">Stage-aware sales memory and reply guidance for this thread</div>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Stage</div><div className="mt-2 text-sm text-white">{selectedState.stage.toLowerCase().replace(/_/g, " ")}</div></div>
          <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Priority</div><div className="mt-2 text-sm text-white">{selectedState.priority}</div></div>
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
          <div className="flex items-center justify-between gap-3 text-xs text-slate-400"><span>Confidence</span><span>{Math.round(selectedState.confidence * 100)}%</span></div>
          <Progress className="mt-3 bg-white/8" value={selectedState.confidence * 100} />
        </div>
        <div className="rounded-2xl border border-white/8 bg-white/5 p-3 text-sm leading-6 text-slate-200">{selectedSummary}</div>
        <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Next best move</div><div className="mt-2 text-sm leading-6 text-slate-200">{selectedState.nextBestMove || "Keep the next reply short, calm, and diagnostic."}</div></div>
        {selectedLeadContext ? (
          <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Linked clinic</div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/8 bg-[#0b1019] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Company</div>
                <div className="mt-2 text-sm text-white">{selectedLeadContext.companyName}</div>
                {selectedLeadContext.finalScore != null ? (
                  <div className="mt-1 text-xs text-slate-400">Score {selectedLeadContext.finalScore}</div>
                ) : null}
              </div>
              <div className="rounded-2xl border border-white/8 bg-[#0b1019] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Decision maker</div>
                <div className="mt-2 text-sm text-white">{selectedLeadContext.decisionMakerName || "Not verified yet"}</div>
                {selectedLeadContext.decisionMakerRole ? (
                  <div className="mt-1 text-xs text-slate-400">{selectedLeadContext.decisionMakerRole}</div>
                ) : null}
              </div>
              <div className="rounded-2xl border border-white/8 bg-[#0b1019] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Top issue</div>
                <div className="mt-2 text-sm text-white">{selectedLeadContext.topIssue || "No issue summary yet"}</div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-[#0b1019] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Best channel</div>
                <div className="mt-2 text-sm text-white">{selectedLeadContext.bestContactChannel || selectedLeadContext.recommendedChannel || "whatsapp"}</div>
                {selectedLeadContext.bestContactPhone ? (
                  <div className="mt-1 text-xs text-slate-400">{selectedLeadContext.bestContactPhone}</div>
                ) : null}
              </div>
            </div>
            {selectedLeadContext.branchPhones?.length ? (
              <div className="mt-3 rounded-2xl border border-white/8 bg-[#0b1019] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Branch phones</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedLeadContext.branchPhones.map((branch, index) => (
                    <Badge className="border border-white/10 bg-white/5 text-slate-300" key={`${branch.name || branch.phone || "branch"}-${index}`}>
                      {branch.name || "Branch"}{branch.phone ? ` | ${branch.phone}` : ""}
                    </Badge>
                  ))}
                </div>
              </div>
            ) : null}
            {selectedLeadContext.likelyContacts?.length ? (
              <div className="mt-3 rounded-2xl border border-white/8 bg-[#0b1019] p-3">
                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Likely contacts</div>
                <div className="mt-3 space-y-2">
                  {selectedLeadContext.likelyContacts.map((contact, index) => (
                    <div
                      className="rounded-2xl border border-white/8 bg-white/[0.03] p-3"
                      key={`${contact.name || contact.phone || contact.email || contact.linkedin || "contact"}-${index}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-white">
                            {contact.name || "Unlabeled contact"}
                          </div>
                          <div className="mt-1 text-xs text-slate-400">
                            {[contact.role, contact.contactType, contact.ownerScope]
                              .filter(Boolean)
                              .join(" | ") || "Public contact candidate"}
                          </div>
                        </div>
                        {typeof contact.confidence === "number" ? (
                          <Badge className="border border-white/10 bg-white/5 text-slate-300">
                            {Math.round(contact.confidence * 100)}% confidence
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-300">
                        {contact.phone ? (
                          <Badge className="border border-white/10 bg-white/5 text-slate-300">
                            <Phone className="mr-1 size-3.5" />
                            {contact.phone}
                          </Badge>
                        ) : null}
                        {contact.email ? (
                          <Badge className="border border-white/10 bg-white/5 text-slate-300">
                            <Mail className="mr-1 size-3.5" />
                            {contact.email}
                          </Badge>
                        ) : null}
                        {contact.linkedin ? (
                          <Badge className="border border-white/10 bg-white/5 text-slate-300">
                            <Link2 className="mr-1 size-3.5" />
                            LinkedIn
                          </Badge>
                        ) : null}
                        {contact.channel ? (
                          <Badge className="border border-white/10 bg-white/5 text-slate-300">
                            Channel {contact.channel}
                          </Badge>
                        ) : null}
                      </div>
                      {contact.reason || contact.source ? (
                        <div className="mt-2 text-xs leading-5 text-slate-500">
                          {[contact.reason, contact.source].filter(Boolean).join(" | ")}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
        {selectedState.handoffReason ? <div className="rounded-2xl border border-amber-300/15 bg-amber-500/10 p-3 text-sm text-amber-100">{selectedState.handoffReason}</div> : null}
      </CardContent>
    </Card>
  ) : null;

  return (
    <div className="flex h-dvh min-w-0 flex-col bg-[#060912] text-slate-100">
      <header className="border-b border-white/6 bg-[#0a101b]/95 px-3 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-[1700px] flex-col gap-3">
          <div className="flex items-center gap-3">
            <SidebarToggle />
            <Sheet onOpenChange={setThreadsOpen} open={threadsOpen}>
              <SheetTrigger asChild>
                <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10 lg:hidden" size="icon-sm" variant="outline">
                  <MessageCircleMore className="size-4" />
                </Button>
              </SheetTrigger>
              <SheetContent className="w-[88vw] border-white/8 bg-[#0b1019] p-0 text-slate-100" side="left">
                <SheetHeader className="border-b border-white/6 px-5 py-4">
                  <SheetTitle>WhatsApp threads</SheetTitle>
                </SheetHeader>
                <div className="h-[calc(100dvh-5rem)] p-4">{threadList}</div>
              </SheetContent>
            </Sheet>
            <div className="min-w-0">
              <div className="truncate font-semibold text-sm text-white">WhatsApp sales workspace</div>
              <div className="truncate text-xs text-slate-500">Memory-aware AI assist with human takeover, built for clinic sales</div>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <WhatsAppCampaignSheet />
              <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" onClick={() => void refreshInbox()} size="sm" variant="outline"><RefreshCcw className={cn("size-4", isRefreshing && "animate-spin")} />Refresh</Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="border border-white/10 bg-white/5 text-slate-300"><Phone className="size-3.5" />{publicConfig.businessNumber ?? "Business number not configured"}</Badge>
            <Badge className={cn("border", publicConfig.outboundReady ? "border-emerald-300/15 bg-emerald-500/10 text-emerald-100" : "border-amber-300/15 bg-amber-500/10 text-amber-100")}><Webhook className="size-3.5" />{publicConfig.outboundReady ? `${publicConfig.providerLabel} connected` : `${publicConfig.providerLabel} not configured`}</Badge>
            {selectedConversation?.backendConversationId ? <Badge className="border border-sky-300/15 bg-sky-500/10 text-sky-100"><BrainCircuit className="size-3.5" />Memory linked</Badge> : null}
            {selectedLeadContext?.companyName ? <Badge className="border border-white/10 bg-white/5 text-slate-300">Linked clinic {selectedLeadContext.companyName}</Badge> : null}
          </div>
        </div>
      </header>

      <div className="mx-auto grid h-full w-full max-w-[1700px] min-w-0 flex-1 gap-4 p-3 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="hidden min-h-0 lg:block">{threadList}</aside>
        <section className="min-h-0">
          <Card className="flex h-full min-h-0 border-white/8 bg-[#111722] text-slate-100">
            {selectedConversation ? (
              <>
                <CardHeader className="gap-4 border-b border-white/6 bg-[#0b1019]">
                  <div className="flex flex-wrap items-center gap-3">
                    <Avatar className="size-12 border border-white/10">
                      <AvatarFallback className="bg-emerald-500/15 font-semibold text-emerald-100">{selectedConversation.contactName.slice(0, 2).toUpperCase()}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-base text-white">{selectedConversation.contactName}</div>
                      <div className="truncate text-sm text-slate-400">{selectedConversation.contactPhone}</div>
                      {selectedLeadContext ? (
                        <div className="mt-1 truncate text-xs text-slate-500">
                          Linked to {selectedLeadContext.companyName}
                          {selectedLeadContext.finalScore != null
                            ? ` | score ${selectedLeadContext.finalScore}`
                            : ""}
                        </div>
                      ) : null}
                    </div>
                    <div className="ml-auto flex flex-wrap items-center gap-2">
                      <Sheet onOpenChange={setAssistOpen} open={assistOpen}>
                        <SheetTrigger asChild>
                          <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10 lg:hidden" size="sm" variant="outline"><BrainCircuit className="size-4" />AI</Button>
                        </SheetTrigger>
                        <SheetContent className="w-[92vw] border-white/8 bg-[#0b1019] p-4 text-slate-100" side="right">
                          <SheetHeader className="pb-4"><SheetTitle>AI assist</SheetTitle></SheetHeader>
                          <div className="h-[calc(100dvh-5rem)] overflow-auto pr-1">{assistCard}</div>
                        </SheetContent>
                      </Sheet>
                      <Badge className={cn("border", selectedConversation.mode === "bot" ? "border-emerald-300/15 bg-emerald-500/10 text-emerald-100" : "border-amber-300/15 bg-amber-500/10 text-amber-100")}>{selectedConversation.mode === "bot" ? <Bot className="size-3.5" /> : <UserRound className="size-3.5" />}{selectedConversation.mode === "bot" ? "AI active" : "Human active"}</Badge>
                      <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" onClick={() => void handleToggleMode()} variant="outline">{selectedConversation.mode === "bot" ? "Take over" : "Return to AI"}</Button>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Stage</div><div className="mt-2 text-sm text-white">{selectedState.stage.toLowerCase().replace(/_/g, " ")}</div></div>
                    <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Confidence</div><div className="mt-2 text-sm text-white">{Math.round(selectedState.confidence * 100)}%</div></div>
                    <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Priority</div><div className="mt-2 text-sm text-white">{selectedState.priority}</div></div>
                    <div className="rounded-2xl border border-white/8 bg-white/5 p-3"><div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Updated</div><div className="mt-2 text-sm text-white">{formatDistanceToNowStrict(selectedConversation.updatedAt)} ago</div></div>
                  </div>
                  {selectedLeadContext ? (
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="rounded-2xl border border-white/8 bg-[#0d1420] p-3">
                        <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Clinic signal</div>
                        <div className="mt-2 text-sm text-white">{selectedLeadContext.topIssue || "No issue summary yet"}</div>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-[#0d1420] p-3">
                        <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Decision maker</div>
                        <div className="mt-2 text-sm text-white">{selectedLeadContext.decisionMakerName || "Not confirmed yet"}</div>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-[#0d1420] p-3">
                        <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Best contact path</div>
                        <div className="mt-2 text-sm text-white">{selectedLeadContext.bestContactChannel || "whatsapp"}</div>
                        <div className="mt-1 text-xs text-slate-400">
                          {selectedLeadContext.bestContactPhone || selectedLeadContext.bestContactEmail || selectedLeadContext.bestContactLinkedin || "Using the strongest visible contact path"}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </CardHeader>
                <CardContent className="grid min-h-0 flex-1 gap-4 p-3 lg:grid-cols-[minmax(0,1fr)_340px]">
                  <div className="flex min-h-0 flex-col rounded-3xl border border-white/6 bg-[#0b1019]">
                    <div className="flex items-center justify-between gap-3 border-b border-white/6 px-4 py-3 text-xs text-slate-400">
                      <span>{isLoadingThread ? "Syncing thread..." : publicConfig.outboundReady ? `Live WhatsApp send is enabled via ${publicConfig.providerLabel}` : `Replies are stored locally until ${publicConfig.providerLabel} is configured`}</span>
                      <span>{selectedConversation.status}</span>
                    </div>
                    <ScrollArea className="min-h-0 flex-1 px-4 py-5">
                      <div className="mx-auto flex max-w-4xl flex-col gap-3">
                        {selectedMessages.length === 0 ? <div className="rounded-3xl border border-white/8 bg-white/5 px-5 py-4 text-center text-sm text-slate-500">No messages yet. Send the first message or wait for inbound WhatsApp replies.</div> : selectedMessages.map((message) => (<div className={cn("flex", message.authorType === "contact" ? "justify-start" : "justify-end")} key={message.id}><div className="max-w-[86%]"><div className={cn("rounded-[22px] px-4 py-3 shadow-sm", message.authorType === "contact" ? "bg-[#1a2232] text-slate-100 ring-1 ring-white/6" : message.authorType === "human" ? "bg-[#d8fdd2] text-slate-950 ring-1 ring-emerald-200/80" : message.authorType === "system" ? "bg-[#243045] text-slate-100 ring-1 ring-white/8" : "bg-emerald-500/15 text-emerald-50 ring-1 ring-emerald-400/20")}><div className="whitespace-pre-wrap text-sm leading-6">{message.body}</div></div><div className={cn("mt-1 flex items-center gap-2 px-1 text-[11px] text-slate-500", message.authorType === "contact" ? "justify-start" : "justify-end")}><span>{message.authorLabel}</span><span>|</span><span>{format(message.createdAt, "p")}</span><span>|</span><span>{message.status}</span></div></div></div>))}
                        <div ref={tailRef} />
                      </div>
                    </ScrollArea>
                    <Separator className="bg-white/6" />
                    <div className="bg-[#0b1019] p-4">
                      <div className="mx-auto grid max-w-4xl gap-3">
                        <Textarea className="min-h-[56px] resize-none rounded-3xl border-white/8 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 md:min-h-[68px]" disabled={isSending} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void handleSendMessage(); } }} placeholder="Type the next WhatsApp reply..." value={draft} />
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="text-xs text-slate-500">Operator: {currentOperatorLabel} | {botManagedCount} AI-managed threads</div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" disabled={isDraftingAi} onClick={() => void handleDraftAiReply()} size="sm" variant="outline"><Sparkles className="size-4" />{isDraftingAi ? "Drafting..." : "Draft AI"}</Button>
                            <Button className="bg-emerald-500 text-slate-950 hover:bg-emerald-400" disabled={isSending || !draft.trim()} onClick={() => void handleSendMessage()} size="sm"><SendHorizontal className="size-4" />Send</Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="hidden min-h-0 lg:block"><ScrollArea className="h-full pr-1">{assistCard}</ScrollArea></div>
                </CardContent>
              </>
            ) : (
              <CardContent className="grid flex-1 place-items-center">
                <div className="max-w-sm text-center">
                  <div className="mx-auto mb-4 grid size-16 place-items-center rounded-full bg-emerald-500/15 text-emerald-200"><MessageCircleMore className="size-7" /></div>
                  <div className="font-semibold text-lg text-white">No thread selected</div>
                  <div className="mt-2 text-sm text-slate-500">Open a WhatsApp thread to review the conversation and AI state.</div>
                </div>
              </CardContent>
            )}
          </Card>
        </section>
      </div>
    </div>
  );
}
