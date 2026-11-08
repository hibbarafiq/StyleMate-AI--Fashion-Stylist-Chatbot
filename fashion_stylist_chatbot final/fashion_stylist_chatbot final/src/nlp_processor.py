"""Extract user intent and fashion preferences from chat messages utilizing the updated dataset schema."""

import re

DEFAULT_PREFERENCES = {
    "occasion": None,
    "season": None,
    "weather": None,
    "gender_group": None,
    "age": None,
    "age_group": None,
    "specific_event": None,
    "body_type": None,
    "height": None,
    "height_detail": None,
    "skin_tone": None,
    "color": None,
    "unavailable_items": [],
    "disliked_items": [],
    "seen_outfit_ids": [],
    "last_recommendation": None,
    "pending_question": None,
}

OCCASIONS = {
    "wedding wear": ["wedding", "shaadi", "shadi", "baraat", "walima", "mehndi", "mangni", "mayun"],
    "party wear": ["party", "birthday", "celebration", "gathering", "social"],
    "formal wear": ["formal", "office", "business", "interview", "meeting", "academic defense"],
    "college wear": ["school", "college", "university", "class", "campus", "presentation"],
    "casual wear": ["casual", "everyday", "daily", "routine", "home", "brunch", "outing"],
}

SPECIFIC_EVENTS = {
    "birthday party": "Birthday Party",
    "birthday": "Birthday Party",
    "wedding ceremony": "Wedding Ceremony",
    "job interview": "Job Interview",
    "interview": "Job Interview",
    "formal dinner": "Formal Dinner",
    "casual outing": "Casual Outing",
    "graduation": "Graduation",
    "prom": "Prom",
    "engagement party": "Engagement Party",
    "mehndi": "Mehndi",
    "baraat": "Baraat",
    "walima": "Walima",
    "nikkah": "Nikkah",
    "sangeet": "Sangeet",
    "reception": "Reception",
}

SEASONS = {
    "Spring": ["spring"],
    "Hot / Summer": ["summer", "garmi", "hot", "sunny", "heat"],
    "Autumn": ["autumn", "fall"],
    "Cold / Winter": ["winter", "sardi", "cold", "chilly", "freezing"],
    "Rainy / Humid": ["rain", "rainy", "monsoon", "humid", "barish"],
}

ITEM_TERMS = [
    "heels", "sneakers", "accessories", "jewellery", "jewelry",
    "sandals", "loafers", "flats", "shoes", "shoe", "footwear", "boots", "dupatta",
    "hijab", "jacket", "coat", "jeans", "trousers", "skirt",
    "dress", "bag", "scarf", "jhumka", "earrings", "necklace", "clutch"
]

COLORS = [
    "black", "white", "red", "blue", "navy", "green",
    "emerald", "pink", "purple", "beige", "brown",
    "yellow", "gray", "grey", "maroon", "cream", "gold"
]

FASHION_TERMS = [
    "fashion", "outfit", "wear", "clothes", "clothing", "style", "dress",
    "shirt", "trousers", "jeans", "skirt", "shoes", "shoe", "footwear",
    "heels", "sneakers", "sandals", "color", "colour", "accessories"
]
GENERAL_REQUEST_STARTERS = [
    "what", "who", "when", "where", "why", "how", "explain", "define",
    "calculate", "solve", "tell me", "can you tell me"
]


def contains_phrase(text, phrase):
    return bool(re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text))


def contains_any(text, phrases):
    return any(contains_phrase(text, phrase) for phrase in phrases)


