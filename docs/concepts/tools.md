# Tools

Tools let the assistant call into your application logic during a turn—for example to search data, run a workflow, or fetch the user’s current context—then feed the results back into the model.

At a high level:

- **Server tools** run on your backend. The assistant calls them through your inference pipeline, and you stream their results back into the conversation.
- **Client tools** run in the browser or host app. ChatKit surfaces a tool call as a streamed thread item, lets the client handle it, then resumes the conversation with the tool’s output.

## Server tools

Server tools are ordinary Python functions you register with your inference setup (for example, as tools on an agent or as explicit steps in your pipeline). During inference, the model can decide to call them; ChatKit serializes the call, runs your function, and feeds the output back to the model.

Use server tools to:

- Look up data in your own APIs or databases.
- Kick off long-running jobs while streaming progress updates.
- Update your own domain state (tickets, orders, files, etc.) in response to a turn.

From the model’s perspective, tools are structured, named capabilities it can invoke instead of guessing from free text.

## Client tools

Some operations can only run on the client—for example:

- Reading the current selection in a canvas or document.
- Inspecting local application state that never leaves the browser.
- Calling into the host app (for example, a design tool or IDE) via its own APIs.

Client tools let the model request that kind of data mid-turn:

- On the server, you instruct your inference pipeline to stop when a specific tool is called (for example, by using `StopAtTools` around that tool).
- ChatKit turns the tool call into a streamed thread item.
- On the client, `onClientTool` receives that item, runs your callback, and returns a JSON result.
- ChatKit sends the result back to the server, which starts a new stream to continue the run with the tool output included as model input.

Use client tools when the model needs fresh, local context it cannot safely obtain from server-side state alone.
