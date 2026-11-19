"""Static safety messages by locale and rule ID."""

GATE_MESSAGES = {
    "en": {
        "pause_training": "Pause training and tell a trusted adult. Seek advice from a qualified clinician before resuming.",
        "awaiting_clearance": "Ask a qualified clinician about return to sport. Review their approved plan with your coach before training.",
        "recovery_guidance": "This feature needs clinician clearance and written guidance. Enter only the relevant movement restrictions or instructions.",
        "food_allergies": "Ask a caregiver or dietitian to help choose meals and check labels and cross-contact. This module pauses personalized meal ideas when allergies are reported.",
    },
    "ta": {
        "pause_training": "பயிற்சியை நிறுத்தி, நம்பிக்கைக்குரிய பெரியவரிடம் சொல்லுங்கள். மீண்டும் தொடங்குவதற்கு முன் தகுதியான மருத்துவ நிபுணரின் ஆலோசனையைப் பெறுங்கள்.",
        "awaiting_clearance": "விளையாட்டுக்கு எப்போது திரும்பலாம் என்று தகுதியான மருத்துவ நிபுணரிடம் கேளுங்கள். பயிற்சிக்கு முன் அவர் அனுமதித்த திட்டத்தை உங்கள் பயிற்சியாளருடன் பரிசீலியுங்கள்.",
        "recovery_guidance": "இந்த அம்சத்தைப் பயன்படுத்த மருத்துவ நிபுணரின் அனுமதியும் எழுத்துப்பூர்வ வழிகாட்டுதலும் தேவை. தொடர்புடைய அசைவுக் கட்டுப்பாடுகள் அல்லது வழிமுறைகளை மட்டும் உள்ளிடுங்கள்.",
        "food_allergies": "உணவைத் தேர்ந்தெடுக்கவும், லேபிள்களையும் ஒவ்வாமை ஏற்படுத்தும் பொருட்கள் கலந்திருக்கக்கூடிய வாய்ப்பையும் சரிபார்க்கவும், பராமரிப்பாளர் அல்லது உணவியல் நிபுணரின் உதவியைக் கேளுங்கள். உணவு ஒவ்வாமை தெரிவிக்கப்பட்டால் தனிப்பயன் உணவு யோசனைகள் நிறுத்தப்படும்.",
    },
    "hi": {
        "pause_training": "प्रशिक्षण रोकें और किसी भरोसेमंद वयस्क को बताएं। फिर से शुरू करने से पहले किसी योग्य स्वास्थ्य विशेषज्ञ से सलाह लें।",
        "awaiting_clearance": "खेल में वापसी के बारे में किसी योग्य स्वास्थ्य विशेषज्ञ से पूछें। प्रशिक्षण से पहले उनकी मंज़ूर की हुई योजना अपने प्रशिक्षक के साथ देखें।",
        "recovery_guidance": "इस सुविधा के लिए स्वास्थ्य विशेषज्ञ की मंज़ूरी और लिखित मार्गदर्शन चाहिए। गतिविधियों से जुड़े प्रासंगिक प्रतिबंध या निर्देश ही दर्ज करें।",
        "food_allergies": "भोजन चुनने, लेबल पढ़ने और एलर्जी पैदा करने वाली चीज़ों के अनजाने में मिल जाने की संभावना जाँचने के लिए किसी देखभालकर्ता या आहार विशेषज्ञ की मदद लें। एलर्जी की जानकारी मिलने पर व्यक्तिगत भोजन सुझाव रोक दिए जाते हैं।",
    },
}


LANGUAGES = {"English": "en", "தமிழ்": "ta", "हिन्दी": "hi"}
MODEL_LANGUAGES = {"en": "English", "ta": "Tamil", "hi": "Hindi"}

CHECKIN_MESSAGES = {
    "en": "Pause training and tell a trusted adult. Ask a qualified clinician for guidance before returning.",
    "ta": "பயிற்சியை நிறுத்தி, நம்பிக்கைக்குரிய பெரியவரிடம் சொல்லுங்கள். மீண்டும் தொடங்கும் முன் தகுதியான மருத்துவ நிபுணரின் ஆலோசனையைப் பெறுங்கள்.",
    "hi": "प्रशिक्षण रोकें और किसी भरोसेमंद वयस्क को बताएं। फिर से शुरू करने से पहले किसी योग्य स्वास्थ्य विशेषज्ञ से सलाह लें।",
}

