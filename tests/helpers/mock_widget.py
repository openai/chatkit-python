import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, AsyncIterator, Callable, Literal, assert_never
from pathlib import Path
from agents import Agent, Runner
from anyio import sleep
from pydantic import BaseModel, Field, TypeAdapter

from chatkit.actions import Action, ActionConfig
from chatkit.types import ThreadStreamEvent
from chatkit.widgets import (
    Box,
    Button,
    Card,
    Col,
    DatePicker,
    Divider,
    Icon,
    Image,
    ListView,
    ListViewItem,
    Markdown,
    Row,
    Select,
    Spacer,
    Text,
    Title,
    Transition,
    WidgetComponent,
    WidgetRoot,
    WidgetStatus,
)

from .email_data import (
    BRAINSTORM_SESSION,
    CHATKIT_ROADMAP,
    FLIGHT_REMINDER,
)

# HELPERS


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


chatkit_address = os.getenv("CHATKIT_ADDRESS") or "http://localhost:3000"


def asset(path: str) -> str:
    """
    Helper function to create an asset URL.
    """
    return f"{chatkit_address}/{path}"


## STATE MODELS


class DraftTask(BaseModel):
    title: str
    description: str
    priority: Literal["low", "high"] = "low"
    timeframe: Literal["today", "tomorrow", "week", "month", "custom"] = "tomorrow"
    due_date: datetime | None = None

    def model_post_init(self, __context) -> None:
        if self.due_date is None:
            self.due_date = self._calculate_due_date()

    def _calculate_due_date(self) -> datetime:
        now = datetime.now()
        if self.timeframe == "today":
            return now.replace(hour=23, minute=59, second=59, microsecond=0)
        elif self.timeframe == "tomorrow":
            return (now + timedelta(days=1)).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
        elif self.timeframe == "week":
            # End of this week (Sunday)
            days_until_sunday = 6 - now.weekday()
            return (now + timedelta(days=days_until_sunday)).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
        elif self.timeframe == "month":
            # End of this month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            return (next_month - timedelta(days=1)).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
        else:  # custom - treat as today for now
            return now.replace(hour=23, minute=59, second=59, microsecond=0)

    def priority_color(self) -> str:
        if self.priority == "high":
            return "red-400"
        return "secondary"

    def urgency_color(self) -> str:
        if self.due_date is None:
            self.due_date = self._calculate_due_date()

        now = datetime.now(self.due_date.tzinfo)
        due = self.due_date
        days_until_due = (due - now).days

        if days_until_due < 1:
            return "red-400"

        if days_until_due < 3:
            return "yellow-600"

        return "secondary"

    def humanized_due_date(self) -> str:
        if self.due_date is None:
            self.due_date = self._calculate_due_date()

        now = datetime.now(self.due_date.tzinfo)
        due = self.due_date

        # Check if it's overdue
        if due < now:
            days_overdue = (now - due).days
            if days_overdue == 0:
                return "Due today"
            elif days_overdue == 1:
                return "Due yesterday"
            else:
                return f"Due {days_overdue} days ago"

        # Check future dates
        days_until_due = (due - now).days

        if days_until_due == 0:
            return "Due today"
        elif days_until_due == 1:
            return "Due tomorrow"
        elif days_until_due <= 7:
            return f"Due in {days_until_due} days"
        elif days_until_due <= 14:
            return "Due next week"
        else:
            return f"Due on {due.strftime('%b %d')}"


class DraftCalendarEvent(BaseModel):
    title: str
    description: str
    date: str
    start_time: str
    end_time: str
    calendar: Literal["Work", "Personal"]

    def calendar_color(self) -> str:
        return "blue-400" if self.calendar == "Work" else "red-400"

    def time(self) -> str:
        return f"{self.start_time} - {self.end_time}"


class DraftEmail(BaseModel):
    subject: str
    body: str
    to: str


class Email(DraftEmail):
    id: str = Field(default_factory=lambda: _gen_id("email"))
    sender_image: str
    sender: str
    sender_type: Literal["org", "person"]
    sent_at: str


class Task(DraftTask):
    id: str = Field(default_factory=lambda: _gen_id("task"))
    completed: bool


class CalendarEvent(DraftCalendarEvent):
    id: str = Field(default_factory=lambda: _gen_id("event"))


class BaseWidgetView(BaseModel):
    status_text: str | None = None
    status_icon: str = "favicon.svg"
    collapsed: bool = False

    def status(self) -> WidgetStatus | None:
        if not self.status_text:
            return None
        return {"text": self.status_text, "favicon": asset(self.status_icon)}


class EmailDraft(BaseWidgetView):
    type: Literal["email_draft"] = Field(default="email_draft", frozen=True)
    email: DraftEmail
    streaming: bool
    status_icon: str = "gmail-send-status-icon.png"


class EmailView(BaseWidgetView):
    type: Literal["email_view"] = Field(default="email_view", frozen=True)
    email: Email
    show_back_button: bool
    status_icon: str = "gmail-status-icon.png"


class EmailsList(BaseWidgetView):
    type: Literal["emails_list"] = Field(default="emails_list", frozen=True)
    emails: list[Email]
    status_icon: str = "gmail-status-icon.png"


class TaskDraft(BaseWidgetView):
    type: Literal["task_draft"] = Field(default="task_draft", frozen=True)
    todo: DraftTask
    status_icon: str = "linear-status-icon.png"


class TaskView(BaseWidgetView):
    type: Literal["task_view"] = Field(default="task_view", frozen=True)
    task: Task
    show_back_button: bool
    status_icon: str = "linear-status-icon.png"


class TasksList(BaseWidgetView):
    type: Literal["tasks_list"] = Field(default="tasks_list", frozen=True)
    tasks: list[Task]
    status_icon: str = "linear-status-icon.png"


class CalendarEventDraft(BaseWidgetView):
    type: Literal["calendar_event_draft"] = Field(
        default="calendar_event_draft", frozen=True
    )
    event: DraftCalendarEvent
    status_icon: str = "calendar-status-icon.png"


