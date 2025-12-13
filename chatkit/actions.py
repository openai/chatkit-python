from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar, get_args, get_origin

from pydantic import BaseModel, Field
from typing_extensions import deprecated

Handler = Literal["client", "server"]
LoadingBehavior = Literal["auto", "none", "self", "container"]

DEFAULT_HANDLER: Handler = "server"
DEFAULT_LOADING_BEHAVIOR: LoadingBehavior = "auto"


_direct_usage_of_action_classes_deprecated = deprecated(
    "Direct usage of named action classes is deprecated. "
    "Use WidgetTemplate to build widgets from .widget files instead. "
    "Visit https://widgets.chatkit.studio/ to author widget files."
)


@_direct_usage_of_action_classes_deprecated
class ActionConfig(BaseModel):
    type: str
    payload: Any = None
    handler: Handler = DEFAULT_HANDLER
    loadingBehavior: LoadingBehavior = DEFAULT_LOADING_BEHAVIOR


TType = TypeVar("TType", bound=str)
TPayload = TypeVar("TPayload")


@_direct_usage_of_action_classes_deprecated
class Action(BaseModel, Generic[TType, TPayload]):
    type: TType = Field(default=TType, frozen=True)  # pyright: ignore
    payload: TPayload = None  # pyright: ignore - default to None to allow no-payload actions

    @classmethod
    def create(
        cls,
        payload: TPayload,
        handler: Handler = DEFAULT_HANDLER,
        loading_behavior: LoadingBehavior = DEFAULT_LOADING_BEHAVIOR,
    ) -> ActionConfig:
        actionType: Any = None
        anno = cls.model_fields["type"].annotation
        if get_origin(anno) is Literal:
            lits = get_args(anno)
            if len(lits) == 1 and isinstance(lits[0], str):
                actionType = lits[0]

        if actionType is None:
            raise TypeError(
                "Cannot infer 'type' for this Action[...]. Do not call create() on generic Action."
            )

        return ActionConfig(
            type=actionType,
            payload=payload,
            handler=handler,
            loadingBehavior=loading_behavior,
        )
