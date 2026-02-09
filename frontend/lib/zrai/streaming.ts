/**
 * ZRAI Lead OS - Streaming Utilities
 * 
 * Server-Sent Events (SSE) streaming for long-running operations.
 */

/**
 * Creates an SSE stream response for long-running ZRAI operations.
 */
export function createSSEStream() {
  const encoder = new TextEncoder();
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;

  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
    cancel() {
      controller = null;
    },
  });

  const send = (event: string, data: unknown) => {
    if (controller) {
      const message = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
      controller.enqueue(encoder.encode(message));
    }
  };

  const sendProgress = (progress: number, message?: string) => {
    send('progress', { progress, message });
  };

  const sendPartialResult = (data: unknown) => {
    send('partial', data);
  };

  const sendComplete = (data: unknown) => {
    send('complete', data);
    if (controller) {
      controller.close();
    }
  };

  const sendError = (error: { code: string; message: string }) => {
    send('error', error);
    if (controller) {
      controller.close();
    }
  };

  const response = new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });

  return {
    response,
    send,
    sendProgress,
    sendPartialResult,
    sendComplete,
    sendError,
  };
}

/**
 * Client-side SSE event handler for ZRAI operations.
 */
export interface SSEEventHandlers<T> {
  onProgress?: (progress: number, message?: string) => void;
  onPartial?: (data: Partial<T>) => void;
  onComplete?: (data: T) => void;
  onError?: (error: { code: string; message: string }) => void;
}

export function createSSEClient<T>(
  url: string,
  options: RequestInit,
  handlers: SSEEventHandlers<T>
): { abort: () => void } {
  const abortController = new AbortController();

  fetch(url, {
    ...options,
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const error = await response.json().catch(() => ({ code: 'unknown', message: 'Request failed' }));
        handlers.onError?.(error);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        handlers.onError?.({ code: 'no_stream', message: 'No response stream' });
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const chunk of lines) {
          if (!chunk.trim()) continue;

          const eventMatch = chunk.match(/^event: (.+)$/m);
          const dataMatch = chunk.match(/^data: (.+)$/m);

          if (eventMatch && dataMatch) {
            const event = eventMatch[1];
            const data = JSON.parse(dataMatch[1]);

            switch (event) {
              case 'progress':
                handlers.onProgress?.(data.progress, data.message);
                break;
              case 'partial':
                handlers.onPartial?.(data);
                break;
              case 'complete':
                handlers.onComplete?.(data);
                break;
              case 'error':
                handlers.onError?.(data);
                break;
            }
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        handlers.onError?.({ code: 'network_error', message: error.message });
      }
    });

  return {
    abort: () => abortController.abort(),
  };
}

/**
 * Progress tracker for multi-step operations.
 */
export class ProgressTracker {
  private steps: string[];
  private currentStep: number = 0;
  private onProgress: (progress: number, message: string) => void;

  constructor(steps: string[], onProgress: (progress: number, message: string) => void) {
    this.steps = steps;
    this.onProgress = onProgress;
  }

  start() {
    this.currentStep = 0;
    this.report();
  }

  next() {
    if (this.currentStep < this.steps.length - 1) {
      this.currentStep++;
      this.report();
    }
  }

  complete() {
    this.currentStep = this.steps.length;
    this.onProgress(100, 'Complete');
  }

  private report() {
    const progress = Math.round((this.currentStep / this.steps.length) * 100);
    this.onProgress(progress, this.steps[this.currentStep]);
  }
}
