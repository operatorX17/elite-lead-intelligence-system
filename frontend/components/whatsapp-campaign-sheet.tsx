"use client";

import { formatDistanceToNowStrict } from "date-fns";
import { Check, Pause, Play, RefreshCcw, Rocket, Send, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { WhatsAppCampaignAnalytics } from "@/lib/whatsapp/campaign-analytics";
import {
  DEFAULT_WHATSAPP_CAMPAIGN_PRESET,
  WHATSAPP_CAMPAIGN_PRESETS,
  getWhatsAppCampaignPresetById,
  stringifyCampaignTemplateVariables,
  WhatsAppCampaignRecord,
  WhatsAppCampaignRecipientRecord,
} from "@/lib/whatsapp/campaigns";

async function apiRequest<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.error?.formErrors?.[0] ?? payload?.error ?? "Request failed");
  }
  return payload as T;
}

function statusTone(status: string) {
  switch (status) {
    case "completed":
    case "replied":
      return "border-emerald-300/20 bg-emerald-500/10 text-emerald-100";
    case "approved":
    case "active":
    case "sent":
      return "border-sky-300/20 bg-sky-500/10 text-sky-100";
    case "failed":
    case "rejected":
      return "border-rose-300/20 bg-rose-500/10 text-rose-100";
    case "paused":
      return "border-amber-300/20 bg-amber-500/10 text-amber-100";
    default:
      return "border-white/10 bg-white/5 text-slate-300";
  }
}

