"""Concise, single-outfit responses for the StyleMate chat utilizing the updated 24-column dataset."""


def recommendation_response(recommendations, profile):
    """Show one complete, fully coordinated look with accessories, fabrics, and styling tips."""
    if not recommendations:
        return (
            "I couldn't find a suitable match in the current catalog meeting your criteria. "
            "Would you like to adjust the occasion, weather, or preferences?"
        )

    rec = recommendations[0]
    outfit_id = rec.get("outfit_id", "FW-0001")
    outfit_name = rec.get("outfit_name", "Curated Outfit")
    outfit_type = rec.get("outfit_type", "Complete Ensemble")
    clothing_items = rec.get("clothing_items", "")
    recommended_colors = rec.get("recommended_colors", "")
    color_match_desc = rec.get("skin_tone_color_match", "")
    fabric = rec.get("fabric", "")
    season = rec.get("season", "")
    occasion = rec.get("occasion", "")
    specific_event = rec.get("specific_event", "")
    requested_event = str(profile.get("specific_event") or "").lower()
    if not requested_event or requested_event not in str(specific_event).lower():
        specific_event = ""
    footwear = rec.get("footwear", "")
    earrings = rec.get("earrings", "")
    jewelry = rec.get("jewelry", "")
    watch = rec.get("watch", "")
    bag_or_clutch = rec.get("bag_or_clutch", "")
    other_accessories = rec.get("other_accessories", "")
    dupatta_styling = rec.get("dupatta_or_scarf_styling", "")
    styling_tips = rec.get("styling_tips", "")
    modesty_level = rec.get("modesty_level", "")

    lines = [
        f"Outfit ID: {outfit_id}",
        f"I'd suggest **{outfit_name}** ({outfit_type}).",
        f"**Main Outfit**: {clothing_items}.",
    ]

    match_percentage = rec.get("match_percentage")
    if match_percentage is not None:
        matched = rec.get("matched_details", 0)
        provided = rec.get("provided_details", 0)
        lines.append(
            f"**Catalog match: {match_percentage}%** "
        )

    if recommended_colors:
        color_line = f"**Recommended Colors**: {recommended_colors}"
        if color_match_desc:
            color_line += f" — *{color_match_desc}*"
        lines.append(color_line)

    details = []
    if occasion: details.append(occasion)
    if specific_event and specific_event != "Not Applicable": details.append(specific_event)
    if season: details.append(f"Season: {season}")
    if fabric: details.append(f"Fabric: {fabric}")
    if details:
        lines.append(" · ".join(details))

    # Accessories & Coordinated Items
    accessories = []
    if footwear and footwear != "Not Applicable": accessories.append(f"**Footwear**: {footwear}")
    if bag_or_clutch and bag_or_clutch != "Not Applicable": accessories.append(f"**Bag/Clutch**: {bag_or_clutch}")
    if earrings and earrings != "Not Applicable": accessories.append(f"**Earrings**: {earrings}")
    if jewelry and jewelry != "Not Applicable": accessories.append(f"**Jewelry**: {jewelry}")
    if watch and watch != "Not Applicable": accessories.append(f"**Watch**: {watch}")
    if other_accessories and other_accessories != "Not Applicable": accessories.append(f"**Accessories**: {other_accessories}")
    if dupatta_styling and dupatta_styling != "Not Applicable": accessories.append(f"**Stole/Dupatta**: {dupatta_styling}")

    if accessories:
        lines.append("**Coordinated Accessories**:\n" + "\n".join([f"- {acc}" for acc in accessories]))

    if styling_tips and styling_tips != "Not Applicable":
        lines.append(f"💡 **Styling Tip**: {styling_tips}")

    gender = str(profile.get("gender_group") or "").lower()
    age_group = str(profile.get("age_group") or "").lower()
    if age_group != "child" and occasion in {"Wedding Wear", "Party Wear", "Formal Wear"}:
        if gender in {"female", "woman"}:
            lines.append("**Hair & Makeup**: Keep the makeup balanced for the occasion and choose a comfortable hairstyle that will last through the event.")
        elif gender in {"male", "man"}:
            lines.append("**Grooming**: A neat hairstyle and simple, clean grooming will complete the look.")

    if modesty_level and modesty_level != "Not Applicable":
        lines.append(f"✨ *Modesty & Fit*: {modesty_level}")

    lines.append("Tell me what you'd like to change, and I'll adjust it.")
    return "\n\n".join(lines)


def ask_for_details(profile):
    missing = []
    prompts = {
        "gender_group": "who it's for (female or female)",
        "occasion": "the event or occasion",
        "age_group": "their age or age range",
        "skin_tone": "their skin tone",
        "height": "their height (cm, feet/inches, or short/average/tall)",
        "season": "the season or weather",
    }
    for field, prompt in prompts.items():
        if not profile.get(field) and not (field == "season" and profile.get("weather")):
            missing.append(prompt)
    if not missing:
        return "Tell me if you'd like to refine this look."
    if len(missing) == 1:
        return f"To tailor this, what's {missing[0]}?"
    return "To tailor this, tell me " + ", ".join(missing[:-1]) + f", and {missing[-1]}."