"""Static data for the transplant hub: blood-group rules, directory of well-known hospitals (NAMES ONLY, unverified), journey steps, message templates."""
BLOOD_GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
# kidney transplant: ABO matters (Rh does not). recipient ABO -> donor ABOs that are compatible
ABO_DONORS = {"O": ["O"], "A": ["A", "O"], "B": ["B", "O"], "AB": ["AB", "A", "B", "O"]}

# (name, short, city, state, country, kind, transplant). Directory entries are well-known institutions; they are NOT verified listings.
HOSPITALS = [
    ("All India Institute of Medical Sciences (AIIMS), New Delhi", "AIIMS", "New Delhi", "Delhi", "India", "hospital", True),
    ("All India Institute of Medical Sciences (AIIMS), Jodhpur", "AIIMS Jodhpur", "Jodhpur", "Rajasthan", "India", "hospital", False),
    ("Kovai Medical Center and Hospital (KMCH)", "KMCH", "Coimbatore", "Tamil Nadu", "India", "hospital", True),
    ("PSG Hospitals", "PSG", "Coimbatore", "Tamil Nadu", "India", "hospital", True),
    ("Christian Medical College (CMC), Vellore", "CMC Vellore", "Vellore", "Tamil Nadu", "India", "hospital", True),
    ("Apollo Hospitals, Greams Road", "Apollo Chennai", "Chennai", "Tamil Nadu", "India", "hospital", True),
    ("MIOT International", "MIOT", "Chennai", "Tamil Nadu", "India", "hospital", True),
    ("Madras Medical Mission", "MMM", "Chennai", "Tamil Nadu", "India", "hospital", True),
    ("Rela Institute and Medical Centre", "Rela", "Chennai", "Tamil Nadu", "India", "hospital", True),
    ("Government Rajaji Hospital", "GRH Madurai", "Madurai", "Tamil Nadu", "India", "hospital", True),
    ("Institute of Post-Graduate Medical Education and Research (SSKM Hospital)", "SSKM", "Kolkata", "West Bengal", "India", "hospital", True),
    ("AMRI Hospitals, Dhakuria", "AMRI", "Kolkata", "West Bengal", "India", "hospital", True),
    ("Apollo Multispeciality Hospitals, Kolkata", "Apollo Kolkata", "Kolkata", "West Bengal", "India", "hospital", True),
    ("Fortis Hospital, Anandapur", "Fortis Kolkata", "Kolkata", "West Bengal", "India", "hospital", True),
    ("Medica Superspecialty Hospital", "Medica", "Kolkata", "West Bengal", "India", "hospital", True),
    ("Narayana Superspeciality Hospital, Howrah", "Narayana Howrah", "Howrah", "West Bengal", "India", "hospital", True),
    ("R. G. Kar Medical College and Hospital", "RG Kar", "Kolkata", "West Bengal", "India", "hospital", False),
    ("Nizam's Institute of Medical Sciences (NIMS)", "NIMS", "Hyderabad", "Telangana", "India", "hospital", True),
    ("Yashoda Hospitals", "Yashoda", "Hyderabad", "Telangana", "India", "hospital", True),
    ("KIMS Hospitals", "KIMS", "Hyderabad", "Telangana", "India", "hospital", True),
    ("Apollo Hospitals, Jubilee Hills", "Apollo Hyderabad", "Hyderabad", "Telangana", "India", "hospital", True),
    ("King George Hospital", "KGH", "Visakhapatnam", "Andhra Pradesh", "India", "hospital", False),
    ("Postgraduate Institute of Medical Education and Research (PGIMER)", "PGIMER", "Chandigarh", "Chandigarh", "India", "hospital", True),
    ("Sanjay Gandhi Postgraduate Institute (SGPGI)", "SGPGI", "Lucknow", "Uttar Pradesh", "India", "hospital", True),
    ("Kokilaben Dhirubhai Ambani Hospital", "Kokilaben", "Mumbai", "Maharashtra", "India", "hospital", True),
    ("Medanta - The Medicity", "Medanta", "Gurugram", "Haryana", "India", "hospital", True),
    ("Sir Ganga Ram Hospital", "SGRH", "New Delhi", "Delhi", "India", "hospital", True),
    ("Manipal Hospital", "Manipal", "Bengaluru", "Karnataka", "India", "hospital", True),
    ("Aster Medcity", "Aster", "Kochi", "Kerala", "India", "hospital", True),
    ("Cleveland Clinic", "Cleveland Clinic", "Cleveland", "Ohio", "USA", "hospital", True),
    ("Mayo Clinic", "Mayo", "Rochester", "Minnesota", "USA", "hospital", True),
    ("Guy's and St Thomas' NHS Foundation Trust", "Guy's", "London", "England", "UK", "hospital", True),
    ("Singapore General Hospital", "SGH", "Singapore", "", "Singapore", "hospital", True),
    ("Cleveland Clinic Abu Dhabi", "CCAD", "Abu Dhabi", "", "UAE", "hospital", True),
]

