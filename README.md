<div dir="rtl">

# הבנתי

**כל מה שהמרצה אמר, ותשובה על כל מה שלא הבנת.** כלי חינמי בקוד פתוח לסטודנטים, ל-Windows.

הבנתי כותבת בשבילך כל מה שנאמר בהרצאה, בעברית או באנגלית, ושומרת תמונה של כל שקופית ושל הלוח. ככה אפשר להקשיב במקום להעתיק, ולשאול AI בדיוק על הרגע שלא הבנת.

- **הרצאה חיה:** זום, שידור או כל מה שמתנגן במחשב. התמלול רץ במחשב שלך.
- **הרצאה מוקלטת:** קובץ או קישור (דרייב, דרופבוקס, וואןדרייב, הקלטת זום). נגן שמסונכרן עם התמלול.
- **קורסים:** תיקייה לכל קורס, מילון מונחים שמשפר את התמלול, חיפוש בכל מה שנאמר.
- **הכנה למבחן:** מבחן תרגול, סיכום, כרטיסיות חזרה ודף נוסחאות מכל הרצאות הקורס.
- **שאלה ל-AI:** ChatGPT, Gemini או Claude בלחיצה (השאלה מועתקת עם ההקשר). עם מפתח API של OpenAI משלך, "הבנתי עונה" מציגה את התשובה בתוך האפליקציה.

## הורדה והתקנה

1. להוריד את `Hevanti.zip` מ-[הגרסה האחרונה](https://github.com/pechter-roei41/hevanti/releases/latest) ולחלץ.
2. להתקין [Python 3.14](https://www.python.org/downloads/windows/) (לסמן **Add python.exe to PATH**).
3. לחיצה כפולה על `Install`, ואחר כך על `Hevanti`.

המדריך המלא: [המדריך של הבנתי](https://claude.ai/artifact/Rho2yLpowLsxqy1Zsw6QAD)

## פרטיות

- התמלול והצילומים נשארים במחשב שלך. האפליקציה פתוחה רק במחשב שלך (`127.0.0.1`).
- ל-AI נשלח רק מה שבוחרים לשאול. עם "הבנתי עונה" הבקשה יוצאת ישירות מהמחשב שלך ל-OpenAI, עם המפתח שלך. אין שרת של הבנתי באמצע.
- המפתח נשמר מוצפן עם Windows DPAPI, ורק המשתמש שלך במחשב הזה יכול לקרוא אותו.

## איך זה בנוי

| קובץ | מה יש בו |
|---|---|
| `System/Program/live_transcribe.py` | הכל בצד המחשב: תמלול ([faster-whisper](https://github.com/SYSTRAN/faster-whisper), מודל העברית של [ivrit.ai](https://huggingface.co/ivrit-ai)), צילומי מסך, השרת המקומי, הקורסים ו-"הבנתי עונה" |
| `System/Program/app.html` | האפליקציה (נפתחת בדפדפן) |
| `System/Program/player.html` | הנגן של הרצאה מוקלטת |
| `System/Program/ask.js` | תיבת "שאלה ל-AI" |
| `tools/build_zip.py` | בונה את `Hevanti.zip` |

גרסה חדשה: תגית כמו `v2.0-20261014` (אותו מספר, בנייה חדשה) או `v2.1`. GitHub Actions בונה את ה-ZIP ומצרף אותו ל-Release, והאפליקציה מודיעה לסטודנטים שיש עדכון.

## תרומה ובעיות

מצאת באג? [לפתוח Issue](https://github.com/pechter-roei41/hevanti/issues) עם צילום מסך ו-`System\error_log.txt`. Pull requests מתקבלים בשמחה.

## רישיון

[MIT](LICENSE) © 2026 רועי פכטר. מודלים וספריות של צד שלישי מורדים מהמקור שלהם ובכפוף לרישיונות שלהם. הרצאות ושקופיות שייכות למי שיצר אותן: לשימוש אישי ללמידה, לפי מדיניות המוסד.

</div>

---

**Hevanti** is a free, open-source lecture companion for students on Windows: live and recorded lecture transcription (Hebrew and English, runs locally with faster-whisper and the ivrit.ai Hebrew model), automatic slide capture, per-course glossaries, full-text search, exam prep, and one-click questions to ChatGPT, Gemini or Claude, with optional in-app answers using your own OpenAI API key. MIT licensed.
