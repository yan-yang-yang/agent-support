# Extractable Components

## ChatScreen
- Source: `apps/web/src/components/chat/ChatScreen.tsx`
- Category: layout
- Description: Full-height mobile H5 chat shell with header, scrolling content, and composer.
- Extractable props: none today; future `activeConversationId` and `historyOpen` are state inputs.
- Hardcoded: Device shell geometry, mobile max width, background, safe-area treatment.

## ServiceHeader
- Source: `apps/web/src/components/chat/ServiceHeader.tsx`
- Category: layout
- Description: Service identity, AI status, and history/reset action.
- Extractable props: `disabled`, `onOpenHistory`.
- Hardcoded: Umbrella icon, title, online label, color and spacing classes.

## QuickActions
- Source: `apps/web/src/components/chat/QuickActions.tsx`
- Category: basic
- Description: Three public-umbrella support entry actions.
- Extractable props: `disabled`, `onSelect`.
- Hardcoded: Issue labels, helper text, icons, visual classes.

## BusinessCard
- Source: `apps/web/src/components/chat/BusinessCard.tsx`
- Category: basic
- Description: Rental, billing, and nearby-station structured result cards.
- Extractable props: `data` discriminated union.
- Hardcoded: Card labels, icons, colors, layout.

## ConversationHistorySheet
- Source: `apps/web/src/components/chat/ConversationHistorySheet.tsx`
- Category: layout
- Description: Right-side mobile drawer for creating, grouping, and switching persisted conversations.
- Extractable props: `open`, `conversations`, `activeConversationId`, `disabled`.
- Hardcoded: Drawer title, group labels, issue icon mapping, active-row styling.

## Sheet
- Source: `apps/web/src/components/ui/sheet.tsx`
- Category: basic
- Description: shadcn/ui-style Radix Dialog sheet primitive with dimmed overlay and right-side motion.
- Extractable props: `open`, `onOpenChange`, `className`.
- Hardcoded: Overlay color, drawer width, close control, transition classes.

## Button
- Source: `apps/web/src/components/ui/button.tsx`
- Category: basic
- Description: shadcn/ui-style button with default, ghost, and outline variants.
- Extractable props: `variant`, `size`, `disabled`.
- Hardcoded: Variant CSS classes.

## Card
- Source: `apps/web/src/components/ui/card.tsx`
- Category: basic
- Description: Rounded white bordered card surface and content wrapper.
- Extractable props: `className`.
- Hardcoded: Base radius, border, shadow, and padding.