class CalendarEventView(BaseWidgetView):
    type: Literal["calendar_event_view"] = Field(
        default="calendar_event_view", frozen=True
    )
    event: CalendarEvent
    show_back_button: bool
    status_icon: str = "calendar-status-icon.png"


class CalendarEventsList(BaseWidgetView):
    type: Literal["calendar_events_list"] = Field(
        default="calendar_events_list", frozen=True
    )
    events: list[CalendarEvent]
    status_icon: str = "calendar-status-icon.png"


class Index(BaseWidgetView):
    type: Literal["index"] = Field(default="index", frozen=True)
    selected: Literal["email", "calendar", "tasks", "index"]

    def get_section_icon(self, section: str) -> str:
        """Get the appropriate icon for each section"""
        icon_map = {
            "email": "gmail-status-icon.png",
            "calendar": "calendar-status-icon.png",
            "tasks": "linear-status-icon.png",
            "index": "favicon.svg",
        }
        return icon_map.get(section, "favicon.svg")

    def __init__(self, **data):
        super().__init__(**data)
        # Set status_icon based on current selection
        if self.selected:
            self.status_icon = self.get_section_icon(self.selected)
        else:
            self.status_icon = "favicon.svg"


State = Annotated[
    EmailDraft
    | EmailView
    | EmailsList
    | TaskDraft
    | TaskView
    | TasksList
    | CalendarEventDraft
    | CalendarEventView
    | CalendarEventsList
    | Index,
    Field(discriminator="type"),
]


## ACTIONS


class BasePayload(BaseModel):
    widget_id: str


class ShowWidgetPayload(BasePayload):
    widget: Literal["email", "calendar", "tasks", "index"]


class SendEmailPayload(BasePayload):
    email: DraftEmail


class ViewEmailPayload(BasePayload):
    email_id: str


class UpdateDraftTaskPayload(BasePayload):
    todo: DraftTask


class CreateTaskPayload(BasePayload):
    todo: DraftTask


class ViewTaskPayload(BasePayload):
    task_id: str


class ToggleTaskCompletePayload(BasePayload):
    task_id: str


class CreateEventPayload(BasePayload):
    event: DraftCalendarEvent


class ViewEventPayload(BasePayload):
    event_id: str


ShowWidgetAction = Action[Literal["sample.show_widget"], ShowWidgetPayload]
DraftEmailAction = Action[Literal["sample.draft_email"], BasePayload]
ShowInboxAction = Action[Literal["sample.show_inbox"], BasePayload]
SendEmailAction = Action[Literal["sample.send_email"], SendEmailPayload]
DiscardEmailAction = Action[Literal["sample.discard_email"], BasePayload]
ViewEmailAction = Action[Literal["sample.view_email"], ViewEmailPayload]
DraftTaskAction = Action[Literal["sample.draft_task"], BasePayload]
UpdateDraftTaskAction = Action[
    Literal["sample.update_draft_task"], UpdateDraftTaskPayload
]
CreateTaskAction = Action[Literal["sample.create_task"], CreateTaskPayload]
CancelTaskAction = Action[Literal["sample.cancel_task"], BasePayload]
ViewTasksAction = Action[Literal["sample.view_tasks"], BasePayload]
ViewTaskAction = Action[Literal["sample.view_task"], ViewTaskPayload]
ToggleTaskCompleteAction = Action[
    Literal["sample.toggle_task_complete"], ToggleTaskCompletePayload
]
DraftEventAction = Action[Literal["sample.draft_event"], BasePayload]
CreateEventAction = Action[Literal["sample.create_event"], CreateEventPayload]
DiscardEventAction = Action[Literal["sample.discard_event"], BasePayload]
ViewScheduleAction = Action[Literal["sample.view_schedule"], BasePayload]
ViewEventAction = Action[Literal["sample.view_event"], ViewEventPayload]


SampleWidgetAction = Annotated[
    ShowWidgetAction
    | DraftEmailAction
    | ShowInboxAction
    | SendEmailAction
    | DiscardEmailAction
    | ViewEmailAction
    | DraftTaskAction
    | CreateTaskAction
    | CancelTaskAction
    | ViewTasksAction
    | ViewTaskAction
    | ToggleTaskCompleteAction
    | UpdateDraftTaskAction
    | DraftEventAction
    | CreateEventAction
    | DiscardEventAction
    | ViewScheduleAction
    | ViewEventAction,
    Field(discriminator="type"),
]

ActionAdapter: TypeAdapter[SampleWidgetAction] = TypeAdapter(SampleWidgetAction)


email_generator = Agent(
    model="gpt-4.1",
    name="Description generator",
    instructions="""Generate an email about a given subject. Do not include any other text than the email. Do not include the subject itself. The email should end with "\n\nThanks,\nZach"
    """,
)


class ActionOutput(BaseModel):
    widget: WidgetRoot | None = None
    event: ThreadStreamEvent | None = None

    @staticmethod
    def from_event(event: ThreadStreamEvent) -> "ActionOutput":
        return ActionOutput(widget=None, event=event)

    @staticmethod
    def from_widget(widget: WidgetRoot) -> "ActionOutput":
        return ActionOutput(widget=widget, event=None)


