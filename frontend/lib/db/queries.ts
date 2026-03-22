import "server-only";

import {
  and,
  asc,
  count,
  desc,
  eq,
  gt,
  gte,
  inArray,
  lt,
  type SQL,
} from "drizzle-orm";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import type { ArtifactKind } from "@/components/artifact";
import type { VisibilityType } from "@/components/visibility-selector";
import { ChatSDKError } from "../errors";
import { generateUUID } from "../utils";
import {
  type Chat,
  chat,
  type DBMessage,
  type Document,
  document,
  message,
  type Stream,
  type Suggestion,
  stream,
  suggestion,
  type User,
  user,
  type Vote,
  vote,
} from "./schema";
import { generateHashedPassword } from "./utils";

// Optionally, if not using email/pass login, you can
// use the Drizzle adapter for Auth.js / NextAuth
// https://authjs.dev/reference/adapter/drizzle

// biome-ignore lint: Forbidden non-null assertion.
const client = postgres(process.env.POSTGRES_URL!);
const db = drizzle(client);

type MemoryDbStore = {
  users: Map<string, User>;
  chats: Map<string, Chat>;
  messages: Map<string, DBMessage>;
  votes: Map<string, Vote>;
  documents: Map<string, Document[]>;
  suggestions: Map<string, Suggestion[]>;
  streams: Map<string, Stream[]>;
};

const globalMemoryDb = globalThis as typeof globalThis & {
  __zraiMemoryDbStore?: MemoryDbStore;
  __zraiForceMemoryDb?: boolean;
};

function isMemoryDbEnabled() {
  return (
    process.env.ZRAI_IN_MEMORY_DB === "true" ||
    globalMemoryDb.__zraiForceMemoryDb === true
  );
}

function enableRuntimeMemoryDb() {
  globalMemoryDb.__zraiForceMemoryDb = true;
}

let memoryStore = globalMemoryDb.__zraiMemoryDbStore;

if (!memoryStore) {
  memoryStore = {
    users: new Map<string, User>(),
    chats: new Map<string, Chat>(),
    messages: new Map<string, DBMessage>(),
    votes: new Map<string, Vote>(),
    documents: new Map<string, Document[]>(),
    suggestions: new Map<string, Suggestion[]>(),
    streams: new Map<string, Stream[]>(),
  };
  globalMemoryDb.__zraiMemoryDbStore = memoryStore;
}

const memoryUsers = memoryStore.users;
const memoryChats = memoryStore.chats;
const memoryMessages = memoryStore.messages;
const memoryVotes = memoryStore.votes;
const memoryDocuments = memoryStore.documents;
const memorySuggestions = memoryStore.suggestions;
const memoryStreams = memoryStore.streams;

function getVoteKey(chatId: string, messageId: string) {
  return `${chatId}:${messageId}`;
}

export async function getUser(email: string): Promise<User[]> {
  if (isMemoryDbEnabled()) {
    return Array.from(memoryUsers.values()).filter(
      (currentUser) => currentUser.email === email
    );
  }

  try {
    return await db.select().from(user).where(eq(user.email, email));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getUser(email);
  }
}

export async function createUser(email: string, password: string) {
  const hashedPassword = generateHashedPassword(password);

  if (isMemoryDbEnabled()) {
    const newUser: User = {
      id: generateUUID(),
      email,
      password: hashedPassword,
    };

    memoryUsers.set(newUser.id, newUser);
    return [newUser];
  }

  try {
    return await db.insert(user).values({ email, password: hashedPassword });
  } catch (_error) {
    enableRuntimeMemoryDb();
    return createUser(email, password);
  }
}

export async function createGuestUser() {
  const email = `guest-${Date.now()}`;
  const password = generateHashedPassword(generateUUID());

  if (isMemoryDbEnabled()) {
    const newUser: User = {
      id: generateUUID(),
      email,
      password,
    };

    memoryUsers.set(newUser.id, newUser);

    return [{ id: newUser.id, email: newUser.email }];
  }

  try {
    return await db.insert(user).values({ email, password }).returning({
      id: user.id,
      email: user.email,
    });
  } catch (_error) {
    enableRuntimeMemoryDb();
    return createGuestUser();
  }
}

