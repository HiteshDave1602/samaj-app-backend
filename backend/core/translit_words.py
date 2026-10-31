# Known spellings, looked up before the letter rules in translit.py, which can't see long vowels or hard t/d in
# English spelling (Patel, Shah, Ahmedabad). Key: lowercase English. Value: the Hindi spelling, from which Gujarati
# is derived, or (Gujarati, Hindi) where the two are written differently. Add words here as members report them.
WORDS: dict[str, str | tuple[str, str]] = {
    # places
    "ahmedabad": ("અમદાવાદ", "अहमदाबाद"), "amdavad": "अमदावाद", "surat": ("સુરત", "सूरत"), "vadodara": "वडोदरा",
    "baroda": ("બરોડા", "बड़ौदा"), "rajkot": "राजकोट", "bhavnagar": "भावनगर", "jamnagar": "जामनगर",
    "junagadh": "जूनागढ़", "gandhinagar": "गांधीनगर", "nadiad": "नडियाद", "navsari": "नवसारी", "valsad": "वलसाड",
    "vapi": "वापी", "bharuch": "भरूच", "ankleshwar": "अंकलेश्वर", "mehsana": ("મહેસાણા", "मेहसाणा"),
    "palanpur": "पालनपुर", "patan": ("પાટણ", "पाटन"), "morbi": "मोरबी", "gondal": "गोंडल",
    "porbandar": "पोरबंदर", "dwarka": "द्वारका", "somnath": "सोमनाथ", "veraval": "वेरावल", "amreli": "अमरेली",
    "botad": "बोटाद", "bhuj": "भुज", "kutch": "कच्छ", "kachchh": "कच्छ", "mandvi": "मांडवी",
    "gandhidham": "गांधीधाम", "godhra": "गोधरा", "dahod": "दाहोद", "himmatnagar": "हिम्मतनगर", "modasa": "मोडासा",
    "kalol": "कलोल", "bardoli": "बारडोली", "vyara": "व्यारा", "bilimora": "बिलिमोरा", "umargam": "उमरगाम",
    "daman": ("દમણ", "दमण"), "silvassa": "सिलवासा", "chikhali": "चिखली", "surendranagar": "सुरेंद्रनगर",
    "wadhwan": "वढवाण", "dholka": "धोलका", "viramgam": "वीरमगाम", "sanand": "साणंद", "kheda": "खेड़ा",
    "mumbai": "मुंबई", "pune": "पुणे", "delhi": "दिल्ली", "kolkata": "कोलकाता", "chennai": "चेन्नई",
    "bangalore": "बैंगलोर", "bengaluru": "बेंगलुरु", "hyderabad": "हैदराबाद", "jaipur": "जयपुर",
    "udaipur": "उदयपुर", "indore": "इंदौर", "nashik": "नासिक", "nagpur": "नागपुर", "ujjain": "उज्जैन",
    "gujarat": "गुजरात", "rajasthan": "राजस्थान", "maharashtra": "महाराष्ट्र", "saurashtra": "सौराष्ट्र",
    "kathiyawad": "काठियावाड़",
    # surnames
    "shah": "शाह", "patel": "पटेल", "mehta": ("મહેતા", "मेहता"), "joshi": "जोशी", "trivedi": "त्रिवेदी",
    "chaturvedi": "चतुर्वेदी", "dwivedi": "द्विवेदी", "pandya": "पंड्या", "bhatt": "भट्ट", "dave": "दवे",
    "desai": "देसाई", "parikh": ("પરીખ", "पारिख"), "modi": "मोदी", "gandhi": "गांधी", "thakkar": "ठक्कर",
    "thakor": "ठाकोर", "solanki": "सोलंकी", "chauhan": "चौहान", "parmar": "परमार", "rathod": "राठौड़",
    "jadeja": "जडेजा", "vaghela": "वाघेला", "zala": "झाला", "gohil": "गोहिल", "jani": "जानी", "vyas": "व्यास",
    "upadhyay": "उपाध्याय", "pandit": "पंडित", "mishra": "मिश्रा", "sharma": "शर्मा", "acharya": "आचार्य",
    "raval": "रावल", "rawal": "रावल", "oza": "ओझा", "bhatia": "भाटिया", "kothari": "कोठारी", "doshi": "दोशी",
    "sheth": "शेठ", "seth": "सेठ", "soni": "सोनी", "panchal": "पंचाल", "mistry": "मिस्त्री",
    "prajapati": "प्रजापति", "chavda": "चावड़ा", "makwana": "मकवाणा", "chaudhary": "चौधरी",
    "choudhary": "चौधरी", "nayak": "नायक", "rana": "राणा", "amin": "अमीन", "vora": "वोरा", "bhavsar": "भावसार",
    "suthar": "सुथार", "darji": "दरजी", "kapadia": "कापड़िया", "maheta": ("મહેતા", "मेहता"),
    # first names
    "shanta": "शांता", "shanti": "शांति", "kanta": "कांता", "krishna": "कृष्णा", "anand": "आनंद",
    "kamya": "काम्या", "sunny": "सनी", "bhavesh": "भावेश", "rajesh": "राजेश", "raj": "राज", "rakesh": "राकेश",
    "rajendra": "राजेंद्र", "nilesh": "नीलेश", "kamlesh": "कमलेश", "jignesh": "जिग्नेश", "chirag": "चिराग",
    "prakash": "प्रकाश", "vikas": "विकास", "sanjay": "संजय", "akash": "आकाश", "aakash": "आकाश",
    "arjun": "अर्जुन", "ashok": "अशोक", "sunil": "सुनील", "kishor": "किशोर", "kishore": "किशोर",
    "mahendra": "महेंद्र", "narendra": "नरेंद्र", "jitendra": "जितेंद्र", "dharmesh": "धर्मेश",
    "kalpesh": "कल्पेश", "parth": "पार्थ", "harsh": "हर्ष", "karan": ("કરણ", "करण"), "kiran": ("કિરણ", "किरण"),
    "krupa": "कृपा", "kajal": "काजल", "nisha": "निशा", "neha": "नेहा", "jyoti": "ज्योति", "bhavna": "भावना",
    "varsha": "वर्षा", "rekha": "रेखा", "meena": "मीना", "mina": "मीना", "mamta": "ममता", "isha": "ईशा", "ishaan": "ईशान", "ishan": "ईशान", "mamata": "ममता", "geeta": "गीता", "gita": "गीता", "sita": "सीता",
    "radha": "राधा", "usha": "उषा", "asha": "आशा", "jaya": "जया", "sarla": "सरला", "savita": "सविता",
    "hansa": "हंसा", "manisha": "मनीषा", "mansi": "मानसी", "dhruv": "ध्रुव", "aarav": "आरव", "vivaan": "विवान",
    "shreya": "श्रेया", "aditi": "अदिति", "ankit": "अंकित", "rahul": "राहुल", "sagar": "सागर", "tushar": "तुषार",
    "darshan": "दर्शन", "deepak": "दीपक", "dipak": "दीपक", "gaurav": "गौरव", "hardik": "हार्दिक",
    "keyur": "केयूर", "nirav": "नीरव", "pratik": "प्रतीक", "sameer": "समीर", "urvashi": "उर्वशी",
    "shital": "शीतल", "payal": "पायल", "falguni": "फाल्गुनी", "daksha": "दक्षा", "hemlata": "हेमलता",
    "lalita": "ललिता", "pushpa": "पुष्पा", "shobha": "शोभा", "tara": "तारा", "vimla": "विमला",
    "parvati": "पार्वती", "laxmi": "लक्ष्मी", "lakshmi": "लक्ष्मी", "ganesh": "गणेश", "mahadev": "महादेव",
    "ram": "राम", "laxman": "लक्ष्मण", "gopal": "गोपाल", "govind": "गोविंद", "keshav": "केशव", "madhav": "माधव",
    "narayan": "नारायण", "bhagwan": "भगवान", "mansukh": "मनसुख", "chandrakant": "चंद्रकांत", "natvar": "नटवर",
    "navin": "नवीन", "naveen": "नवीन", "pravin": "प्रवीण", "praveen": "प्रवीण", "dilip": "दिलीप",
    "jagdish": "जगदीश", "arvind": "अरविंद", "ashwin": "अश्विन", "bipin": "बिपिन", "sneha": "स्नेहा",
    "kirti": "कीर्ति", "radhika": "राधिका", "nitin": "नितिन", "hemant": "हेमंत", "vasant": "वसंत",
    "kaushik": "कौशिक", "mayur": "मयूर", "pankaj": "पंकज", "rajni": "रजनी", "smita": "स्मिता", "taral": "तरल",
    # endings, also used as suffixes: Shantaben, Rameshbhai, Bhavnagar
    "ben": "बेन", "bhai": "भाई", "kumar": "कुमार", "nagar": "नगर", "pur": "पुर", "abad": "आबाद",
    "gadh": "गढ़", "wala": "वाला", "vala": "वाला",
}

# Longest first, so "nagar" wins over "pur" style overlaps.
SUFFIXES = sorted(("ben", "bhai", "kumar", "nagar", "pur", "abad", "gadh", "wala", "vala"), key=len, reverse=True)
