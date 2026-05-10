/**
 * ZRAI Lead OS - Suggested Actions Component
 * 
 * ZRAI-specific quick actions for the chat interface.
 */

'use client';

import type { UseChatHelpers } from '@ai-sdk/react';
import { motion } from 'framer-motion';
import { memo } from 'react';
import { ZRAI_SUGGESTED_ACTIONS } from '@/lib/zrai/constants';
import type { ChatMessage } from '@/lib/types';
import { Suggestion } from './elements/suggestion';
import type { VisibilityType } from './visibility-selector';

type ZRAISuggestedActionsProps = {
  chatId: string;
  sendMessage: UseChatHelpers<ChatMessage>['sendMessage'];
  selectedVisibilityType: VisibilityType;
};

function PureZRAISuggestedActions({ chatId, sendMessage }: ZRAISuggestedActionsProps) {
  return (
    <div
      className="grid w-full gap-2 sm:grid-cols-2"
      data-testid="zrai-suggested-actions"
    >
      {ZRAI_SUGGESTED_ACTIONS.map((item, index) => (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          initial={{ opacity: 0, y: 20 }}
          key={item.action}
          transition={{ delay: 0.05 * index }}
        >
          <Suggestion
            className="h-auto w-full whitespace-normal p-3 text-left"
            onClick={() => {
              window.history.pushState({}, '', `/chat/${chatId}`);
              sendMessage({
                role: 'user',
                parts: [{ type: 'text', text: item.action }],
              });
            }}
            suggestion={item.action}
          >
            <div className="flex flex-col">
              <span className="font-medium">{item.title}</span>
              <span className="text-xs text-zinc-500">{item.label}</span>
            </div>
          </Suggestion>
        </motion.div>
      ))}
    </div>
  );
}

export const ZRAISuggestedActions = memo(
  PureZRAISuggestedActions,
  (prevProps, nextProps) => {
    if (prevProps.chatId !== nextProps.chatId) {
      return false;
    }
    if (prevProps.selectedVisibilityType !== nextProps.selectedVisibilityType) {
      return false;
    }

    return true;
  }
);
