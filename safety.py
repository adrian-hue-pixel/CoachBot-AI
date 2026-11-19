"""Deterministic preflight gates for user-facing requests.

The offline evaluator uses fixed fictional profiles and intentionally measures
raw model outputs. The public app must apply these gates before generation.
"""

import re
from typing import TYPE_CHECKING
import unicodedata

from checkins import LOADS

if TYPE_CHECKING:
    from coach import Profile


def blocking_rule(profile: "Profile", feature, *, physical, recovery):
    """Return the first applicable rule ID, ordered as in the public safety gate."""
    if profile.concern or profile.check_in == "Pain or worsening symptoms":
        return "pause_training"
    if profile.injury_status == "Active injury or awaiting clearance" and feature in physical:
        return "awaiting_clearance"
    if feature in recovery and (profile.injury_status != "Clinician cleared" or not profile.restrictions.strip()):
        return "recovery_guidance"
    if feature == "Weekly nutrition ideas" and profile.allergies.strip():
        return "food_allergies"
    return None


# These are categories for local enforcement and retry feedback. A rejected
# phrase is deliberately never copied into the UI, logs or retry request.
FOOD_GROUP = (
    r"food groups?|carb(?:ohydrate)?s?|grains?|starches?|fruit|vegetables?|dairy|"
    r"proteins?|fats?|bread|rice|meat"
)
MINERALS_AND_VITAMINS = (
    r"vitamins?(?:\s+[abcdek](?:\d{1,2})?)?|[bdenk](?:1[02]|[1-9])|folic acid|folate|"
    r"iron|magnesium|calcium|zinc|selenium|iodine|copper|manganese|chromium|"
    r"potassium|sodium|phosphorus|electrolytes?"
)
MICRONUTRIENT_AMOUNT = r"\d[\d,.]*\s*[-–]?\s*(?:mg|mcg|μg|ug|iu|milligrams?|micrograms?|international units?)"


