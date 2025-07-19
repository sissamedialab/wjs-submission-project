from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from .workflow import Step


class StepState(NamedTuple):
    step: "Step"
    state: bool
