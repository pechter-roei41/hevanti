# מדיניות פרטיות · Privacy policy

הבנתי (Hevanti), גרסה 2.21, 13.11.2026. תוקף: מהגרסה הזאת ועד שתתפרסם מדיניות חדשה. הגרסאות הקודמות של הדף נמצאות בהיסטוריה של המאגר.

## בקצרה

- הבנתי רצה במחשב שלך. אין לה שרת ואין חשבון משלה, והיא לא אוספת סטטיסטיקות ולא שולחת נתוני שימוש לאף אחד.
- התמלול של ההרצאות, צילומי המסך של השקופיות והטקסט שנקרא מהם נשמרים רק במחשב שלך, בתיקייה "הקורסים שלי".
- מידע יוצא מהמחשב רק במקרים שמפורטים כאן. החשוב שבהם: אם הזנת מפתח Gemini, שאלות ושקופיות נשלחות ל-Google.
- אתה האחראי לבדוק אם מותר לך להקליט את ההרצאה (ראו "תנאי שימוש").

## מה נשמר, ואיפה

| מה | איפה | הערות |
| --- | --- | --- |
| תמלולים, צילומי מסך של שקופיות, הטקסט שנקרא מהם, שאלות ותשובות | `Documents\הבנתי\הקורסים שלי` (אפשר לשנות) | אם התיקייה בתוך OneDrive או Google Drive, שירות הענן מעתיק אותה לחשבון שלך שם, כולל התמונות. |
| ההגדרות, ומפתח Gemini | `%LOCALAPPDATA%\Hevanti\settings.json` | המפתח מוצפן עם Windows DPAPI (רק החשבון שלך ב-Windows יכול לפענח). אם אי אפשר להצפין, הוא לא נשמר. |
| מודלי התמלול | `%LOCALAPPDATA%\Hevanti\models` | בגרסאות קודמות: `C:\Users\Public\whisper_models`. |
| יומן שגיאות | `System\error_log.txt` בתיקיית ההתקנה | בלי מפתחות ובלי חלק הכתובת שאחרי הסימן ? של קישור. מוגבל לכ-1MB. |
| רישום שימוש של שאלות ל-Gemini | `%LOCALAPPDATA%\Hevanti\tokens.jsonl` | ספירה בלבד (מתי ובאיזה מודל, כמה), בלי תוכן השאלות. |
| הקלטות שהורדו מקישור | `%LOCALAPPDATA%\Hevanti\videos` | |
| פרופילי דפדפן של החלון הצף וחלון ההתחלה המהירה | `%LOCALAPPDATA%\Hevanti` | |

הבנתי מקשיבה לצליל של הרמקולים של המחשב בלבד (לא למיקרופון), ומצלמת את המסך רק כשהיא רצה ובאזור שבחרת. ברירת המחדל היא כל המסך הראשי, ולכן כדאי לבחור חלון אחד או חלק מהמסך. חלונות של כלי AI ושל הבנתי נצבעים באפור כדי שתשובה לא תישמר כשקופית.

## מה נשלח החוצה, ולמי

| מתי | מה נשלח, ולמי |
| --- | --- |
| אתה שואל שאלה ("תשובה כאן", או Enter בחלון הצף), ויש לך מפתח Gemini | השאלה, התמלול של הדקות האחרונות, השקופית שעל המסך והטקסט של שקופיות קודמות נשלחים ל-Google (`generativelanguage.googleapis.com`), עם המפתח שלך. במשימה על הרצאה שלמה (סיכום, מבחן) נשלח התמלול שלה. |
| **אחרי שהזנת מפתח Gemini, בלי לחיצה** | "קריאת נוסחאות וכתב יד" פועלת מעצמה: כל תמונת שקופית שנשמרה ואינה טקסט מודפס ברור נשלחת ל-Google. אפשר לכבות בהגדרות, מתחת למפתח. בשקופית יכולים להופיע פנים ושמות של משתתפים בשיחת וידאו, והם נשלחים כמו שהם. |
| בדיקת מודלים זמינים (פעם ביום, עם מפתח) | בקשה ל-Google עם המפתח, כדי לבחור איזה מודל עונה היום. בלי תוכן. |
| בהרצאה הראשונה, או בשפה חדשה | מודל התמלול יורד מ-Hugging Face (`huggingface.co`). לא נשלח מידע עליך. |
| בהתקנה | Python, חבילות הפייתון וקובץ ההתקנה של Tesseract יורדים מ-python.org, מ-PyPI (`pypi.org`) וממאגרי GitHub, ונבדקים לפי טביעה (SHA-256) לפני השימוש. |
| פתיחת הקלטה מקישור | הקובץ יורד מהכתובת שנתת. אפשר שרכיב ההורדה `yt-dlp` יותקן או יתעדכן מ-PyPI. סרטוני YouTube לא מורדים: הם מתנגנים בנגן הרשמי של YouTube בתוך האפליקציה, שטוען סקריפטים מ-YouTube ופועל לפי התנאים שלו. |
| התקנת התמיכה בכרטיס מסך של NVIDIA (כפתור בדף הבית, או `install_gpu`) | ספריות NVIDIA (cuBLAS ו-cuDNN) יורדות מ-PyPI, ונבדקות לפי טביעה (SHA-256). |
| בכל הפעלה, אלא אם כיבית | בקשה ל-GitHub (`api.github.com`) כדי לדעת מהי הגרסה האחרונה. לא נשלח מידע עליך. |
| "העתקה ל-ChatGPT, Gemini או Claude" | השאלה מועתקת ללוח, ואתה מדביק בעצמך. הבנתי רק פותחת את האתר או האפליקציה. |
| "סנכרון לענן" (כבוי כברירת מחדל) | התמלולים נכתבים לתיקיית Google Drive או OneDrive במחשב שלך, והשירות מסנכרן אותם לפי התנאים שלו. |
| חיבור לאפליקציית AI שלך (Claude, ChatGPT, Gemini CLI) | האפליקציה קוראת הרצאות רק כשמבקשים ממנה, ומה שהיא קוראת עובר לחברה שלה. |
| "דיווח על תקלה" | לא נשלח כלום. הבנתי רק מציגה טקסט להעתקה (בלי מפתח, בלי תמלולים), ואתה שולח בעצמך. |