export async function ensureUserRecord({
  email,
  id,
}: {
  id: string;
  email?: string | null;
}) {
  const resolvedEmail =
    email && email.length > 0 ? email : `guest-${id}@local.zrai`;

  if (isMemoryDbEnabled()) {
    if (!memoryUsers.has(id)) {
      memoryUsers.set(id, {
        id,
        email: resolvedEmail,
        password: generateHashedPassword(generateUUID()),
      });
    }

    return memoryUsers.get(id) ?? null;
  }

  try {
    const [existingUser] = await db
      .select()
      .from(user)
      .where(eq(user.id, id))
      .limit(1);

    if (existingUser) {
      return existingUser;
    }

    const [createdUser] = await db
      .insert(user)
      .values({
        id,
        email: resolvedEmail,
        password: generateHashedPassword(generateUUID()),
      })
      .onConflictDoNothing({ target: user.id })
      .returning();

    if (createdUser) {
      return createdUser;
    }

    const [retrievedUser] = await db
      .select()
      .from(user)
      .where(eq(user.id, id))
      .limit(1);

    return retrievedUser ?? null;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return ensureUserRecord({ id, email });
  }
}

export async function saveChat({
  id,
  userId,
  title,
  visibility,
}: {
  id: string;
  userId: string;
  title: string;
  visibility: VisibilityType;
}) {
  if (isMemoryDbEnabled()) {
    const newChat: Chat = {
      id,
      createdAt: new Date(),
      title,
      userId,
      visibility,
    };

    memoryChats.set(id, newChat);
    return [newChat];
  }

  try {
    return await db.insert(chat).values({
      id,
      createdAt: new Date(),
      userId,
      title,
      visibility,
    });
  } catch (_error) {
    enableRuntimeMemoryDb();
    return saveChat({ id, userId, title, visibility });
  }
}

export async function deleteChatById({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    memoryChats.delete(id);

    for (const [messageId, currentMessage] of memoryMessages.entries()) {
      if (currentMessage.chatId === id) {
        memoryMessages.delete(messageId);
      }
    }

    for (const [voteKey, currentVote] of memoryVotes.entries()) {
      if (currentVote.chatId === id) {
        memoryVotes.delete(voteKey);
      }
    }

    memoryStreams.delete(id);
    return null;
  }

  try {
    await db.delete(vote).where(eq(vote.chatId, id));
    await db.delete(message).where(eq(message.chatId, id));
    await db.delete(stream).where(eq(stream.chatId, id));

    const [chatsDeleted] = await db
      .delete(chat)
      .where(eq(chat.id, id))
      .returning();
    return chatsDeleted;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return deleteChatById({ id });
  }
}

export async function deleteAllChatsByUserId({ userId }: { userId: string }) {
  if (isMemoryDbEnabled()) {
    const userChats = Array.from(memoryChats.values()).filter(
      (currentChat) => currentChat.userId === userId
    );

    for (const currentChat of userChats) {
      await deleteChatById({ id: currentChat.id });
    }

    return { deletedCount: userChats.length };
  }

  try {
    const userChats = await db
      .select({ id: chat.id })
      .from(chat)
      .where(eq(chat.userId, userId));

    if (userChats.length === 0) {
      return { deletedCount: 0 };
    }

    const chatIds = userChats.map((c) => c.id);

    await db.delete(vote).where(inArray(vote.chatId, chatIds));
    await db.delete(message).where(inArray(message.chatId, chatIds));
    await db.delete(stream).where(inArray(stream.chatId, chatIds));

    const deletedChats = await db
      .delete(chat)
      .where(eq(chat.userId, userId))
      .returning();

    return { deletedCount: deletedChats.length };
  } catch (_error) {
    enableRuntimeMemoryDb();
    return deleteAllChatsByUserId({ userId });
  }
}