RULE_TITLES = {
    "en": ("Pain or concerning symptoms", "Clearance pending", "Written guidance required",
           "Food allergy reported", "Soreness reached 4 of 5", "Soreness rose on three consecutive days"),
    "ta": ("வலி அல்லது கவலைக்குரிய அறிகுறிகள்", "மருத்துவ அனுமதி நிலுவையில் உள்ளது", "எழுத்துப்பூர்வ வழிகாட்டுதல் தேவை",
           "உணவு ஒவ்வாமை தெரிவிக்கப்பட்டது", "தசை வலி 5-இல் 4-ஐ எட்டியது", "தசை வலி தொடர்ந்து மூன்று நாட்கள் அதிகரித்தது"),
    "hi": ("दर्द या चिंताजनक लक्षण", "चिकित्सकीय मंज़ूरी बाकी है", "लिखित मार्गदर्शन चाहिए",
           "खाद्य एलर्जी की सूचना", "मांसपेशियों का दर्द 5 में से 4 तक पहुँचा", "मांसपेशियों का दर्द लगातार तीन दिन बढ़ा"),
}
RULE_IDS = ("pause_training", "awaiting_clearance", "recovery_guidance",
            "food_allergies", "high_soreness", "rising_soreness")

FALLBACK_TEXT = {
    "en": "Take a break and review next steps with a coach or trusted adult.",
    "ta": "ஓய்வெடுத்து, அடுத்த படிகளைப் பற்றி பயிற்சியாளர் அல்லது நம்பிக்கைக்குரிய பெரியவருடன் பேசுங்கள்.",
    "hi": "आराम करें और अगले कदमों के बारे में अपने प्रशिक्षक या भरोसेमंद वयस्क से बात करें।",
}
CHAT_REFUSAL = {
    "en": "Talk with a trusted adult and a qualified clinician about health concerns. You can ask me about game decisions or match preparation for your sport.",
    "ta": "உடல்நலம் குறித்த கவலைகளை நம்பிக்கைக்குரிய பெரியவர் மற்றும் தகுதியான மருத்துவ நிபுணருடன் பேசுங்கள். உங்கள் விளையாட்டின் முடிவுகள் அல்லது போட்டித் தயாரிப்பு பற்றி என்னிடம் கேட்கலாம்.",
    "hi": "स्वास्थ्य संबंधी चिंताओं के बारे में किसी भरोसेमंद वयस्क और योग्य स्वास्थ्य विशेषज्ञ से बात करें। आप अपने खेल के फैसलों या मैच की तैयारी के बारे में पूछ सकते हैं।",
}

CHAT_SCOPE = {
    "en": "Ask about game decisions or match preparation for your selected sport.",
    "ta": "நீங்கள் தேர்ந்தெடுத்த விளையாட்டின் ஆட்ட முடிவுகள் அல்லது போட்டித் தயாரிப்பு பற்றிக் கேளுங்கள்.",
    "hi": "अपने चुने हुए खेल में खेल के फैसलों या मैच की तैयारी के बारे में पूछें।",
}

CHAT_URGENT = {
    "en": "Stop playing or exercising now. Tell a trusted adult and get medical help now. If symptoms are severe or worsening, call your local emergency number.",
    "ta": "விளையாட்டு அல்லது உடற்பயிற்சியை இப்போதே நிறுத்துங்கள். நம்பிக்கைக்குரிய பெரியவரிடம் சொல்லி உடனே மருத்துவ உதவி பெறுங்கள். அறிகுறிகள் கடுமையாக இருந்தாலோ மோசமடைந்தாலோ உள்ளூர் அவசர உதவி எண்ணை அழையுங்கள்.",
    "hi": "खेलना या व्यायाम करना अभी बंद करें। किसी भरोसेमंद वयस्क को बताएं और तुरंत चिकित्सकीय मदद लें। लक्षण गंभीर हों या बढ़ रहे हों तो स्थानीय आपातकालीन नंबर पर कॉल करें।",
}

SHIELD_TITLES = {"en": "Coaching plan paused", "ta": "பயிற்சித் திட்டம் இடைநிறுத்தப்பட்டது", "hi": "प्रशिक्षण योजना रोक दी गई"}


def gate_copy(locale, rule):
    message = GATE_MESSAGES[locale].get(rule, CHECKIN_MESSAGES[locale])
    return SHIELD_TITLES[locale], RULE_TITLES[locale][RULE_IDS.index(rule)], message
