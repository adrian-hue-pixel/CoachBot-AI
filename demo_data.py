"""Fictional coaching examples for the no-key demo."""

from i18n import FALLBACK_TEXT

DAYS = {
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "ta": ("திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"),
    "hi": ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"),
}
EXAMPLES = {
    "Full-body training": (
        "Review your position with a coach and choose an easy activity you already know.",
        "உங்கள் பங்கைப் பயிற்சியாளருடன் பேசி, ஏற்கெனவே தெரிந்த எளிய செயல்பாட்டைத் தேர்ந்தெடுங்கள்.",
        "अपनी भूमिका पर प्रशिक्षक से बात करें और कोई परिचित हल्की गतिविधि चुनें।"),
    "Return-to-sport schedule": (
        "Ask your coach to review the clinician's existing instructions with you.",
        "மருத்துவ நிபுணரின் வழிமுறைகளைப் பயிற்சியாளருடன் பாருங்கள்.",
        "चिकित्सक के मौजूदा निर्देश अपने प्रशिक्षक के साथ देखें।"),
    "Warm-up and cooldown": (
        "Ask your coach to review your usual preparation and wind-down routine.",
        "வழக்கமான தயாரிப்பு மற்றும் நிறைவு நடைமுறையைப் பயிற்சியாளருடன் பரிசீலியுங்கள்.",
        "अपनी परिचित तैयारी और समापन दिनचर्या पर प्रशिक्षक से बात करें।"),
    "Weekly nutrition ideas": ("Discuss a meal of rice, dal and avocado at home.",
        "சாதம், பருப்பு, அவகாடோ கொண்ட உணவைப் பற்றி வீட்டில் பேசுங்கள்।",
        "चावल, दाल और एवोकाडो वाले भोजन पर घर में बात करें।"),
    "Tactical coaching": ("Pause a match clip and discuss where open space appears.",
        "போட்டி காணொளியை நிறுத்தி, காலி இடம் எங்கே இருக்கிறது என்று பேசுங்கள்.",
        "मैच की क्लिप रोककर देखें कि खाली जगह कहाँ दिखाई देती है।"),
    "Pre-match mental focus": ("Picture the first play and choose one simple focus cue.",
        "முதல் ஆட்டத் தருணத்தைக் கற்பனை செய்து, கவனத்திற்கான ஒரு எளிய குறிப்பைத் தேர்ந்தெடுங்கள்.",
        "पहले खेल के क्षण की कल्पना करें और ध्यान के लिए एक सरल संकेत चुनें।"),
    "Hydration and electrolytes": ("Plan water breaks with your coach before, during and after practice.",
        "பயிற்சிக்கு முன், நடுவில் மற்றும் பின் தண்ணீர் இடைவேளைகளைப் பயிற்சியாளருடன் திட்டமிடுங்கள்.",
        "अभ्यास से पहले, बीच में और बाद में पानी के लिए विराम अपने प्रशिक्षक के साथ तय करें।"),
    "Positional drills": ("Watch a clip and compare two choices for your position.",
        "ஒரு காணொளியைப் பார்த்து, உங்கள் பங்குக்கான இரண்டு தேர்வுகளை ஒப்பிடுங்கள்.",
        "एक क्लिप देखकर अपनी भूमिका के दो विकल्पों की तुलना करें।"),
    "Post-injury mobility check-in": (
        "Check in with your coach about how the clinician's guidance is going.",
        "மருத்துவ நிபுணரின் வழிகாட்டுதல் எப்படி செல்கிறது என்று பயிற்சியாளருடன் பேசுங்கள்.",
        "चिकित्सक के निर्देशों के साथ आपका अनुभव कैसा है, इस पर प्रशिक्षक से बात करें।"),
    "No-equipment training": ("Use a quiet space to picture choices you make in a game.",
        "அமைதியான இடத்தில் போட்டியில் எடுக்கும் முடிவுகளைக் கற்பனை செய்யுங்கள்.",
        "शांत जगह में खेल के दौरान अपने फैसलों की कल्पना करें।"),
    "Weekly progress adaptation": ("Review your check-ins with a coach and set aside time to rest.",
        "தினசரிப் பதிவுகளைப் பயிற்சியாளருடன் பார்த்து ஓய்வுக்கு நேரம் ஒதுக்குங்கள்.",
        "अपने दैनिक रिकॉर्ड प्रशिक्षक के साथ देखें और आराम के लिए समय रखें।"),
}

REST = ("Take a rest day and check in with your coach.", "ஓய்வெடுத்து பயிற்சியாளருடன் பேசுங்கள்.", "आराम करें और अपने प्रशिक्षक से बात करें।")
WHY = ("Discuss what fits your week.", "உங்கள் வாரத்திற்கு ஏற்றதைப் பற்றி பேசுங்கள்.", "बात करें कि आपके सप्ताह में क्या ठीक बैठता है।")
FOODS = (
    ("Rice", "Dal", "Avocado"), ("Brown rice", "Chickpeas", "Avocado"), ("Whole grain bread", "Lentils", "Olive oil"),
)
LOCAL_FOODS = {"ta": ("சாதம்", "பருப்பு", "அவகாடோ"), "hi": ("चावल", "दाल", "एवोकाडो")}
WEEKLY = {"Full-body training", "Return-to-sport schedule", "Weekly nutrition ideas",
          "No-equipment training", "Weekly progress adaptation"}


def demo_plan(profile, feature, locale):
    language = ("en", "ta", "hi").index(locale)
    example = EXAMPLES[feature][language]
    rest, why = REST[language], WHY[language]
    rows = []
    for index, day in enumerate(DAYS[locale] if feature in WEEKLY else DAYS[locale][:1]):
        row = {"when": day, "action": example, "why": why}
        if feature == "Weekly nutrition ideas":
            foods = LOCAL_FOODS[locale] if locale in LOCAL_FOODS else FOODS[index % len(FOODS)]
            row.update(zip(("carbs", "protein", "fats"), foods))
            if locale == "en":
                row["action"] = f"Discuss a meal with {foods[0].lower()}, {foods[1].lower()} and {foods[2].lower()} at home."
        elif feature in WEEKLY:
            resting = index in (1, 3, 6) or bool(profile.restrictions.strip())
            if resting:
                row.update(action=rest, load="Rest")
            elif feature != "Return-to-sport schedule":
                row["load"] = "Light" if feature == "Full-body training" else "Rest"
        rows.append(row)
    return {"summary": example, "rows": rows, "review": why}


def fallback_plan(locale):
    return {"summary": FALLBACK_TEXT[locale], "rows": [{
        "when": DAYS[locale][0], "action": REST[("en", "ta", "hi").index(locale)], "load": "Rest",
        "why": WHY[("en", "ta", "hi").index(locale)],
    }], "review": WHY[("en", "ta", "hi").index(locale)]}