JOURNEY = [
    ("nephrologist", "Specialist review", "See a nephrologist who confirms the diagnosis, the stage and whether transplant is advisable."),
    ("blood_hla", "Blood group and tissue (HLA) typing", "Patient and possible donors are typed. Kidney matching needs a compatible ABO blood group; the hospital does the HLA crossmatch."),
    ("donor_found", "Donor identified", "A willing relative or a deceased-donor waitlist registration. Organs are never bought or sold."),
    ("donor_workup", "Donor health evaluation", "Independent doctors check the donor's kidneys, heart and general health, and that the donation is voluntary."),
    ("committee", "Authorisation committee", "Where the law requires it (for example unrelated donors in India), a hospital committee reviews documents and consent."),
    ("crossmatch", "Crossmatch and final tests", "The lab checks the donor's cells against the patient's blood. Heart, lung, infection and dental checks."),
    ("surgery_plan", "Surgery date and ICU plan", "Fix the date, blood arrangement, ward and recovery plan."),
    ("surgery", "Transplant surgery", "Done by the transplant team. Hospital stay is usually about a week."),
    ("immuno", "Anti-rejection medicines plan", "Medicines are taken for life; never skip a dose. Keep a pill reminder and a 24-hour contact number."),
    ("followup", "Follow-up schedule", "Frequent creatinine and drug-level tests in the first months, then regular reviews."),
]
JOURNEY_KEYS = [j[0] for j in JOURNEY]

TONES = ("warm", "formal", "urgent")
RELATIONS = ("family", "father", "mother", "brother", "sister", "son", "daughter", "husband", "wife", "friend", "myself")
ORGANS_LIVING = {"kidney", "liver"}
ORGANS_DECEASED = {"kidney", "heart", "liver", "lungs", "pancreas", "cornea", "skin", "bone"}

# FHIR / LOINC codes for the labs RenalSight stores
LOINC = {
    "scr": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL"),
    "egfr": ("98979-8", "eGFR CKD-EPI 2021", "mL/min/{1.73_m2}"),
    "acr": ("9318-7", "Albumin/Creatinine [Mass Ratio] in Urine", "mg/g"),
    "potassium": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma", "mmol/L"),
    "hgb": ("718-7", "Hemoglobin [Mass/volume] in Blood", "g/dL"),
    "hba1c": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "bun": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma", "mg/dL"),
    "sbp": ("8480-6", "Systolic blood pressure", "mm[Hg]"),
    "dbp": ("8462-4", "Diastolic blood pressure", "mm[Hg]"),
}

