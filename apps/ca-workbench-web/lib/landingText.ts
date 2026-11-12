export type LandLang = "en" | "hi" | "kn";
export const LAND_LANGS: { code: LandLang; label: string }[] = [{ code: "en", label: "EN" }, { code: "hi", label: "हिं" }, { code: "kn", label: "ಕನ್ನಡ" }];
type LandingText = {
  navFlow: string; navProduct: string; navProof: string; signIn: string; demo: string;
  skip: string; navLabel: string; homeLabel: string; languageLabel: string; filmLabel: string; posterLabel: string;
  kicker: string; h1a: string; h1b: string; lede: string; loading: string; scroll: string;
  beats: readonly [string, string, string]; statement: string; riseKicker: string; riseTitle: string; riseBody: string; sandbox: string;
  kpi: readonly [string, string, string, string]; due: string; agentsKicker: string; agentsTitle: string;
  agents: readonly [AgentText, AgentText, AgentText, AgentText, AgentText];
  flowKicker: string; flowTitle: string; steps: readonly [string, string, string, string, string, string, string, string];
  proofKicker: string; proofTitle: string; proof: readonly [string, string, string, string]; proofNote: string;
  closeTitle: string; closeBody: string; code: string; foot: string;
};
type AgentText = { title: string; body: string };