class SampleWidget(BaseModel):
    id: str = Field(default_factory=lambda: _gen_id("wig"))
    emails: list[Email] = []
    tasks: list[Task] = []
    events: list[CalendarEvent] = []
    state: State = Index(selected="index", status_text="Fetched widgets")

    @staticmethod
    def parse_action(action: Action[str, Any]) -> SampleWidgetAction:
        return ActionAdapter.validate_python(action.model_dump())

    def load_events(self):
        self.events = [
            CalendarEvent(
                title="Dentist appointment",
                description="Regular checkup and cleaning",
                date="Wed, July 16",
                start_time="2:00",
                end_time="3:00 PM",
                calendar="Personal",
            ),
            CalendarEvent(
                title="Team standup",
                description="Daily team sync meeting",
                date="Thu, July 17",
                start_time="3:30",
                end_time="4:00 PM",
                calendar="Work",
            ),
            CalendarEvent(
                title="Q3 roadmap review",
                description="Quarterly planning session",
                date="Fri, July 18",
                start_time="9:00",
                end_time="10:30 AM",
                calendar="Work",
            ),
            CalendarEvent(
                title="Lunch with Sarah",
                description="Catch up over lunch",
                date="Sat, July 19",
                start_time="12:00",
                end_time="1:30 PM",
                calendar="Personal",
            ),
        ]

    def load_emails(self):
        self.emails = [
            Email(
                sender="David Weedon",
                sender_image=asset("david.png"),
                sender_type="person",
                subject="ChatKit Roadmap",
                body=CHATKIT_ROADMAP,
                to="zach@chatkit.studio",
                sent_at="8:40 AM",
            ),
            Email(
                sender="United Airlines",
                sender_image=asset("united.png"),
                sender_type="org",
                subject="Quick reminders about your upcoming trip to San Francisco",
                body=FLIGHT_REMINDER,
                to="zach@chatkit.studio",
                sent_at="8:12 AM",
            ),
            Email(
                sender="Tyler Smith",
                sender_image=asset("tyler.png"),
                sender_type="person",
                subject="re: Morning brainstorm",
                body=BRAINSTORM_SESSION,
                to="zach@chatkit.studio",
                sent_at="Yesterday",
            ),
        ]

    def load_tasks(self):
        self.tasks = [
            Task(
                title="Add source annotations to responses",
                description="Implement source annotations feature to add context to assistant responses. This is currently marked as 'In progress' in the roadmap.",
                priority="high",
                timeframe="today",
                completed=False,
            ),
            Task(
                title="Fix mobile web scrolling issues",
                description="Address the rough mobile web experience, particularly scrolling and input caret tracking issues mentioned in known issues.",
                priority="high",
                timeframe="tomorrow",
                completed=False,
            ),
            Task(
                title="Implement graceful page refresh handling",
                description="Fix the issue where refreshing the page while waiting for an assistant message causes the message to be dropped entirely.",
                priority="high",
                timeframe="week",
                completed=False,
            ),
            Task(
                title="Design enhanced interactive widgets",
                description="Develop richer interactive elements for the widget system. This is planned for the upcoming roadmap.",
                priority="high",
                timeframe="month",
                completed=True,
            ),
            Task(
                title="Add robust attachment error handling",
                description="Implement proper error handling for attachments to prevent items from staying in uploading state indefinitely.",
                priority="high",
                timeframe="week",
                completed=False,
            ),
            Task(
                title="Implement source scope selection",
                description="Add the ability for users to choose specific data sources when interacting with the assistant.",
                priority="low",
                timeframe="month",
                completed=False,
            ),
            Task(
                title="Add custom fonts support",
                description="Enable users to use different typefaces in their ChatKit interface. This is planned for customization features.",
                priority="low",
                timeframe="month",
                completed=False,
            ),
            Task(
                title="Implement dark mode theme switching",
                description="Complete the theme switching functionality between light and dark modes with proper system integration.",
                priority="low",
                timeframe="tomorrow",
                completed=True,
            ),
            Task(
                title="Set up ChatKit Explorer development environment",
                description="Configure the complete development setup including dependencies, environment variables, and make commands for local development.",
                priority="low",
                timeframe="today",
                completed=True,
            ),
        ]

    def render(
        self,
        state: State | None = None,
    ) -> WidgetRoot:
        if state is not None:
            self.state = state

        if self.state.type == "index":
            return render_index(self.id, self.state)
        if self.state.type == "email_draft":
            return render_email_draft(self.id, self.state)
        if self.state.type == "email_view":
            return render_email_view(self.id, self.state)
        if self.state.type == "emails_list":
            return render_emails_list(self.id, self.state)
        if self.state.type == "task_draft":
            return render_task_draft(self.id, self.state)
        if self.state.type == "task_view":
            return render_task_view(self.id, self.state)
        if self.state.type == "tasks_list":
            return render_tasks_list(self.id, self.state)
        if self.state.type == "calendar_event_draft":
            return render_calendar_event_draft(self.id, self.state)
        if self.state.type == "calendar_event_view":
            return render_calendar_event_view(self.id, self.state)
        if self.state.type == "calendar_events_list":
            return render_calendar_events_list(self.id, self.state)

        assert_never(self.state)

    def render_with_status(self, text: str | None) -> WidgetRoot:
        self.state.status_text = text
        return self.render()

    async def save_and_generate(
        self,
        next_state: State,
        generate: Callable[[], AsyncIterator[ThreadStreamEvent]],
        save: Callable[[], AsyncIterator[ThreadStreamEvent]],
    ):
        async for event in save():
            yield ActionOutput.from_event(event)

        first = True
        async for event in generate():
            if first:
                first = False
                yield ActionOutput.from_widget(self.render(next_state))
            yield ActionOutput.from_event(event)

    async def handle_action(
        self,
        action: SampleWidgetAction,
        generate: Callable[[], AsyncIterator[ThreadStreamEvent]],
        save: Callable[[], AsyncIterator[ThreadStreamEvent]],
    ) -> AsyncIterator[ActionOutput]:
        if action.type == "sample.show_widget":
            next_state = Index(
                selected=action.payload.widget,
                status_text=f"Fetched {action.payload.widget} widget"
                if action.payload.widget != "index"
                else "Fetched widgets",
            )
            yield ActionOutput.from_widget(self.render(next_state))
            
        
        elif action.type == "sample.draft_email":
            readme_path = Path(__file__).parent.parent.parent / "README.md"
            with open(readme_path, "r") as f:
                readme = f.read()

            body_text = Runner.run_streamed(
                email_generator,
                "Draft an email asking David about the current status of the ChatKit roadmap. Keep it short and high level, ask questions about some of the items in the readme. Current status in the README:\n\n"
                + readme,
            )

            next_email_state: EmailDraft = EmailDraft(
                status_text="Drafting email",
                email=DraftEmail(
                    subject="ChatKit Roadmap",
                    body="",
                    to="david@chatkit.studio",
                ),
                streaming=True,
            )
            yield ActionOutput.from_widget(self.render(next_email_state))

            async for event in body_text.stream_events():
                if event.type == "raw_response_event":
                    if event.data.type == "response.output_text.delta":
                        next_email_state.email.body += event.data.delta
                        next_email_state.streaming = True
                        yield ActionOutput.from_widget(self.render(next_email_state))

            next_email_state.status_text = "Drafted email"
            next_email_state.streaming = False
            yield ActionOutput.from_widget(self.render(next_email_state))

        elif action.type == "sample.show_inbox":
            if not self.emails:
                yield ActionOutput.from_widget(
                    self.render_with_status("Fetching inbox")
                )
                await sleep(2)
                self.load_emails()
            next_state = EmailsList(status_text="Fetched inbox", emails=self.emails)
            yield ActionOutput.from_widget(self.render(next_state))

        elif action.type == "sample.send_email":
            if self.state.type != "email_draft":
                raise ValueError("Invalid state for sending email")
            self.state.email = action.payload.email
            self.state.status_text = "Sending"
            yield ActionOutput.from_widget(self.render())
            email = Email(
                sender="Zach Johnston",
                sender_image=asset("zach.png"),
                sender_type="person",
                sent_at="Just now",
                subject=action.payload.email.subject,
                body=action.payload.email.body,
                to=action.payload.email.to,
            )
            next_state = EmailView(
                status_text="Sent email",
                status_icon="gmail-send-status-icon.png",
                email=email,
                show_back_button=False,
            )
            async for event in self.save_and_generate(next_state, generate, save):
                yield event

        elif action.type == "sample.discard_email":
            yield ActionOutput.from_widget(self.render_with_status("Discarding"))
            self.state.status_text = "Discarded email draft"
            self.state.collapsed = True
            async for event in self.save_and_generate(self.state, generate, save):
                yield event

        elif action.type == "sample.view_email":
            for email in self.emails:
                if email.id == action.payload.email_id:
                    next_state = EmailView(
                        status_text=self.state.status_text,
                        email=email,
                        show_back_button=True,
                    )
                    yield ActionOutput.from_widget(self.render(next_state))
                    break
            else:
                raise ValueError(f"Email with id {action.payload.email_id} not found")

        elif action.type == "sample.draft_task":
            next_state = TaskDraft(
                status_text="Drafted task",
                todo=DraftTask(
                    title="Design resizable popup mode",
                    description="Create a design proposal for how ChatKit's popup mode can support dynamic height and user resizing.",
                    priority="low",
                    timeframe="tomorrow",
                ),
            )
            yield ActionOutput.from_widget(self.render(next_state))

        elif action.type == "sample.create_task":
            if self.state.type != "task_draft":
                raise ValueError("Invalid state for creating task")
            self.state.todo = action.payload.todo
            self.state.status_text = "Creating task"
            yield ActionOutput.from_widget(self.render())
            task = Task(
                title=action.payload.todo.title,
                description=action.payload.todo.description,
                priority=action.payload.todo.priority,
                timeframe=action.payload.todo.timeframe,
                due_date=action.payload.todo.due_date,
                completed=False,
            )
            self.tasks.append(task)
            next_state = TaskView(
                status_text="Created task",
                task=task,
                show_back_button=False,
            )
            async for event in self.save_and_generate(next_state, generate, save):
                yield event

        elif action.type == "sample.cancel_task":
            yield ActionOutput.from_widget(self.render_with_status("Discarding"))
            self.state.status_text = "Discarded task draft"
            self.state.collapsed = True
            async for event in self.save_and_generate(self.state, generate, save):
                yield event

        elif action.type == "sample.view_tasks":
            if not self.tasks:
                yield ActionOutput.from_widget(
                    self.render_with_status("Fetching tasks")
                )
                await sleep(2)
                self.load_tasks()
            next_state = TasksList(status_text="Fetched tasks", tasks=self.tasks)
            yield ActionOutput.from_widget(self.render(next_state))

        elif action.type == "sample.view_task":
            for task in self.tasks:
                if task.id == action.payload.task_id:
                    next_state = TaskView(
                        status_text=self.state.status_text,
                        task=task,
                        show_back_button=True,
                    )
                    yield ActionOutput.from_widget(self.render(next_state))
                    break
            else:
                raise ValueError(f"Task with id {action.payload.task_id} not found")

        elif action.type == "sample.toggle_task_complete":
            for task in self.tasks:
                if task.id == action.payload.task_id:
                    task.completed = not task.completed
                    break
            else:
                raise ValueError(f"Task with id {action.payload.task_id} not found")

            if self.state.type == "tasks_list":
                self.state.tasks = self.tasks
            elif self.state.type == "task_view":
                self.state.task = task

            yield ActionOutput.from_widget(self.render())

        elif action.type == "sample.update_draft_task":
            if self.state.type != "task_draft":
                raise ValueError("Invalid draft task update")
            self.state.todo = action.payload.todo
            yield ActionOutput.from_widget(self.render())

        elif action.type == "sample.draft_event":
            next_state = CalendarEventDraft(
                status_text="Drafted calendar event",
                event=DraftCalendarEvent(
                    title="Q3 roadmap review",
                    description="Quarterly planning session to review and align on the Q3 roadmap.",
                    date="Wed 16",
                    start_time="9:00",
                    end_time="10:30 AM",
                    calendar="Work",
                ),
            )
            yield ActionOutput.from_widget(self.render(next_state))

        elif action.type == "sample.create_event":
            yield ActionOutput.from_widget(
                self.render_with_status("Creating calendar event")
            )
            event = CalendarEvent(
                title=action.payload.event.title,
                date=action.payload.event.date,
                start_time=action.payload.event.start_time,
                end_time=action.payload.event.end_time,
                description=action.payload.event.description,
                calendar=action.payload.event.calendar,
            )
            self.events.append(event)
            next_state = CalendarEventView(
                status_text="Added event to calendar",
                event=event,
                show_back_button=False,
            )
            async for event in self.save_and_generate(next_state, generate, save):
                yield event

        elif action.type == "sample.discard_event":
            yield ActionOutput.from_widget(self.render_with_status("Discarding"))
            self.state.status_text = "Discarded draft event"
            self.state.collapsed = True
            async for event in self.save_and_generate(self.state, generate, save):
                yield event

        elif action.type == "sample.view_schedule":
            if not self.events:
                yield ActionOutput.from_widget(
                    self.render_with_status("Fetching schedule")
                )
                await sleep(2)
                self.load_events()
            next_state = CalendarEventsList(
                status_text="Fetched schedule", events=self.events
            )
            yield ActionOutput.from_widget(self.render(next_state))

        elif action.type == "sample.view_event":
            for event in self.events:
                if event.id == action.payload.event_id:
                    next_state = CalendarEventView(
                        status_text=self.state.status_text,
                        event=event,
                        show_back_button=True,
                    )
                    yield ActionOutput.from_widget(self.render(next_state))
                    break
            else:
                raise ValueError(f"Event with id {action.payload.event_id} not found")

        else:
            assert_never(action)


