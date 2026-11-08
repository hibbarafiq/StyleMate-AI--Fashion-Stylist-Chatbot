"""Small regression suite for core StyleMate behaviour. Run: python -m unittest discover -s tests"""
import tempfile
import unittest
from pathlib import Path

import database
from database import get_conversation_profile, save_conversation_profile
from src.nlp_processor import extract_preferences
from src.alternatives import suggest_alternatives
from src.recommendation_engine import RecommendationEngine
from src.chat_controller import ChatController
from src.response_generator import recommendation_response
from src.conversation_manager import new_profile, rebuild_profile, remembered_preferences


def complete_profile(**overrides):
    profile = {
        "gender_group": "Female",
        "age_group": "Young Adult",
        "occasion": "Party Wear",
        "specific_event": "Birthday Party",
        "season": "Hot / Summer",
        "weather": "Hot / Summer",
        "skin_tone": "Medium",
        "height": "Average",
    }
    profile.update(overrides)
    return profile


class NLPTests(unittest.TestCase):
    def test_wedding_and_group_are_extracted(self):
        parsed = extract_preferences("I need a wedding outfit for a woman")
        self.assertEqual(parsed["updates"].get("occasion"), "Wedding Wear")
        self.assertEqual(parsed["updates"].get("gender_group"), "Female")

    def test_unavailable_item_is_extracted(self):
        parsed = extract_preferences("I don't have heels for the wedding")
        self.assertIn("heels", parsed["unavailable"])
        self.assertEqual(parsed["updates"].get("occasion"), "Wedding Wear")

    def test_age_group_is_extracted(self):
        parsed = extract_preferences("Looking for an outfit for a senior citizen")
        self.assertEqual(parsed["updates"].get("age_group"), "Senior citizen")

    def test_numeric_age_height_and_season_are_extracted_together(self):
        parsed = extract_preferences("I'm a 27-year-old woman, 5'4, medium skin, going to a summer wedding")
        self.assertEqual(parsed["updates"].get("age_group"), "Young Adult")
        self.assertEqual(parsed["updates"].get("height"), "Average")
        self.assertEqual(parsed["updates"].get("height_detail"), "5'4")
        self.assertEqual(parsed["updates"].get("season"), "Hot / Summer")
        self.assertEqual(parsed["updates"].get("skin_tone"), "Medium")

    def test_compact_age_does_not_confuse_height_or_item_numbers(self):
        parsed = extract_preferences("Female, 27, medium skin, 5'4")
        self.assertEqual(parsed["updates"].get("age"), "27")
        self.assertEqual(parsed["updates"].get("age_group"), "Young Adult")
        unrelated = extract_preferences("Change to option 2")
        self.assertNotIn("age", unrelated["updates"])

    def test_average_body_type_does_not_assume_average_height(self):
        parsed = extract_preferences("Female with an average body type")
        self.assertEqual(parsed["updates"].get("body_type"), "Average")
        self.assertNotIn("height", parsed["updates"])


