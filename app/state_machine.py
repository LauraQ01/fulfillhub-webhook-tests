TRANSITIONS: dict[str, dict[str, str]] = {
    "pending": {
        "payment.authorized": "authorized",
        "payment.declined": "declined",
    },
    "authorized": {
        "payment.captured": "captured",
        "payment.declined": "declined",
    },
    "captured": {
        "payment.settled": "settled",
        "payment.refunded": "refunded",
    },
    "settled": {
        "payment.refunded": "refunded",
        "payment.chargeback": "chargebacked",
    },
}

# All valid event types across all states
ALL_VALID_EVENTS: set[str] = {
    event for transitions in TRANSITIONS.values() for event in transitions
}


class InvalidTransitionError(Exception):
    """Event type is not valid in any state."""


class OutOfOrderEventError(Exception):
    """Event type is valid globally but not for the current payment state."""


def apply_transition(current_status: str, event_type: str) -> str:
    """
    Apply a state transition.

    Returns the new status if transition is valid.
    Raises OutOfOrderEventError if event_type is valid globally but not for current_status.
    Raises InvalidTransitionError if event_type is not valid in any state.
    """
    if event_type not in ALL_VALID_EVENTS:
        raise InvalidTransitionError(
            f"Event type '{event_type}' is not a valid event in any state."
        )

    state_transitions = TRANSITIONS.get(current_status, {})
    if event_type in state_transitions:
        return state_transitions[event_type]

    raise OutOfOrderEventError(
        f"Event '{event_type}' cannot be applied to payment in '{current_status}' status."
    )