# HELPER TEMPLATES


def back_button_list_item(action: ActionConfig):
    action.loadingBehavior = "container"
    return ListViewItem(
        onClickAction=action,
        gap=3,
        children=[
            Button(
                size="3xs",
                iconStart="chevron-left",
                color="primary",
                variant="soft",
                iconSize="sm",
                label="",
                pill=True,
                uniform=True,
                onClickAction=action,
            ),
            Text(value="Back", color="emphasis"),
        ],
    )


# INDEX TEMPLATES


def render_index(id: str, state: Index):
    if state.selected == "index":
        return render_widget_list(id, state)
    if state.selected == "email":
        return render_email_widget_list(id, state)
    if state.selected == "calendar":
        return render_calendar_widget_list(id, state)
    if state.selected == "tasks":
        return render_tasks_widget_list(id, state)

    assert_never(state.selected)


def render_widget_list(id: str, state: Index):
    return ListView(
        status=state.status(),
        key="index.pick",
        children=[
            ListViewItem(
                onClickAction=ShowWidgetAction.create(
                    ShowWidgetPayload(widget="email", widget_id=id),
                    loading_behavior="container",
                ),
                gap=3,
                children=[
                    Image(
                        src=asset("gmail-list-icon.png"),
                        size="60px",
                        frame=True,
                    ),
                    Col(
                        children=[
                            Text(
                                value="Email widget",
                                weight="medium",
                                color="emphasis",
                            ),
                            Text(
                                value="Craft and preview an email before sending",
                                color="secondary",
                            ),
                        ]
                    ),
                ],
            ),
            ListViewItem(
                onClickAction=ShowWidgetAction.create(
                    ShowWidgetPayload(widget="calendar", widget_id=id),
                    loading_behavior="container",
                ),
                gap=3,
                children=[
                    Image(
                        src=asset("calendar-list-icon.png"),
                        size="60px",
                        frame=True,
                    ),
                    Col(
                        children=[
                            Text(
                                value="Calendar widget",
                                weight="medium",
                                color="emphasis",
                            ),
                            Text(
                                value="Add events to your calendar",
                                color="secondary",
                            ),
                        ]
                    ),
                ],
            ),
            ListViewItem(
                onClickAction=ShowWidgetAction.create(
                    ShowWidgetPayload(widget="tasks", widget_id=id),
                    loading_behavior="container",
                ),
                gap=3,
                children=[
                    Image(
                        src=asset("linear-list-icon.png"),
                        size="60px",
                        frame=True,
                    ),
                    Col(
                        children=[
                            Text(
                                value="Tasks widget",
                                weight="medium",
                                color="emphasis",
                            ),
                            Text(
                                value="Manage your tasks and to-dos",
                                color="secondary",
                            ),
                        ]
                    ),
                ],
            ),
        ],
    )