Google עשויה להשתמש במה שנשלח ל-Gemini לפי התנאים שלה. **במפתח חינמי היא עשויה להשתמש בו כדי לשפר את המוצרים שלה**, ולכן אל תשלח חומר רגיש. האתר של הבנתי (לא האפליקציה) טוען גופן מ-Google Fonts, ולכן Google רואה את כתובת ה-IP של מי שמבקר בו.

## השרת המקומי

כדי שהחלונות של הבנתי ידברו עם התוכנה, היא מפעילה שרת קטן על `127.0.0.1` בלבד. הדפים וכל מה שהם מציגים (תמלולים, תמונות) ניתנים רק לדפדפן שנפתח מהבנתי עצמה (הוא מקבל סוד שמשתנה בכל הפעלה), והפקודות דורשות את הסוד וכותרת מיוחדת. כך אתר בדפדפן שלך, תוכנה אחרת, או משתמש אחר במחשב משותף לא יכולים לקרוא את ההרצאות שלך או להפעיל את התוכנה.

## מחיקה והסרה

- למחוק הרצאה שלמה: בתפריט ההרצאה. היא נשלחת לסל המיחזור של Windows. למחוק רק צילומי מסך: הם נמחקים לצמיתות, בלי סל. עותק בענן יכול להישאר שם (ב-OneDrive עד 30 יום).
- הסרת הבנתי מ-Windows (הגדרות, אפליקציות) מוחקת את התוכנה, את ההגדרות עם המפתח ואת מודלי התמלול. **ההרצאות שלך לא נמחקות** אף פעם בעדכון או בהסרה.
- מה שנשאר אחרי ההסרה בתיקיית `%LOCALAPPDATA%\Hevanti` (הקלטות שהורדו, תיקיית קריאת הטקסט) אפשר למחוק ידנית.
- המפתח של Gemini: אפשר למחוק אותו בהגדרות, והוא נמחק יחד עם כל העותקים שלו. את המפתח עצמו אפשר לבטל באתר של Google.

## פרטים של אנשים אחרים

בהרצאה ובשקופיות יכולים להופיע המרצה, סטודנטים ואנשים אחרים. הבנתי שומרת אותם רק במחשב שלך. אם הזנת מפתח Gemini, שקופיות נשלחות ל-Google כמפורט למעלה. אל תפיץ הקלטות, תמלולים או שקופיות.

## ילדים

הבנתי נועדה לסטודנטים באוניברסיטאות ובמכללות ואינה מיועדת לילדים.

## שינויים ויצירת קשר

שינוי במדיניות יפורסם בדף הזה וב-`System\VERSION.txt` של הגרסה שבה הוא נכנס. שאלות, בקשות, או דיווח על בעיית פרטיות: <hevanti.support@gmail.com> או [issue](https://github.com/pechter-roei41/hevanti/issues).

---

## In English

Hevanti (version 2.21, 13 Nov 2026) runs on your computer. It has no server and no account of its own, collects no statistics and sends no usage data.

**Kept on your computer:** transcripts, slide pictures and the text read from them (in `Documents\הבנתי`); the settings and your Gemini key (encrypted with Windows DPAPI); the speech models; an error log without keys; a count of questions to Gemini without their content. If the lectures folder sits inside OneDrive or Google Drive, that service copies it to your account.

**Sent to others:** (1) If you saved a Gemini key: your question, the last minutes of the transcript, the current slide and the text of earlier slides go to Google when you ask; and, without a click, slide pictures that are not clear printed text go to Google for formula and handwriting reading (can be turned off in Settings). Slides can show other people's faces and names. On the free tier Google may use this to improve its products. (2) A daily check of which Gemini models answer (with the key, no content). (3) Download of the speech model from Hugging Face, of Python and packages from python.org and PyPI, of Tesseract from GitHub (checked by SHA-256), and of yt-dlp and NVIDIA libraries from PyPI when needed. (4) On start, a request to GitHub for the latest version (can be turned off). (5) Recordings from links are downloaded from the address you give; YouTube plays in YouTube's own player under its terms and is never downloaded. (6) Cloud sync (off by default) and your own AI apps read lectures only when you turn them on or ask. "Report a problem" sends nothing: it only shows text you copy.

**Local server:** it listens on `127.0.0.1` only; pages and everything they show are given only to a browser opened by Hevanti (a secret that changes every run), so other sites, other programs and other Windows users cannot read your lectures.

**Deleting:** uninstalling removes the program, the settings with the key and the models; your lectures are never deleted by an update or an uninstall. Contact: hevanti.support@gmail.com.