class ConversationFlowTests(unittest.TestCase):
    def test_party_request_asks_followups_before_recommendation(self):
        profile = {}
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        response, profile = controller.handle_message("I have to go to a party")
        self.assertIn("who it's for", response.lower())
        self.assertIn("age or age range", response.lower())
        self.assertIn("skin tone", response.lower())
        self.assertIn("height", response.lower())
        self.assertEqual(profile.get("occasion"), "Party Wear")
        self.assertEqual(profile.get("pending_question"), "gender_group")

        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        response, profile = controller.handle_message("Female, 27 years old, medium skin, 5'4, summer")
        self.assertEqual(profile.get("gender_group"), "Female")
        self.assertIn("outfit id", response.lower())
        self.assertIn("catalog match:", response.lower())

    def test_multiple_details_in_one_message_generate_personalized_recommendation(self):
        controller = ChatController(remember_enabled=False)
        response, profile = controller.handle_message("I'm a 27-year-old woman, 5'4, medium skin, going to a summer wedding")
        self.assertIn("outfit id", response.lower())
        self.assertEqual(profile["occasion"], "Wedding Wear")
        self.assertEqual(profile["season"], "Hot / Summer")
        self.assertEqual(profile["age_group"], "Young Adult")

    def test_optional_details_can_be_skipped(self):
        controller = ChatController(remember_enabled=False)
        controller.handle_message("I have a party")
        response, profile = controller.handle_message("Female, skip optional")
        self.assertIn("outfit id", response.lower())
        self.assertEqual(profile["age_group"], "Skipped")
        self.assertEqual(profile["skin_tone"], "Skipped")
        self.assertEqual(profile["height"], "Skipped")
        self.assertEqual(profile["season"], "Skipped")

    def test_party_is_classified_as_party_wear(self):
        parsed = extract_preferences("I need an outfit for a party")
        self.assertEqual(parsed["updates"].get("occasion"), "Party Wear")

    def test_change_footwear_request_gets_alternatives_without_consuming_prompt(self):
        profile = complete_profile(occasion="Wedding Wear", specific_event="Wedding Ceremony", pending_question="age_group")
        controller = ChatController(saved_preferences=profile, remember_enabled=False)

        response, updated_profile = controller.handle_message("Please change the footwear")

        self.assertIn("flats", response.lower())
        self.assertIn("sandals", response.lower())
        self.assertEqual(updated_profile["pending_question"], "age_group")
        self.assertEqual(updated_profile["age_group"], "Young Adult")

    def test_repeated_greetings_do_not_trigger_styling_or_clear_context(self):
        profile = {"occasion": "Party Wear", "pending_question": "gender_group"}
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        for greeting in ("Hi", "Hello!", "Hy", "Assalamualaikum"):
            response, profile = controller.handle_message(greeting)
            self.assertNotIn("Outfit ID", response)
            self.assertEqual(profile["pending_question"], "gender_group")

    def test_general_question_is_not_treated_as_an_intake_answer(self):
        profile = {"occasion": "Party Wear", "pending_question": "gender_group"}
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        response, profile = controller.handle_message("What is 2 + 2?")
        self.assertEqual(response, "2 + 2 = 4")
        self.assertEqual(profile["pending_question"], "gender_group")

    def test_general_request_without_question_mark_is_not_treated_as_intake(self):
        controller = ChatController(saved_preferences={"pending_question": "gender_group"}, remember_enabled=False)
        response, profile = controller.handle_message("Tell me a joke")
        self.assertNotIn("Outfit ID", response)
        self.assertEqual(profile["pending_question"], "gender_group")

    def test_change_color_returns_a_replacement_color(self):
        controller = ChatController(saved_preferences={"occasion": "Party Wear"}, remember_enabled=False)
        response, profile = controller.handle_message("Change the color to blue")
        self.assertIn("blue", response.lower())
        self.assertEqual(profile["color"], "Blue")

    def test_casual_dress_replacement_respects_requested_style(self):
        profile = {"occasion": "Party Wear", "gender_group": "Female"}
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        response, _ = controller.handle_message("Replace this dress with something more casual")
        self.assertIn("more casual", response.lower())
        self.assertIn("trousers", response.lower())

    def test_another_option_uses_a_different_catalog_look(self):
        profile = complete_profile()
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        _, profile = controller.handle_message("I need an outfit for a party")
        first_id = profile["last_recommendation"]["outfit_id"]
        response, profile = controller.handle_message("Show me another option")
        self.assertIn("Outfit ID", response)
        self.assertNotEqual(profile["last_recommendation"]["outfit_id"], first_id)

    def test_replace_it_uses_the_current_conversation_recommendation(self):
        profile = complete_profile()
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        _, profile = controller.handle_message("I need an outfit for a party")
        first_id = profile["last_recommendation"]["outfit_id"]
        response, profile = controller.handle_message("Replace it")
        self.assertIn("Outfit ID", response)
        self.assertNotEqual(profile["last_recommendation"]["outfit_id"], first_id)
        self.assertEqual(profile["occasion"], "Party Wear")

    def test_rejection_asks_for_a_different_recommendation(self):
        profile = complete_profile()
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        _, profile = controller.handle_message("I need an outfit for a party")
        first_id = profile["last_recommendation"]["outfit_id"]
        response, profile = controller.handle_message("Not this one")
        self.assertIn("Outfit ID", response)
        self.assertNotEqual(profile["last_recommendation"]["outfit_id"], first_id)

    def test_provided_event_is_not_asked_again(self):
        profile = complete_profile(occasion="Wedding Wear", specific_event="Mehndi")
        controller = ChatController(saved_preferences=profile, remember_enabled=False)
        response, updated = controller.handle_message("I prefer green")
        self.assertNotIn("to tailor this", response.lower())
        self.assertNotIn("male or female", response.lower())
        self.assertEqual(updated["specific_event"], "Mehndi")

    def test_event_and_season_changes_update_recommendation_context(self):
        controller = ChatController(saved_preferences=complete_profile(), remember_enabled=False)
        first_response, profile = controller.handle_message("I need an outfit")
        first_id = profile["last_recommendation"]["outfit_id"]
        response, profile = controller.handle_message("Actually, it's a winter wedding")
        self.assertIn("Outfit ID", response)
        self.assertNotEqual(profile["last_recommendation"]["outfit_id"], first_id)
        self.assertEqual(profile["occasion"], "Wedding Wear")
        self.assertEqual(profile["season"], "Cold / Winter")
        self.assertIsNone(profile["specific_event"])


class AlternativeTests(unittest.TestCase):
    def test_heels_alternatives_exist(self):
        suggestions = dict(suggest_alternatives(["heels"]))
        self.assertIn("heels", suggestions)
        self.assertIn("flats", suggestions["heels"])