def render_email_widget_list(id: str, state: Index):
    return ListView(
        status=state.status(),
        key="index.email",
        children=[
            back_button_list_item(
                ShowWidgetAction.create(ShowWidgetPayload(widget="index", widget_id=id))
            ),
            ListViewItem(
                onClickAction=ShowInboxAction.create(
                    BasePayload(widget_id=id), loading_behavior="container"
                ),
                gap=3,
                children=[
                    Image(
                        src=asset("gmail-inbox-icon.png"),
                        size="40px",
                        frame=True,
                    ),
                    Text(value="View inbox", color="emphasis"),
                ],
            ),
            ListViewItem(
                onClickAction=DraftEmailAction.create(BasePayload(widget_id=id)),
                gap=3,
                children=[
                    Image(
                        src=asset("gmail-send-icon.png"),
                        size="40px",
                        frame=True,
                    ),
                    Text(value="Send an email", color="emphasis"),
                ],
            ),
        ],
    )


def render_tasks_widget_list(id: str, state: Index):
    return ListView(
        status=state.status(),
        key="index.tasks",
        children=[
            back_button_list_item(
                action=ShowWidgetAction.create(
                    ShowWidgetPayload(widget="index", widget_id=id)
                )
            ),
            ListViewItem(
                onClickAction=ViewTasksAction.create(
                    BasePayload(widget_id=id), loading_behavior="container"
                ),
                gap=3,
                children=[
                    Image(src=asset("linear-view-icon.png"), size=40, frame=True),
                    Text(value="View tasks", color="emphasis"),
                ],
            ),
            ListViewItem(
                onClickAction=DraftTaskAction.create(
                    BasePayload(widget_id=id), loading_behavior="container"
                ),
                gap=3,
                children=[
                    Image(src=asset("linear-create-icon.png"), size=40, frame=True),
                    Text(value="Create a task", color="emphasis"),
                ],
            ),
        ],
    )