# Message templates. Tamil, Bengali and Telugu are first drafts for native-speaker review.
T = {
    "en": {
        "greet": {"warm": "🙏 A kind request for your help", "formal": "Request for support - kidney donation", "urgent": "🚨 URGENT: help needed to find a kidney donor"},
        "body": "{who} {is_} admitted at {hospital}{city_part} and {needs} a kidney transplant{age_part}. Blood group: {bg}. Donors with {compat} blood groups can be tested.",
        "ask": "If you, or anyone you know, would like to be tested as a donor, or can simply share this message with friends, family and groups, please get in touch.",
        "contact": "Contact: {name} - {phone}",
        "safe": "Donation is voluntary and is never paid for. The hospital's transplant team and authorisation committee check every donor. Please share. Thank you. 🙏",
        "self": "I", "self_is": "am", "self_needs": "need", "other_is": "is", "other_needs": "needs",
    },
    "ta": {
        "greet": {"warm": "🙏 தயவுசெய்து உதவுங்கள்", "formal": "சிறுநீரக தானம் தொடர்பான கோரிக்கை", "urgent": "🚨 அவசரம்: சிறுநீரக தானம் தேவை"},
        "body": "{who} {hospital}{city_part} மருத்துவமனையில் சிகிச்சையில் உள்ளார்{age_part}; சிறுநீரக மாற்று அறுவை சிகிச்சை தேவை. இரத்த வகை: {bg}. {compat} வகை உள்ளவர்கள் பரிசோதனைக்கு வரலாம்.",
        "ask": "நீங்கள் அல்லது உங்களுக்குத் தெரிந்தவர்கள் தானம் செய்ய பரிசோதனை செய்ய விரும்பினால், அல்லது இந்தச் செய்தியை நண்பர்கள், குடும்பத்தினர், குழுக்களுடன் பகிர்ந்தால், தயவுசெய்து தொடர்பு கொள்ளுங்கள்.",
        "contact": "தொடர்புக்கு: {name} - {phone}",
        "safe": "தானம் தன்னார்வமானது; இதற்குப் பணம் கொடுக்கவோ பெறவோ கூடாது. மருத்துவமனையின் மாற்று அறுவை சிகிச்சைக் குழு ஒவ்வொரு தானதாரரையும் சரிபார்க்கும். பகிருங்கள். நன்றி. 🙏",
        "self": "நான்", "self_is": "", "self_needs": "", "other_is": "", "other_needs": "",
    },
    "bn": {
        "greet": {"warm": "🙏 দয়া করে সাহায্য করুন", "formal": "কিডনি দান বিষয়ে অনুরোধ", "urgent": "🚨 জরুরি: কিডনি দাতা প্রয়োজন"},
        "body": "{who} {hospital}{city_part} হাসপাতালে চিকিৎসাধীন{age_part} এবং কিডনি প্রতিস্থাপন প্রয়োজন। রক্তের গ্রুপ: {bg}। {compat} গ্রুপের দাতারা পরীক্ষা করাতে পারেন।",
        "ask": "আপনি বা আপনার পরিচিত কেউ দাতা হিসেবে পরীক্ষা করাতে চাইলে, অথবা এই বার্তা বন্ধু, পরিবার ও গ্রুপে শেয়ার করলে, দয়া করে যোগাযোগ করুন।",
        "contact": "যোগাযোগ: {name} - {phone}",
        "safe": "দান সম্পূর্ণ স্বেচ্ছায়, এর জন্য কোনো অর্থ লেনদেন হয় না। হাসপাতালের ট্রান্সপ্লান্ট দল ও অনুমোদন কমিটি প্রত্যেক দাতাকে যাচাই করে। শেয়ার করুন। ধন্যবাদ। 🙏",
        "self": "আমি", "self_is": "", "self_needs": "", "other_is": "", "other_needs": "",
    },
    "te": {
        "greet": {"warm": "🙏 దయచేసి సహాయం చేయండి", "formal": "కిడ్నీ దానం గురించి విజ్ఞప్తి", "urgent": "🚨 అత్యవసరం: కిడ్నీ దాత కావాలి"},
        "body": "{who} {hospital}{city_part} ఆసుపత్రిలో చికిత్స పొందుతున్నారు{age_part}; కిడ్నీ మార్పిడి అవసరం. రక్త గ్రూప్: {bg}. {compat} గ్రూప్ ఉన్నవారు పరీక్ష చేయించుకోవచ్చు.",
        "ask": "మీరు లేదా మీకు తెలిసినవారు దాతగా పరీక్ష చేయించుకోవాలనుకుంటే, లేదా ఈ సందేశాన్ని స్నేహితులు, కుటుంబం, గ్రూపులతో షేర్ చేస్తే, దయచేసి సంప్రదించండి.",
        "contact": "సంప్రదించండి: {name} - {phone}",
        "safe": "దానం స్వచ్ఛందం; దీనికి డబ్బు ఇవ్వడం లేదా తీసుకోవడం జరగదు. ఆసుపత్రి ట్రాన్స్‌ప్లాంట్ బృందం మరియు అనుమతి కమిటీ ప్రతి దాతను పరిశీలిస్తాయి. షేర్ చేయండి. ధన్యవాదాలు. 🙏",
        "self": "నేను", "self_is": "", "self_needs": "", "other_is": "", "other_needs": "",
    },
}
