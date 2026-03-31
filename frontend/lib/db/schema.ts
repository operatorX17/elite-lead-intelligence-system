import { sql, type InferSelectModel } from "drizzle-orm";
import {
  boolean,
  foreignKey,
  integer,
  json,
  jsonb,
  pgTable,
  primaryKey,
  text,
  timestamp,
  uniqueIndex,
  uuid,
  varchar,
} from "drizzle-orm/pg-core";
import type {
  WhatsAppAgentState,
  WhatsAppLinkedLeadContext,
  WhatsAppOpsState,
} from "@/lib/whatsapp/state";

export const user = pgTable("User", {
  id: uuid("id").primaryKey().notNull().defaultRandom(),
  email: varchar("email", { length: 64 }).notNull(),
  password: varchar("password", { length: 64 }),
});

export type User = InferSelectModel<typeof user>;

export const chat = pgTable("Chat", {
  id: uuid("id").primaryKey().notNull().defaultRandom(),
  createdAt: timestamp("createdAt").notNull(),
  title: text("title").notNull(),
  lastContext: jsonb("lastContext"),
  userId: uuid("userId")
    .notNull()
    .references(() => user.id),
  visibility: varchar("visibility", { enum: ["public", "private"] })
    .notNull()
    .default("private"),
});

export type Chat = InferSelectModel<typeof chat>;

// DEPRECATED: The following schema is deprecated and will be removed in the future.
// Read the migration guide at https://chat-sdk.dev/docs/migration-guides/message-parts
export const messageDeprecated = pgTable("Message", {
  id: uuid("id").primaryKey().notNull().defaultRandom(),
  chatId: uuid("chatId")
    .notNull()
    .references(() => chat.id),
  role: varchar("role").notNull(),
  content: json("content").notNull(),
  createdAt: timestamp("createdAt").notNull(),
});

export type MessageDeprecated = InferSelectModel<typeof messageDeprecated>;

export const message = pgTable("Message_v2", {
  id: uuid("id").primaryKey().notNull().defaultRandom(),
  chatId: uuid("chatId")
    .notNull()
    .references(() => chat.id),
  role: varchar("role").notNull(),
  parts: json("parts").notNull(),
  attachments: json("attachments").notNull(),
  createdAt: timestamp("createdAt").notNull(),
});

export type DBMessage = InferSelectModel<typeof message>;

// DEPRECATED: The following schema is deprecated and will be removed in the future.
// Read the migration guide at https://chat-sdk.dev/docs/migration-guides/message-parts
export const voteDeprecated = pgTable(
  "Vote",
  {
    chatId: uuid("chatId")
      .notNull()
      .references(() => chat.id),
    messageId: uuid("messageId")
      .notNull()
      .references(() => messageDeprecated.id),
    isUpvoted: boolean("isUpvoted").notNull(),
  },
  (table) => {
    return {
      pk: primaryKey({ columns: [table.chatId, table.messageId] }),
    };
  }
);

export type VoteDeprecated = InferSelectModel<typeof voteDeprecated>;

export const vote = pgTable(
  "Vote_v2",
  {
    chatId: uuid("chatId")
      .notNull()
      .references(() => chat.id),
    messageId: uuid("messageId")
      .notNull()
      .references(() => message.id),
    isUpvoted: boolean("isUpvoted").notNull(),
  },
  (table) => {
    return {
      pk: primaryKey({ columns: [table.chatId, table.messageId] }),
    };
  }
);

export type Vote = InferSelectModel<typeof vote>;

export const document = pgTable(
  "Document",
  {
    id: uuid("id").notNull().defaultRandom(),
    createdAt: timestamp("createdAt").notNull(),
    title: text("title").notNull(),
    content: text("content"),
    kind: varchar("text", { enum: [
      "text", 
      "code", 
      "image", 
      "sheet",
      // ZRAI artifact kinds
      "lead-card",
      "lead-list",
      "proof-viewer",
      "scoring-dashboard",
      "outreach-draft",
      "conversation-thread",
      "metrics-dashboard",
      "lead-sheet"
    ] })
      .notNull()
      .default("text"),
    userId: uuid("userId")
      .notNull()
      .references(() => user.id),
  },
  (table) => {
    return {
      pk: primaryKey({ columns: [table.id, table.createdAt] }),
    };
  }
);

