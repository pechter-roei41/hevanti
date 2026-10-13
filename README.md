<div dir="rtl">

# הבנתי

**כל מה שהמרצה אמר, ותשובה על כל מה שלא הבנת.** כלי חינמי בקוד פתוח לסטודנטים, ל-Windows.

הבנתי כותבת בשבילך כל מה שנאמר בהרצאה, בעברית או באנגלית, ושומרת תמונה של כל שקופית ושל הלוח. ככה אפשר להקשיב במקום להעתיק, ולשאול AI בדיוק על הרגע שלא הבנת.

- **הרצאה חיה:** זום, שידור או כל מה שמתנגן במחשב. התמלול רץ במחשב שלך.
- **הרצאה מוקלטת:** קובץ או קישור (דרייב, דרופבוקס, וואןדרייב, הקלטת זום). נגן שמסונכרן עם התמלול.
- **סרטון ביוטיוב:** מתנגן בנגן הרשמי של יוטיוב בתוך הבנתי (בלי הורדה), ומתומלל תוך כדי צפייה עם הזמן של הסרטון.
- **קורסים:** תיקייה לכל קורס, מילון מונחים שמשפר את התמלול, חיפוש בכל מה שנאמר.
- **הכנה למבחן:** מבחן תרגול, סיכום, כרטיסיות חזרה ודף נוסחאות מכל הרצאות הקורס.
- **חיבור AI:** כפתור אחד מחבר את Claude למחשב או את ChatGPT ל-Windows להבנתי (שרת MCP קטן), ואז שואלים אותם ישר בחלון שלהם: "מה הוא אמר עכשיו?" - הם קוראים לבד את הדקות האחרונות ואת השקופית.
- **חלון צף:** חלון קטן שנשאר מעל ההרצאה, עם מה שנאמר עכשיו, השקופית ותיבת שאלה.
- **בלי חיבור:** ChatGPT, Gemini או Claude בלחיצה, השאלה מועתקת עם ההקשר.

## הורדה והתקנה

1. להוריד את `Hevanti.zip` מ-[הגרסה האחרונה](https://github.com/pechter-roei41/hevanti/releases/latest) ולחלץ.
2. להתקין [Python 3.14](https://www.python.org/downloads/windows/) (לסמן **Add python.exe to PATH**).
3. לחיצה כפולה על `Install`, ואחר כך על `Hevanti`.

המדריך המלא: [המדריך של הבנתי](https://claude.ai/artifact/Rho2yLpowLsxqy1Zsw6QAD)

## פרטיות

- התמלול והצילומים נשארים במחשב שלך. האפליקציה פתוחה רק במחשב שלך (`127.0.0.1`).
- אין שרת של הבנתי. המחבר (`hevanti_mcp.py`) רק קורא קבצים מ"ההרצאות שלי", ורק כשה-AI שלך מבקש. מה שה-AI קורא עובר לחברה שלו כמו כל שיחה איתו.

## איך זה בנוי

| קובץ | מה יש בו |
|---|---|
| `System/Program/live_transcribe.py` | הכל בצד המחשב: תמלול ([faster-whisper](https://github.com/SYSTRAN/faster-whisper), מודל העברית של [ivrit.ai](https://huggingface.co/ivrit-ai)), צילומי מסך, השרת המקומי, הקורסים, יוטיוב וחיבור ה-AI |
| `System/Program/app.html` | האפליקציה (נפתחת בדפדפן) |
| `System/Program/player.html` | הנגן של הרצאה מוקלטת |
| `System/Program/ask.js` | תיבת "שאלה ל-AI" |
| `System/Program/hevanti_mcp.py` | המחבר ל-AI (שרת MCP, ספרייה סטנדרטית בלבד): `now`, `transcript`, `slide`, `search`, `lectures` |
| `tools/build_zip.py` | בונה את `Hevanti.zip` |

גרסה חדשה: תגית כמו `v2.0-20261014` (אותו מספר, בנייה חדשה) או `v2.1`. GitHub Actions בונה את ה-ZIP ומצרף אותו ל-Release, והאפליקציה מודיעה לסטודנטים שיש עדכון.

## תרומה ובעיות

מצאת באג? [לפתוח Issue](https://github.com/pechter-roei41/hevanti/issues) עם צילום מסך ו-`System\error_log.txt`. Pull requests מתקבלים בשמחה.

## רישיון

[MIT](LICENSE) © 2026 רועי פכטר. מודלים וספריות של צד שלישי מורדים מהמקור שלהם ובכפוף לרישיונות שלהם. הרצאות ושקופיות שייכות למי שיצר אותן: לשימוש אישי ללמידה, לפי מדיניות המוסד.

</div>

---

**Hevanti** is a free, open-source lecture companion for students on Windows: live and recorded lecture transcription (Hebrew and English, runs locally with faster-whisper and the ivrit.ai Hebrew model), automatic slide capture, per-course glossaries, full-text search, exam prep, YouTube videos played in the official embedded player and transcribed while watching (with video timestamps), a floating always-on-top window, and a one-click MCP connector so Claude for desktop or ChatGPT (Codex) can read the live lecture, the current slide and all transcripts directly. MIT licensed.