BANNED = {
    "nutrition_targets": (
        r"\b(?:calories?|kcal|kilocalories?|macros?|macronutrient)\s*(?:target|goal|limit|budget|intake|deficit|surplus)",
        r"\b(?:target|limit|track|count|cut|restrict)\b.{0,25}\b(?:calories?|macros?)\b",
        r"\b\d[\d,.]*\s*(?:kcal|calories?|kilocalories?|g(?:rams?)?\s*(?:of\s+)?(?:carb\w*|protein|fat\w*))\b",
        r"\bmacros?\s*[:=]\s*\d|\b(?:carbs?|protein|fat)\s*[:=-]?\s*\d+(?:\.\d+)?\s*(?:g(?:rams?)?|%)\b",
        r"\b(?:lose weight|weight loss|calorie restriction|energy deficit)\b",
        r"கலோரி|மேக்ரோ|எடை குறை|कैलोरी|मैक्रो|वज़न घटा|वजन घटा",
    ),
    "restrictive_eating": (
        r"\b(?:skip(?:ping)?|miss|forgo|omit|go without|avoid|give up)\s+(?:[\w-]+\s+){0,3}"
        r"(?:breakfast|lunch|dinner|supper|(?:morning|midday|evening) meals?|meals?)\b",
        r"\b(?:intermittent fasting|train(?:ing)? fasted|fasted (?:practice|workouts?|training)|"
        r"fast(?:ing)? (?:(?:until|through) (?:after|before|noon|evening|tomorrow|the (?:morning|afternoon|evening)|[0-9])|for (?:(?:\d+|[\w-]+) )?(?:hours?|days?|a week)|before (?:practice|training))|(?:start|try|follow|use|extend|begin|continue|consider|recommend) (?:a |an |your )?(?:[\w-]+ )?fast(?:ing)?|"
        r"fasting (?:will|can|should) (?:help|support|keep)|delay (?:eating|breakfast|lunch|dinner|(?:your )?(?:first )?meal) until|"
        r"(?:don't|do not) eat (?:until|before)|(?:eat|have) only (?:one|two|a single|[12]) meals?)\b",
        rf"\b(?:cut\s+(?:out\s+|all\s+)|remove\s+|eliminate\s+|drop\s+|give\s+up\s+|leave\s+out\s+|go\s+without\s+)"
        rf"(?:(?:all|entire|an|a|the|any|your|every|whole)\s+){{0,4}}(?:{FOOD_GROUP})\b",
        rf"\b(?:cut|avoid|exclude)\s+(?:(?:any|an|all|entire|the|every|whole)\s+){{1,4}}(?:{FOOD_GROUP})\b",
        r"\b(?:stay|keep (?:yourself|your weight)|remain|get)\s+(?:as\s+)?(?:light(?:er)?|lean)\b"
        r"(?!\s+(?:on\s+(?:your|the)\s+feet|hearted))",
        r"(?:உணவை|காலை உணவை)\s*(?:தவிர்|விட்டுவிடு)|உண்ணாவிரதம்\s*(?:இரு|மேற்கொள்)|"
        r"(?:नाश्ता|खाना|भोजन)\s+(?:छोड़|मत खा)|(?:उपवास|व्रत)\s+(?:रखो|करो)",
    ),
    "supplements": (
        r"\b(?:supplements?|creatine|whey|pre[ -]?workouts?|protein powder|bcaa\w*|energy drinks?)\b",
        r"\b\d[\d,.]*\s*(?:mg|grams?|scoops?)\s*(?:of\s+)?(?:sodium|potassium|electrolytes?)\b",
        rf"\b{MICRONUTRIENT_AMOUNT}\b\s*(?:of\s+)?(?:{MINERALS_AND_VITAMINS})\b",
        rf"\b(?:{MINERALS_AND_VITAMINS})\b\s*(?:[(:=–-]\s*|(?:at|dose of)\s+)?{MICRONUTRIENT_AMOUNT}\b",
        r"கிரியாட்டின்|புரதத் தூள்|சப்ளிமெண்ட்|सप्लीमेंट|क्रिएटिन|प्रोटीन पाउडर",
    ),
    "unsafe_load": (
        r"\b(?:1\s*rm|(?:one|1)[ -]rep max(?:imum)?|max(?:imum)?[ -](?:lifts?|effort|weights?|loads?|deadlift|squat|bench press)|100\s*% of (?:your |the )?max|"
        r"train(?:ing)? to failure|as heavy as possible|all[ -]out)\b",
        r"\b(?:push|play|train|work|exercise|run|keep going) (?:on |anyway |right )?(?:through|despite) (?:the |your )?pain\b",
        r"\b(?:ignore|tolerate|push past) (?:the |your )?pain\b",
        r"\b(?:push|play|train|work|exercise|run|lift|keep going|keep training|continue(?: the drill)?)"
        r"\s+(?:(?:on|anyway|right)\s+)?(?:through|despite|even if)\s+(?:the |your )?"
        r"(?:soreness|fatigue|exhaustion|tiredness|aching|(?:legs|muscles|you) (?:are|feel) (?:aching|sore|tired|exhausted))\b",
        r"\b(?:ignore|tolerate|push past) (?:the |your )?(?:soreness|fatigue|aching|exhaustion)\b",
        r"\b(?:until|till) you (?:can(?:not|'t) (?:continue|go on|go any further|do any more)|"
        r"(?:have )?(?:nothing|no energy) left|(?:are|'re) (?:exhausted|spent))\b",
        r"\b(?:100|one hundred)\s*(?:%|percent|per cent)\s*(?:of (?:your|the) )?(?:max(?:imum)?\s+)?effort\b",
        r"\bas (?:much weight|heavy) as you can(?: (?:lift|manage|handle))?\b|"
        r"\b(?:use|give|at|with|aim for) (?:your )?(?:full|maximal|maximum) effort\b|\bto (?:complete|total) exhaustion\b",
        r"வலியைப் புறக்கணி|दर्द के बावजूद|दर्द को नज़रअंदाज़",
    ),
    "external_or_personal_data": (
        r"https?://|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}|"
        r"\b(?:full name|my name is|i am called|i live at|home address|phone number|send a photo|upload (?:a |your )?photo)\b",
    ),
}
BANNED = {category: re.compile("|".join(patterns), re.IGNORECASE) for category, patterns in BANNED.items()}

