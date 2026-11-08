"""Manage a multi-turn, dataset-grounded fashion-stylist conversation."""

import ast
import operator
import re

from src.nlp_processor import extract_preferences
from src.conversation_manager import new_profile, update_profile
from src.recommendation_engine import RecommendationEngine
from src.response_generator import recommendation_response
from src.alternatives import suggest_alternatives


def contains_reference(text):
    return bool(re.search(r"\b(it|this one|that one|another|different one|something else)\b", text))


def evaluate_arithmetic_question(text):
    expression = re.search(r"\d+(?:\.\d+)?(?:\s*[+\-*/%]\s*\d+(?:\.\d+)?)+", text)
    if not expression:
        return None

    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
    }

    def calculate(node):
        if isinstance(node, ast.Expression):
            return calculate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](calculate(node.left), calculate(node.right))
        raise ValueError("Unsupported arithmetic expression")

    try:
        value = calculate(ast.parse(expression.group(), mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
        return None
    return f"{expression.group().strip()} = {value:g}"


class ChatController:
    """Collect useful preferences one turn at a time, then recommend outfits."""

    INTAKE_FIELDS = [
        ("gender_group", "who it's for (female or male)"),
        ("occasion", "the event or occasion"),
        ("age_group", "their age or age range"),
        ("skin_tone", "their skin tone"),
        ("height", "their height (cm, feet/inches, or short/average/tall)"),
        ("season", "the season or weather"),
    ]
    REQUIRED_FIELDS = {"gender_group", "occasion"}
    OPTIONAL_FIELDS = {"age_group", "skin_tone", "height", "season"}

    # Plain greetings (after stripping punctuation / extra spaces)
    GREETINGS = {
        "hi", "hii", "hiii", "hy", "hyy", "hello", "helo", "hey", "heya", "hey there",
        "hi there", "hello there", "yo", "hola", "greetings", "good morning",
        "good afternoon", "good evening",
    }
    SALAM_PREFIXES = ("assalam", "asalam", "assalaam", "salam", "aslam", "salaam", "assalamu", "assalamo")

    def __init__(self, saved_preferences=None, remember_enabled=True):
        self.profile = new_profile(saved_preferences)
        self.remember_enabled = remember_enabled
        self.engine = RecommendationEngine()

    @staticmethod
    def _is_skip(text):
        text = text.lower().strip()
        return text in {"skip", "no preference", "doesn't matter", "doesnt matter", "you decide", "anything", "not sure"}

    @classmethod
    def _is_salam(cls, text):
        """Match Assalam-o-Alaikum and its common spellings, e.g. 'assalamualaikum', 'Salam', 'As-salamu alaykum'."""
        letters = re.sub(r"[^a-z]", "", text.lower())
        return bool(letters) and len(letters) <= 30 and letters.startswith(cls.SALAM_PREFIXES)

    @classmethod
    def _is_hi(cls, text):
        cleaned = re.sub(r"[^a-z ]", "", text.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned in cls.GREETINGS

    @staticmethod
    def _normalise_answer(field, message, parsed):
        """Prefer extracted/canonical values; retain a safe answer fallback."""
        updates = parsed.get("updates", {})
        if field in updates:
            return updates[field]
        answer = message.strip()
        low = answer.lower()
        if field == "gender_group":
            if any(x in low for x in ["female", "woman", "women", "girl", "ladies"]): return "Female"
            if any(x in low for x in ["male", "man", "men", "boy"]): return "Male"
            if any(x in low for x in ["child", "kid", "baby"]): return "Child"
        if field == "age_group":
            age_range = re.fullmatch(r"\s*(\d{1,2})(?:\s*(?:-|to)\s*(\d{1,2}))?\s*", message)
            if age_range:
                first_age = int(age_range.group(1))
                second_age = int(age_range.group(2)) if age_range.group(2) else first_age
                age = round((first_age + second_age) / 2)
                if age < 13: return "Child"
                if age < 20: return "Teenager"
                if age < 40: return "Young Adult"
                if age < 60: return "Middle-aged Adult"
                return "Senior Citizen"
            if any(x in low for x in ["senior", "elderly", "old", "senior citizen"]): return "Senior citizen"
            if any(x in low for x in ["child", "kid"]): return "Child"
            if any(x in low for x in ["teen", "teenager"]): return "Teenager"
            if any(x in low for x in ["young adult", "college"]): return "Young adult"
            if any(x in low for x in ["middle", "adult"]): return "Middle-aged adult"
        if field == "occasion":
            if "wedding" in low: return "Wedding Wear"
            if "party" in low: return "Party Wear"
            if any(x in low for x in ["formal", "office", "interview", "work"]): return "Formal Wear"
            if "college" in low or "school" in low or "student" in low: return "College Wear"
            if any(x in low for x in ["casual", "everyday", "daily", "outing"]): return "Casual Wear"
        if field == "specific_event":
            return answer.title()
        if field == "weather":
            if any(x in low for x in ["hot", "sunny", "heat", "summer", "garmi"]): return "Hot / Summer"
            if any(x in low for x in ["cold", "chilly", "winter", "freezing", "sardi"]): return "Cold / Winter"
            if any(x in low for x in ["rain", "monsoon", "humid", "barish"]): return "Rainy / Humid"
            if "spring" in low: return "Spring"
            if "autumn" in low or "fall" in low: return "Autumn"
            return answer.title()
        if field == "skin_tone":
            for tone in ["fair", "light", "medium", "olive", "tan", "dark", "deep"]:
                if tone in low: return tone.title()
        if field == "body_type":
            for bt in ["slim", "athletic", "average", "curvy", "plus-size", "plus size"]:
                if bt in low: return bt.title()
        if field == "height":
            for h in ["petite", "short", "average", "tall", "high"]:
                if h in low: return h.title()
        return None

    def _missing_intake_fields(self):
        return [
            field for field, _ in self.INTAKE_FIELDS
            if not self.profile.get(field) or (
                field in self.REQUIRED_FIELDS and self.profile.get(field) == "Skipped"
            )
        ]

    def _intake_question(self, missing_fields):
        labels = [label for field, label in self.INTAKE_FIELDS if field in missing_fields]
        if not labels:
            return None
        self.profile["pending_question"] = missing_fields[0]
        if len(labels) == 1:
            return f"To tailor this, what's {labels[0]}?"
        details = ", ".join(labels[:-1]) + f", and {labels[-1]}"
        optional_names = {
            "age_group": "age",
            "skin_tone": "skin tone",
            "height": "height",
            "season": "season",
        }
        skippable = [optional_names[field] for field in missing_fields if field in self.OPTIONAL_FIELDS]
        suffix = ""
        if skippable:
            optional_list = ", ".join(skippable[:-1])
            optional_list += f" or {skippable[-1]}" if len(skippable) > 1 else skippable[0]
            suffix = f" You can skip the {optional_list} if you'd like."
        return f"To tailor this, tell me {details}.{suffix}"

    def _apply_optional_skips(self, text):
        if text in {"skip", "skip optional", "no preference", "doesn't matter", "doesnt matter", "not sure"}:
            fields = self.OPTIONAL_FIELDS
        else:
            if not re.search(r"\b(skip|no preference|doesn't matter|doesnt matter)\b", text):
                return
            fields = set()
            for field, terms in {
                "age_group": ("age", "age group"),
                "skin_tone": ("skin", "skin tone", "tone"),
                "height": ("height",),
                "season": ("season", "weather"),
            }.items():
                if any(term in text for term in terms):
                    fields.add(field)
            if not fields:
                fields = self.OPTIONAL_FIELDS
        for field in fields:
            if not self.profile.get(field):
                self.profile[field] = "Skipped"

    @staticmethod
    def _record_recommendation(profile, recommendation):
        if not recommendation:
            return
        profile["last_recommendation"] = recommendation
        seen = profile.get("seen_outfit_ids", []) or []
        outfit_id = recommendation.get("outfit_id")
        if outfit_id:
            profile["seen_outfit_ids"] = list(dict.fromkeys(seen + [outfit_id]))

    def _suggest_another_outfit(self):
        recommendations = self.engine.recommend(self.profile, limit=1)
        if not recommendations:
            return "I couldn't find another matching look in the catalog. Want to change the occasion or color?", self.profile
        self._record_recommendation(self.profile, recommendations[0])
        return recommendation_response(recommendations, self.profile), self.profile

    @staticmethod
    def _color_options(color):
        alternatives = {
            "black": "navy, burgundy, charcoal, or deep green",
            "white": "cream, beige, or a soft pastel",
            "red": "maroon, burgundy, rose, or navy",
            "blue": "teal, green, lavender, or neutral tones",
            "navy": "black, charcoal, cream, or burgundy",
            "green": "teal, navy, beige, or burgundy",
            "emerald": "navy, burgundy, cream, or gold accents",
            "pink": "lavender, peach, burgundy, or cream",
            "purple": "navy, rose, cream, or teal",
            "yellow": "cream, olive, navy, or brown",
            "brown": "beige, cream, navy, or olive",
            "beige": "cream, navy, burgundy, or olive",
            "maroon": "navy, emerald, cream, or blush",
            "cream": "white, beige, navy, or pastel shades",
            "gold": "silver, pearl, champagne, or rose gold",
            "gray": "navy, burgundy, emerald, or cream",
            "grey": "navy, burgundy, emerald, or cream",
        }
        return alternatives.get((color or "").lower(), "navy, teal, burgundy, or a neutral shade")

    def handle_message(self, message):
        message = (message or "").strip()
        text = message.lower()
        if not message:
            return "How may I help you with your outfit today?", self.profile

        # Greetings are answered first and never change the profile or start the questionnaire.
        if self._is_salam(message):
            return "Wa-Alaikum-Assalam! What can I help you style today?", self.profile
        if self._is_hi(message):
            return "Hi! What can I help you style today?", self.profile

        parsed = extract_preferences(message)
        if parsed.get("intent") == "greeting":
            greeting = "Wa-Alaikum-Assalam! How can I help?" if self._is_salam(message) else "Hi! What can I help you with today?"
            return greeting, self.profile
        if text in {"thanks", "thank you", "thank u", "thx"}:
            return "You're welcome!", self.profile

        if parsed.get("intent") == "general_question":
            if re.search(r"\bhow are you\b", text):
                return "I'm doing well, thanks for asking. What can I help you with?", self.profile
            if re.search(r"\b(your name|who are you)\b", text):
                return "I'm StyleMate, a fashion-styling assistant.", self.profile
            calculation = evaluate_arithmetic_question(text)
            if calculation:
                return calculation, self.profile
            return "I’m focused on fashion styling, so I can’t answer general knowledge questions reliably. I can help with outfits, colors, or item alternatives.", self.profile

        if parsed.get("color_change"):
            self.profile = update_profile(self.profile, parsed, self.remember_enabled)
            requested_color = parsed.get("updates", {}).get("color")
            if requested_color:
                return f"Sure, let's use **{requested_color}** instead.", self.profile
            recommendation = self.profile.get("last_recommendation") or {}
            current_colors = str(recommendation.get("recommended_colors", "")).lower()
            color_names = ["emerald", "maroon", "purple", "yellow", "green", "black", "white", "red", "blue", "navy", "pink", "beige", "brown", "gray", "grey", "cream", "gold"]
            current_color = next((color for color in color_names if re.search(rf"\b{color}\b", current_colors)), "")
            options = self._color_options(current_color)
            return f"For a different color, try {options}.", self.profile

        replacement_items = parsed.get("replacement", []) or []
        if replacement_items:
            self.profile = update_profile(self.profile, parsed, self.remember_enabled)
            item_alternatives = suggest_alternatives(replacement_items)
            if item_alternatives:
                style = "more casual " if "casual" in text or "relaxed" in text else ""
                item, options = item_alternatives[0]
                return f"For a {style}alternative to **{item}**, try **{options[0]}** or **{options[1]}**. These can work with your {self.profile.get('occasion') or 'event'} look.", self.profile
            if self.profile.get("last_recommendation") and contains_reference(text):
                return self._suggest_another_outfit()
            return "Which item would you like to replace? I can suggest a suitable alternative.", self.profile

        # Capture current-chat details and explicit rejections before interpreting follow-ups.
        previous_occasion = self.profile.get("occasion")
        self.profile = update_profile(self.profile, parsed, self.remember_enabled)
        if (
            previous_occasion
            and parsed.get("updates", {}).get("occasion")
            and parsed["updates"]["occasion"] != previous_occasion
            and "specific_event" not in parsed.get("updates", {})
        ):
            self.profile["specific_event"] = None
        for key in ("unavailable", "disliked"):
            profile_key = "unavailable_items" if key == "unavailable" else "disliked_items"
            existing = self.profile.get(profile_key, []) or []
            self.profile[profile_key] = list(dict.fromkeys(existing + (parsed.get(key) or [])))
        unavailable_now = parsed.get("unavailable", []) or []
        disliked_now = parsed.get("disliked", []) or []
        item_alternatives = suggest_alternatives(unavailable_now + disliked_now)
        if item_alternatives:
            item, options = item_alternatives[0]
            return f"No problem. Instead of **{item}**, try **{options[0]}** or **{options[1]}**.", self.profile
        color_rejections = [color for color in disliked_now if color in {
            "black", "white", "red", "blue", "navy", "green", "emerald", "pink",
            "purple", "beige", "brown", "yellow", "gray", "grey", "maroon", "cream", "gold"
        }]
        if color_rejections:
            old_color = color_rejections[0]
            self.profile["color"] = None
            return f"No problem. Instead of **{old_color}**, try {self._color_options(old_color)}.", self.profile

        rejection_terms = ("don't like", "dont like", "dislike", "hate", "not this one", "not that one", "not it", "another option", "something else", "different one")
        if (any(term in text for term in rejection_terms) or text in {"no", "no thanks", "not really"}) and self.profile.get("last_recommendation"):
            return self._suggest_another_outfit()

        self._apply_optional_skips(text)

        # A short answer can fill the first outstanding field from an earlier prompt.
        pending = self.profile.get("pending_question")
        if pending:
            if pending not in parsed.get("updates", {}) and self.profile.get(pending) != "Skipped":
                answer = self._normalise_answer(pending, message, parsed)
                if answer:
                    self.profile[pending] = answer
                    if pending == "age_group" and re.fullmatch(r"\s*\d{1,2}(?:\s*(?:-|to)\s*\d{1,2})?\s*", message):
                        self.profile["age"] = message.strip()

        missing_fields = self._missing_intake_fields()
        if missing_fields:
            return self._intake_question(missing_fields), self.profile

        recommendations = self.engine.recommend(self.profile, limit=1)
        if recommendations:
            self._record_recommendation(self.profile, recommendations[0])
        response = recommendation_response(recommendations, self.profile)
        self.profile["pending_question"] = None
        return response, self.profile