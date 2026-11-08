"""Merge extracted facts into the current conversation profile."""
from copy import deepcopy
from src.nlp_processor import DEFAULT_PREFERENCES

REMEMBERED_FIELDS = {"gender_group", "age_group", "skin_tone", "body_type", "height", "color"}


def new_profile(saved_preferences=None):
    profile = deepcopy(DEFAULT_PREFERENCES)
    if isinstance(saved_preferences, dict):
        for key, value in saved_preferences.items():
            if key in profile:
                profile[key] = value
    return profile


def remembered_preferences(profile):
    """Keep long-term memory to personal preferences, not chat-specific plans."""
    if not isinstance(profile, dict):
        return {}
    return {
        key: profile[key]
        for key in REMEMBERED_FIELDS
        if profile.get(key) not in (None, "", "Skipped")
    }


def rebuild_profile(messages):
    """Recreate a legacy chat's working context from only its own user turns."""
    from src.chat_controller import ChatController

    controller = ChatController(remember_enabled=False)
    for message in messages or []:
        if message.get("role") == "user":
            controller.handle_message(message.get("message", ""))
    return controller.profile


def update_profile(profile: dict, parsed: dict, remember_enabled=True):
    """Update known fields; unavailable/disliked items accumulate uniquely."""
    updated = deepcopy(profile)
    for key, value in parsed.get("updates", {}).items():
        if key in updated and value not in (None, ""):
            updated[key] = value
    for parsed_key, profile_key in [("unavailable", "unavailable_items"), ("disliked", "disliked_items")]:
        existing = updated.get(profile_key, []) or []
        additions = parsed.get(parsed_key, []) or []
        updated[profile_key] = list(dict.fromkeys(existing + additions))
    if not remember_enabled:
        return updated
    return updated


def missing_recommendation_fields(profile):
    """Return missing fields used by the personalized intake flow."""
    missing = []
    required_fields = [
        ("gender_group", "who the outfit is for"),
        ("occasion", "event or occasion"),
        ("age_group", "age or age range"),
        ("skin_tone", "skin tone"),
        ("height", "height"),
        ("season", "season or weather"),
    ]
    for field, label in required_fields:
        if not profile.get(field) and not (field == "season" and profile.get("weather")):
            missing.append(label)
    return missing