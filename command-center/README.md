# Nexa: AI Command Center (hackathon foundation)

A domain-neutral React + TypeScript frontend for an "AI command center". It runs entirely on mock data.

```bash
npm install
npm run dev      # http://localhost:5190
npm run build    # typecheck + production build
```

## Map

| Area | File |
| --- | --- |
| Product name, headline, all mock data, fake AI (`askAI`) | `src/data.ts` |
| Global state: tasks, toasts, palette, AI busy, chat history, live events | `src/store.tsx` |
| Design tokens and every style | `src/styles.css` (`:root` at the top) |
| Routes | `src/main.tsx` |
| Shell: top bar, sidebar, context panel, palette, create-task modal | `src/pages/AppShell.tsx` |

Components (`src/components`): `CommandPalette`, `Sidebar`/`BottomNav`, `TopBar`, `StatusIndicator` (`StatusDot`, `SystemStatus`), `MetricCard`, `IntelligencePanel`, `AI` (`AIConsole`, `AIInput`, `AIMessage`, `AIThinking`, `RichText`), `DataCard`/`Segmented`, `Chart` (`LineChart`, `Sparkline`, `ActivityGraph`, `Ring`, `Progress`), `Timeline`, `ActivityFeed`, `Modal`, `Toast`, `Tooltip`/`Kbd`, `States` (`EmptyState`, `ErrorState`, `LoadingState`, `Skeleton`), `IntelligenceCore` (landing canvas).

## Adapting to the problem statement

1. **Rename the nouns** in `src/data.ts`: `Task`, `Insight`, `DataRecord`, `Source`, `ActivityEvent`. Update `product` and `currentProject`.
2. **Replace the primary workspace.** `src/pages/Workspace.tsx` renders `<AIConsole/>`. Swap in a camera feed, map, document viewer and so on. Every panel is a `DataCard`, so the layout stays the same.
3. **Make the AI real.** Replace the body of `askAI()` in `src/data.ts`. Keep the `AIResponse` shape (content, sources, actions, confidence, trace) and the UI keeps working.
4. **Re-skin** with `--accent` / `--violet` in `:root`. The canvas uses matching RGB constants at the top of `IntelligenceCore.tsx`.
5. **Navigation** lives in `navItems` (`Sidebar.tsx`), the palette `commands` (`CommandPalette.tsx`) and the routes (`main.tsx`).

## Demo tips

- `Ctrl/⌘ K` opens the palette. Typing anything offers "Ask Nexa: …".
- Single-key shortcuts (outside of text fields): `N` new task, `A` ask, `R` run analysis, `,` settings.
- A prompt containing "fail" or "error" shows the AI error state.
- **Data → Simulate outage** shows the error state. A filter with no matches shows the empty state.
- **Intelligence → Pinned** shows the empty state.