export async function getChatsByUserId({
  id,
  limit,
  startingAfter,
  endingBefore,
}: {
  id: string;
  limit: number;
  startingAfter: string | null;
  endingBefore: string | null;
}) {
  if (isMemoryDbEnabled()) {
    let filteredChats = Array.from(memoryChats.values())
      .filter((currentChat) => currentChat.userId === id)
      .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

    if (startingAfter) {
      const selectedChat = memoryChats.get(startingAfter);
      if (!selectedChat) {
        throw new ChatSDKError(
          "not_found:database",
          `Chat with id ${startingAfter} not found`
        );
      }

      filteredChats = filteredChats.filter(
        (currentChat) => currentChat.createdAt > selectedChat.createdAt
      );
    } else if (endingBefore) {
      const selectedChat = memoryChats.get(endingBefore);
      if (!selectedChat) {
        throw new ChatSDKError(
          "not_found:database",
          `Chat with id ${endingBefore} not found`
        );
      }

      filteredChats = filteredChats.filter(
        (currentChat) => currentChat.createdAt < selectedChat.createdAt
      );
    }

    const hasMore = filteredChats.length > limit;

    return {
      chats: hasMore ? filteredChats.slice(0, limit) : filteredChats,
      hasMore,
    };
  }

  try {
    const extendedLimit = limit + 1;

    const query = (whereCondition?: SQL<any>) =>
      db
        .select()
        .from(chat)
        .where(
          whereCondition
            ? and(whereCondition, eq(chat.userId, id))
            : eq(chat.userId, id)
        )
        .orderBy(desc(chat.createdAt))
        .limit(extendedLimit);

    let filteredChats: Chat[] = [];

    if (startingAfter) {
      const [selectedChat] = await db
        .select()
        .from(chat)
        .where(eq(chat.id, startingAfter))
        .limit(1);

      if (!selectedChat) {
        throw new ChatSDKError(
          "not_found:database",
          `Chat with id ${startingAfter} not found`
        );
      }

      filteredChats = await query(gt(chat.createdAt, selectedChat.createdAt));
    } else if (endingBefore) {
      const [selectedChat] = await db
        .select()
        .from(chat)
        .where(eq(chat.id, endingBefore))
        .limit(1);

      if (!selectedChat) {
        throw new ChatSDKError(
          "not_found:database",
          `Chat with id ${endingBefore} not found`
        );
      }

      filteredChats = await query(lt(chat.createdAt, selectedChat.createdAt));
    } else {
      filteredChats = await query();
    }

    const hasMore = filteredChats.length > limit;

    return {
      chats: hasMore ? filteredChats.slice(0, limit) : filteredChats,
      hasMore,
    };
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getChatsByUserId({ id, limit, startingAfter, endingBefore });
  }
}

export async function getChatById({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    return memoryChats.get(id) ?? null;
  }

  try {
    const [selectedChat] = await db.select().from(chat).where(eq(chat.id, id));
    if (!selectedChat) {
      return null;
    }

    return selectedChat;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getChatById({ id });
  }
}

export async function saveMessages({ messages }: { messages: DBMessage[] }) {
  if (isMemoryDbEnabled()) {
    for (const currentMessage of messages) {
      memoryMessages.set(currentMessage.id, currentMessage);
    }
    return messages;
  }

  try {
    return await db.insert(message).values(messages);
  } catch (_error) {
    enableRuntimeMemoryDb();
    return saveMessages({ messages });
  }
}

export async function updateMessage({
  id,
  parts,
}: {
  id: string;
  parts: DBMessage["parts"];
}) {
  if (isMemoryDbEnabled()) {
    const currentMessage = memoryMessages.get(id);
    if (currentMessage) {
      memoryMessages.set(id, { ...currentMessage, parts });
    }
    return currentMessage ?? null;
  }

  try {
    return await db.update(message).set({ parts }).where(eq(message.id, id));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return updateMessage({ id, parts });
  }
}

export async function getMessagesByChatId({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    return Array.from(memoryMessages.values())
      .filter((currentMessage) => currentMessage.chatId === id)
      .sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime());
  }

  try {
    return await db
      .select()
      .from(message)
      .where(eq(message.chatId, id))
      .orderBy(asc(message.createdAt));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getMessagesByChatId({ id });
  }
}

export async function voteMessage({
  chatId,
  messageId,
  type,
}: {
  chatId: string;
  messageId: string;
  type: "up" | "down";
}) {
  if (isMemoryDbEnabled()) {
    const nextVote: Vote = {
      chatId,
      messageId,
      isUpvoted: type === "up",
    };
    memoryVotes.set(getVoteKey(chatId, messageId), nextVote);
    return nextVote;
  }

  try {
    const [existingVote] = await db
      .select()
      .from(vote)
      .where(and(eq(vote.messageId, messageId)));

    if (existingVote) {
      return await db
        .update(vote)
        .set({ isUpvoted: type === "up" })
        .where(and(eq(vote.messageId, messageId), eq(vote.chatId, chatId)));
    }
    return await db.insert(vote).values({
      chatId,
      messageId,
      isUpvoted: type === "up",
    });
  } catch (_error) {
    enableRuntimeMemoryDb();
    return voteMessage({ chatId, messageId, type });
  }
}

