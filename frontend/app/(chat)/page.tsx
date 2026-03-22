import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { auth } from "@/app/(auth)/auth";
import { Chat } from "@/components/chat";
import { DataStreamHandler } from "@/components/data-stream-handler";
import { chatModels, DEFAULT_CHAT_MODEL } from "@/lib/ai/models";
import { generateUUID } from "@/lib/utils";

export default function Page() {
  return (
    <Suspense fallback={<div className="flex h-dvh" />}>
      <NewChatPage />
    </Suspense>
  );
}

async function NewChatPage() {
  const [session, cookieStore] = await Promise.all([auth(), cookies()]);

  if (!session?.user) {
    redirect("/login?redirectUrl=/");
  }

  const modelIdFromCookie = cookieStore.get("chat-model");
  const id = generateUUID();

  // Validate that the model ID from cookie exists in our models list
  const isValidModel =
    modelIdFromCookie &&
    chatModels.some((m) => m.id === modelIdFromCookie.value);
  const modelId = isValidModel ? modelIdFromCookie.value : DEFAULT_CHAT_MODEL;

  return (
    <>
      <Chat
        autoResume={false}
        id={id}
        initialChatModel={modelId}
        initialMessages={[]}
        initialVisibilityType="private"
        isReadonly={false}
        key={id}
      />
      <DataStreamHandler />
    </>
  );
}
