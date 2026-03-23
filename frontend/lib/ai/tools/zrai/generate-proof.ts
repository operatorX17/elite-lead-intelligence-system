/**
 * ZRAI Lead OS - Generate Proof Tool
 *
 * Generates proof artifacts (screenshots, recordings) for a lead's website.
 */

import { tool, type UIMessageStreamWriter } from "ai";
import { z } from "zod";
import type { ChatMessage } from "@/lib/types";
import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";
import { createZRAIProgressReporter } from "./progress";

export const generateProof = ({
  dataStream,
}: {
  dataStream: UIMessageStreamWriter<ChatMessage>;
}) =>
  tool({
    description: `Generate proof artifacts for a lead's website, such as screenshots or recordings.
Use this tool to capture visual evidence of a lead's website, landing pages, or specific issues.
Useful for showing leads what you observed about their site.`,
    inputSchema: z.object({
      lead_id: z.string().uuid().describe("The unique identifier of the lead"),
      proof_type: z
        .enum(["screenshot", "recording", "extracted_data"])
        .default("screenshot")
        .describe(
          "Type of proof to generate: screenshot (static image), recording (video), or extracted_data (text/data extraction)"
        ),
    }),
    execute: async ({ lead_id, proof_type }) => {
      const progress = createZRAIProgressReporter({
        dataStream,
        tool: "generateProof",
        title: "Generating proof artifact",
        stages: ["Load target", "Capture evidence", "Prepare proof viewer"],
      });
      progress.start("Loading the lead and preparing the proof run.", {
        leadId: lead_id,
        proofType: proof_type,
      });
      try {
        progress.advance(
          1,
          `Running the ${proof_type} capture flow against the lead website.`
        );
        const response = await fetch(ZRAI_BACKEND_ENDPOINTS.proof, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_id, proof_type }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          progress.error(1, data.error?.message || "Failed to generate proof", {
            status: response.status,
          });
          return {
            success: false,
            error: data.error?.message || "Failed to generate proof",
            suggestion:
              data.error?.code === "not_found"
                ? "Lead not found. Please check the lead ID."
                : data.error?.code === "timeout"
                  ? "The website took too long to load. Try again later."
                  : data.error?.code === "budget_exceeded"
                    ? "Browser session budget exceeded. Try again tomorrow."
                    : "The website may be blocking automated access.",
          };
        }

        const { proof } = data;
        progress.advance(
          2,
          "Assembling audit bullets and proof assets for the viewer.",
          {
            hasHeroScreenshot: Boolean(proof.hero_screenshot_url),
            hasCtaScreenshot: Boolean(proof.cta_screenshot_url),
          }
        );
        progress.success("Proof artifact is ready for review.");

        return {
          success: true,
          proof,
          summary: `Generated ${proof_type} for the lead's website. ${
            proof.metadata?.url ? `URL: ${proof.metadata.url}` : ""
          }`,
          artifactTrigger: {
            kind: "proof-viewer" as const,
            data: proof,
          },
        };
      } catch (error) {
        progress.error(
          1,
          error instanceof Error ? error.message : "Network error",
          { leadId: lead_id }
        );
        return {
          success: false,
          error: error instanceof Error ? error.message : "Network error",
          suggestion: "Please check your connection and try again.",
        };
      }
    },
  });
