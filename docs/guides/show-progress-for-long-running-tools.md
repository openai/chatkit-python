# Show progress for long-running tools

Long-running tools can feel stalled without feedback. Use progress updates for lightweight status pings and workflows for structured, persisted task checklists.

|                     | Progress updates (`ProgressUpdateEvent`) | Workflow items (`Workflow`, `WorkflowTask*`) |
|---------------------|------------------------------------------|----------------------------------------------|
| Purpose             | Quick, ephemeral status text             | Structured list of tasks with statuses       |
| Persistence         | Not saved to the thread                  | Persisted as thread items                    |
| UI                  | Inline, transient shimmer text           | Collapsible checklist widget                 |
| When new content streams | Automatically cleared and replaced by streamed content | Remains visible above the streamed content       |
| Best for            | Reporting current phase ("Indexing…")    | Multi-step plans users may revisit later     |
| How to emit         | `ctx.context.stream(ProgressUpdateEvent(...))` | `start_workflow`, `add_workflow_task`, `update_workflow_task`, `end_workflow` |

## Progress updates

Emit `ProgressUpdateEvent` when you need lightweight, real-time status. They stream immediately to the client and disappear after the turn—they are not stored in the thread.

### From tools

Inside a tool, use `AgentContext.stream` to enqueue progress events. They are delivered to the client immediately and are not persisted as thread items.

```python
from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext
from chatkit.types import ProgressUpdateEvent

@function_tool()
async def ingest_files(ctx: RunContextWrapper[AgentContext], paths: list[str]):
    await ctx.context.stream(ProgressUpdateEvent(icon="upload", text="Uploading..."))
    await upload(paths)

    await ctx.context.stream(
        ProgressUpdateEvent(icon="search", text="Indexing and chunking...")
    )
    await index_files(paths)

    await ctx.context.stream(ProgressUpdateEvent(icon="check", text="Done"))
```

`stream_agent_response` will forward these events for you alongside any assistant text or tool call updates.

### From custom pipelines

If you are not using the Agents SDK, yield `ProgressUpdateEvent` directly from the `respond` or `action` methods while your backend works:

```python
async def respond(...):
    yield ProgressUpdateEvent(icon="search", text="Searching tickets...")
    results = await search_tickets()

    yield ProgressUpdateEvent(icon="code", text="Generating summary...")
    yield from await stream_summary(results)
```

Use short, action-oriented messages and throttle updates to meaningful stages instead of every percent to avoid noisy streams.

## Workflow items

Use workflows when you want a persisted, user-visible checklist of tasks. They render as a widget in the transcript and survive after the turn. Combine with progress updates if you need both a checklist and lightweight status text.

Workflows support multiple task variants (custom, search, thought, file, image); see [`Task`](../../../api/chatkit/types/#chatkit.types.Task). Summaries shown when closing a workflow use [`WorkflowSummary`](../../../api/chatkit/types/#chatkit.types.WorkflowSummary) (for example, `CustomSummary` in the snippet below).

Example streaming workflow updates using `AgentContext` helpers:

```python
from agents import RunContextWrapper, function_tool
from chatkit.agents import AgentContext
from chatkit.types import CustomSummary, CustomTask, Workflow

@function_tool()
async def long_running_tool_with_steps(ctx: RunContextWrapper[AgentContext]):
    # Create an empty workflow container
    await ctx.context.start_workflow(Workflow(type="custom", tasks=[]))

    # Add and update the first task
    discovery = CustomTask(title="Search data sources", status_indicator="loading")
    await ctx.context.add_workflow_task(discovery)

    # Run the first task
    await search_my_data_sources()

    await ctx.context.update_workflow_task(
        discovery.model_copy(update={"status_indicator": "complete"}), task_index=0
    )

    # Add a follow-up task
    summary = CustomTask(title="Summarize findings", status_indicator="loading")
    await ctx.context.add_workflow_task(summary)

    # Run the second task
    await summarize_my_findings()

    await ctx.context.update_workflow_task(
        summary.model_copy(update={"status_indicator": "complete"}), task_index=1
    )

    # Close the workflow and collapse it in the UI
    await ctx.context.end_workflow(
        summary=CustomSummary(title="Analysis complete"),
        expanded=False,
    )
```

Workflows are saved as thread items by `stream_agent_response` when you yield the associated events; they show up for all participants and remain visible in history.