INJURY = (
    r"(?:sprain(?:ed)?|fracture(?:d)?|concussion|(?:[\w-]+\s+){0,2}(?:tear|injury)|strain(?:ed)?|"
    r"torn (?:[\w-]+\s+){0,2}(?:ligament|tendon|muscle|meniscus|acl))"
)
CLINICAL_MENTION = re.compile(
    r"\b(?:diagnos\w*|rehab(?:ilitat\w*)?|treatment plan|"
    r"(?:sounds like (?:you have )?|you (?:likely |probably |may |might |could )?have |this is |your [\w ]{1,36}? is )"
    rf"(?:an? )?{INJURY})\b"
    rf"|\b(?:suggests?|indicat(?:es?|ing)|points? to|consistent with|likely to be|"
    rf"possibly|probably|most likely|likely (?:have|sustained))\s+(?:an? )?{INJURY}\b"
    r"|\b(?:(?:you |you've |you have )(?:(?:most |very )?likely |probably |may have |might have |could have )?"
    r"|(?:most likely|probably|possibly) )"
    r"(?:tore|torn|ruptur(?:ed)|sprained|fractured|dislocated)\s+(?:[\w-]+\s+){0,4}"
    r"(?:ligament|tendon|muscle|meniscus|acl|ankle|wrist|knee|shoulder|bone|finger)\b"
    r"|நோயறிதல்|மறுவாழ்வு பயிற்சி|निदान|पुनर्वास व्यायाम", re.I
)
FIRST_AID = re.compile(
    r"\b(?:apply|use|put|place)\s+(?:[\w-]+\s+){0,4}"
    r"(?:ice(?:\s+packs?)?|cold\s+(?:packs?|compress(?:es)?)|compression(?:\s+(?:wraps?|bandages?|sleeves?))?|"
    r"(?:a\s+)?tight\s+bandage)\b|"
    r"\b(?:ice|compress|elevate)\s+(?:[\w-]+\s+){0,4}"
    r"(?:injur(?:y|ed (?:area|limb))|area|limb|ankle|knee|wrist|leg|arm|"
    r"shoulder|foot|hand|swelling|bruis(?:e|ed area)|bandage)\b|"
    r"\b(?:treat|manage)\s+(?:[\w-]+\s+){0,5}(?:with|using)\s+(?:ice|compression|elevation)\b|"
    r"\bwrap\s+(?:[\w-]+\s+){0,5}(?:swollen|injured|bandage|compression)\b|"
    r"\b(?:use|follow|try)\s+(?:the\s+)?rice\s+(?:method|protocol|approach|for (?:the |your )?(?:injury|sprain|swelling))\b",
    re.I,
)
CLINICAL_LIMIT = re.compile(
    r"\b(?:not (?:an? |your |the )?|(?:can(?:not|'t)|do(?: not|n't)|won't|never) "
    r"(?:give |provide |offer |make |diagnose or prescribe )?(?:an? |your |the )?)$",
    re.I,
)
CLINICIAN = r"(?:qualified )?(?:clinician|doctor|physician|physiotherapist|health(?:care| care) (?:professional|provider))"
CLINICAL_REFERRAL = re.compile(
    rf"\b(?:ask|consult|see|visit|speak (?:to|with)|talk (?:to|with)|check with) (?:an? |your |the )?{CLINICIAN}"
    r"(?:\s+(?:about|for|if|whether|to|before)\b[\w '’-]{0,42})?\s*$", re.I
)
CLINICAL_REFERRAL_SUFFIX = re.compile(rf"(?:\s+(?:plan|routine|exercises?|guidance))?\s+(?:with|from) (?:an? |your |the )?{CLINICIAN}\b", re.I)
REFERRAL_ACTION = re.compile(r"\b(?:discuss|review|check|confirm|seek) (?:(?:an?|your|the|existing|written|approved) ){0,4}$", re.I)


CLAUSE_BOUNDARY = re.compile(
    r"[.!?;:]|\b(?:but|however|yet)\b|\band (?=(?:start|do|follow|perform|complete|begin|you)\b)"
)
PROTECTIVE_CONTEXT = re.compile(
    r"\b(?:not|don't|do not|never|avoid|stop|without|refrain from|instead of)"
    r"\s+(?:[\w-]+\s+){0,2}$", re.I
)


def _advice_match(pattern, text, *, clinical=False):
    for match in pattern.finditer(text):
        before = CLAUSE_BOUNDARY.split(text[:match.start()])[-1]
        if clinical:
            if CLINICAL_LIMIT.search(before) or CLINICAL_REFERRAL.search(before):
                continue
            if REFERRAL_ACTION.search(before) and CLINICAL_REFERRAL_SUFFIX.match(text[match.end():]):
                continue
        if PROTECTIVE_CONTEXT.search(before):
            continue
        return True
    return False


def _clinical_advice(text):
    return _advice_match(CLINICAL_MENTION, text, clinical=True) or _advice_match(FIRST_AID, text, clinical=True)


