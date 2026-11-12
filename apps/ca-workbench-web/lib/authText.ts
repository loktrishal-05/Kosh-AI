export const AUTH_LANGS = ["en", "hi", "kn"] as const;
export type AuthLang = typeof AUTH_LANGS[number];

const en = {
  brand: "Kosh AI", language: "Language", languageName: "EN", home: "Back to home", skip: "Skip to content",
  eyebrow: "KOSH AI · EVALUATION BUILD", signIn: "Sign in", signInTitle: "Welcome back.", signInBody: "Your bills, books and next steps, in one workbench.",
  username: "Username", password: "Password", showPassword: "Show password", signingIn: "Signing you in…", signInFailed: "Could not sign in. Please try again.",
  demoButton: "Demo admin: sign in with one click", demoHint: "Evaluating Kosh AI? This fills in the demo administrator’s details and signs you in. No account is needed.",
  demoChecking: "Demo admin: checking the server…", demoUnavailable: "Could not reach the server to set up the demo sign-in.", retry: "Try again",
  demoOff: "The one-click demo is switched off on this server. Use your username and password.", demoStarting: "Demo details filled in. Signing you in…", or: "or use your username and password",
  newHere: "New here?", requestAccess: "Request access", assurance: "Nothing is filed or sent automatically.",
  signupEyebrow: "A LITTLE LESS PAPERWORK", signupTitle: "Join the team.", signupBody: "Bring your practice or business to Kosh AI. Tell us a little about your work and ask the team for access.",
  benefitBills: "Start with the bills", benefitBillsBody: "Read bills and bring the figures into your books.",
  benefitChecks: "See the working", benefitChecksBody: "Check the GST, TDS and e-way bill arithmetic.",
  benefitHuman: "Keep the final say", benefitHumanBody: "Review the draft. A person approves and files.",
  signupFormBody: "Access is arranged by the team. This form opens an email draft.", name: "Your name", email: "Work email", firm: "Firm or business name", role: "Your role", chooseRole: "Choose your role",
  roleCA: "CA / accountant", roleOwner: "Business owner", roleOther: "Other", note: "Anything we should know? (optional)",
  consent: "I agree to be contacted about my access request.", emailHint: "Review and send the draft in your email app. Submitting this form does not create an account.",
  openDraft: "Request access by email", unwired: "Access requests are not wired up yet. No request has been sent. Please check back later.",
  draftReady: "An email draft was requested. If it did not open, check your email app. Review and send it yourself; nothing has been sent by Kosh AI.",
  draftFailed: "Could not open your email app. Please check that a mail app is set up and try again.",
  required: "Please complete this field.", emailInvalid: "Enter a valid work email address.", consentRequired: "Please agree to be contacted before continuing.",
  alreadyMember: "Already have access?", emailSubject: "Kosh AI access request", consentSummary: "I agree to be contacted about this access request."
};