class RecommendationTests(unittest.TestCase):
    def test_catalog_match_percentage_uses_actual_matching_fields(self):
        engine = RecommendationEngine()
        row = engine.df.iloc[0]
        profile = {
            "gender_group": row["gender"],
            "age_group": row["age_group"],
            "occasion": row["occasion"],
            "specific_event": row["specific_event"],
            "season": row["season"],
            "skin_tone": row["skin_tone"],
            "height": row["height_category"],
        }
        recommendation = engine.recommend(profile, limit=1)[0]
        self.assertEqual(recommendation["match_percentage"], 100)
        response = recommendation_response([recommendation], profile)
        self.assertIn("Catalog match: 100%", response)
        self.assertIn("not model accuracy", response)

        mismatched_profile = dict(profile, skin_tone="Deep", height="Tall", season="Winter")
        match_percentage, matched, provided = engine._matches_profile(row, mismatched_profile)
        self.assertLess(match_percentage, 100)
        self.assertLess(matched, provided)

    def test_recommendations_do_not_repeat_unavailable_heels(self):
        engine = RecommendationEngine()
        results = engine.recommend({"occasion": "wedding", "gender_group": "Female", "unavailable_items": ["heels"]}, limit=10)
        for result in results:
            combined = " ".join([
                str(result.get("outfit_name", "")),
                str(result.get("clothing_items", "")),
                str(result.get("footwear", ""))
            ]).lower()
            self.assertNotIn("heels", combined)


class ResponseTests(unittest.TestCase):
    def test_only_one_outfit_is_presented(self):
        recommendations = [
            {"outfit_id": "WW-0001", "outfit_name": "Look One", "occasion": "Wedding Wear", "season": "Summer", "clothing_items": "Blue top"},
            {"outfit_id": "WW-0002", "outfit_name": "Look Two", "occasion": "Wedding Wear", "season": "Summer", "clothing_items": "Black dress"},
        ]
        response = recommendation_response(recommendations, {})
        self.assertIn("Look One", response)
        self.assertNotIn("Look Two", response)

    def test_unavailable_item_gets_short_alternatives(self):
        controller = ChatController(saved_preferences={}, remember_enabled=False)
        response, _ = controller.handle_message("I don't have heels")
        self.assertIn("flats", response.lower())
        self.assertIn("instead", response.lower())


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_dir, self.old_path = database.DATABASE_DIR, database.DATABASE_PATH
        database.DATABASE_DIR = Path(self.temp.name)
        database.DATABASE_PATH = Path(self.temp.name) / "test.db"
        database.init_db()
        self.user_id = database.create_user_with_credentials("test@example.com", "test-hash", "Test User")

    def tearDown(self):
        database.DATABASE_DIR, database.DATABASE_PATH = self.old_dir, self.old_path
        self.temp.cleanup()

    def test_empty_conversation_is_not_listed(self):
        database.create_conversation(self.user_id)
        self.assertEqual(database.list_conversations(self.user_id), [])

    def test_real_chat_is_persisted_and_titled(self):
        chat_id = database.create_conversation(self.user_id)
        database.add_message(chat_id, "user", "I need a wedding outfit")
        database.update_conversation_title(chat_id, "   I need a wedding outfit!  ")
        chats = database.list_conversations(self.user_id)
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]["title"], "I need a wedding outfit")
        self.assertEqual(len(database.get_messages(chat_id)), 1)

    def test_conversation_profiles_are_isolated_and_new_chat_is_empty(self):
        first_chat = database.create_conversation(self.user_id)
        second_chat = database.create_conversation(self.user_id)
        save_conversation_profile(first_chat, {"occasion": "Party Wear", "specific_event": "Birthday party"})
        self.assertEqual(get_conversation_profile(first_chat)["occasion"], "Party Wear")
        self.assertEqual(get_conversation_profile(second_chat), {})

    def test_cross_chat_memory_excludes_event_details(self):
        stored = remembered_preferences({
            "gender_group": "Female",
            "skin_tone": "Medium",
            "occasion": "Party Wear",
            "specific_event": "Birthday party",
        })
        new_chat_profile = new_profile(stored)
        self.assertEqual(new_chat_profile["gender_group"], "Female")
        self.assertIsNone(new_chat_profile["occasion"])
        self.assertIsNone(new_chat_profile["specific_event"])

    def test_legacy_conversation_context_rebuilds_from_its_own_messages(self):
        chat_id = database.create_conversation(self.user_id)
        database.add_message(chat_id, "user", "I'm going to a birthday party")
        profile = rebuild_profile(database.get_messages(chat_id))
        self.assertEqual(profile["occasion"], "Party Wear")
        self.assertEqual(profile["specific_event"], "Birthday Party")
        self.assertIsNone(get_conversation_profile(chat_id).get("occasion"))


if __name__ == "__main__":
    unittest.main()