MOVEMENT_PATTERNS = {
    "jump": r"jump\w*|hop(?:s|ped|ping)?|plyometric\w*|leap\w*|skipping|(?<!out of )bound(?:s|ed|ing)?|குதிக்க|छलांग|कूद",
    "run": r"run(?:s|ning)?|sprint\w*|jog\w*|shuttle runs?|ஓட|दौड़",
    "cut": r"cut(?:s|ting)?|pivot\w*|change[s]? of direction|change direction|திசை மாற்ற|दिशा बदल",
    "overhead": r"overhead|(?:over|above) (?:your |the |their |her |his )?(?:head|shoulders?)|reach(?:es|ed|ing)? (?:straight )?up(?:wards?)?|தலைக்கு மேல்|सिर के ऊपर",
    "squat": r"squat\w*|குந்து|स्क्वाट",
    "lunge": r"lunge\w*|லஞ்ச்|लंज",
    "contact": r"contact(?!\s+(?:your|the coach|a clinician|an adult)\b)|tackl\w*|collision\w*|scrimmag\w*|மோதல்|टक्कर",
    "lift": r"lift\w*|resistance train\w*|free weights?|பளு தூக்|वज़न उठ|वजन उठ",
}
RESTRICTION_MARKERS = re.compile(r"\b(?:no|avoid|without|do not|don't|cannot|can't|skip|limit)\b|வேண்டாம்|தவிர்|मत |बचें", re.I)
PRESCRIPTIVE_EXERCISE = re.compile(
    r"\b\d+\s*(?:reps?|repetitions?|sets?)(?:\b|\s+of)|"
    r"\b\d+\s*[x×]\s*\d+\b|"
    r"\b(?:do|perform|complete|repeat)\s+(?:\d+|one|two|three|four|five|ten)\s+"
    r"(?:[\w-]+\s+){0,2}(?:reps?|repetitions?|sets?|rounds?|drills?|exercises?|"
    r"push[ -]?ups?|squats?|lunges?|sprints?|jumps?|hops?|laps?)\b|"
    r"\b(?:do|perform|complete)\s+(?:(?:a|the|your|these)\s+)?(?:\w+\s+){0,2}"
    r"(?:workouts?|exercise sets?|reps?|push[ -]?ups?|squats?|lunges?|sprints?)\b|"
    r"\d+\s*(?:தடவை|முறை)\s*(?:செய்|ஓட|குதி)|\d+\s*(?:रेप|सेट|बार)\s*(?:कर|लग)", re.I
)


QUANTITY = r"(?:\d+(?:[.,]\d+)?|one|two|three|four|five|ten|twenty|thirty|forty|sixty|half an?)"
DURATION_OR_DISTANCE = (
    r"[-\s]*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|"
    r"kilomet(?:re|er)s?|met(?:re|er)s?|yards?|miles?|laps?|km|m)"
)
EXERCISE_TERM = (
    r"(?:jogs?|runs?|walks?|sprints?|rides?|cycles?|laps?|holds?|planks?|drills?|"
    r"intervals?|stretches?|squats?|lunges?|workouts?|skips?|push[ -]?ups?|hops?|exercise)"
)
TIMED_OR_VOLUME = re.compile(
    rf"\b(?:do|perform|complete|repeat|finish|start|take|add|schedule|try|include)\s+"
    rf"(?:(?:an?|the|your|another|easy|light|brisk|steady)\s+){{0,4}}{QUANTITY}{DURATION_OR_DISTANCE}"
    rf"(?:\s+of)?\s+(?:[\w-]+\s+){{0,2}}{EXERCISE_TERM}\b|"
    rf"\b(?:hold|maintain|repeat|perform|do)\s+(?:[\w-]+\s+){{0,4}}{EXERCISE_TERM}\s+for\s+"
    rf"{QUANTITY}{DURATION_OR_DISTANCE}\b|"
    rf"\b(?:run|jog|walk|sprint|cycle|ride|skip|stretch|plank)\s+(?:(?:briskly|gently|slowly|steadily|for|an?|another)\s+){{0,4}}"
    rf"{QUANTITY}{DURATION_OR_DISTANCE}\b", re.I
)


def _prescribed_exercise(text):
    return _advice_match(PRESCRIPTIVE_EXERCISE, text) or _advice_match(TIMED_OR_VOLUME, text)


def _named_movement(pattern, text):
    return re.search(rf"(?<!\w)(?:{pattern})(?!\w)", text)


chat_medical_request = re.compile(
    r"\b(?:what(?:'s| is) wrong with|what (?:injury|condition) (?:do|might) i have|signs of|"
    r"is (?:it|this|my) (?:a |an )?(?:sprain|fracture|concussion|torn)|how (?:do i |to )?(?:treat|heal|rehab))\b"
    r"|\b(?:do i have (?:a |an )?(?:concussion|fracture|sprain|tear)|"
    r"my (?:ankle|knee|shoulder|head|wrist) (?:hurts|is swollen)|is my .*? sprained)\b"
    r"|என்ன காயம்|इलाज|क्या .* चोट", re.I
)