export type AuthText = { [K in keyof typeof en]: string };
/** Hindi and Kannada are short first drafts awaiting native-speaker review. */
export const AUTH: Record<AuthLang, AuthText> = {
  en,
  hi: {
    brand: "Kosh AI", language: "भाषा", languageName: "हिं", home: "होम पर वापस", skip: "मुख्य भाग पर जाएँ",
    eyebrow: "KOSH AI · मूल्यांकन संस्करण", signIn: "साइन इन", signInTitle: "फिर से स्वागत है।", signInBody: "बिल, बही और अगले कदम, एक ही जगह।",
    username: "यूज़रनेम", password: "पासवर्ड", showPassword: "पासवर्ड दिखाएँ", signingIn: "साइन इन हो रहा है…", signInFailed: "साइन इन नहीं हुआ। फिर कोशिश करें।",
    demoButton: "डेमो एडमिन: एक क्लिक में साइन इन", demoHint: "Kosh AI देख रहे हैं? डेमो की जानकारी भरकर साइन इन होगा। खाते की ज़रूरत नहीं है।",
    demoChecking: "डेमो: सर्वर जाँच रहे हैं…", demoUnavailable: "डेमो के लिए सर्वर से संपर्क नहीं हुआ।", retry: "फिर कोशिश करें",
    demoOff: "इस सर्वर पर डेमो बंद है। यूज़रनेम और पासवर्ड डालें।", demoStarting: "डेमो जानकारी भरी गई। साइन इन हो रहा है…", or: "या यूज़रनेम और पासवर्ड डालें",
    newHere: "पहली बार आए हैं?", requestAccess: "प्रवेश का अनुरोध करें", assurance: "कुछ भी अपने आप दाखिल या भेजा नहीं जाता।",
    signupEyebrow: "कागज़ी काम थोड़ा कम", signupTitle: "टीम से जुड़ें।", signupBody: "अपने काम में Kosh AI जोड़ें। अपने बारे में बताएँ और टीम से प्रवेश माँगें।",
    benefitBills: "बिल से शुरुआत", benefitBillsBody: "बिल पढ़ें और आँकड़े बही में लाएँ।",
    benefitChecks: "हिसाब देखें", benefitChecksBody: "GST, TDS और ई-वे बिल का हिसाब जाँचें।",
    benefitHuman: "अंतिम फैसला आपका", benefitHumanBody: "मसौदा जाँचें। मंज़ूरी और दाखिला इंसान करता है।",
    signupFormBody: "टीम प्रवेश देती है। यह फ़ॉर्म ईमेल का मसौदा खोलता है।", name: "आपका नाम", email: "काम का ईमेल", firm: "फ़र्म या व्यवसाय का नाम", role: "आपकी भूमिका", chooseRole: "भूमिका चुनें",
    roleCA: "सीए / लेखाकार", roleOwner: "व्यवसाय मालिक", roleOther: "अन्य", note: "कुछ और बताना चाहेंगे? (वैकल्पिक)",
    consent: "प्रवेश अनुरोध के बारे में संपर्क करने की सहमति है।", emailHint: "ईमेल ऐप में मसौदा जाँचकर भेजें। इस फ़ॉर्म से खाता नहीं बनता।",
    openDraft: "ईमेल से प्रवेश माँगें", unwired: "प्रवेश अनुरोध अभी चालू नहीं हैं। कोई अनुरोध नहीं भेजा गया। बाद में फिर देखें।",
    draftReady: "ईमेल मसौदा खोलने का अनुरोध किया। न खुले तो ईमेल ऐप जाँचें। खुद जाँचकर भेजें; Kosh AI ने कुछ नहीं भेजा।",
    draftFailed: "ईमेल ऐप नहीं खुला। ऐप की सेटिंग जाँचकर फिर कोशिश करें।",
    required: "यह जानकारी भरें।", emailInvalid: "सही काम का ईमेल डालें।", consentRequired: "आगे बढ़ने से पहले संपर्क की सहमति दें।",
    alreadyMember: "प्रवेश पहले से है?", emailSubject: "Kosh AI प्रवेश अनुरोध", consentSummary: "इस प्रवेश अनुरोध के बारे में संपर्क करने की सहमति है।"
  },
  kn: {
    brand: "Kosh AI", language: "ಭಾಷೆ", languageName: "ಕನ್ನಡ", home: "ಮುಖಪುಟಕ್ಕೆ ಮರಳಿ", skip: "ಮುಖ್ಯ ವಿಷಯಕ್ಕೆ ಹೋಗಿ",
    eyebrow: "KOSH AI · ಮೌಲ್ಯಮಾಪನ ಆವೃತ್ತಿ", signIn: "ಸೈನ್ ಇನ್", signInTitle: "ಮತ್ತೆ ಸ್ವಾಗತ.", signInBody: "ಬಿಲ್, ಲೆಕ್ಕ ಮತ್ತು ಮುಂದಿನ ಕೆಲಸ, ಒಂದೇ ಕಡೆ.",
    username: "ಬಳಕೆದಾರ ಹೆಸರು", password: "ಪಾಸ್‌ವರ್ಡ್", showPassword: "ಪಾಸ್‌ವರ್ಡ್ ತೋರಿಸಿ", signingIn: "ಸೈನ್ ಇನ್ ಆಗುತ್ತಿದೆ…", signInFailed: "ಸೈನ್ ಇನ್ ಆಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    demoButton: "ಡೆಮೊ ಅಡ್ಮಿನ್: ಒಂದೇ ಕ್ಲಿಕ್‌ನಲ್ಲಿ ಸೈನ್ ಇನ್", demoHint: "Kosh AI ನೋಡುತ್ತಿದ್ದೀರಾ? ಡೆಮೊ ವಿವರಗಳನ್ನು ತುಂಬಿ ಸೈನ್ ಇನ್ ಮಾಡುತ್ತದೆ. ಖಾತೆ ಬೇಕಿಲ್ಲ.",
    demoChecking: "ಡೆಮೊ: ಸರ್ವರ್ ಪರಿಶೀಲನೆ…", demoUnavailable: "ಡೆಮೊಗಾಗಿ ಸರ್ವರ್ ಸಂಪರ್ಕ ಸಿಗಲಿಲ್ಲ.", retry: "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ",
    demoOff: "ಈ ಸರ್ವರ್‌ನಲ್ಲಿ ಡೆಮೊ ಇಲ್ಲ. ಹೆಸರು ಮತ್ತು ಪಾಸ್‌ವರ್ಡ್ ಬಳಸಿ.", demoStarting: "ಡೆಮೊ ವಿವರ ತುಂಬಿದೆ. ಸೈನ್ ಇನ್ ಆಗುತ್ತಿದೆ…", or: "ಅಥವಾ ಹೆಸರು ಮತ್ತು ಪಾಸ್‌ವರ್ಡ್ ಬಳಸಿ",
    newHere: "ಹೊಸದಾಗಿ ಬಂದಿದ್ದೀರಾ?", requestAccess: "ಪ್ರವೇಶ ಕೇಳಿ", assurance: "ಯಾವುದೂ ತಾನಾಗಿ ಸಲ್ಲಿಕೆ ಅಥವಾ ರವಾನೆ ಆಗುವುದಿಲ್ಲ.",
    signupEyebrow: "ಕಾಗದದ ಕೆಲಸ ಸ್ವಲ್ಪ ಕಡಿಮೆ", signupTitle: "ತಂಡಕ್ಕೆ ಸೇರಿ.", signupBody: "ನಿಮ್ಮ ಕೆಲಸಕ್ಕೆ Kosh AI ಸೇರಿಸಿ. ನಿಮ್ಮ ಬಗ್ಗೆ ತಿಳಿಸಿ, ತಂಡದಿಂದ ಪ್ರವೇಶ ಕೇಳಿ.",
    benefitBills: "ಬಿಲ್‌ನಿಂದ ಆರಂಭಿಸಿ", benefitBillsBody: "ಬಿಲ್ ಓದಿ, ಅಂಕಿಗಳನ್ನು ಲೆಕ್ಕಕ್ಕೆ ಸೇರಿಸಿ.",
    benefitChecks: "ಲೆಕ್ಕವನ್ನು ನೋಡಿ", benefitChecksBody: "GST, TDS ಮತ್ತು ಇ-ವೇ ಬಿಲ್ ಲೆಕ್ಕ ಪರಿಶೀಲಿಸಿ.",
    benefitHuman: "ಅಂತಿಮ ನಿರ್ಧಾರ ನಿಮ್ಮದು", benefitHumanBody: "ಕರಡು ಪರಿಶೀಲಿಸಿ. ವ್ಯಕ್ತಿಯೇ ಅನುಮೋದಿಸಿ ಸಲ್ಲಿಸುತ್ತಾರೆ.",
    signupFormBody: "ತಂಡವು ಪ್ರವೇಶ ನೀಡುತ್ತದೆ. ಈ ಫಾರ್ಮ್ ಇಮೇಲ್ ಕರಡು ತೆರೆಯುತ್ತದೆ.", name: "ನಿಮ್ಮ ಹೆಸರು", email: "ಕೆಲಸದ ಇಮೇಲ್", firm: "ಸಂಸ್ಥೆ ಅಥವಾ ವ್ಯಾಪಾರದ ಹೆಸರು", role: "ನಿಮ್ಮ ಪಾತ್ರ", chooseRole: "ಪಾತ್ರ ಆಯ್ಕೆ ಮಾಡಿ",
    roleCA: "ಸಿಎ / ಲೆಕ್ಕಿಗ", roleOwner: "ವ್ಯಾಪಾರ ಮಾಲೀಕ", roleOther: "ಇತರೆ", note: "ಇನ್ನೇನಾದರೂ ತಿಳಿಸುವಿರಾ? (ಐಚ್ಛಿಕ)",
    consent: "ಪ್ರವೇಶ ವಿನಂತಿಯ ಬಗ್ಗೆ ಸಂಪರ್ಕಿಸಲು ನನ್ನ ಒಪ್ಪಿಗೆ ಇದೆ.", emailHint: "ಇಮೇಲ್ ಆ್ಯಪ್‌ನಲ್ಲಿ ಕರಡು ಪರಿಶೀಲಿಸಿ ಕಳುಹಿಸಿ. ಈ ಫಾರ್ಮ್ ಖಾತೆ ಸೃಷ್ಟಿಸುವುದಿಲ್ಲ.",
    openDraft: "ಇಮೇಲ್ ಮೂಲಕ ಪ್ರವೇಶ ಕೇಳಿ", unwired: "ಪ್ರವೇಶ ವಿನಂತಿ ಇನ್ನೂ ಸಿದ್ಧವಾಗಿಲ್ಲ. ಯಾವುದೇ ವಿನಂತಿ ಕಳುಹಿಸಿಲ್ಲ. ನಂತರ ಮತ್ತೆ ನೋಡಿ.",
    draftReady: "ಇಮೇಲ್ ಕರಡು ತೆರೆಯಲು ಕೇಳಲಾಗಿದೆ. ತೆರೆಯದಿದ್ದರೆ ಇಮೇಲ್ ಆ್ಯಪ್ ನೋಡಿ. ನೀವೇ ಪರಿಶೀಲಿಸಿ ಕಳುಹಿಸಿ; Kosh AI ಏನನ್ನೂ ಕಳುಹಿಸಿಲ್ಲ.",
    draftFailed: "ಇಮೇಲ್ ಆ್ಯಪ್ ತೆರೆಯಲಿಲ್ಲ. ಆ್ಯಪ್ ಸಿದ್ಧವಿದೆಯೇ ನೋಡಿ, ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
    required: "ಈ ವಿವರ ತುಂಬಿ.", emailInvalid: "ಸರಿಯಾದ ಕೆಲಸದ ಇಮೇಲ್ ನಮೂದಿಸಿ.", consentRequired: "ಮುಂದುವರಿಯಲು ಸಂಪರ್ಕದ ಒಪ್ಪಿಗೆ ನೀಡಿ.",
    alreadyMember: "ಈಗಾಗಲೇ ಪ್ರವೇಶವಿದೆಯೇ?", emailSubject: "Kosh AI ಪ್ರವೇಶ ವಿನಂತಿ", consentSummary: "ಈ ಪ್ರವೇಶ ವಿನಂತಿಯ ಬಗ್ಗೆ ಸಂಪರ್ಕಿಸಲು ಒಪ್ಪಿಗೆ ಇದೆ."
  }
};
