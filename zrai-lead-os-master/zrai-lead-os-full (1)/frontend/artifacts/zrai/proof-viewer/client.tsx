"use client";

/**
 * ZRAI Proof Viewer Artifact - Client Component
 * 
 * Displays Steel.dev screenshots and proof artifacts.
 */

import { useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import type { ProofArtifact } from "@/lib/zrai/types";

type ProofViewerMetadata = {
  proof: ProofArtifact | null;
  zoom: number;
  loading: boolean;
};

function ProofViewerContent({ 
  content, 
  metadata,
  setMetadata,
}: { 
  content: string; 
  metadata: ProofViewerMetadata;
  setMetadata: (fn: (prev: ProofViewerMetadata) => ProofViewerMetadata) => void;
}) {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  let proof: ProofArtifact | null = metadata?.proof || null;
  
  if (!proof && content) {
    try {
      proof = JSON.parse(content);
    } catch {
      // Content might be a URL directly
      if (content.startsWith('http') || content.startsWith('data:')) {
        proof = {
          id: 'inline',
          lead_id: '',
          proof_type: 'screenshot',
          url: content,
          storage_path: '',
          metadata: {},
          created_at: new Date().toISOString(),
        };
      }
    }
  }

  const zoom = metadata?.zoom || 100;

  if (!proof) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No proof available</div>
          <div className="text-sm">Use the generate proof tool to capture screenshots</div>
        </div>
      </div>
    );
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleZoom = (delta: number) => {
    setMetadata((prev) => ({
      ...prev,
      zoom: Math.max(25, Math.min(400, (prev.zoom || 100) + delta)),
    }));
  };

  const handleDownload = async () => {
    if (!proof?.url) return;
    
    try {
      const response = await fetch(proof.url);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `proof-${proof.id}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Downloaded!");
    } catch {
      toast.error("Failed to download");
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-700 dark:bg-zinc-800">
        <div className="flex items-center gap-2">
          <button
            className="rounded px-2 py-1 text-sm hover:bg-zinc-200 dark:hover:bg-zinc-700"
            onClick={() => handleZoom(-25)}
          >
            −
          </button>
          <span className="min-w-[60px] text-center text-sm">{zoom}%</span>
          <button
            className="rounded px-2 py-1 text-sm hover:bg-zinc-200 dark:hover:bg-zinc-700"
            onClick={() => handleZoom(25)}
          >
            +
          </button>
          <button
            className="rounded px-2 py-1 text-sm hover:bg-zinc-200 dark:hover:bg-zinc-700"
            onClick={() => {
              setMetadata((prev) => ({ ...prev, zoom: 100 }));
              setPosition({ x: 0, y: 0 });
            }}
          >
            Reset
          </button>
        </div>
        <button
          className="rounded bg-blue-500 px-3 py-1 text-sm text-white hover:bg-blue-600"
          onClick={handleDownload}
        >
          Download
        </button>
      </div>

      {/* Metadata */}
      <div className="flex gap-4 border-b border-zinc-200 bg-zinc-100 px-3 py-2 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
        <span>Type: {proof.proof_type}</span>
        {proof.metadata?.width && <span>Size: {proof.metadata.width}x{proof.metadata.height}</span>}
        <span>Captured: {new Date(proof.created_at).toLocaleString()}</span>
      </div>

      {/* Image Viewer */}
      <div 
        className="relative flex-1 cursor-grab overflow-hidden bg-zinc-900 active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {proof.proof_type === 'screenshot' && proof.url && (
          <img
            src={proof.url}
            alt="Proof screenshot"
            className="absolute select-none"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${zoom / 100})`,
              transformOrigin: 'top left',
            }}
            draggable={false}
          />
        )}
        
        {proof.proof_type === 'extracted_data' && (
          <div className="p-4 text-white">
            <pre className="whitespace-pre-wrap text-sm">
              {proof.metadata?.extracted_text || 'No extracted data'}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export const proofViewerArtifact = new Artifact<"proof-viewer", ProofViewerMetadata>({
  kind: "proof-viewer",
  description: "Display Steel.dev screenshots and proof artifacts with zoom and pan",
  initialize: ({ setMetadata }) => {
    setMetadata({
      proof: null,
      zoom: 100,
      loading: false,
    });
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-proofViewer") {
      const data = (streamPart as any).data as ProofArtifact;
      setMetadata((prev) => ({
        ...prev,
        proof: data,
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
    <ProofViewerContent 
      content={props.content} 
      metadata={props.metadata}
      setMetadata={props.setMetadata}
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
      description: "Copy URL",
      onClick: ({ metadata }) => {
        if (metadata?.proof?.url) {
          navigator.clipboard.writeText(metadata.proof.url);
          toast.success("URL copied!");
        }
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">🔄</span>,
      description: "Regenerate proof",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Regenerate the proof screenshot" }],
        });
      },
    },
    {
      icon: <span className="text-xs">📝</span>,
      description: "Extract text",
      onClick: ({ sendMessage }) => {
        sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Extract text from this screenshot" }],
        });
      },
    },
  ],
});
