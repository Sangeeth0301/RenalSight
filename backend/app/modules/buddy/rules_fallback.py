"""No-AI fallback: when every LLM provider is unavailable the Buddy still answers from the user's saved data.

Fixed sentences only (no machine translation at run time). Tamil, Bengali and Telugu strings are first drafts and
MUST be reviewed by a native-speaking clinician before real use.
"""
from __future__ import annotations

STR = {
    "en": {
        "offline": "The AI helper is not available right now. Here is a summary from your saved records.",
        "stage": "Kidney stage: {g} ({name}).",
        "egfr": "Kidney filter value (eGFR): {egfr}.",
        "advice": "Please talk to your doctor about these results.",
        "urgent": "Your kidney status is serious. Please contact your doctor or a hospital today.",
        "nodata": "Please add a lab report so I can show your kidney status.",
        "names": {1: "healthy", 2: "mildly stressed", 3: "scarred", 4: "wounded", 5: "failing"},
    },
    "ta": {
        "offline": "AI உதவியாளர் தற்போது கிடைக்கவில்லை. உங்கள் சேமிக்கப்பட்ட பதிவுகளின் சுருக்கம் இதோ.",
        "stage": "சிறுநீரக நிலை: {g}.",
        "egfr": "சிறுநீரக வடிகட்டும் அளவு (eGFR): {egfr}.",
        "advice": "இந்த முடிவுகளைப் பற்றி உங்கள் மருத்துவரிடம் பேசுங்கள்.",
        "urgent": "உங்கள் சிறுநீரக நிலை தீவிரமாக உள்ளது. இன்றே உங்கள் மருத்துவர் அல்லது மருத்துவமனையை அணுகுங்கள்.",
        "nodata": "உங்கள் சிறுநீரக நிலையைக் காட்ட, ஒரு ஆய்வக அறிக்கையைச் சேர்க்கவும்.",
        "names": {1: "", 2: "", 3: "", 4: "", 5: ""},
    },
    "bn": {
        "offline": "এআই সহায়ক এখন পাওয়া যাচ্ছে না। আপনার সংরক্ষিত তথ্যের সারসংক্ষেপ এখানে দেওয়া হলো।",
        "stage": "কিডনির অবস্থা: {g}।",
        "egfr": "কিডনির ছাঁকনি মান (eGFR): {egfr}।",
        "advice": "এই ফলাফল নিয়ে আপনার ডাক্তারের সঙ্গে কথা বলুন।",
        "urgent": "আপনার কিডনির অবস্থা গুরুতর। আজই আপনার ডাক্তার বা হাসপাতালে যোগাযোগ করুন।",
        "nodata": "আপনার কিডনির অবস্থা দেখাতে একটি ল্যাব রিপোর্ট যোগ করুন।",
        "names": {1: "", 2: "", 3: "", 4: "", 5: ""},
    },
    "te": {
        "offline": "AI సహాయకుడు ప్రస్తుతం అందుబాటులో లేదు. మీ నిల్వ చేసిన రికార్డుల సారాంశం ఇది.",
        "stage": "కిడ్నీ స్థితి: {g}.",
        "egfr": "కిడ్నీ వడపోత విలువ (eGFR): {egfr}.",
        "advice": "ఈ ఫలితాల గురించి మీ డాక్టర్‌తో మాట్లాడండి.",
        "urgent": "మీ కిడ్నీ పరిస్థితి తీవ్రంగా ఉంది. ఈరోజే మీ డాక్టర్‌ను లేదా ఆసుపత్రిని సంప్రదించండి.",
        "nodata": "మీ కిడ్నీ స్థితిని చూపడానికి ఒక ల్యాబ్ రిపోర్ట్ జోడించండి.",
        "names": {1: "", 2: "", 3: "", 4: "", 5: ""},
    },
}


def fallback_reply(language: str, state: dict | None) -> str:
    t = STR.get(language, STR["en"])
    parts = [t["offline"]]
    if not state or not state.get("has_data"):
        parts.append(t["nodata"])
        return " ".join(parts)
    name = t["names"].get(state["visual_stage"], "")
    parts.append(t["stage"].format(g=state["g_stage"], name=name).replace(" ()", ""))
    parts.append(t["egfr"].format(egfr=state["egfr"]))
    parts.append(t["urgent"] if state.get("urgent") else t["advice"])
    return " ".join(parts)


ANALYST = {
    "en": {"offline": "The AI analyst is not available right now. You can still use the Population Pulse page.",
           "line": "{region} {year}: about {n} million adults may have kidney disease (estimate).", "none": "Population data is not loaded yet."},
    "ta": {"offline": "AI பகுப்பாய்வாளர் தற்போது கிடைக்கவில்லை. நீங்கள் மக்கள்தொகை நிலை (Population Pulse) பக்கத்தைப் பயன்படுத்தலாம்.",
           "line": "{region} {year}: சுமார் {n} மில்லியன் பெரியவர்களுக்கு சிறுநீரக நோய் இருக்கலாம் (மதிப்பீடு).", "none": "மக்கள்தொகை தரவு இன்னும் ஏற்றப்படவில்லை."},
    "bn": {"offline": "এআই বিশ্লেষক এখন পাওয়া যাচ্ছে না। আপনি জনসংখ্যা (Population Pulse) পাতাটি ব্যবহার করতে পারেন।",
           "line": "{region} {year}: আনুমানিক {n} মিলিয়ন প্রাপ্তবয়স্কের কিডনি রোগ থাকতে পারে (অনুমান)।", "none": "জনসংখ্যার তথ্য এখনও লোড করা হয়নি।"},
    "te": {"offline": "AI విశ్లేషకుడు ప్రస్తుతం అందుబాటులో లేదు. మీరు జనాభా (Population Pulse) పేజీని ఉపయోగించవచ్చు.",
           "line": "{region} {year}: సుమారు {n} మిలియన్ పెద్దలకు కిడ్నీ వ్యాధి ఉండవచ్చు (అంచనా).", "none": "జనాభా డేటా ఇంకా లోడ్ కాలేదు."},
}


def analyst_reply(language: str, region: str | None, year: int | None, millions: float | None) -> str:
    t = ANALYST.get(language, ANALYST["en"])
    if region is None:
        return f"{t['offline']} {t['none']}"
    return f"{t['offline']} " + t["line"].format(region=region, year=year, n=f"{millions:.0f}")