export async function getVotesByChatId({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    return Array.from(memoryVotes.values()).filter(
      (currentVote) => currentVote.chatId === id
    );
  }

  try {
    return await db.select().from(vote).where(eq(vote.chatId, id));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getVotesByChatId({ id });
  }
}

export async function saveDocument({
  id,
  title,
  kind,
  content,
  userId,
}: {
  id: string;
  title: string;
  kind: ArtifactKind;
  content: string;
  userId: string;
}) {
  if (isMemoryDbEnabled()) {
    const currentDocument: Document = {
      id,
      createdAt: new Date(),
      title,
      content,
      kind,
      userId,
    };

    const versions = memoryDocuments.get(id) ?? [];
    versions.push(currentDocument);
    memoryDocuments.set(id, versions);

    return [currentDocument];
  }

  try {
    return await db
      .insert(document)
      .values({
        id,
        title,
        kind,
        content,
        userId,
        createdAt: new Date(),
      })
      .returning();
  } catch (_error) {
    enableRuntimeMemoryDb();
    return saveDocument({ id, title, kind, content, userId });
  }
}

export async function getDocumentsById({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    return memoryDocuments.get(id) ?? [];
  }

  try {
    const documents = await db
      .select()
      .from(document)
      .where(eq(document.id, id))
      .orderBy(asc(document.createdAt));

    return documents;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getDocumentsById({ id });
  }
}

export async function getDocumentById({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    const documents = memoryDocuments.get(id) ?? [];
    return documents.at(-1);
  }

  try {
    const [selectedDocument] = await db
      .select()
      .from(document)
      .where(eq(document.id, id))
      .orderBy(desc(document.createdAt));

    return selectedDocument;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getDocumentById({ id });
  }
}

export async function deleteDocumentsByIdAfterTimestamp({
  id,
  timestamp,
}: {
  id: string;
  timestamp: Date;
}) {
  if (isMemoryDbEnabled()) {
    const documents = memoryDocuments.get(id) ?? [];
    const keptDocuments = documents.filter(
      (currentDocument) => currentDocument.createdAt <= timestamp
    );
    memoryDocuments.set(id, keptDocuments);
    memorySuggestions.delete(id);
    return documents.filter(
      (currentDocument) => currentDocument.createdAt > timestamp
    );
  }

  try {
    await db
      .delete(suggestion)
      .where(
        and(
          eq(suggestion.documentId, id),
          gt(suggestion.documentCreatedAt, timestamp)
        )
      );

    return await db
      .delete(document)
      .where(and(eq(document.id, id), gt(document.createdAt, timestamp)))
      .returning();
  } catch (_error) {
    enableRuntimeMemoryDb();
    return deleteDocumentsByIdAfterTimestamp({ id, timestamp });
  }
}

export async function saveSuggestions({
  suggestions,
}: {
  suggestions: Suggestion[];
}) {
  if (isMemoryDbEnabled()) {
    for (const currentSuggestion of suggestions) {
      const currentSuggestions =
        memorySuggestions.get(currentSuggestion.documentId) ?? [];
      currentSuggestions.push(currentSuggestion);
      memorySuggestions.set(currentSuggestion.documentId, currentSuggestions);
    }
    return suggestions;
  }

  try {
    return await db.insert(suggestion).values(suggestions);
  } catch (_error) {
    enableRuntimeMemoryDb();
    return saveSuggestions({ suggestions });
  }
}

export async function getSuggestionsByDocumentId({
  documentId,
}: {
  documentId: string;
}) {
  if (isMemoryDbEnabled()) {
    return memorySuggestions.get(documentId) ?? [];
  }

  try {
    return await db
      .select()
      .from(suggestion)
      .where(eq(suggestion.documentId, documentId));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getSuggestionsByDocumentId({ documentId });
  }
}

export async function getMessageById({ id }: { id: string }) {
  if (isMemoryDbEnabled()) {
    const currentMessage = memoryMessages.get(id);
    return currentMessage ? [currentMessage] : [];
  }

  try {
    return await db.select().from(message).where(eq(message.id, id));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getMessageById({ id });
  }
}

