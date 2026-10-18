"""Fixed message drafts for Doctor Copilot (first drafts: a native-speaking clinician must review ta/bn/te before real use)."""

MSG = {
    "checkup": {
        "en": "Hello {name}, I reviewed your latest report. Your kidney stage is {stage}. Please keep taking your medicines, limit salt, and tell me if you notice swelling or passing less urine. - Dr. {doctor}",
        "ta": "வணக்கம் {name}, உங்கள் சமீபத்திய அறிக்கையைப் பார்த்தேன். உங்கள் சிறுநீரக நிலை {stage}. தொடர்ந்து மருந்துகளை எடுங்கள், உப்பைக் குறையுங்கள்; கால் வீக்கம் அல்லது சிறுநீர் குறைவாக வந்தால் என்னிடம் சொல்லுங்கள். - மரு. {doctor}",
        "bn": "নমস্কার {name}, আমি আপনার সর্বশেষ রিপোর্ট দেখেছি। আপনার কিডনির পর্যায় {stage}। নিয়মিত ওষুধ খান, লবণ কম খান; পা ফুললে বা প্রস্রাব কম হলে আমাকে জানান। - ডা. {doctor}",
        "te": "నమస్కారం {name}, మీ తాజా రిపోర్ట్ చూశాను. మీ కిడ్నీ దశ {stage}. మందులు క్రమం తప్పకుండా వాడండి, ఉప్పు తగ్గించండి; కాళ్ల వాపు లేదా మూత్రం తగ్గితే నాకు చెప్పండి. - డా. {doctor}",
    },
    "urgent": {
        "en": "Hello {name}, your latest report needs attention. Please come to the clinic or call me today. If you have breathlessness, chest pain or very little urine, go to the nearest hospital now. - Dr. {doctor}",
        "ta": "வணக்கம் {name}, உங்கள் சமீபத்திய அறிக்கைக்குக் கவனம் தேவை. இன்றே கிளினிக்கிற்கு வாருங்கள் அல்லது என்னை அழையுங்கள். மூச்சுத் திணறல், நெஞ்சு வலி அல்லது சிறுநீர் மிகக் குறைவாக இருந்தால் உடனே அருகிலுள்ள மருத்துவமனைக்குச் செல்லுங்கள். - மரு. {doctor}",
        "bn": "নমস্কার {name}, আপনার সর্বশেষ রিপোর্টে মনোযোগ দরকার। আজই চেম্বারে আসুন বা আমাকে ফোন করুন। শ্বাসকষ্ট, বুকে ব্যথা বা খুব কম প্রস্রাব হলে এখনই নিকটতম হাসপাতালে যান। - ডা. {doctor}",
        "te": "నమస్కారం {name}, మీ తాజా రిపోర్ట్‌పై శ్రద్ధ అవసరం. ఈరోజే క్లినిక్‌కు రండి లేదా నాకు ఫోన్ చేయండి. ఊపిరి ఆడకపోయినా, ఛాతీ నొప్పి ఉన్నా, మూత్రం చాలా తక్కువగా వచ్చినా వెంటనే దగ్గరి ఆసుపత్రికి వెళ్లండి. - డా. {doctor}",
    },
}


def draft_message(topic: str, lang: str, name: str, stage: str | None, doctor: str) -> str:
    t = MSG.get(topic, MSG["checkup"])
    return t.get(lang, t["en"]).format(name=name, stage=stage or "-", doctor=doctor)
