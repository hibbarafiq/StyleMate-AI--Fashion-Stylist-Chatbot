"""Suggest substitutions when the user lacks, rejects, or wants to change an item."""
ALTERNATIVES = {
    "heels": ["flats", "dressy sandals", "low block heels if comfortable"],
    "high heels": ["flats", "dressy sandals", "low block heels if comfortable"],
    "shoes": ["comfortable flats", "clean sneakers", "sandals appropriate for the occasion"],
    "shoe": ["comfortable flats", "clean sneakers", "sandals appropriate for the occasion"],
    "footwear": ["comfortable flats", "dressy sandals", "clean sneakers appropriate for the occasion"],
    "sneakers": ["loafers", "flats", "simple casual shoes"],
    "boots": ["closed-toe flats", "loafers", "simple sneakers"],
    "khussas": ["traditional flats", "kolhapuris", "comfortable slip-ons"],
    "kolhapuris": ["khussas", "flat sandals", "comfortable slip-ons"],
    "dupatta": ["a modest long outer layer", "a scarf in a coordinating color", "a pre-stitched stole"],
    "hijab": ["a coordinating lightweight scarf or head covering, if desired"],
    "jacket": ["a cardigan", "a long shirt or outer layer", "a shawl in cooler weather"],
    "coat": ["a cardigan", "a warm shawl", "a suitable long outer layer"],
    "jeans": ["straight-leg trousers", "wide-leg trousers", "a modest long skirt where appropriate"],
    "skirt": ["wide-leg trousers", "straight-leg trousers"],
    "dress": ["a coordinated top-and-bottom outfit", "a long tunic with trousers"],
    "accessories": ["one simple watch", "a coordinating scarf", "minimal jewelry"],
    "jewelry": ["minimal earrings", "a simple watch", "no jewelry—keep the outfit clean"],
    "jewellery": ["minimal earrings", "a simple watch", "no jewelry—keep the outfit clean"],
    "bag": ["a small neutral crossbody bag", "a simple clutch for formal events"],
    "clutch": ["a mini velvet potli", "a crossbody sling bag", "a small structured handbag"],
}


def suggest_alternatives(items):
    suggestions = []
    for item in items or []:
        key = item.lower()
        options = ALTERNATIVES.get(key)
        if options:
            suggestions.append((item, options))
    return suggestions