/** Every user-facing word on the landing page. Hindi and Kannada are first drafts awaiting native-speaker review. */
export const LAND = {
  en: {
    skip: "Skip to content", navLabel: "Main", homeLabel: "Kosh AI home", languageLabel: "Language",
    filmLabel: "Bills on a shop counter settle into a ledger, ending with a human stamp.", posterLabel: "A ledger with bills settled into rows and one vermilion stamp",
    navFlow: "How it works", navProduct: "Product", navProof: "Proof", signIn: "Sign in", demo: "Try the live demo",
    kicker: "KOSH AI  ·  GST, TDS AND E-WAY BILLS FOR SMALL BUSINESS",
    h1a: "The work arrives done.", h1b: "A human files.",
    lede: "Kosh AI reads the bills, does the arithmetic, chases the suppliers and explains it all in the owner's language. Then it stops, and a person stamps it.",
    loading: "Loading the film", scroll: "Scroll",
    beats: ["Bills pile up in a bag, a chat, a shoebox.", "Kosh AI threads each one to the ledger and checks the arithmetic.", "One person reads it, and stamps it. Nothing files itself."],
    statement: "A shop owner should never need to understand GSTR-2B, Rule 37 or Section 194C to stay compliant.",
    riseKicker: "THE ACCOUNTANT'S VIEW", riseTitle: "Eighty clients. One queue.",
    riseBody: "The CA sees every client ranked by deadline and exceptions, and opens only what needs a human.", sandbox: "Sandbox data. This console cannot file returns.",
    kpi: ["Clients", "Ready to file", "With exceptions", "Total exceptions"], due: "Due",
    agentsKicker: "FROM BILL TO APPROVAL", agentsTitle: "What the agents do",
    agents: [
      { title: "Read the bill", body: "Extract bill details from a photo or PDF, validate the GSTIN and flag uncertain readings for review." },
      { title: "Check the arithmetic", body: "A deterministic engine calculates GST, TDS and e-way-bill validity. The language model never does the sums." },
      { title: "Nudge the supplier", body: "Match bills with GSTR-2B and follow up on missing entries. At most three nudges per invoice, at least 48 hours apart." },
      { title: "Explain in the owner's language", body: "Give the owner a grounded summary in English, Hindi or Kannada, using only numbers the engine produced." },
      { title: "Stop for a human", body: "Prepare the draft for review. Filing needs a person's approval and a single-use OTP bound to that exact draft." },
    ],
    flowKicker: "HOW IT WORKS", flowTitle: "Eight steps. You touch two.",
    steps: ["Bills arrive", "Read the bill", "Match with GSTR‑2B", "Chase the supplier", "Check the rest", "Explain simply", "Human approves", "Save, never file"],
    proofKicker: "PROOF, NOT PROMISES", proofTitle: "What we can actually show",
    proof: ["automated tests passing", "languages on the owner view", "kB first load on the owner view", "supplier nudges per invoice, at most"],
    proofNote: "Tests: 924 Python and 50 workbench, run on 12 Nov 2026. Size: Next.js build output for /owner. Nudge cap: enforced in the tool and the engine. Not pilot results.",
    closeTitle: "Compliance that arrives done.", closeBody: "Open the live demo with one click. No account needed.", code: "Read the code",
    foot: "Sandbox build. Nothing is filed or sent automatically. Not tax or legal advice.",
  },
  hi: {
    skip: "मुख्य सामग्री पर जाएँ", navLabel: "मुख्य नेविगेशन", homeLabel: "Kosh AI मुख्य पृष्ठ", languageLabel: "भाषा",
    filmLabel: "दुकान के काउंटर के बिल खाते में जुड़ते हैं और अंत में इंसान मोहर लगाता है।", posterLabel: "खाते की पंक्तियों में सजे बिल और एक सिंदूरी मोहर",
    navFlow: "कैसे काम करता है", navProduct: "प्रोडक्ट", navProof: "प्रमाण", signIn: "साइन इन", demo: "लाइव डेमो देखें",
    kicker: "KOSH AI  ·  छोटे व्यापार के लिए GST, TDS और ई-वे बिल",
    h1a: "काम पूरा होकर आता है।", h1b: "फाइल इंसान करता है।",
    lede: "Kosh AI बिल पढ़ता है, हिसाब करता है, सप्लायर को याद दिलाता है और सब कुछ मालिक की भाषा में समझाता है। फिर रुक जाता है, और एक इंसान मोहर लगाता है।",
    loading: "फिल्म लोड हो रही है", scroll: "नीचे जाएँ",
    beats: ["बिल थैले, चैट और जूतों के डिब्बे में जमा होते रहते हैं।", "Kosh AI हर बिल को खाते से जोड़ता है और हिसाब जाँचता है।", "एक व्यक्ति पढ़ता है और मोहर लगाता है। कुछ भी अपने आप फाइल नहीं होता।"],
    statement: "दुकानदार को GSTR-2B, नियम 37 या धारा 194C समझे बिना भी नियमों का पालन कर पाना चाहिए।",
    riseKicker: "अकाउंटेंट का नज़ारा", riseTitle: "अस्सी ग्राहक। एक कतार।",
    riseBody: "CA हर ग्राहक को आख़िरी तारीख़ और गड़बड़ियों के क्रम में देखता है और सिर्फ़ वही खोलता है जहाँ इंसान चाहिए।", sandbox: "सैंडबॉक्स डेटा। यह कंसोल रिटर्न फाइल नहीं कर सकता।",
    kpi: ["ग्राहक", "फाइल के लिए तैयार", "गड़बड़ी वाले", "कुल गड़बड़ियाँ"], due: "अंतिम तिथि",
    agentsKicker: "बिल से मंज़ूरी तक", agentsTitle: "एजेंट क्या करते हैं",
    agents: [
      { title: "बिल पढ़ना", body: "फोटो या PDF से बिल की जानकारी निकालते हैं, GSTIN जाँचते हैं और अस्पष्ट जानकारी समीक्षा के लिए चिह्नित करते हैं।" },
      { title: "हिसाब जाँचना", body: "निश्चित नियमों वाला इंजन GST, TDS और ई-वे बिल की वैधता की गणना करता है। भाषा मॉडल हिसाब नहीं करता।" },
      { title: "सप्लायर को याद दिलाना", body: "बिलों का GSTR-2B से मिलान करके छूटी प्रविष्टियों के लिए याद दिलाते हैं। प्रति बिल अधिकतम तीन रिमाइंडर, कम से कम 48 घंटे के अंतर से।" },
      { title: "मालिक की भाषा में समझाना", body: "इंजन के दिए आँकड़ों से ही अंग्रेज़ी, हिंदी या कन्नड़ में मालिक को सारांश समझाते हैं।" },
      { title: "इंसान की मंज़ूरी के लिए रुकना", body: "ड्राफ्ट समीक्षा के लिए तैयार करते हैं। फाइल करने के लिए इंसान की मंज़ूरी और उसी ड्राफ्ट से जुड़ा एक बार का OTP चाहिए।" },
    ],
    flowKicker: "कैसे काम करता है", flowTitle: "आठ कदम। आप सिर्फ़ दो करते हैं।",
    steps: ["बिल आते हैं", "बिल पढ़ना", "GSTR-2B से मिलान", "सप्लायर को याद दिलाना", "बाकी जाँच", "सरल भाषा में समझाना", "इंसान मंज़ूर करता है", "सहेजें, फाइल नहीं"],
    proofKicker: "वादे नहीं, प्रमाण", proofTitle: "जो हम सच में दिखा सकते हैं",
    proof: ["ऑटोमैटिक टेस्ट पास", "ओनर व्यू की भाषाएँ", "kB पहला लोड, ओनर व्यू", "प्रति बिल अधिकतम सप्लायर रिमाइंडर"],
    proofNote: "टेस्ट: 924 Python और 50 वर्कबेंच, 12 नवंबर 2026 को चलाए गए। आकार: /owner का Next.js बिल्ड आउटपुट। रिमाइंडर सीमा: टूल और इंजन दोनों में लागू। यह पायलट के नतीजे नहीं हैं।",
    closeTitle: "काम पूरा होकर आता है।", closeBody: "एक क्लिक में लाइव डेमो खोलें। खाता नहीं चाहिए।", code: "कोड पढ़ें",
    foot: "सैंडबॉक्स बिल्ड। कुछ भी अपने आप फाइल या भेजा नहीं जाता। यह कर या कानूनी सलाह नहीं है।",
  },
  kn: {
    skip: "ಮುಖ್ಯ ವಿಷಯಕ್ಕೆ ಹೋಗಿ", navLabel: "ಮುಖ್ಯ ನ್ಯಾವಿಗೇಶನ್", homeLabel: "Kosh AI ಮುಖಪುಟ", languageLabel: "ಭಾಷೆ",
    filmLabel: "ಅಂಗಡಿಯ ಕೌಂಟರ್‌ನ ಬಿಲ್‌ಗಳು ಲೆಕ್ಕದ ಪುಸ್ತಕಕ್ಕೆ ಸೇರುತ್ತವೆ, ಕೊನೆಯಲ್ಲಿ ಮನುಷ್ಯರು ಮುದ್ರೆ ಹಾಕುತ್ತಾರೆ.", posterLabel: "ಸಾಲುಗಳಲ್ಲಿ ಜೋಡಿಸಿದ ಬಿಲ್‌ಗಳು ಮತ್ತು ಒಂದು ಕೆಂಪು ಮುದ್ರೆ ಇರುವ ಲೆಕ್ಕದ ಪುಸ್ತಕ",
    navFlow: "ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ", navProduct: "ಉತ್ಪನ್ನ", navProof: "ಪುರಾವೆ", signIn: "ಸೈನ್ ಇನ್", demo: "ಲೈವ್ ಡೆಮೊ ನೋಡಿ",
    kicker: "KOSH AI  ·  ಸಣ್ಣ ವ್ಯಾಪಾರಕ್ಕಾಗಿ GST, TDS ಮತ್ತು ಇ-ವೇ ಬಿಲ್",
    h1a: "ಕೆಲಸ ಮುಗಿದು ಬರುತ್ತದೆ.", h1b: "ಸಲ್ಲಿಸುವುದು ಮನುಷ್ಯ.",
    lede: "Kosh AI ಬಿಲ್‌ಗಳನ್ನು ಓದುತ್ತದೆ, ಲೆಕ್ಕ ಮಾಡುತ್ತದೆ, ಪೂರೈಕೆದಾರರಿಗೆ ನೆನಪಿಸುತ್ತದೆ ಮತ್ತು ಎಲ್ಲವನ್ನೂ ಮಾಲೀಕರ ಭಾಷೆಯಲ್ಲಿ ವಿವರಿಸುತ್ತದೆ. ನಂತರ ನಿಲ್ಲುತ್ತದೆ, ಮತ್ತು ಒಬ್ಬ ವ್ಯಕ್ತಿ ಮುದ್ರೆ ಹಾಕುತ್ತಾರೆ.",
    loading: "ಫಿಲ್ಮ್ ಲೋಡ್ ಆಗುತ್ತಿದೆ", scroll: "ಕೆಳಗೆ ಹೋಗಿ",
    beats: ["ಬಿಲ್‌ಗಳು ಚೀಲ, ಚಾಟ್ ಮತ್ತು ಶೂ ಡಬ್ಬದಲ್ಲಿ ಕೂಡುತ್ತಲೇ ಇರುತ್ತವೆ.", "Kosh AI ಪ್ರತಿ ಬಿಲ್ ಅನ್ನು ಖಾತೆಗೆ ಜೋಡಿಸಿ ಲೆಕ್ಕ ಪರಿಶೀಲಿಸುತ್ತದೆ.", "ಒಬ್ಬ ವ್ಯಕ್ತಿ ಓದಿ ಮುದ್ರೆ ಹಾಕುತ್ತಾರೆ. ಯಾವುದೂ ತಾನಾಗಿ ಸಲ್ಲಿಕೆಯಾಗುವುದಿಲ್ಲ."],
    statement: "ಅಂಗಡಿ ಮಾಲೀಕರು GSTR-2B, ನಿಯಮ 37 ಅಥವಾ ಸೆಕ್ಷನ್ 194C ಅರ್ಥಮಾಡಿಕೊಳ್ಳದೆಯೂ ನಿಯಮ ಪಾಲಿಸುವಂತಿರಬೇಕು.",
    riseKicker: "ಲೆಕ್ಕಿಗರ ನೋಟ", riseTitle: "ಎಂಬತ್ತು ಗ್ರಾಹಕರು. ಒಂದು ಸಾಲು.",
    riseBody: "CA ಪ್ರತಿ ಗ್ರಾಹಕರನ್ನು ಕೊನೆಯ ದಿನಾಂಕ ಮತ್ತು ದೋಷಗಳ ಕ್ರಮದಲ್ಲಿ ನೋಡುತ್ತಾರೆ, ಮನುಷ್ಯ ಬೇಕಾದದ್ದನ್ನು ಮಾತ್ರ ತೆರೆಯುತ್ತಾರೆ.", sandbox: "ಸ್ಯಾಂಡ್‌ಬಾಕ್ಸ್ ಡೇಟಾ. ಈ ಕನ್ಸೋಲ್ ರಿಟರ್ನ್ ಸಲ್ಲಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ.",
    kpi: ["ಗ್ರಾಹಕರು", "ಸಲ್ಲಿಕೆಗೆ ಸಿದ್ಧ", "ದೋಷಗಳಿರುವವು", "ಒಟ್ಟು ದೋಷಗಳು"], due: "ಕೊನೆಯ ದಿನಾಂಕ",
    agentsKicker: "ಬಿಲ್‌ನಿಂದ ಅನುಮೋದನೆಯವರೆಗೆ", agentsTitle: "ಏಜೆಂಟ್‌ಗಳು ಏನು ಮಾಡುತ್ತವೆ",
    agents: [
      { title: "ಬಿಲ್ ಓದುವುದು", body: "ಫೋಟೋ ಅಥವಾ PDF ನಿಂದ ಬಿಲ್ ವಿವರಗಳನ್ನು ಪಡೆಯುತ್ತವೆ, GSTIN ಪರಿಶೀಲಿಸುತ್ತವೆ ಮತ್ತು ಸ್ಪಷ್ಟವಿಲ್ಲದ ಮಾಹಿತಿಯನ್ನು ಪರಿಶೀಲನೆಗೆ ಗುರುತಿಸುತ್ತವೆ." },
      { title: "ಲೆಕ್ಕ ಪರಿಶೀಲಿಸುವುದು", body: "ನಿಶ್ಚಿತ ನಿಯಮಗಳ ಎಂಜಿನ್ GST, TDS ಮತ್ತು ಇ-ವೇ ಬಿಲ್ ಮಾನ್ಯತೆಯನ್ನು ಲೆಕ್ಕ ಮಾಡುತ್ತದೆ. ಭಾಷಾ ಮಾದರಿ ಲೆಕ್ಕ ಮಾಡುವುದಿಲ್ಲ." },
      { title: "ಪೂರೈಕೆದಾರರಿಗೆ ನೆನಪಿಸುವುದು", body: "ಬಿಲ್‌ಗಳನ್ನು GSTR-2B ಜೊತೆ ಹೊಂದಿಸಿ, ಕಾಣೆಯಾದ ದಾಖಲೆಗಳಿಗೆ ನೆನಪಿಸುತ್ತವೆ. ಪ್ರತಿ ಬಿಲ್‌ಗೆ ಗರಿಷ್ಠ ಮೂರು ನೆನಪೋಲೆಗಳು, ಕನಿಷ್ಠ 48 ಗಂಟೆಗಳ ಅಂತರದಲ್ಲಿ." },
      { title: "ಮಾಲೀಕರ ಭಾಷೆಯಲ್ಲಿ ವಿವರಿಸುವುದು", body: "ಎಂಜಿನ್ ನೀಡಿದ ಅಂಕಿಗಳನ್ನೇ ಬಳಸಿ ಇಂಗ್ಲಿಷ್, ಹಿಂದಿ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ ಮಾಲೀಕರಿಗೆ ಸಾರಾಂಶ ನೀಡುತ್ತವೆ." },
      { title: "ಮನುಷ್ಯರ ಅನುಮತಿಗಾಗಿ ನಿಲ್ಲುವುದು", body: "ಪರಿಶೀಲನೆಗಾಗಿ ಕರಡು ಸಿದ್ಧಪಡಿಸುತ್ತವೆ. ಸಲ್ಲಿಸಲು ಮನುಷ್ಯರ ಅನುಮತಿ ಮತ್ತು ಅದೇ ಕರಡಿಗೆ ಸಂಬಂಧಿಸಿದ ಒಮ್ಮೆ ಬಳಸುವ OTP ಬೇಕು." },
    ],
    flowKicker: "ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ", flowTitle: "ಎಂಟು ಹಂತಗಳು. ನೀವು ಎರಡನ್ನು ಮಾಡುತ್ತೀರಿ.",
    steps: ["ಬಿಲ್‌ಗಳು ಬರುತ್ತವೆ", "ಬಿಲ್ ಓದುವುದು", "GSTR-2B ಜೊತೆ ಹೊಂದಾಣಿಕೆ", "ಪೂರೈಕೆದಾರರಿಗೆ ನೆನಪಿಸುವುದು", "ಉಳಿದ ಪರಿಶೀಲನೆ", "ಸರಳವಾಗಿ ವಿವರಿಸುವುದು", "ಮನುಷ್ಯ ಒಪ್ಪುತ್ತಾರೆ", "ಉಳಿಸಿ, ಸಲ್ಲಿಸಬೇಡಿ"],
    proofKicker: "ಭರವಸೆಯಲ್ಲ, ಪುರಾವೆ", proofTitle: "ನಾವು ನಿಜವಾಗಿ ತೋರಿಸಬಹುದಾದದ್ದು",
    proof: ["ಸ್ವಯಂಚಾಲಿತ ಪರೀಕ್ಷೆಗಳು ಪಾಸ್", "ಓನರ್ ವ್ಯೂ ಭಾಷೆಗಳು", "kB ಮೊದಲ ಲೋಡ್, ಓನರ್ ವ್ಯೂ", "ಪ್ರತಿ ಬಿಲ್‌ಗೆ ಗರಿಷ್ಠ ಪೂರೈಕೆದಾರ ನೆನಪೋಲೆಗಳು"],
    proofNote: "ಪರೀಕ್ಷೆಗಳು: 924 Python ಮತ್ತು 50 ವರ್ಕ್‌ಬೆಂಚ್, 12 ನವೆಂಬರ್ 2026 ರಂದು ಚಲಾಯಿಸಲಾಗಿದೆ. ಗಾತ್ರ: /owner ನ Next.js ಬಿಲ್ಡ್ ಔಟ್‌ಪುಟ್. ಮಿತಿ: ಟೂಲ್ ಮತ್ತು ಎಂಜಿನ್ ಎರಡರಲ್ಲೂ ಜಾರಿಯಲ್ಲಿದೆ. ಇವು ಪೈಲಟ್ ಫಲಿತಾಂಶಗಳಲ್ಲ.",
    closeTitle: "ಕೆಲಸ ಮುಗಿದು ಬರುತ್ತದೆ.", closeBody: "ಒಂದೇ ಕ್ಲಿಕ್‌ನಲ್ಲಿ ಲೈವ್ ಡೆಮೊ ತೆರೆಯಿರಿ. ಖಾತೆ ಬೇಕಿಲ್ಲ.", code: "ಕೋಡ್ ಓದಿ",
    foot: "ಸ್ಯಾಂಡ್‌ಬಾಕ್ಸ್ ಬಿಲ್ಡ್. ಯಾವುದೂ ತಾನಾಗಿ ಸಲ್ಲಿಕೆ ಅಥವಾ ರವಾನೆಯಾಗುವುದಿಲ್ಲ. ಇದು ತೆರಿಗೆ ಅಥವಾ ಕಾನೂನು ಸಲಹೆಯಲ್ಲ.",
  },
} as const satisfies Record<LandLang, LandingText>;
