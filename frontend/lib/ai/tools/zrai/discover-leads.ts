/**
 * ZRAI Lead OS - Discover Leads Tool
 *
 * Discovers leads based on niche and geo via the ZRAI Discovery Agent.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { MAX_DISCOVERY_LIMIT, ZRAI_BACKEND_URL } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

const FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v1/search";

function normalizeClinicDiscoveryNiche(niche: string): string {
  const raw = String(niche || "").trim();
  const lowered = raw.toLowerCase();

  if (
    /(skin|aesthetic|derma|dermatology|cosmetic|medspa|beauty)/i.test(lowered)
  ) {
    return "premium skin and aesthetic clinics";
  }

  if (/(dental|dentist|orthodontic|oral)/i.test(lowered)) {
    return "premium dental clinics";
  }

  if (/(hair|transplant|trichology)/i.test(lowered)) {
    return "premium hair clinics";
  }

  return raw;
}

function buildClinicDiscoveryFallbacks(niche: string): string[] {
  const raw = String(niche || "").trim();
  const normalized = normalizeClinicDiscoveryNiche(raw);
  const candidates = [
    raw,
    normalized,
    "premium skin and aesthetic clinics",
    "skin clinics",
    "aesthetic clinics",
    "dermatology clinics",
    "cosmetic clinics",
  ];

  const deduped: string[] = [];
  const seen = new Set<string>();
  for (const candidate of candidates) {
    const value = String(candidate || "").trim();
    const key = value.toLowerCase();
    if (!value || seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(value);
  }
  return deduped;
}

function buildClinicFirecrawlQueries(niche: string, geo: string): string[] {
  const normalized = normalizeClinicDiscoveryNiche(niche).toLowerCase();

  if (/(skin|aesthetic|derma|dermatology|cosmetic|medspa|beauty)/i.test(normalized)) {
    return [
      `site:.in ${geo} "skin clinic" "book appointment"`,
      `${geo} premium dermatology clinic`,
      `${geo} "aesthetic clinic" whatsapp`,
      `${geo} "cosmetic clinic" consultation`,
    ];
  }

  if (/(dental|dentist|orthodontic|oral)/i.test(normalized)) {
    return [
      `site:.in ${geo} "dental clinic" "book appointment"`,
      `${geo} premium dental clinic`,
      `${geo} cosmetic dentistry clinic`,
    ];
  }

  if (/(hair|transplant|trichology)/i.test(normalized)) {
    return [
      `site:.in ${geo} "hair transplant clinic" consultation`,
      `${geo} premium hair clinic`,
      `${geo} trichology clinic whatsapp`,
    ];
  }

  return [`${geo} ${niche}`];
}

function extractDomain(rawUrl: string): string {
  try {
    return new URL(rawUrl).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "";
  }
}

const SEO_BRAND_BLOCKLIST = [
  "best ",
  "top ",
  "#1",
  "near me",
  "directory",
  "list of",
  "clinic in ",
  "hospital in ",
  "dermatologist in ",
  "skin clinic in ",
  "hair clinic in ",
  "cosmetic clinic in ",
  "multispecialty hospital in ",
];

const SEO_GEO_HINTS = [
  "bangalore",
  "bengaluru",
  "jayanagar",
  "indiranagar",
  "whitefield",
  "koramangala",
  "hsr",
  "marathahalli",
];

function normalizeBrandToken(value: string): string {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function looksLikeSeoBrandNoise(value: string): boolean {
  const lowered = String(value || "").trim().toLowerCase();
  if (!lowered) {
    return true;
  }
  return SEO_BRAND_BLOCKLIST.some((token) => lowered.includes(token));
}

function inferCompanyName(rawUrl: string, title: string): string {
  const domain = extractDomain(rawUrl);
  const fallback = (domain.split(".")[0]?.replace(/[-_]+/g, " ").trim() || domain)
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

  const rawTitle = String(title || "").trim();
  if (!rawTitle) {
    return fallback;
  }

  const domainStem = domain.split(".")[0] || "";
  const domainToken = normalizeBrandToken(domainStem);
  const rawSegments: string[] = [];

  for (const segment of rawTitle.split("|")) {
    const cleaned = segment.trim().replace(/^[-:,\s]+|[-:,\s]+$/g, "");
    if (cleaned) {
      rawSegments.push(cleaned);
    }
    for (const subsegment of cleaned.split(/\s[-–—]\s/)) {
      const normalized = subsegment.trim().replace(/^[-:,\s]+|[-:,\s]+$/g, "");
      if (normalized) {
        rawSegments.push(normalized);
      }
    }
    if (cleaned.includes(":")) {
      const prefix = cleaned.split(":", 1)[0]?.trim().replace(/^[-:,\s]+|[-:,\s]+$/g, "");
      if (prefix) {
        rawSegments.push(prefix);
      }
    }
  }

  let bestSegment = "";
  let bestScore = Number.NEGATIVE_INFINITY;

  for (const segment of rawSegments) {
    const lowered = segment.toLowerCase();
    const normalized = normalizeBrandToken(segment);
    let score = 0;

    if (looksLikeSeoBrandNoise(segment)) {
      score -= 6;
    }
    if (SEO_GEO_HINTS.some((hint) => lowered.includes(hint))) {
      score -= 3;
    }
    if (segment.split(/\s+/).length > 8) {
      score -= 2;
    }
    if (segment.length >= 3 && segment.length <= 60) {
      score += 1;
    }
    if (segment.split(/\s+/).length <= 6) {
      score += 1;
    }
    if (["clinic", "clinics", "aesthetic", "skin", "hair", "care", "laser"].some((token) => lowered.includes(token))) {
      score += 1;
    }
    if (domainToken && normalized.includes(domainToken)) {
      score += 6;
    }
    if (lowered.includes("example.com")) {
      score -= 6;
    }

    if (score > bestScore) {
      bestSegment = segment;
      bestScore = score;
    }
  }

  return bestSegment && bestScore >= 2 ? bestSegment : fallback;
}

function isBlockedClinicSearchResult(rawUrl: string, title: string): boolean {
  const domain = extractDomain(rawUrl);
  const loweredTitle = String(title || "").toLowerCase();

  if (!domain) {
    return true;
  }

  if (
    [
      "instagram.com",
      "facebook.com",
      "m.facebook.com",
      "linkedin.com",
      "www.linkedin.com",
      "youtube.com",
      "x.com",
      "twitter.com",
    ].includes(domain)
  ) {
    return true;
  }

  if (
    loweredTitle.includes("top 10") ||
    loweredTitle.includes("list of best") ||
    loweredTitle.includes("near me")
  ) {
    return true;
  }

  return false;
}

async function discoverClinicLeadsWithFirecrawl({
  geo,
  limit,
  niche,
}: {
  geo: string;
  limit: number;
  niche: string;
}) {
  const apiKey = process.env.FIRECRAWL_API_KEY || process.env.FIRE_CRAWL_API_KEY;
  if (!apiKey) {
    return [];
  }

  const queries = buildClinicFirecrawlQueries(niche, geo);
  const leads: Array<Record<string, unknown>> = [];
  const seenDomains = new Set<string>();

  for (const query of queries) {
    const response = await fetch(FIRECRAWL_SEARCH_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        limit: Math.min(Math.max(limit, 8), 10),
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      continue;
    }

    const payload = (await response.json()) as {
      data?: Array<{ description?: string; title?: string; url?: string }>;
    };

    for (const item of payload.data || []) {
      const website = String(item.url || "").trim();
      const domain = extractDomain(website);
      const title = String(item.title || "").trim();

      if (!website || !domain || seenDomains.has(domain)) {
        continue;
      }
      if (isBlockedClinicSearchResult(website, title)) {
        continue;
      }

      seenDomains.add(domain);
      leads.push({
        id: `fc-${domain}`,
        company_name: inferCompanyName(website, title),
        domain,
        website,
        niche,
        geo,
        status: "discovered",
        source: "firecrawl-search",
        snippet: item.description || "",
      });

      if (leads.length >= limit) {
        return leads;
      }
    }
  }

  return leads;
}

function isBudgetConstraint(detail: string | undefined): boolean {
  const message = String(detail || "").toLowerCase();
  return (
    message.includes("remaining usage") ||
    message.includes("billing/subscription") ||
    message.includes("budget exceeded") ||
    message.includes("paid plan")
  );
}

export const discoverLeads = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Discover new leads based on niche and geographic location. 
Use this tool when the user wants to find new prospects or leads in a specific industry or region.
Returns a list of discovered leads with basic company information.

NOTE: Discovery can take 2-5 minutes as it scrapes real data from Google Maps. 
Only set mock=true when the user explicitly asks for mock, fake, or test data.`,
    inputSchema: z.object({
      niche: z
        .string()
        .describe(
          'The industry niche to search for (e.g., "saas", "ecommerce", "agency", "fintech")'
        ),
      geo: z
        .string()
        .describe(
          'Geographic location to search. Preserve exact city names when the user gives one (e.g., "Bangalore", "Austin, Texas", "London"). Only use country or region codes like "us" or "uk" when the user asked for a country or region. Never omit this field.'
        ),
      limit: z
        .number()
        .min(1)
        .max(MAX_DISCOVERY_LIMIT)
        .optional()
        .default(20)
        .describe("Maximum number of leads to discover (1-200)"),
      mock: z
        .boolean()
        .optional()
        .default(false)
        .describe(
          "Use mock data for instant results only when the user explicitly requests test data"
        ),
    }),
    execute: async ({ niche, geo, limit, mock }) => {
      const normalizedNiche = normalizeClinicDiscoveryNiche(niche);
      console.log(
        `[discoverLeads] Starting discovery: niche=${niche}, normalizedNiche=${normalizedNiche}, geo=${geo}, limit=${limit}, mock=${mock}`
      );
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "discoverLeads",
        title: "Running discovery agent",
        stages: ["Parse request", "Fetch live leads", "Prepare lead artifact"],
      });
      progress.start(`Interpreting ${niche} lead discovery for ${geo}.`, {
        geo,
        limit,
        mock,
        niche,
      });

      try {
        // Call backend directly (bypassing frontend API route for reliability)
        const backendUrl = ZRAI_BACKEND_URL || "http://localhost:8001";
        const url = `${backendUrl}/api/v1/discover`;
        const clinicFallbackNiches = buildClinicDiscoveryFallbacks(niche);

        console.log(`[discoverLeads] Calling backend: ${url}`);
        progress.advance(
          1,
          mock
            ? "Using mock discovery mode for a fast dry run."
            : "Calling the live discovery backend and waiting for lead results."
        );

        const callDiscovery = async (requestedNiche: string) =>
          fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ niche: requestedNiche, geo, limit, mock }),
          });

        let response = await callDiscovery(normalizedNiche || niche);

        console.log(`[discoverLeads] Response status: ${response.status}`);

        if (!response.ok) {
          const errorText = await response.text();
          console.error("[discoverLeads] Backend error:", errorText);
          let detail: string | undefined;

          try {
            const parsed = JSON.parse(errorText) as { detail?: string };
            detail = parsed.detail;
          } catch {
            detail = errorText;
          }

          if (isBudgetConstraint(detail) && normalizedNiche !== niche) {
            console.warn(
              `[discoverLeads] Retrying discovery with normalized clinic niche after budget-style failure: ${normalizedNiche}`
            );
            response = await callDiscovery(normalizedNiche);
            if (response.ok) {
              const retryData = await response.json();
              progress.advance(
                2,
                `Normalized the clinic query and prepared ${retryData.count} discovered lead${retryData.count === 1 ? "" : "s"} for review.`,
                { discovered: retryData.count, retried: true }
              );
              progress.success(
                `Discovery complete. Prepared ${retryData.count} lead${retryData.count === 1 ? "" : "s"} for review.`,
                { discovered: retryData.count, runId: retryData.run_id ?? null }
              );
              return {
                success: true,
                leads: retryData.leads,
                count: retryData.count,
                run_id: retryData.run_id,
                summary:
                  retryData.count > 0
                    ? `Discovered ${retryData.count} real leads in the ${normalizedNiche} niche (${geo}) using the live discovery backend.`
                    : `Discovery completed for ${normalizedNiche} in ${geo}, but no verified leads matched the current filters yet.`,
                artifactTrigger: {
                  kind: "lead-list" as const,
                  data: {
                    leads: retryData.leads,
                    niche: normalizedNiche,
                    geo,
                  },
                },
              };
            }
          }

          const normalizedDetail = detail?.trim();
          const suggestion = normalizedDetail?.includes("getaddrinfo failed")
            ? "Supabase is unreachable in this local environment. Restart the backend so it can use the local memory fallback. Do not retry automatically."
            : normalizedDetail?.toLowerCase().includes("timed out")
              ? "Live discovery timed out. Stop here and ask the user whether to retry with a narrower query or smaller lead count."
              : isBudgetConstraint(normalizedDetail)
                ? "Discovery hit an upstream scraper budget constraint. Refine the niche or retry with a clinic-specific query instead of switching to mock data."
                : response.status >= 500
                  ? "The backend is up, but discovery failed inside the service. Check the backend logs for the real dependency error."
                : "Check if the ZRAI backend server is running on port 8001.";
          progress.error(
            1,
            normalizedDetail ||
              `Discovery failed with status ${response.status}.`,
            { status: response.status }
          );

          return {
            success: false,
            error: normalizedDetail || `Backend error: ${response.status}`,
            suggestion,
          };
        }

        const data = await response.json();
        console.log(`[discoverLeads] Success: ${data.count} leads discovered`);

        if (!mock && Number(data.count || 0) === 0 && clinicFallbackNiches.length > 1) {
          for (const fallbackNiche of clinicFallbackNiches.slice(1)) {
            console.warn(
              `[discoverLeads] Primary discovery returned 0 leads; retrying clinic fallback niche: ${fallbackNiche}`
            );
            const fallbackResponse = await callDiscovery(fallbackNiche);
            if (!fallbackResponse.ok) {
              continue;
            }

            const fallbackData = await fallbackResponse.json();
            if (Number(fallbackData.count || 0) <= 0) {
              continue;
            }

            progress.advance(
              2,
              `Broadened the clinic search and found ${fallbackData.count} lead${fallbackData.count === 1 ? "" : "s"} for review.`,
              { discovered: fallbackData.count, retried: true }
            );
            progress.success(
              `Discovery complete. Prepared ${fallbackData.count} lead${fallbackData.count === 1 ? "" : "s"} for review.`,
              { discovered: fallbackData.count, runId: fallbackData.run_id ?? null }
            );

            return {
              success: true,
              leads: fallbackData.leads,
              count: fallbackData.count,
              run_id: fallbackData.run_id,
              summary: `Discovered ${fallbackData.count} real leads in ${geo} after broadening the clinic search from "${niche}" to "${fallbackNiche}".`,
              artifactTrigger: {
                kind: "lead-list" as const,
                data: {
                  leads: fallbackData.leads,
                  niche: fallbackNiche,
                  geo,
                },
              },
            };
          }
        }

        if (!mock && Number(data.count || 0) === 0) {
          const firecrawlLeads = await discoverClinicLeadsWithFirecrawl({
            niche,
            geo,
            limit,
          });

          if (firecrawlLeads.length > 0) {
            progress.advance(
              2,
              `Live backend returned no clinics, so Firecrawl search recovered ${firecrawlLeads.length} likely matches for review.`,
              { discovered: firecrawlLeads.length, fallback: "firecrawl-search" }
            );
            progress.success(
              `Discovery complete. Prepared ${firecrawlLeads.length} lead${firecrawlLeads.length === 1 ? "" : "s"} for review.`,
              { discovered: firecrawlLeads.length, runId: null }
            );

            return {
              success: true,
              leads: firecrawlLeads,
              count: firecrawlLeads.length,
              run_id: null,
              summary: `Discovered ${firecrawlLeads.length} clinic leads in ${geo} using Firecrawl search fallback after the primary discovery service returned no verified matches.`,
              artifactTrigger: {
                kind: "lead-list" as const,
                data: {
                  leads: firecrawlLeads,
                  niche,
                  geo,
                },
              },
            };
          }
        }

        progress.advance(
          2,
          `Normalizing ${data.count} discovered lead${data.count === 1 ? "" : "s"} for the artifact.`,
          { discovered: data.count }
        );
        progress.success(
          `Discovery complete. Prepared ${data.count} lead${data.count === 1 ? "" : "s"} for review.`,
          { discovered: data.count, runId: data.run_id ?? null }
        );

        return {
          success: true,
          leads: data.leads,
          count: data.count,
          run_id: data.run_id,
          summary: mock
            ? `Discovered ${data.count} mock leads in the ${niche} niche (${geo}). Using test data for fast development.`
            : `Discovered ${data.count} real leads in the ${niche} niche (${geo}) using the live discovery backend.`,
          artifactTrigger: {
            kind: "lead-list" as const,
            data: {
              leads: data.leads,
              niche,
              geo,
            },
          },
        };
      } catch (error) {
        console.error("[discoverLeads] Exception:", error);
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error",
          { geo, limit, mock, niche }
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion:
            error instanceof Error &&
            error.message.toLowerCase().includes("fetch failed")
              ? "The backend connection dropped during live discovery. Stop here and ask the user whether to retry with a narrower query or smaller lead count."
              : "Please check if the backend is running (python -m uvicorn src.api.server:app --port 8001). If you only want a fast dry run, explicitly ask for mock data.",
        };
      }
    },
  });