def render_calendar_widget_list(id: str, state: Index):
    return ListView(
        status=state.status(),
        key="index.calendar",
        children=[
            back_button_list_item(
                action=ShowWidgetAction.create(
                    ShowWidgetPayload(widget="index", widget_id=id)
                )
            ),
            ListViewItem(
                onClickAction=ViewScheduleAction.create(
                    BasePayload(widget_id=id), loading_behavior="container"
                ),
                gap=3,
                children=[
                    Image(
                        src=asset("calendar-schedule-icon.png"),
                        size="40px",
                        frame=True,
                    ),
                    Text(value="View schedule", color="emphasis"),
                ],
            ),
            ListViewItem(
                onClickAction=DraftEventAction.create(
                    BasePayload(widget_id=id), loading_behavior="container"
                ),
                gap=3,
                children=[
                    Image(
                        src=asset("calendar-create-icon.png"),
                        size="40px",
                        frame=True,
                    ),
                    Text(value="Create an event", color="emphasis"),
                ],
            ),
        ],
    )


# EMAIL TEMPLATES


def render_email_draft(id: str, state: EmailDraft):
    return Card(
        key="email.draft",
        size="lg",
        status=state.status(),
        collapsed=state.collapsed,
        asForm=True,
        confirm={
            "label": "Send email",
            "action": SendEmailAction.create(
                SendEmailPayload(email=state.email, widget_id=id),
                loading_behavior="self",
            ),
        }
        if not state.collapsed
        else None,
        cancel={
            "label": "Discard",
            "action": DiscardEmailAction.create(BasePayload(widget_id=id)),
        }
        if not state.collapsed
        else None,
        children=[
            Col(
                gap=3,
                children=[
                    Row(
                        gap=4,
                        align="baseline",
                        children=[
                            Text(
                                value="TO",
                                weight="semibold",
                                color="tertiary",
                                size="xs",
                                width=64,
                            ),
                            Text(value=state.email.to),
                        ],
                    ),
                    Divider(),
                    Row(
                        gap=4,
                        align="baseline",
                        children=[
                            Text(
                                value="SUBJECT",
                                weight="semibold",
                                color="tertiary",
                                size="xs",
                                width=64,
                            ),
                            Text(
                                value=state.email.subject,
                                editable={"name": "subject", "required": True}
                                if not state.collapsed
                                and state.status_text != "Sending"
                                else False,
                            ),
                        ],
                    ),
                    Divider(),
                    Row(
                        flex="auto",
                        children=[
                            Text(
                                width="100%",
                                value=state.email.body,
                                streaming=state.streaming,
                                id="email_body",
                                minLines=10,
                                editable={
                                    "name": "body",
                                    "autoFocus": True,
                                    "required": True,
                                }
                                if not state.collapsed
                                and state.status_text != "Sending"
                                else False,
                            ),
                        ],
                    ),
                ],
            )
        ],
    )


def render_email_view(id: str, state: EmailView):
    footer: list[WidgetComponent] = []
    if state.show_back_button:
        footer = [
            Divider(flush=True),
            Row(
                children=[
                    Button(
                        onClickAction=ShowInboxAction.create(
                            BasePayload(widget_id=id), loading_behavior="container"
                        ),
                        label="Back",
                        color="primary",
                        variant="outline",
                        pill=True,
                        iconStart="chevron-left",
                    )
                ]
            ),
        ]

    return Card(
        key="email.view",
        size="lg",
        status=state.status(),
        children=[
            Row(
                gap=3,
                children=[
                    Image(
                        src=state.email.sender_image,
                        size=40,
                        radius="full",
                        frame=True,
                    ),
                    Col(
                        children=[
                            Text(
                                value=state.email.sender,
                                weight="semibold",
                                size="md",
                                color="emphasis",
                            ),
                            Text(
                                value=f"To: {state.email.to}",
                                size="sm",
                                color="secondary",
                            ),
                        ]
                    ),
                    Spacer(),
                    Text(
                        value=state.email.sent_at or "",
                        size="sm",
                        color="secondary",
                    ),
                ],
            ),
            Divider(flush=True),
            Col(
                gap=6,
                children=[
                    Text(
                        value=state.email.subject,
                        weight="semibold",
                        size="xl",
                        color="emphasis",
                    ),
                    Markdown(value=state.email.body),
                ],
            ),
        ]
        + footer,
    )


def render_emails_list(id: str, state: EmailsList):
    return ListView(
        key="email.inbox",
        status=state.status(),
        children=[
            back_button_list_item(
                ShowWidgetAction.create(
                    ShowWidgetPayload(widget="email", widget_id=id),
                    loading_behavior="container",
                )
            )
        ]
        + [
            ListViewItem(
                onClickAction=ViewEmailAction.create(
                    ViewEmailPayload(email_id=email.id, widget_id=id)
                ),
                gap=3,
                align="start",
                key=email.id,
                children=[
                    Image(
                        src=email.sender_image,
                        size="40px",
                        radius="md" if email.sender_type == "org" else "full",
                        frame=True,
                    ),
                    Col(
                        children=[
                            Row(
                                align="start",
                                children=[
                                    Col(
                                        children=[
                                            Text(
                                                value=email.sender,
                                                weight="semibold",
                                                color="emphasis",
                                            ),
                                            Text(
                                                value=email.subject,
                                                color="emphasis",
                                                size="sm",
                                            ),
                                        ]
                                    ),
                                    Spacer(),
                                    Text(
                                        value=email.sent_at or "",
                                        size="sm",
                                        color="secondary",
                                    ),
                                ],
                            ),
                            Text(
                                value=re.sub(r"\s+", " ", email.body)[:500],
                                size="sm",
                                color="secondary",
                                maxLines=2,
                            ),
                        ]
                    ),
                ],
            )
            for email in state.emails
        ],
    )


