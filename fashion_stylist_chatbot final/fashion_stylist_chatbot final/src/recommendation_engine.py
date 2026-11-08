"""Catalog-based outfit ranking using the updated 24-column dataset."""
import re
import pandas as pd
from config import MODEL_PATH
from src.data_loader import load_dataset


class RecommendationEngine:
    def __init__(self):
        self.df = load_dataset()

    @staticmethod
    def _season_matches(season, catalog_season):
        season = (season or "").lower()
        catalog_season = (catalog_season or "").lower()
        if any(value in season for value in ("summer", "hot")):
            return catalog_season in {"summer", "spring"}
        if any(value in season for value in ("winter", "cold")):
            return catalog_season in {"winter", "autumn"}
        return season in catalog_season or catalog_season in season

    @staticmethod
    def _matches_profile(row, profile):
        weights = {
            "gender_group": 1,
            "age_group": 2,
            "occasion": 3,
            "specific_event": 5,
            "season": 4,
            "skin_tone": 3,
            "height": 2,
            "color": 4,
            "body_type": 2,
        }
        checks = {}
        gender = str(profile.get("gender_group") or "").lower()
        if gender and gender != "skipped":
            catalog_gender = str(row.gender).lower()
            checks["gender_group"] = (
                catalog_gender in {"female", "unisex", "unisex/kids"}
                if any(value in gender for value in ("female", "woman", "girl"))
                else catalog_gender in {"male", "unisex", "unisex/kids"}
                if any(value in gender for value in ("male", "man", "boy"))
                else catalog_gender in {"child", "unisex/kids", "unisex"}
            )

        age = str(profile.get("age_group") or "").lower()
        if age and age != "skipped":
            catalog_age = str(row.age_group).lower()
            age_terms = {
                "senior": "senior", "elderly": "senior", "old": "senior",
                "child": "child", "kid": "child", "teen": "teen",
                "young": "young", "middle": "middle",
            }
            age_term = next((term for key, term in age_terms.items() if key in age), age)
            checks["age_group"] = age_term in catalog_age

        occasion = str(profile.get("occasion") or "").lower()
        if occasion and occasion != "skipped":
            occasion_map = {"formal": "formal wear", "wedding": "wedding wear", "party": "party wear", "casual": "casual wear", "college": "college wear"}
            target = next((value for key, value in occasion_map.items() if key in occasion), occasion)
            checks["occasion"] = str(row.occasion).lower() == target

        event = str(profile.get("specific_event") or "").lower()
        if event and event not in {"skipped", "not applicable"}:
            checks["specific_event"] = event in str(row.specific_event).lower()

        season = str(profile.get("season") or profile.get("weather") or "").lower()
        if season and season != "skipped":
            checks["season"] = RecommendationEngine._season_matches(season, str(row.season))

        for field, column in (("skin_tone", "skin_tone"), ("height", "height_category"), ("body_type", "body_type")):
            value = str(profile.get(field) or "").lower()
            if value and value != "skipped":
                if field == "height" and value == "petite":
                    value = "short"
                if field == "skin_tone" and value == "dark":
                    value = "deep"
                checks[field] = value in str(getattr(row, column)).lower()

        color = str(profile.get("color") or "").lower()
        if color and color != "skipped":
            checks["color"] = bool(re.search(rf"\b{re.escape(color)}\b", str(row.recommended_colors).lower()))

        provided_weight = sum(weights[field] for field in checks)
        matched_weight = sum(weights[field] for field, matched in checks.items() if matched)
        percentage = round(100 * matched_weight / provided_weight) if provided_weight else 0
        return percentage, sum(checks.values()), len(checks)

    def recommend(self, profile: dict, limit=1):
        df = self.df.copy()

        # 1. Gender Filter
        gender = (profile.get("gender_group") or "").strip().lower()
        if gender and gender != "skipped":
            if "female" in gender or "woman" in gender or "girl" in gender:
                df = df[df["gender"].str.lower().isin(["female", "unisex", "unisex/kids"])]
            elif "male" in gender or "man" in gender or "boy" in gender:
                df = df[df["gender"].str.lower().isin(["male", "unisex", "unisex/kids"])]
            elif "child" in gender or "kid" in gender:
                df = df[df["gender"].str.lower().isin(["child", "unisex/kids", "unisex"])]

        # 2. Age Group Filter
        age = (profile.get("age_group") or "").strip().lower()
        if age and age != "skipped":
            if "senior" in age or "elderly" in age or "old" in age:
                df_age = df[df["age_group"].str.lower().str.contains("senior")]
                if not df_age.empty: df = df_age
            elif "child" in age or "kid" in age:
                df_age = df[df["age_group"].str.lower().str.contains("child")]
                if not df_age.empty: df = df_age
            elif "teen" in age:
                df_age = df[df["age_group"].str.lower().str.contains("teen")]
                if not df_age.empty: df = df_age
            elif "young" in age:
                df_age = df[df["age_group"].str.lower().str.contains("young")]
                if not df_age.empty: df = df_age
            elif "middle" in age:
                df_age = df[df["age_group"].str.lower().str.contains("middle")]
                if not df_age.empty: df = df_age

        # 3. Occasion Filter
        occasion = (profile.get("occasion") or "").strip().lower()
        if occasion and occasion != "skipped":
            occ_map = {
                "formal": "formal wear",
                "wedding": "wedding wear",
                "party": "party wear",
                "casual": "casual wear",
                "college": "college wear",
            }
            target_occ = None
            for k, v in occ_map.items():
                if k in occasion:
                    target_occ = v
                    break
            if target_occ:
                df_occ = df[df["occasion"].str.lower() == target_occ]
                if not df_occ.empty:
                    df = df_occ

        if df.empty:
            df = self.df.copy()

        seen_ids = {str(value) for value in profile.get("seen_outfit_ids", []) if value}
        if seen_ids:
            df = df[~df["outfit_id"].astype(str).isin(seen_ids)]

        # Ranking heuristic based on matching features
        weather = (profile.get("season") or profile.get("weather") or "").strip().lower()
        skin_tone = (profile.get("skin_tone") or "").strip().lower()
        body_type = (profile.get("body_type") or "").strip().lower()
        height = (profile.get("height") or "").strip().lower()
        specific_event = (profile.get("specific_event") or "").strip().lower()
        preferred_color = (profile.get("color") or "").strip().lower()
        
        unavailable = [str(x).lower() for x in profile.get("unavailable_items", []) if x]
        disliked = [str(x).lower() for x in profile.get("disliked_items", []) if x]
        prohibited = unavailable + disliked

        ranked = []
        for row in df.itertuples(index=False):
            # Combine all text fields to check against prohibited items
            combined_text = " ".join([
                str(row.outfit_name), str(row.outfit_type), str(row.clothing_items),
                str(row.recommended_colors), str(row.fabric), str(row.footwear),
                str(row.bag_or_clutch), str(row.other_accessories)
            ]).lower()

            if any(p in combined_text for p in prohibited):
                continue

            score = 0.0

            # Specific event match
            if specific_event and specific_event in str(row.specific_event).lower():
                score += 5.0

            # Season / Weather match
            row_season = str(row.season).lower()
            if weather:
                if any(w in weather for w in ["summer", "hot"]) and any(s in row_season for s in ["summer", "spring"]):
                    score += 4.0
                elif any(w in weather for w in ["winter", "cold"]) and any(s in row_season for s in ["winter", "autumn"]):
                    score += 4.0
                elif any(
                    season in weather and season in row_season
                    for season in ["spring", "autumn", "rainy"]
                ):
                    score += 4.0

            # Skin Tone match
            if skin_tone and skin_tone in str(row.skin_tone).lower():
                score += 3.0

            if preferred_color and preferred_color in str(row.recommended_colors).lower():
                score += 4.0

            # Body Type match
            if body_type and body_type in str(row.body_type).lower():
                score += 2.0

            # Height Category match
            if height and height in str(row.height_category).lower():
                score += 2.0

            match_percentage, matched_details, provided_details = self._matches_profile(row, profile)
            ranked.append((match_percentage, score, row, matched_details, provided_details))

        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)

        results = []
        for match_percentage, score, row, matched_details, provided_details in ranked[:limit]:
            results.append({
                "outfit_id": row.outfit_id,
                "gender": row.gender,
                "age_group": row.age_group,
                "occasion": row.occasion,
                "specific_event": row.specific_event,
                "outfit_name": row.outfit_name,
                "outfit_type": row.outfit_type,
                "clothing_items": row.clothing_items,
                "recommended_colors": row.recommended_colors,
                "skin_tone": row.skin_tone,
                "skin_tone_color_match": row.skin_tone_color_match,
                "body_type": row.body_type,
                "height_category": row.height_category,
                "season": row.season,
                "fabric": row.fabric,
                "footwear": row.footwear,
                "earrings": row.earrings,
                "jewelry": row.jewelry,
                "watch": row.watch,
                "bag_or_clutch": row.bag_or_clutch,
                "other_accessories": row.other_accessories,
                "dupatta_or_scarf_styling": row.dupatta_or_scarf_styling,
                "styling_tips": row.styling_tips,
                "modesty_level": row.modesty_level,
                "score": score,
                "match_percentage": match_percentage,
                "matched_details": matched_details,
                "provided_details": provided_details,
            })

        return results

    def predict_item_category(self, text):
        """Predict an item category if the trained ML model is available."""
        if not MODEL_PATH.exists():
            return None
        try:
            import joblib
            model = joblib.load(MODEL_PATH)
            return str(model.predict([text])[0])
        except Exception:
            return None