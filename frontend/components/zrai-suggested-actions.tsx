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
      className="flex w-full snap-x gap-2 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:gap-2 sm:overflow-visible sm:pb-0"
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
            className="h-auto min-h-0 w-[158px] shrink-0 snap-start whitespace-normal rounded-xl p-2 text-left sm:w-full sm:min-h-[88px] sm:rounded-2xl sm:p-3"
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
              <span className="line-clamp-2 font-medium text-[13px] leading-4 sm:text-base sm:leading-5">{item.title}</span>
              <span className="mt-0.5 line-clamp-1 text-[10px] text-zinc-500 sm:text-xs">{item.label}</span>
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
