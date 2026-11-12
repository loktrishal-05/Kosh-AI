import type { Lang } from "./ownerText.ts";

const en = {
  clients: "Clients", books: "Books", tally: "Tally Assistant", owner: "Owner view", impact: "Impact", welcome: "Welcome", navigation: "Main navigation", client: "Client record",
  commands: "Commands", commandTitle: "Go to a workspace", commandSearch: "Search pages or clients", commandHelp: "Use ↑ and ↓ to choose, Enter to open, Esc to close.", close: "Close", noCommands: "No matching pages", changeSearch: "Clear search", results: "Matching pages",
  darkTheme: "Dark theme", lightTheme: "Light theme", theme: "Colour theme", dataTable: "View data table", item: "Item", value: "Value",
  loading: "Preparing your workspace", error: "This view could not be prepared. Your records have not changed.", retry: "Try again", emptyClients: "No client records yet", openBooks: "Open Books", resetFilters: "Clear filters",
  invoiceStatuses: "Invoice reconciliation", invoiceCount: "Invoices", priorities: "Clients by priority score", priorityPoints: "Priority points", priorityNote: "Score = exceptions × 10 + deadline proximity (up to 30 points). Counts follow the current filters. Sandbox records.",
  hoursChart: "Where the monthly hours go", monthlyHours: "Hours per month", saved: "Saved", remaining: "Remaining", feesChart: "Annual fees in the model", annualFees: "Rupees per year", totalFees: "Total fees", sortingFees: "Sorting effort",
  capacityChart: "Capacity at different sorting shares", shareDone: "Sorting done (%)", capacity: "Capacity (×)", modelNote: "Calculated scenarios from your inputs, not measured results or a time series.", noSavings: "At 0% sorting done, this model shows no saving.", resetModel: "Reset assumptions",
  ownerEyebrow: "FOR THE SHOP OWNER", language: "Language", business: "Demo business", emptyOwner: "No business is available to explain yet.", speechError: "Reading aloud stopped. Try again or read the card.", speechUnavailable: "Reading aloud needs a phone or browser that supports speech. The text is the same.", ownerNote: "Hindi and Kannada wording is a first draft pending review by a native speaker. Sandbox data.",
} as const;
type Text = { [K in keyof typeof en]: string };
export const WORKBENCH: Record<Lang, Text> = {
  en,
  hi: {
    clients: "ग्राहक", books: "खाते", tally: "Tally सहायक", owner: "मालिक का नज़रिया", impact: "असर", welcome: "परिचय", navigation: "मुख्य नेविगेशन", client: "ग्राहक रिकॉर्ड",
    commands: "कमांड", commandTitle: "कार्यस्थल खोलें", commandSearch: "पन्ने या ग्राहक खोजें", commandHelp: "↑ और ↓ से चुनें, Enter से खोलें, Esc से बंद करें।", close: "बंद करें", noCommands: "कोई पन्ना नहीं मिला", changeSearch: "खोज हटाएँ", results: "मिलते पन्ने",
    darkTheme: "गहरा रंग", lightTheme: "हल्का रंग", theme: "रंग थीम", dataTable: "आँकड़ों की तालिका देखें", item: "मद", value: "मान",
    loading: "कार्यस्थल तैयार हो रहा है", error: "यह नज़ारा तैयार नहीं हुआ। आपके रिकॉर्ड नहीं बदले हैं।", retry: "फिर कोशिश करें", emptyClients: "अभी कोई ग्राहक रिकॉर्ड नहीं है", openBooks: "खाते खोलें", resetFilters: "फ़िल्टर हटाएँ",
    invoiceStatuses: "बिलों का मिलान", invoiceCount: "बिल", priorities: "प्राथमिकता अंकों के अनुसार ग्राहक", priorityPoints: "प्राथमिकता अंक", priorityNote: "अंक = त्रुटियाँ × 10 + अंतिम तारीख़ की नज़दीकी (अधिकतम 30 अंक)। गिनती मौजूदा फ़िल्टर के अनुसार है। सैंडबॉक्स रिकॉर्ड।",
    hoursChart: "महीने के घंटों का बँटवारा", monthlyHours: "घंटे प्रति महीना", saved: "बचत", remaining: "बाकी", feesChart: "मॉडल में सालाना फ़ीस", annualFees: "रुपये प्रति वर्ष", totalFees: "कुल फ़ीस", sortingFees: "छँटाई का काम",
    capacityChart: "अलग छँटाई हिस्सों पर क्षमता", shareDone: "छँटाई पूरी (%)", capacity: "क्षमता (×)", modelNote: "आपके इनपुट से गणना किए उदाहरण; मापे नतीजे या समय के आँकड़े नहीं।", noSavings: "0% छँटाई पूरी होने पर मॉडल में कोई बचत नहीं है।", resetModel: "अनुमान रीसेट करें",
    ownerEyebrow: "दुकान मालिक के लिए", language: "भाषा", business: "डेमो व्यवसाय", emptyOwner: "अभी समझाने के लिए कोई व्यवसाय नहीं है।", speechError: "पढ़ना रुक गया। फिर कोशिश करें या कार्ड पढ़ें।", speechUnavailable: "सुनने के लिए बोलने की सुविधा वाला फ़ोन या ब्राउज़र चाहिए। लिखी बात वही है।", ownerNote: "हिंदी और कन्नड़ का मसौदा मूल वक्ता की समीक्षा की प्रतीक्षा में है। सैंडबॉक्स डेटा।",
  },
  kn: {
    clients: "ಗ್ರಾಹಕರು", books: "ಖಾತೆಗಳು", tally: "Tally ಸಹಾಯಕ", owner: "ಮಾಲೀಕರ ನೋಟ", impact: "ಪರಿಣಾಮ", welcome: "ಪರಿಚಯ", navigation: "ಮುಖ್ಯ ನ್ಯಾವಿಗೇಶನ್", client: "ಗ್ರಾಹಕರ ದಾಖಲೆ",
    commands: "ಆದೇಶಗಳು", commandTitle: "ಕಾರ್ಯಸ್ಥಳ ತೆರೆಯಿರಿ", commandSearch: "ಪುಟ ಅಥವಾ ಗ್ರಾಹಕರನ್ನು ಹುಡುಕಿ", commandHelp: "↑ ಮತ್ತು ↓ ಬಳಸಿ ಆಯ್ಕೆ ಮಾಡಿ, Enter ಬಳಸಿ ತೆರೆಯಿರಿ, Esc ಬಳಸಿ ಮುಚ್ಚಿರಿ.", close: "ಮುಚ್ಚಿರಿ", noCommands: "ಹೊಂದುವ ಪುಟಗಳಿಲ್ಲ", changeSearch: "ಹುಡುಕಾಟ ಅಳಿಸಿ", results: "ಹೊಂದುವ ಪುಟಗಳು",
    darkTheme: "ಗಾಢ ಬಣ್ಣ", lightTheme: "ತಿಳಿ ಬಣ್ಣ", theme: "ಬಣ್ಣದ ಥೀಮ್", dataTable: "ದತ್ತಾಂಶ ಕೋಷ್ಟಕ ನೋಡಿ", item: "ವಿಷಯ", value: "ಮೌಲ್ಯ",
    loading: "ಕಾರ್ಯಸ್ಥಳ ಸಿದ್ಧವಾಗುತ್ತಿದೆ", error: "ಈ ನೋಟವನ್ನು ಸಿದ್ಧಪಡಿಸಲಾಗಲಿಲ್ಲ. ನಿಮ್ಮ ದಾಖಲೆಗಳು ಬದಲಾಗಿಲ್ಲ.", retry: "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ", emptyClients: "ಇನ್ನೂ ಗ್ರಾಹಕರ ದಾಖಲೆಗಳಿಲ್ಲ", openBooks: "ಖಾತೆಗಳನ್ನು ತೆರೆಯಿರಿ", resetFilters: "ಫಿಲ್ಟರ್ ಅಳಿಸಿ",
    invoiceStatuses: "ಬಿಲ್ ಹೊಂದಾಣಿಕೆ", invoiceCount: "ಬಿಲ್‌ಗಳು", priorities: "ಆದ್ಯತೆಯ ಅಂಕಗಳಂತೆ ಗ್ರಾಹಕರು", priorityPoints: "ಆದ್ಯತೆಯ ಅಂಕಗಳು", priorityNote: "ಅಂಕ = ದೋಷಗಳು × 10 + ಗಡುವಿನ ಸಮೀಪತೆ (ಗರಿಷ್ಠ 30 ಅಂಕ). ಎಣಿಕೆಗಳು ಆಯ್ದ ಫಿಲ್ಟರ್‌ಗಳಂತೆ ಬದಲಾಗುತ್ತವೆ. ಸ್ಯಾಂಡ್‌ಬಾಕ್ಸ್ ದಾಖಲೆಗಳು.",
    hoursChart: "ತಿಂಗಳ ಗಂಟೆಗಳ ಹಂಚಿಕೆ", monthlyHours: "ತಿಂಗಳಿಗೆ ಗಂಟೆಗಳು", saved: "ಉಳಿತಾಯ", remaining: "ಉಳಿದದ್ದು", feesChart: "ಮಾದರಿಯಲ್ಲಿ ವಾರ್ಷಿಕ ಶುಲ್ಕ", annualFees: "ವರ್ಷಕ್ಕೆ ರೂಪಾಯಿ", totalFees: "ಒಟ್ಟು ಶುಲ್ಕ", sortingFees: "ವಿಂಗಡಣೆ ಕೆಲಸ",
    capacityChart: "ವಿಂಗಡಣೆಯ ಪಾಲಿನಂತೆ ಸಾಮರ್ಥ್ಯ", shareDone: "ವಿಂಗಡಣೆ ಪೂರ್ಣ (%)", capacity: "ಸಾಮರ್ಥ್ಯ (×)", modelNote: "ನಿಮ್ಮ ಇನ್‌ಪುಟ್‌ನಿಂದ ಲೆಕ್ಕ ಹಾಕಿದ ಉದಾಹರಣೆಗಳು; ಅಳೆಯಲಾದ ಫಲಿತಾಂಶ ಅಥವಾ ಕಾಲಮಾಲೆಯಲ್ಲ.", noSavings: "0% ವಿಂಗಡಣೆ ಪೂರ್ಣವಾದಾಗ ಈ ಮಾದರಿಯಲ್ಲಿ ಉಳಿತಾಯವಿಲ್ಲ.", resetModel: "ಊಹೆಗಳನ್ನು ಮರುಹೊಂದಿಸಿ",
    ownerEyebrow: "ಅಂಗಡಿ ಮಾಲೀಕರಿಗಾಗಿ", language: "ಭಾಷೆ", business: "ಡೆಮೋ ವ್ಯಾಪಾರ", emptyOwner: "ವಿವರಿಸಲು ಇನ್ನೂ ವ್ಯಾಪಾರ ಲಭ್ಯವಿಲ್ಲ.", speechError: "ಓದುವುದು ನಿಂತಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ ಕಾರ್ಡ್ ಓದಿ.", speechUnavailable: "ಕೇಳಲು ಮಾತಿನ ಸೌಲಭ್ಯವಿರುವ ಫೋನ್ ಅಥವಾ ಬ್ರೌಸರ್ ಬೇಕು. ಪಠ್ಯ ಅದೇ ಆಗಿದೆ.", ownerNote: "ಹಿಂದಿ ಮತ್ತು ಕನ್ನಡದ ಮೊದಲ ಕರಡು ಮೂಲಭಾಷಿಕರ ಪರಿಶೀಲನೆಗಾಗಿ ಕಾಯುತ್ತಿದೆ. ಸ್ಯಾಂಡ್‌ಬಾಕ್ಸ್ ದತ್ತಾಂಶ.",
  },
};