export function WhatsAppCampaignSheet() {
  const [open, setOpen] = useState(false);
  const [campaigns, setCampaigns] = useState<WhatsAppCampaignRecord[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [messageTemplate, setMessageTemplate] = useState(
    DEFAULT_WHATSAPP_CAMPAIGN_PRESET.firstMessage
  );
  const [contactsText, setContactsText] = useState("");
  const [templateName, setTemplateName] = useState(
    DEFAULT_WHATSAPP_CAMPAIGN_PRESET.templateName
  );
  const [messageStyle, setMessageStyle] = useState<"template" | "freeform">(
    DEFAULT_WHATSAPP_CAMPAIGN_PRESET.messageStyle
  );
  const [providerTemplateId, setProviderTemplateId] = useState("");
  const [providerTemplateVariablesText, setProviderTemplateVariablesText] =
    useState('{\n  "1": "{{company_name}}"\n}');
  const [dailyLimit, setDailyLimit] = useState("20");
  const [waveSize, setWaveSize] = useState("10");
  const [waveGapMinutes, setWaveGapMinutes] = useState("30");
  const [notes, setNotes] = useState(
    `Angle: ${DEFAULT_WHATSAPP_CAMPAIGN_PRESET.angle}\nUse: ${DEFAULT_WHATSAPP_CAMPAIGN_PRESET.recommendedFor}\nFollow-up: ${DEFAULT_WHATSAPP_CAMPAIGN_PRESET.suggestedFollowUp}`
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [runningCampaignId, setRunningCampaignId] = useState<string | null>(null);
  const [approvingCampaignId, setApprovingCampaignId] = useState<string | null>(null);
  const [savingRecipientId, setSavingRecipientId] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<WhatsAppCampaignAnalytics | null>(null);

  const selectedCampaign =
    campaigns.find((campaign) => campaign.id === selectedCampaignId) ?? null;
  const selectedPreset =
    getWhatsAppCampaignPresetById(templateName) ?? DEFAULT_WHATSAPP_CAMPAIGN_PRESET;
  const selectedCampaignPreset = selectedCampaign
    ? getWhatsAppCampaignPresetById(selectedCampaign.templateName)
    : null;

  const sortedCampaigns = useMemo(
    () =>
      [...campaigns].sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      ),
    [campaigns]
  );
  const selectedCampaignAnalytics = useMemo(() => {
    if (!selectedCampaign) {
      return null;
    }

    const contacted =
      selectedCampaign.counts.sent +
      selectedCampaign.counts.replied +
      selectedCampaign.counts.failed;
    const replyBase = selectedCampaign.counts.sent + selectedCampaign.counts.replied;
    const replyRate =
      replyBase > 0
        ? Math.round((selectedCampaign.counts.replied / replyBase) * 100)
        : 0;

    return {
      ready: selectedCampaign.counts.approved,
      contacted,
      replied: selectedCampaign.counts.replied,
      replyRate,
    };
  }, [selectedCampaign]);

  useEffect(() => {
    if (open) {
      void loadWorkspaceData();
    }
  }, [open]);

  useEffect(() => {
    if (!selectedCampaignId && sortedCampaigns.length > 0) {
      setSelectedCampaignId(sortedCampaigns[0].id);
    }
  }, [sortedCampaigns, selectedCampaignId]);

  async function loadCampaigns() {
    setIsLoading(true);
    try {
      const payload = await apiRequest<{ campaigns: WhatsAppCampaignRecord[] }>(
        "/api/whatsapp/campaigns"
      );
      setCampaigns(payload.campaigns);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load campaigns");
    } finally {
      setIsLoading(false);
    }
  }

  async function loadAnalytics() {
    try {
      const payload = await apiRequest<{ analytics: WhatsAppCampaignAnalytics }>(
        "/api/whatsapp/campaigns/analytics"
      );
      setAnalytics(payload.analytics);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load campaign analytics");
    }
  }

  async function loadWorkspaceData() {
    await Promise.all([loadCampaigns(), loadAnalytics()]);
  }

  async function handleCreateCampaign() {
    setIsCreating(true);
    try {
      const payload = await apiRequest<{ campaign: WhatsAppCampaignRecord }>(
        "/api/whatsapp/campaigns",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            messageStyle,
            templateName,
            providerTemplateId,
            providerTemplateVariablesText,
            messageTemplate,
            contactsText,
            dailyLimit,
            waveSize,
            waveGapMinutes,
            notes,
          }),
        }
      );
      setCampaigns((current) => [payload.campaign, ...current]);
      setSelectedCampaignId(payload.campaign.id);
      setName("");
      setContactsText("");
      setProviderTemplateId("");
      setProviderTemplateVariablesText('{\n  "1": "{{company_name}}"\n}');
      setNotes(
        `Angle: ${selectedPreset.angle}\nUse: ${selectedPreset.recommendedFor}\nFollow-up: ${selectedPreset.suggestedFollowUp}`
      );
      await loadAnalytics();
      toast.success("Campaign drafted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create campaign");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleApproveAll(campaignId: string) {
    setApprovingCampaignId(campaignId);
    try {
      const payload = await apiRequest<{ campaign: WhatsAppCampaignRecord }>(
        `/api/whatsapp/campaigns/${campaignId}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        }
      );
      setCampaigns((current) =>
        current.map((campaign) =>
          campaign.id === campaignId ? payload.campaign : campaign
        )
      );
      await loadAnalytics();
      toast.success("Approved all draft messages");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to approve campaign");
    } finally {
      setApprovingCampaignId(null);
    }
  }

  async function handleRunWave(campaignId: string) {
    setRunningCampaignId(campaignId);
    try {
      const payload = await apiRequest<{ campaign: WhatsAppCampaignRecord; sentCount: number }>(
        `/api/whatsapp/campaigns/${campaignId}/run`,
        { method: "POST" }
      );
      setCampaigns((current) =>
        current.map((campaign) =>
          campaign.id === campaignId ? payload.campaign : campaign
        )
      );
      await loadAnalytics();
      toast.success(
        payload.sentCount > 0
          ? `Sent ${payload.sentCount} messages in the next wave`
          : "No messages were sent in this wave"
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to run wave");
    } finally {
      setRunningCampaignId(null);
    }
  }

  async function updateCampaignStatus(campaignId: string, status: string) {
    try {
      const payload = await apiRequest<{ campaign: WhatsAppCampaignRecord }>(
        `/api/whatsapp/campaigns/${campaignId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        }
      );
      setCampaigns((current) =>
        current.map((campaign) =>
          campaign.id === campaignId ? payload.campaign : campaign
        )
      );
      await loadAnalytics();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update campaign");
    }
  }

  async function updateRecipient(
    campaignId: string,
    recipient: WhatsAppCampaignRecipientRecord,
    patch: Partial<WhatsAppCampaignRecipientRecord>
  ) {
    setSavingRecipientId(recipient.id);
    try {
      const payload = await apiRequest<{ recipient: WhatsAppCampaignRecipientRecord }>(
        `/api/whatsapp/campaigns/${campaignId}/recipients/${recipient.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        }
      );
      setCampaigns((current) =>
        current.map((campaign) =>
          campaign.id === campaignId
            ? {
                ...campaign,
                recipients: campaign.recipients.map((currentRecipient) =>
                  currentRecipient.id === recipient.id
                    ? payload.recipient
                    : currentRecipient
                ),
                counts: {
                  ...campaign.counts,
                },
              }
            : campaign
        )
      );
      await loadCampaigns();
      await loadAnalytics();
      toast.success("Recipient updated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update recipient");
    } finally {
      setSavingRecipientId(null);
    }
  }

  function applyPreset(presetId: string) {
    const preset = getWhatsAppCampaignPresetById(presetId);
    if (!preset) {
      return;
    }

    setTemplateName(preset.templateName);
    setMessageStyle(preset.messageStyle);
    setMessageTemplate(preset.firstMessage);
    setProviderTemplateId("");
    setProviderTemplateVariablesText('{\n  "1": "{{company_name}}"\n}');
    setNotes(
      `Angle: ${preset.angle}\nUse: ${preset.recommendedFor}\nFollow-up: ${preset.suggestedFollowUp}`
    );
    if (!name.trim()) {
      setName(preset.label);
    }
  }

  return (
    <Sheet onOpenChange={setOpen} open={open}>
      <SheetTrigger asChild>
        <Button className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" size="sm" variant="outline">
          <Send className="size-4" />
          Campaigns
        </Button>
      </SheetTrigger>
      <SheetContent className="w-[96vw] border-white/8 bg-[#0b1019] p-0 text-slate-100 sm:max-w-[1280px]" side="right">
        <SheetHeader className="border-b border-white/6 px-6 py-4">
          <SheetTitle>WhatsApp outbound campaigns</SheetTitle>
        </SheetHeader>
        <div className="grid h-[calc(100dvh-5rem)] gap-4 p-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="grid min-h-0 gap-4">
            <Card className="border-white/8 bg-[#111722] text-slate-100">
              <CardHeader className="border-b border-white/6">
                <CardTitle className="text-sm text-white">New campaign</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 pt-4">
                <div className="grid gap-2">
                  <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">
                    Built-in angles
                  </div>
                  <div className="grid gap-2">
                    {WHATSAPP_CAMPAIGN_PRESETS.map((preset) => (
                      <button
                        className={cn(
                          "rounded-2xl border p-3 text-left transition",
                          selectedPreset.id === preset.id
                            ? "border-emerald-400/20 bg-emerald-500/10"
                            : "border-white/8 bg-white/5 hover:bg-white/8"
                        )}
                        key={preset.id}
                        onClick={() => applyPreset(preset.id)}
                        type="button"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium text-sm text-white">{preset.label}</div>
                          <Badge className="border border-white/10 bg-white/5 text-[10px] text-slate-300">
                            {preset.recommendedFor}
                          </Badge>
                        </div>
                        <div className="mt-2 text-xs leading-5 text-slate-400">
                          {preset.description}
                        </div>
                        <div className="mt-2 text-[11px] leading-5 text-slate-500">
                          Follow-up: {preset.suggestedFollowUp}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
                <Input
                  className="border-white/10 bg-white/5 text-slate-100"
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Campaign name"
                  value={name}
                />
                <div className="flex gap-2">
                  {(["template", "freeform"] as const).map((style) => (
                    <Button
                      className={cn(
                        "flex-1 border-white/10",
                        messageStyle === style
                          ? "bg-emerald-500/15 text-emerald-100"
                          : "bg-white/5 text-slate-300"
                      )}
                      key={style}
                      onClick={() => setMessageStyle(style)}
                      variant="outline"
                    >
                      {style === "template" ? "Template" : "Dirty / freeform"}
                    </Button>
                  ))}
                </div>
                <Input
                  className="border-white/10 bg-white/5 text-slate-100"
                  onChange={(event) => setTemplateName(event.target.value)}
                  placeholder="Template label"
                  value={templateName}
                />
                <div className="rounded-2xl border border-emerald-400/15 bg-emerald-500/10 p-3">
                  <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-emerald-200/70">
                    Active angle
                  </div>
                  <div className="mt-2 font-medium text-sm text-emerald-50">
                    {selectedPreset.label}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-emerald-100/75">
                    {selectedPreset.angle}
                  </div>
                </div>
                <Textarea
                  className="min-h-[160px] border-white/10 bg-white/5 text-slate-100"
                  onChange={(event) => setMessageTemplate(event.target.value)}
                  placeholder="First message. Supports {{first_name}}, {{company_name}}, {{top_issue}}, {{city}}"
                  value={messageTemplate}
                />
                {messageStyle === "template" ? (
                  <div className="grid gap-2 rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                    <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">
                      Twilio template delivery
                    </div>
                    <Input
                      className="border-white/10 bg-white/5 text-slate-100"
                      onChange={(event) => setProviderTemplateId(event.target.value)}
                      placeholder="Twilio ContentSid / HX..."
                      value={providerTemplateId}
                    />
                    <Textarea
                      className="min-h-[92px] border-white/10 bg-white/5 text-slate-100"
                      onChange={(event) => setProviderTemplateVariablesText(event.target.value)}
                      placeholder='{"1":"{{company_name}}","2":"{{first_name}}"}'
                      value={providerTemplateVariablesText}
                    />
                    <div className="text-[11px] leading-5 text-slate-500">
                      If ContentSid is set, Twilio will send the approved template and fill these variables per recipient. The message body above stays as your operator preview and fallback copy.
                    </div>
                  </div>
                ) : null}
                <Textarea
                  className="min-h-[160px] border-white/10 bg-white/5 text-slate-100"
                  onChange={(event) => setContactsText(event.target.value)}
                  placeholder={"Contacts: one per line\nName | Phone | Company\nClinic owner | +9198xxxxxx | iSkin"}
                  value={contactsText}
                />
                <div className="grid gap-2 sm:grid-cols-3">
                  <Input
                    className="border-white/10 bg-white/5 text-slate-100"
                    onChange={(event) => setDailyLimit(event.target.value)}
                    placeholder="Daily limit"
                    value={dailyLimit}
                  />
                  <Input
                    className="border-white/10 bg-white/5 text-slate-100"
                    onChange={(event) => setWaveSize(event.target.value)}
                    placeholder="Wave size"
                    value={waveSize}
                  />
                  <Input
                    className="border-white/10 bg-white/5 text-slate-100"
                    onChange={(event) => setWaveGapMinutes(event.target.value)}
                    placeholder="Gap (minutes)"
                    value={waveGapMinutes}
                  />
                </div>
                <Textarea
                  className="min-h-[72px] border-white/10 bg-white/5 text-slate-100"
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Internal notes"
                  value={notes}
                />
                <Button
                  className="bg-emerald-500 text-slate-950 hover:bg-emerald-400"
                  disabled={isCreating}
                  onClick={() => void handleCreateCampaign()}
                >
                  {isCreating ? "Creating..." : "Create campaign"}
                </Button>
              </CardContent>
            </Card>

            <Card className="border-white/8 bg-[#111722] text-slate-100">
              <CardHeader className="border-b border-white/6">
                <CardTitle className="text-sm text-white">Operator bar</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 pt-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                      Active campaigns
                    </div>
                    <div className="mt-2 text-xl font-semibold text-white">
                      {analytics?.overview.activeCampaigns ?? 0}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {analytics?.overview.campaigns ?? 0} total campaigns
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                      Ready to send
                    </div>
                    <div className="mt-2 text-xl font-semibold text-white">
                      {analytics?.overview.readyRecipients ?? 0}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      approved recipients
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                      Reply rate
                    </div>
                    <div className="mt-2 text-xl font-semibold text-white">
                      {analytics?.overview.replyRate ?? 0}%
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {analytics?.overview.repliedRecipients ?? 0} replied /{" "}
                      {analytics?.overview.contactedRecipients ?? 0} contacted
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                      Hot threads
                    </div>
                    <div className="mt-2 text-xl font-semibold text-white">
                      {analytics?.overview.hotThreads ?? 0}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {analytics?.overview.demoReadyThreads ?? 0} demo-ready
                    </div>
                  </div>
                </div>
                {analytics?.hotThreads?.length ? (
                  <div className="grid gap-2">
                    <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">
                      Closest to demo
                    </div>
                    {analytics.hotThreads.slice(0, 4).map((thread) => (
                      <div
                        className="rounded-2xl border border-white/8 bg-white/5 p-3"
                        key={thread.conversationId}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="font-medium text-sm text-white">
                            {thread.companyName ?? thread.contactName}
                          </div>
                          <Badge className="border border-white/10 bg-white/5 text-[10px] text-slate-300">
                            {thread.stage}
                          </Badge>
                          <Badge className={cn("border text-[10px]", statusTone(thread.priority))}>
                            {thread.priority}
                          </Badge>
                        </div>
                        <div className="mt-2 text-xs leading-5 text-slate-400">
                          {thread.summary ?? thread.contactPhone}
                        </div>
                        {thread.nextBestMove ? (
                          <div className="mt-1 text-[11px] leading-5 text-slate-500">
                            Next: {thread.nextBestMove}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-slate-500">
                    No hot reply threads yet. Once clinics engage, the operator bar will surface the threads closest to demo and founder handoff.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="min-h-0 border-white/8 bg-[#111722] text-slate-100">
              <CardHeader className="border-b border-white/6">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="text-sm text-white">Campaigns</CardTitle>
                  <Button
                    className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                    onClick={() => void loadWorkspaceData()}
                    size="sm"
                    variant="outline"
                  >
                    <RefreshCcw className={cn("size-4", isLoading && "animate-spin")} />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="min-h-0 px-0 pb-0">
                <ScrollArea className="h-[360px]">
                  <div className="space-y-2 px-3 pb-3 pt-3">
                    {sortedCampaigns.map((campaign) => (
                      <button
                        className={cn(
                          "w-full rounded-2xl border px-3 py-3 text-left",
                          selectedCampaignId === campaign.id
                            ? "border-emerald-400/20 bg-emerald-500/10"
                            : "border-white/8 bg-white/5"
                        )}
                        key={campaign.id}
                        onClick={() => setSelectedCampaignId(campaign.id)}
                        type="button"
                      >
                        <div className="flex items-center gap-2">
                          <div className="truncate font-medium text-sm text-white">
                            {campaign.name}
                          </div>
                          <Badge className={cn("border text-[10px]", statusTone(campaign.status))}>
                            {campaign.status}
                          </Badge>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          {campaign.counts.total} total | {campaign.counts.approved} approved |{" "}
                          {campaign.counts.sent} sent | {campaign.counts.replied} replied
                        </div>
                        <div className="mt-2 text-[11px] text-slate-500">
                          {campaign.nextWaveAt
                            ? `Next wave ${formatDistanceToNowStrict(new Date(campaign.nextWaveAt))} from now`
                            : "No wave scheduled"}
                        </div>
                      </button>
                    ))}
                    {sortedCampaigns.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-white/10 p-5 text-center text-sm text-slate-500">
                        No campaigns yet.
                      </div>
                    ) : null}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          <Card className="min-h-0 border-white/8 bg-[#111722] text-slate-100">
            {selectedCampaign ? (
              <>
                <CardHeader className="border-b border-white/6">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-base text-white">{selectedCampaign.name}</CardTitle>
                    <Badge className={cn("border", statusTone(selectedCampaign.status))}>
                      {selectedCampaign.status}
                    </Badge>
                    <Badge className="border border-white/10 bg-white/5 text-slate-300">
                      {selectedCampaign.messageStyle}
                    </Badge>
                    {selectedCampaign.providerTemplateId ? (
                      <Badge className="border border-violet-300/15 bg-violet-500/10 text-violet-100">
                        Twilio template
                      </Badge>
                    ) : null}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                    <span>{selectedCampaign.dailyLimit}/day</span>
                    <span>|</span>
                    <span>{selectedCampaign.waveSize}/wave</span>
                    <span>|</span>
                    <span>{selectedCampaign.waveGapMinutes} min gap</span>
                    <span>|</span>
                    <span>{selectedCampaign.counts.replied} replies</span>
                  </div>
                  {selectedCampaignPreset ? (
                    <div className="mt-3 rounded-2xl border border-emerald-400/15 bg-emerald-500/10 p-3">
                      <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-emerald-200/70">
                        Campaign angle
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <div className="font-medium text-sm text-emerald-50">
                          {selectedCampaignPreset.label}
                        </div>
                        <Badge className="border border-emerald-200/10 bg-emerald-950/30 text-[10px] text-emerald-100">
                          {selectedCampaignPreset.recommendedFor}
                        </Badge>
                      </div>
                      <div className="mt-2 text-xs leading-5 text-emerald-100/75">
                        {selectedCampaignPreset.description}
                      </div>
                      <div className="mt-2 text-[11px] leading-5 text-emerald-100/65">
                        Follow-up: {selectedCampaignPreset.suggestedFollowUp}
                      </div>
                    </div>
                  ) : null}
                  {selectedCampaignAnalytics ? (
                    <div className="mt-4 grid gap-3 sm:grid-cols-4">
                      <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                          Ready
                        </div>
                        <div className="mt-2 text-xl font-semibold text-white">
                          {selectedCampaignAnalytics.ready}
                        </div>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                          Contacted
                        </div>
                        <div className="mt-2 text-xl font-semibold text-white">
                          {selectedCampaignAnalytics.contacted}
                        </div>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                          Replied
                        </div>
                        <div className="mt-2 text-xl font-semibold text-white">
                          {selectedCampaignAnalytics.replied}
                        </div>
                      </div>
                      <div className="rounded-2xl border border-white/8 bg-white/5 p-3">
                        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                          Reply rate
                        </div>
                        <div className="mt-2 text-xl font-semibold text-white">
                          {selectedCampaignAnalytics.replyRate}%
                        </div>
                      </div>
                    </div>
                  ) : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      className="bg-emerald-500 text-slate-950 hover:bg-emerald-400"
                      disabled={approvingCampaignId === selectedCampaign.id}
                      onClick={() => void handleApproveAll(selectedCampaign.id)}
                      size="sm"
                    >
                      <ShieldCheck className="size-4" />
                      {approvingCampaignId === selectedCampaign.id ? "Approving..." : "Approve all drafts"}
                    </Button>
                    <Button
                      className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                      disabled={runningCampaignId === selectedCampaign.id}
                      onClick={() => void handleRunWave(selectedCampaign.id)}
                      size="sm"
                      variant="outline"
                    >
                      <Rocket className="size-4" />
                      {runningCampaignId === selectedCampaign.id ? "Sending..." : "Send next wave"}
                    </Button>
                    <Button
                      className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                      onClick={() =>
                        void updateCampaignStatus(
                          selectedCampaign.id,
                          selectedCampaign.status === "paused" ? "active" : "paused"
                        )
                      }
                      size="sm"
                      variant="outline"
                    >
                      {selectedCampaign.status === "paused" ? (
                        <>
                          <Play className="size-4" />
                          Resume
                        </>
                      ) : (
                        <>
                          <Pause className="size-4" />
                          Pause
                        </>
                      )}
                    </Button>
                  </div>
                  <div className="mt-4 rounded-2xl border border-white/8 bg-white/5 p-3 text-sm leading-6 text-slate-200">
                    {selectedCampaign.messageTemplate}
                  </div>
                  {selectedCampaign.providerTemplateId ? (
                    <div className="mt-3 rounded-2xl border border-violet-300/15 bg-violet-500/10 p-3">
                      <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-violet-200/70">
                        Provider template
                      </div>
                      <div className="mt-2 font-mono text-xs text-violet-50">
                        {selectedCampaign.providerTemplateId}
                      </div>
                      {selectedCampaign.providerTemplateVariables ? (
                        <pre className="mt-3 overflow-x-auto rounded-xl bg-[#0b1019] p-3 text-[11px] leading-5 text-violet-100/80">
                          {stringifyCampaignTemplateVariables(
                            selectedCampaign.providerTemplateVariables
                          )}
                        </pre>
                      ) : null}
                    </div>
                  ) : null}
                </CardHeader>
                <CardContent className="min-h-0 p-0">
                  <ScrollArea className="h-[calc(100dvh-14rem)]">
                    <div className="space-y-3 p-4">
                      {selectedCampaign.recipients.map((recipient) => (
                        <div
                          className="rounded-2xl border border-white/8 bg-[#0d1420] p-4"
                          key={recipient.id}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="font-medium text-white">{recipient.contactName}</div>
                            <Badge className={cn("border", statusTone(recipient.status))}>
                              {recipient.status}
                            </Badge>
                            <div className="text-xs text-slate-400">{recipient.contactPhone}</div>
                            {recipient.companyName ? (
                              <Badge className="border border-white/10 bg-white/5 text-slate-300">
                                {recipient.companyName}
                              </Badge>
                            ) : null}
                          </div>
                          <Textarea
                            className="mt-3 min-h-[88px] border-white/10 bg-white/5 text-slate-100"
                            defaultValue={recipient.messageBody}
                            onBlur={(event) => {
                              if (event.target.value.trim() !== recipient.messageBody.trim()) {
                                void updateRecipient(selectedCampaign.id, recipient, {
                                  messageBody: event.target.value,
                                });
                              }
                            }}
                          />
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button
                              className="bg-emerald-500 text-slate-950 hover:bg-emerald-400"
                              disabled={savingRecipientId === recipient.id}
                              onClick={() =>
                                void updateRecipient(selectedCampaign.id, recipient, {
                                  status: "approved",
                                })
                              }
                              size="sm"
                            >
                              <Check className="size-4" />
                              Approve
                            </Button>
                            <Button
                              className="border-white/10 bg-white/5 text-slate-100 hover:bg-white/10"
                              disabled={savingRecipientId === recipient.id}
                              onClick={() =>
                                void updateRecipient(selectedCampaign.id, recipient, {
                                  status: "rejected",
                                })
                              }
                              size="sm"
                              variant="outline"
                            >
                              Reject
                            </Button>
                          </div>
                          {(recipient.sentAt || recipient.repliedAt || recipient.errorText) ? (
                            <div className="mt-3 text-xs leading-5 text-slate-500">
                              {recipient.sentAt
                                ? `Sent ${formatDistanceToNowStrict(new Date(recipient.sentAt))} ago`
                                : null}
                              {recipient.repliedAt
                                ? ` | Replied ${formatDistanceToNowStrict(new Date(recipient.repliedAt))} ago`
                                : null}
                              {recipient.errorText ? ` | Error: ${recipient.errorText}` : null}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </>
            ) : (
              <CardContent className="grid h-full place-items-center">
                <div className="text-center text-sm text-slate-500">
                  Pick a campaign to review approvals and run waves.
                </div>
              </CardContent>
            )}
          </Card>
        </div>
      </SheetContent>
    </Sheet>
  );
}