CHAT_TOPIC = re.compile(
    r"\b(?:footwork|space|position(?:ing|s)?|role|strateg\w*|pass(?:es|ing)?|defend\w*|attack\w*|marking|shoot\w*|drill\w*|"
    r"games?|match\w*|sport\w*|tactic\w*|team\w*|coach\w*|practic\w*|play\w*|throw\w*|"
    r"ball|movement|scor\w*|focus|nerv\w*|calm|confidence|mistakes?|prepare|preparation|cue\w*)\b"
    r"|ஆட்டம்|போட்டி|விளையாட்டு|பந்து|கவனம்|பயிற்சி|खेल|मैच|गेंद|तैयारी|अभ्यास|ध्यान", re.I
)
FOLLOW_UP = re.compile(r"^(?:why|how so|what do you mean|can you explain|an example|give me an example)\b", re.I)
INPUT_LIMITS = {"goal": 150, "restrictions": 250, "allergies": 120, "chat": 300}


def chat_in_scope(question, profile, has_context):
    return bool(
        CHAT_TOPIC.search(question)
        or normalized(profile.sport) in question
        or normalized(profile.position) in question
        or (has_context and FOLLOW_UP.search(question))
    )


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().replace("’", "'").split())


def input_too_long(field, text):
    return len(text) > INPUT_LIMITS[field]


def chat_request_action(question, profile, has_context):
    """Decide whether a chat turn can reach generation."""
    if input_too_long("chat", question):
        return "block"
    plain = normalized(question)
    categories = lint_output(question, profile, sport_scope=True)
    if chat_medical_request.search(plain) or "clinical_advice" in categories:
        return "refuse"
    if categories or not chat_in_scope(plain, profile, has_context):
        return "redirect"
    return "allow"


def lint_output(output, profile=None, *, cap=None, sport_scope=False, rest_only=False):
    """Return stable violation categories for public output or offline scoring."""
    if isinstance(output, str):
        text = output
        rows = ()
    else:
        rows = output["rows"]
        text = " ".join([output["summary"], output["review"]] + [
            value for row in rows for value in row.values() if isinstance(value, str)
        ])
    text = normalized(text)
    violations = [
        category for category, pattern in BANNED.items()
        if (_advice_match(pattern, text) if category in ("restrictive_eating", "unsafe_load") else pattern.search(text))
    ]
    if _clinical_advice(text):
        violations.append("clinical_advice")
    if cap and (any(row.get("load") in LOADS and LOADS.index(row["load"]) > LOADS.index(cap)
                    for row in rows) or (cap == "Light" and re.search(r"\b(?:moderate|high|vigorous) intensity\b|மிதமான தீவிரம்|मध्यम तीव्रता", text))):
        violations.append("workload_cap")
    prescriptive = rest_only and _prescribed_exercise(text)
    if rest_only and (any(row.get("load") not in (None, "Rest") for row in rows) or prescriptive):
        if "workload_cap" not in violations:
            violations.append("workload_cap")
    if profile:
        restrictions = normalized(profile.restrictions)
        if restrictions:
            clauses = re.split(r"[.,;]|\b(?:but|however)\b", restrictions)
            allowed = r"\b(?:allowed|permitted|okay|cleared to|may resume|can continue)\b"
            clauses = [clause for clause in clauses
                       if RESTRICTION_MARKERS.search(clause) or not re.search(allowed, clause)]
            patterns = [pattern for pattern in MOVEMENT_PATTERNS.values()
                        if any(_named_movement(pattern, clause) for clause in clauses)]
            literals = [RESTRICTION_MARKERS.sub("", part).strip()
                        for clause in clauses if RESTRICTION_MARKERS.search(clause)
                        for part in re.split(r"\b(?:and|or)\b", clause)]
            if (any(_named_movement(pattern, text) for pattern in patterns)
                    or any(len(term) > 2 and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) for term in literals)
                    or prescriptive):
                violations.append("stated_restrictions")
        allergens = re.split(r"[,;/]|\band\b", normalized(profile.allergies))
        allergens = [re.sub(r"^(?:allergic to|allergy to)\s+", "", term.strip()).removesuffix("s")
                     for term in allergens]
        if any(term and re.search(rf"(?<!\w){re.escape(term)}s?(?!\w)", text) for term in allergens):
            violations.append("food_allergy")
        if sport_scope:
            sports = {
                "Football": r"\b(?:football|soccer)\b|கால்பந்து|फुटबॉल",
                "Cricket": r"\bcricket\b|கிரிக்கெட்|क्रिकेट",
                "Basketball": r"\bbasketball\b|கூடைப்பந்து|बास्केटबॉल",
            }
            if any(re.search(pattern, text) for sport, pattern in sports.items() if sport != profile.sport):
                violations.append("sport_scope")
    return tuple(violations)
