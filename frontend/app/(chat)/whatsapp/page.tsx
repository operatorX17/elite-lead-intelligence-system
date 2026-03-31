import { redirect } from "next/navigation";
import { auth } from "@/app/(auth)/auth";
import { WhatsAppInbox } from "@/components/whatsapp-inbox";
import {
  getWhatsAppMessagesByConversationId,
  listWhatsAppConversations,
} from "@/lib/db/queries";
import { getWhatsAppPublicConfig } from "@/lib/whatsapp/config";

export default async function WhatsAppPage() {
  const session = await auth();

  if (!session?.user) {
    redirect("/login?redirectUrl=/whatsapp");
  }

  const conversations = await listWhatsAppConversations();
  const initialConversation = conversations[0] ?? null;
  const initialMessages = initialConversation
    ? await getWhatsAppMessagesByConversationId({
        conversationId: initialConversation.id,
      })
    : [];

  return (
    <WhatsAppInbox
      currentOperatorLabel={
        session.user.email ?? session.user.name ?? "Human operator"
      }
      initialConversationId={initialConversation?.id ?? null}
      initialConversations={conversations}
      initialMessages={initialMessages}
      publicConfig={getWhatsAppPublicConfig()}
    />
  );
}