def extract_preferences(message: str) -> dict:
    text = (message or "").lower().strip()

    result = {
        "intent": "chat",
        "updates": {},
        "unavailable": [],
        "disliked": [],
        "replacement": [],
        "color_change": False,
        "message_lower": text,
    }

    if not text:
        return result

    change_terms = ["change", "replace", "switch", "swap", "another", "different", "instead"]
    if contains_any(text, change_terms):
        result["replacement"] = [item for item in ITEM_TERMS if contains_phrase(text, item)]
        result["color_change"] = contains_any(text, ["color", "colour"]) or any(
            contains_phrase(text, color) for color in COLORS
        )

    # Greetings
    if re.fullmatch(r"^(hi+|hy+|hey+|hello+|helo+|salam|assalamualaikum|as-salamu alaykum)[\s!.?,]*$", text):
        result["intent"] = "greeting"
        return result

    # Gender extraction
    if contains_any(text, ["female", "woman", "women", "girl", "girls", "ladies"]):
        result["updates"]["gender_group"] = "Female"
    elif contains_any(text, ["male", "man", "men", "boy", "boys"]):
        result["updates"]["gender_group"] = "Male"
    elif contains_any(text, ["child", "kid", "kids", "baby"]):
        result["updates"]["gender_group"] = "Child"

    # Age Group extraction (supporting senior citizens, teenagers, etc.)
    if contains_any(text, ["senior", "elderly", "old", "senior citizen"]):
        result["updates"]["age_group"] = "Senior citizen"
    elif contains_any(text, ["child", "kid", "baby"]):
        result["updates"]["age_group"] = "Child"
    elif contains_any(text, ["teen", "teenager"]):
        result["updates"]["age_group"] = "Teenager"
    elif contains_any(text, ["young adult", "college student"]):
        result["updates"]["age_group"] = "Young adult"
    elif contains_any(text, ["middle-aged", "middle aged", "adult"]):
        result["updates"]["age_group"] = "Middle-aged adult"

    age_match = re.search(
        r"\b(?:age(?:d)?\s*(?:is|:)?\s*|(?:i am|i'm|they are|he is|she is)\s*)"
        r"(\d{1,2})(?:\s*(?:-|to)\s*(\d{1,2}))?(?:\s*(?:years? old|yrs? old|yo))?\b",
        text,
    ) or re.search(r"\b(\d{1,2})(?:\s*(?:-|to)\s*(\d{1,2}))?\s*(?:-\s*years?-old|years? old|yrs? old|yo)\b", text)
    has_person_context = bool(
        result["updates"].get("gender_group")
        or contains_any(text, ["age", "years old", "year old", "yrs old", "yo"])
    )
    if not age_match and has_person_context:
        age_match = re.search(r"\b(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\b", text)
    if not age_match and has_person_context:
        age_match = re.search(r"(?<![\w'])\d{1,2}(?![\w'])", text)
        if age_match and re.match(r"\s*(?:cm\b|centimeters?\b|m\b|meters?\b|ft\b|feet\b|foot\b|in\b|inches\b|['\"])\s*", text[age_match.end():]):
            age_match = None
    if age_match:
        first_age = int(age_match.group(1)) if age_match.lastindex else int(age_match.group(0))
        second_age = int(age_match.group(2)) if age_match.lastindex and age_match.group(2) else first_age
        age = round((first_age + second_age) / 2)
        result["updates"]["age"] = age_match.group(0).strip()
        if age < 13:
            result["updates"]["age_group"] = "Child"
        elif age < 20:
            result["updates"]["age_group"] = "Teenager"
        elif age < 40:
            result["updates"]["age_group"] = "Young Adult"
        elif age < 60:
            result["updates"]["age_group"] = "Middle-aged Adult"
        else:
            result["updates"]["age_group"] = "Senior Citizen"

    # Occasion extraction
    for occasion, phrases in OCCASIONS.items():
        if contains_any(text, phrases):
            result["updates"]["occasion"] = occasion.title()
            break

    for event, canonical_event in SPECIFIC_EVENTS.items():
        if contains_phrase(text, event):
            result["updates"]["specific_event"] = canonical_event
            break

    # Keep season and current weather available under the same recommendation field.
    for season, phrases in SEASONS.items():
        if contains_any(text, phrases + (["dhoop", "thand", "baarish"] if season in {"Hot / Summer", "Cold / Winter", "Rainy / Humid"} else [])):
            result["updates"]["season"] = season
            result["updates"]["weather"] = season
            break

    # Skin tone extraction
    for tone in ["fair", "light", "medium", "olive", "tan", "dark", "deep"]:
        if contains_phrase(text, tone):
            result["updates"]["skin_tone"] = tone.title()
            break
    if not result["updates"].get("skin_tone") and contains_any(text, ["brown skin", "brown complexion", "skin is brown"]):
        result["updates"]["skin_tone"] = "Tan"

    # Body type extraction
    for bt in ["slim", "athletic", "average", "curvy", "plus-size", "plus size", "apple", "pear", "rectangle", "petite"]:
        if contains_phrase(text, bt):
            result["updates"]["body_type"] = bt.title()
            break

    # Height extraction accepts a category or common metric/imperial measurements.
    for h in ["petite", "short", "average", "tall"]:
        if h == "average" and not re.search(r"\b(?:height|average height)\b", text):
            continue
        if contains_phrase(text, h):
            result["updates"]["height"] = "Short" if h == "petite" else h.title()
            break

    metric_height = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(cm|centimeters?|m|meters?)\b", text)
    imperial_height = re.search(r"\b([4-7])\s*(?:ft|feet|foot|')\s*(\d{1,2})?\s*(?:in|inches|\")?", text)
    if metric_height:
        measured_cm = float(metric_height.group(1))
        if metric_height.group(2).startswith("m") and measured_cm < 3:
            measured_cm *= 100
        result["updates"]["height_detail"] = metric_height.group(0).strip()
    elif imperial_height:
        measured_cm = (int(imperial_height.group(1)) * 12 + int(imperial_height.group(2) or 0)) * 2.54
        result["updates"]["height_detail"] = imperial_height.group(0).strip()
    else:
        measured_cm = None
    if measured_cm is not None:
        result["updates"]["height"] = "Short" if measured_cm < 157 else "Tall" if measured_cm > 175 else "Average"

    for color in COLORS:
        if contains_phrase(text, color):
            result["updates"]["color"] = color.title()
            break

    # Unavailable items
    unavailable_phrases = ["don't have", "dont have", "do not have", "no", "not have", "without", "nahi hai"]
    if contains_any(text, unavailable_phrases):
        result["unavailable"] = [item for item in ITEM_TERMS if contains_phrase(text, item)]
        for color in COLORS:
            if contains_phrase(text, color):
                result["disliked"].append(color)

    # Disliked items/colors
    if contains_any(text, ["don't like", "dont like", "dislike", "hate"]):
        result["disliked"].extend([item for item in ITEM_TERMS if contains_phrase(text, item)])
        result["disliked"].extend([color for color in COLORS if contains_phrase(text, color)])

    starts_general_request = any(
        re.match(rf"^{re.escape(starter)}\b", text) for starter in GENERAL_REQUEST_STARTERS
    )
    if ("?" in text or starts_general_request) and not contains_any(text, FASHION_TERMS) and not result["updates"]:
        result["intent"] = "general_question"

    return result