export type Document = InferSelectModel<typeof document>;

export const suggestion = pgTable(
  "Suggestion",
  {
    id: uuid("id").notNull().defaultRandom(),
    documentId: uuid("documentId").notNull(),
    documentCreatedAt: timestamp("documentCreatedAt").notNull(),
    originalText: text("originalText").notNull(),
    suggestedText: text("suggestedText").notNull(),
    description: text("description"),
    isResolved: boolean("isResolved").notNull().default(false),
    userId: uuid("userId")
      .notNull()
      .references(() => user.id),
    createdAt: timestamp("createdAt").notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.id] }),
    documentRef: foreignKey({
      columns: [table.documentId, table.documentCreatedAt],
      foreignColumns: [document.id, document.createdAt],
    }),
  })
);

export type Suggestion = InferSelectModel<typeof suggestion>;

export const stream = pgTable(
  "Stream",
  {
    id: uuid("id").notNull().defaultRandom(),
    chatId: uuid("chatId").notNull(),
    createdAt: timestamp("createdAt").notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.id] }),
    chatRef: foreignKey({
      columns: [table.chatId],
      foreignColumns: [chat.id],
    }),
  })
);

export type Stream = InferSelectModel<typeof stream>;

export const whatsappConversation = pgTable(
  "WhatsAppConversation",
  {
    id: uuid("id").primaryKey().notNull().defaultRandom(),
    createdAt: timestamp("createdAt").notNull(),
    updatedAt: timestamp("updatedAt").notNull(),
    contactName: text("contactName").notNull(),
    contactPhone: varchar("contactPhone", { length: 32 }).notNull(),
    mode: varchar("mode", { enum: ["bot", "human"] })
      .notNull()
      .default("bot"),
    status: varchar("status", { enum: ["open", "attention", "closed"] })
      .notNull()
      .default("open"),
    unreadCount: integer("unreadCount").notNull().default(0),
    lastMessagePreview: text("lastMessagePreview").notNull().default(""),
    lastMessageAt: timestamp("lastMessageAt").notNull(),
    source: varchar("source", { enum: ["manual", "webhook"] })
      .notNull()
      .default("manual"),
    assignedOperatorLabel: text("assignedOperatorLabel"),
    linkedLeadId: text("linkedLeadId"),
    backendConversationId: text("backendConversationId"),
    leadContext: jsonb("leadContext").$type<WhatsAppLinkedLeadContext>(),
    opsState: jsonb("opsState")
      .$type<WhatsAppOpsState>()
      .notNull()
      .default(sql`'{}'::jsonb`),
    agentState: jsonb("agentState")
      .$type<WhatsAppAgentState>()
      .notNull()
      .default(sql`'{}'::jsonb`),
  },
  (table) => ({
    contactPhoneIdx: uniqueIndex("whatsapp_contact_phone_idx").on(
      table.contactPhone
    ),
  })
);

export type WhatsAppConversation = InferSelectModel<typeof whatsappConversation>;

export const whatsappMessage = pgTable("WhatsAppMessage", {
  id: uuid("id").primaryKey().notNull().defaultRandom(),
  conversationId: uuid("conversationId")
    .notNull()
    .references(() => whatsappConversation.id),
  direction: varchar("direction", { enum: ["incoming", "outgoing"] }).notNull(),
  authorType: varchar("authorType", {
    enum: ["contact", "bot", "human", "system"],
  })
    .notNull()
    .default("contact"),
  authorLabel: text("authorLabel").notNull(),
  body: text("body").notNull(),
  providerMessageId: text("providerMessageId"),
  status: varchar("status", {
    enum: [
      "received",
      "queued",
      "sent",
      "delivered",
      "read",
      "failed",
      "draft",
    ],
  })
    .notNull()
    .default("draft"),
  errorText: text("errorText"),
  createdAt: timestamp("createdAt").notNull(),
});

export type WhatsAppMessage = InferSelectModel<typeof whatsappMessage>;
