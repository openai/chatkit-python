# Keep your app in sync with ChatKit

Use ChatKit’s client events to mirror runtime state into your host app so you can restore threads, gate your own UI, and safely call imperative helpers.

At a high level:

- Track the active `threadId` so you can restore the same thread after navigation or reloads.
- Track loading and responding state to disable your own controls while ChatKit is busy.

## Track the active thread

Use `onThreadChange` to mirror ChatKit’s active thread into your own app state or router. Persist the `threadId` wherever you keep session state (for example, URL params, Redux, or local storage) so you can restore it later.

## Track loading and responding state

ChatKit exposes lifecycle events for thread loading and response streaming. Use them to:

- Disable custom toolbars, buttons, or navigation while a response is in flight.
- Avoid calling imperative helpers while ChatKit is already doing work.

## Wire it all together in `useChatKit`

Here’s a minimal React inbox that mirrors thread and loading state:

```tsx
import {ChatKit, useChatKit} from "@openai/chatkit-react";

export function Inbox({clientToken}: { clientToken: string }) {
  const {
    control,
    sendUserMessage,
    focusComposer,
    setThreadId,
  } = useChatKit({
    // ... your normal options (api, history, composer, etc.)

    onThreadChange: ({threadId}) => setActiveThread(threadId),

    onThreadLoadStart: () => setIsLoading(true),
    onThreadLoadEnd: () => setIsLoading(false),

    onResponseStart: () => setIsResponding(true),
    onResponseEnd: () => setIsResponding(false),
  });

  const isBusy = isLoading || isResponding;

  return (
    <>
      <Toolbar
        disabled={isBusy}
        onNewThread={() => !isBusy && setThreadId(undefined)}
        onFocusComposer={() => !isBusy && focusComposer()}
        onSendQuickMessage={(text) =>
          !isBusy && sendUserMessage({text})
        }
      />
      <ChatKit control={control} />
    </>
  );
}
```

## Guard imperative helpers when ChatKit is busy

Commands such as `sendUserMessage`, `focusComposer`, and `setThreadId` can reject if called during a thread load or while a response is streaming.

Use your mirrored `isLoading` / `isResponding` state to:

- Avoid calling commands when ChatKit is busy (as in the example above).
- Disable your own buttons or menu items until ChatKit finishes.
- Show “working…” affordances that line up with the actual ChatKit lifecycle.

## Hook in your own UI state

Once you have `threadId`, `isLoading`, and `isResponding` mirrored into your app, use them to drive your own UI; for example, disabling controls while ChatKit is busy or restoring the last active thread after navigation or reloads.