# TASK TEMPLATES


def render_task_draft(id: str, state: TaskDraft):
    disabled = state.collapsed or state.status_text == "Creating task"

    return Card(
        key="tasks.draft",
        size="lg",
        padding=0,
        status=state.status(),
        collapsed=state.collapsed,
        asForm=True,
        confirm={
            "label": "Create task",
            "action": CreateTaskAction.create(
                CreateTaskPayload(todo=state.todo, widget_id=id),
                loading_behavior="self",
            ),
        }
        if not state.collapsed
        else None,
        cancel={
            "label": "Cancel",
            "action": CancelTaskAction.create(BasePayload(widget_id=id)),
        }
        if not state.collapsed
        else None,
        children=[
            Col(
                padding=4,
                gap=2,
                children=[
                    Text(
                        editable={"name": "todo.title", "required": True}
                        if not disabled
                        else False,
                        value=state.todo.title,
                        weight="semibold",
                        color="emphasis",
                        size="lg",
                    ),
                    Text(
                        value=state.todo.description,
                        color="emphasis",
                        minLines=6,
                        editable={"name": "todo.description", "autoFocus": True}
                        if not disabled
                        else False,
                    ),
                ],
            ),
            Col(
                padding={"x": 4, "y": 3.5},
                background="surface-secondary",
                border={"top": {"size": 1, "color": "subtle"}},
                children=[
                    Row(
                        gap=2,
                        children=[
                            Row(
                                gap=2,
                                width="fit-content",
                                wrap="wrap",
                                children=[
                                    Select(
                                        name="todo.priority",
                                        disabled=disabled,
                                        defaultValue=state.todo.priority,
                                        pill=True,
                                        options=[
                                            {"value": "low", "label": "Low priority"},
                                            {"value": "high", "label": "High priority"},
                                        ],
                                    ),
                                    Select(
                                        name="todo.timeframe",
                                        disabled=disabled,
                                        defaultValue=state.todo.timeframe,
                                        onChangeAction=UpdateDraftTaskAction.create(
                                            UpdateDraftTaskPayload(
                                                todo=state.todo, widget_id=id
                                            )
                                        ),
                                        pill=True,
                                        options=[
                                            {"value": "today", "label": "Due today"},
                                            {
                                                "value": "tomorrow",
                                                "label": "Due tomorrow",
                                            },
                                            {
                                                "value": "week",
                                                "label": "Due by end of week",
                                            },
                                            {
                                                "value": "month",
                                                "label": "Due by end of month",
                                            },
                                            {
                                                "value": "custom",
                                                "label": "Specific date",
                                            },
                                        ],
                                    ),
                                    *(
                                        [
                                            Row(
                                                gap=2,
                                                children=[
                                                    Text(
                                                        value="Due by",
                                                        size="sm",
                                                        color="secondary",
                                                    ),
                                                    DatePicker(
                                                        name="todo.due_date",
                                                        defaultValue=state.todo.due_date,
                                                        pill=True,
                                                        disabled=disabled,
                                                    ),
                                                ],
                                            )
                                        ]
                                        if state.todo.timeframe == "custom"
                                        else []
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def render_task_view(id: str, state: TaskView):
    header: list[WidgetComponent] = (
        [
            Row(
                margin={"x": -2, "top": -2, "bottom": -1},
                children=[
                    Button(
                        onClickAction=ViewTasksAction.create(
                            BasePayload(widget_id=id), loading_behavior="container"
                        ),
                        label="Back",
                        color="secondary",
                        variant="ghost",
                        iconStart="chevron-left",
                        size="xs",
                        pill=True,
                    ),
                ],
            ),
            Divider(flush=True),
        ]
        if state.show_back_button
        else []
    )

    body = [
        Col(
            gap=1,
            children=[
                Text(
                    value=f"{state.task.priority} priority",
                    color=state.task.priority_color(),
                    size="sm",
                    weight="medium",
                ),
                Title(
                    color="emphasis",
                    value=state.task.title,
                    weight="semibold",
                    size="lg",
                ),
                Row(
                    align="center",
                    height=26,
                    children=[
                        Text(
                            key="task.due_date",
                            value=state.task.humanized_due_date(),
                            color="tertiary",
                            size="sm",
                        )
                    ],
                )
                if not state.task.completed
                else Row(
                    key="task.completed",
                    gap=1,
                    height=22,
                    margin={"top": 1},
                    justify="start",
                    width="fit-content",
                    padding={"left": 1, "right": 2},
                    background="blue-50",
                    radius="full",
                    children=[
                        Icon(name="check-circle-filled", color="blue-400"),
                        Text(
                            value="Complete",
                            color="blue-400",
                            size="xs",
                            weight="semibold",
                        ),
                    ],
                ),
            ],
        ),
        Divider(flush=True),
        Text(value=state.task.description, minLines=6),
    ]

    footer = [
        Transition(
            children=Col(
                align="start",
                children=[
                    Button(
                        onClickAction=ToggleTaskCompleteAction.create(
                            ToggleTaskCompletePayload(
                                task_id=state.task.id, widget_id=id
                            )
                        ),
                        label="Mark complete",
                        color="secondary",
                        variant="outline",
                        iconStart="check-circle",
                        pill=True,
                    ),
                ],
            )
            if not state.task.completed
            else None
        )
    ]

    return Card(
        key="tasks.view",
        size="lg",
        status=state.status(),
        children=[Col(gap=3, children=header + body + footer)],
    )


def render_tasks_list(id: str, state: TasksList):
    return ListView(
        key="tasks.list",
        status=state.status(),
        limit=5,
        children=[
            back_button_list_item(
                ShowWidgetAction.create(ShowWidgetPayload(widget="tasks", widget_id=id))
            ),
        ]
        + [
            ListViewItem(
                onClickAction=ViewTaskAction.create(
                    ViewTaskPayload(task_id=task.id, widget_id=id)
                ),
                children=[
                    Col(
                        children=[
                            Row(
                                gap=3,
                                children=[
                                    Button(
                                        size="3xs",
                                        variant=task.completed and "solid" or "outline",
                                        color=task.completed and "info" or "primary",
                                        iconStart=task.completed and "check" or None,
                                        uniform=True,
                                        pill=True,
                                        iconSize="lg",
                                        label="",
                                        onClickAction=ToggleTaskCompleteAction.create(
                                            ToggleTaskCompletePayload(
                                                task_id=task.id, widget_id=id
                                            )
                                        ),
                                    ),
                                    Text(
                                        value=task.title,
                                        weight="medium",
                                        color="emphasis",
                                    ),
                                ],
                            ),
                            Transition(
                                children=Row(
                                    padding={"left": 8.5},
                                    children=[
                                        Text(
                                            value=task.humanized_due_date(),
                                            size="sm",
                                            weight="medium",
                                            color=task.urgency_color(),
                                        ),
                                    ],
                                )
                                if not task.completed
                                else None,
                            ),
                        ],
                    ),
                ],
            )
            for task in state.tasks
        ],
    )


# CALENDAR TEMPLATES


def render_calendar_event_draft(id: str, state: CalendarEventDraft):
    return Card(
        key="calendar.draft",
        status=state.status(),
        collapsed=state.collapsed,
        confirm={
            "label": "Add to calendar",
            "action": CreateEventAction.create(
                CreateEventPayload(event=state.event, widget_id=id),
                loading_behavior="self",
            ),
        }
        if not state.collapsed
        else None,
        cancel={
            "label": "Discard",
            "action": DiscardEventAction.create(BasePayload(widget_id=id)),
        }
        if not state.collapsed
        else None,
        children=[
            Row(
                align="stretch",
                justify="stretch",
                children=[
                    Col(
                        width="64px",
                        children=[
                            Text(
                                value="Wed",
                                size="xs",
                                color="tertiary",
                                weight="semibold",
                            ),
                            Title(
                                value="16",
                                size="xl",
                                color="emphasis",
                                weight="semibold",
                            ),
                        ],
                    ),
                    Col(
                        gap=2,
                        flex="auto",
                        children=[
                            Row(
                                padding=2,
                                background="surface-tertiary",
                                radius="md",
                                align="stretch",
                                gap=3,
                                children=[
                                    Box(background="red-400", width=4, radius="full"),
                                    Col(
                                        children=[
                                            Text(value="Lunch", weight="medium"),
                                            Text(
                                                value="12:00 - 12:45 PM",
                                                size="xs",
                                                color="secondary",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            Row(
                                padding=2,
                                border={"style": "dashed", "size": 1},
                                radius="md",
                                align="stretch",
                                gap=3,
                                children=[
                                    Box(
                                        background=state.event.calendar_color(),
                                        width=4,
                                        radius="full",
                                    ),
                                    Col(
                                        children=[
                                            Text(
                                                value=state.event.title, weight="medium"
                                            ),
                                            Text(
                                                value=state.event.time(),
                                                size="xs",
                                                color="secondary",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            Row(
                                padding=2,
                                background="surface-tertiary",
                                radius="md",
                                align="stretch",
                                gap=3,
                                children=[
                                    Box(background="red-400", width=4, radius="full"),
                                    Col(
                                        children=[
                                            Text(value="Team standup", weight="medium"),
                                            Text(
                                                value="3:30 - 4:00 PM",
                                                size="xs",
                                                color="secondary",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def render_calendar_event_view(id: str, state: CalendarEventView):
    back_button_row: list[WidgetComponent] = (
        [
            Row(
                margin={"x": -2, "top": -2, "bottom": -2},
                children=[
                    Button(
                        onClickAction=ViewScheduleAction.create(
                            BasePayload(widget_id=id),
                            loading_behavior="container",
                        ),
                        label="Back",
                        color="secondary",
                        variant="ghost",
                        iconStart="chevron-left",
                        size="xs",
                        pill=True,
                    ),
                ],
            ),
            Divider(flush=True),
        ]
        if state.show_back_button
        else []
    )

    return Card(
        key="calendar.view",
        size="lg",
        status=state.status(),
        children=[
            Col(
                gap=4,
                children=back_button_row
                + [
                    Col(
                        gap=1,
                        children=[
                            Row(
                                gap=2,
                                children=[
                                    Box(
                                        radius="full",
                                        background=state.event.calendar_color(),
                                        size=8,
                                    ),
                                    Text(
                                        value=state.event.calendar,
                                        size="sm",
                                        color="emphasis",
                                        weight="medium",
                                    ),
                                ],
                            ),
                            Text(value=state.event.title, size="xl", weight="semibold"),
                            Row(
                                gap=2,
                                children=[
                                    Text(value=state.event.date, color="emphasis"),
                                    Text(
                                        value=state.event.time(),
                                        color="tertiary",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    Image(
                        src=asset("map.png"),
                        radius="sm",
                        width="100%",
                        height="230px",
                        fit="cover",
                    ),
                ],
            ),
        ],
    )


def render_calendar_events_list(id: str, state: CalendarEventsList):
    return ListView(
        key="calendar.list",
        status=state.status(),
        limit=5,
        children=[
            back_button_list_item(
                ShowWidgetAction.create(
                    ShowWidgetPayload(widget="calendar", widget_id=id),
                    loading_behavior="container",
                )
            )
        ]
        + [
            ListViewItem(
                onClickAction=ViewEventAction.create(
                    ViewEventPayload(event_id=event.id, widget_id=id),
                    loading_behavior="container",
                ),
                align="stretch",
                gap=4,
                children=[
                    Box(radius="full", background=event.calendar_color(), width=4),
                    Col(
                        children=[
                            Text(
                                value=event.title,
                                weight="medium",
                            ),
                            Text(
                                value=event.time(),
                                size="xs",
                                color="secondary",
                            ),
                        ],
                    ),
                ],
            )
            for event in state.events
        ],
    )
