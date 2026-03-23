import type { UIMessageStreamWriter } from "ai";
import type { ChatMessage, ZRAIActivityEvent, ZRAIStage } from "@/lib/types";

type ReporterConfig = {
  tool: string;
  title: string;
  stages: string[];
  dataStream: UIMessageStreamWriter<ChatMessage>;
};

type EventStatus = "running" | "complete" | "error";

function buildStages(
  labels: string[],
  activeIndex: number,
  status: EventStatus
): ZRAIStage[] {
  return labels.map((label, index) => {
    if (status === "error") {
      if (index < activeIndex) {
        return { label, state: "complete" };
      }

      if (index === activeIndex) {
        return { label, state: "error" };
      }

      return { label, state: "pending" };
    }

    if (status === "complete") {
      return { label, state: "complete" };
    }

    if (index < activeIndex) {
      return { label, state: "complete" };
    }

    if (index === activeIndex) {
      return { label, state: "active" };
    }

    return { label, state: "pending" };
  });
}

export function createZRAIProgressReporter({
  tool,
  title,
  stages,
  dataStream,
}: ReporterConfig) {
  const emit = (
    index: number,
    detail: string,
    status: EventStatus,
    metrics?: Record<string, string | number | boolean | null>
  ) => {
    const event: ZRAIActivityEvent = {
      tool,
      title,
      detail,
      status,
      timestamp: new Date().toISOString(),
      stages: buildStages(stages, index, status),
      metrics,
    };

    dataStream.write({
      type: "data-zrai-status",
      data: event,
      transient: true,
    });
  };

  return {
    start(
      detail: string,
      metrics?: Record<string, string | number | boolean | null>
    ) {
      emit(0, detail, "running", metrics);
    },
    advance(
      index: number,
      detail: string,
      metrics?: Record<string, string | number | boolean | null>
    ) {
      emit(index, detail, "running", metrics);
    },
    success(
      detail: string,
      metrics?: Record<string, string | number | boolean | null>
    ) {
      emit(stages.length - 1, detail, "complete", metrics);
    },
    error(
      index: number,
      detail: string,
      metrics?: Record<string, string | number | boolean | null>
    ) {
      emit(index, detail, "error", metrics);
    },
  };
}