export async function deleteMessagesByChatIdAfterTimestamp({
  chatId,
  timestamp,
}: {
  chatId: string;
  timestamp: Date;
}) {
  if (isMemoryDbEnabled()) {
    for (const [messageId, currentMessage] of memoryMessages.entries()) {
      if (
        currentMessage.chatId === chatId &&
        currentMessage.createdAt >= timestamp
      ) {
        memoryMessages.delete(messageId);
      }
    }

    for (const [voteKey, currentVote] of memoryVotes.entries()) {
      if (currentVote.chatId === chatId) {
        const currentMessage = memoryMessages.get(currentVote.messageId);
        if (!currentMessage) {
          memoryVotes.delete(voteKey);
        }
      }
    }

    return;
  }

  try {
    const messagesToDelete = await db
      .select({ id: message.id })
      .from(message)
      .where(
        and(eq(message.chatId, chatId), gte(message.createdAt, timestamp))
      );

    const messageIds = messagesToDelete.map(
      (currentMessage) => currentMessage.id
    );

    if (messageIds.length > 0) {
      await db
        .delete(vote)
        .where(
          and(eq(vote.chatId, chatId), inArray(vote.messageId, messageIds))
        );

      return await db
        .delete(message)
        .where(
          and(eq(message.chatId, chatId), inArray(message.id, messageIds))
        );
    }
  } catch (_error) {
    enableRuntimeMemoryDb();
    return deleteMessagesByChatIdAfterTimestamp({ chatId, timestamp });
  }
}

export async function updateChatVisibilityById({
  chatId,
  visibility,
}: {
  chatId: string;
  visibility: "private" | "public";
}) {
  if (isMemoryDbEnabled()) {
    const currentChat = memoryChats.get(chatId);
    if (currentChat) {
      memoryChats.set(chatId, { ...currentChat, visibility });
    }
    return;
  }

  try {
    return await db.update(chat).set({ visibility }).where(eq(chat.id, chatId));
  } catch (_error) {
    enableRuntimeMemoryDb();
    return updateChatVisibilityById({ chatId, visibility });
  }
}

export async function updateChatTitleById({
  chatId,
  title,
}: {
  chatId: string;
  title: string;
}) {
  if (isMemoryDbEnabled()) {
    const currentChat = memoryChats.get(chatId);
    if (currentChat) {
      memoryChats.set(chatId, { ...currentChat, title });
    }
    return;
  }

  try {
    return await db.update(chat).set({ title }).where(eq(chat.id, chatId));
  } catch (error) {
    console.warn("Failed to update title for chat", chatId, error);
    return;
  }
}

export async function getMessageCountByUserId({
  id,
  differenceInHours,
}: {
  id: string;
  differenceInHours: number;
}) {
  if (isMemoryDbEnabled()) {
    const threshold = new Date(Date.now() - differenceInHours * 60 * 60 * 1000);

    return Array.from(memoryMessages.values()).filter((currentMessage) => {
      const currentChat = memoryChats.get(currentMessage.chatId);
      return (
        currentChat?.userId === id &&
        currentMessage.role === "user" &&
        currentMessage.createdAt >= threshold
      );
    }).length;
  }

  try {
    const twentyFourHoursAgo = new Date(
      Date.now() - differenceInHours * 60 * 60 * 1000
    );

    const [stats] = await db
      .select({ count: count(message.id) })
      .from(message)
      .innerJoin(chat, eq(message.chatId, chat.id))
      .where(
        and(
          eq(chat.userId, id),
          gte(message.createdAt, twentyFourHoursAgo),
          eq(message.role, "user")
        )
      )
      .execute();

    return stats?.count ?? 0;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getMessageCountByUserId({ id, differenceInHours });
  }
}

export async function createStreamId({
  streamId,
  chatId,
}: {
  streamId: string;
  chatId: string;
}) {
  if (isMemoryDbEnabled()) {
    const streams = memoryStreams.get(chatId) ?? [];
    streams.push({ id: streamId, chatId, createdAt: new Date() });
    memoryStreams.set(chatId, streams);
    return;
  }

  try {
    await db
      .insert(stream)
      .values({ id: streamId, chatId, createdAt: new Date() });
  } catch (_error) {
    enableRuntimeMemoryDb();
    return createStreamId({ streamId, chatId });
  }
}

export async function getStreamIdsByChatId({ chatId }: { chatId: string }) {
  if (isMemoryDbEnabled()) {
    return (memoryStreams.get(chatId) ?? []).map(({ id }) => id);
  }

  try {
    const streamIds = await db
      .select({ id: stream.id })
      .from(stream)
      .where(eq(stream.chatId, chatId))
      .orderBy(asc(stream.createdAt))
      .execute();

    return streamIds.map(({ id }) => id);
  } catch (_error) {
    enableRuntimeMemoryDb();
    return getStreamIdsByChatId({ chatId });
  }
}
