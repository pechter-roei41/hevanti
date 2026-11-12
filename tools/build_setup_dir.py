"""The folder Hevanti-Setup.exe installs (installer/hevanti.iss packs it): the app files, Hevanti's own Python
(the official embeddable Python from python.org, with site-packages on) and the icon. The release workflow then
installs the packages into that Python (on a Windows runner) and runs Inno Setup.

  python tools/build_setup_dir.py <python-3.x-embed-amd64.zip> <get-pip.py> <out folder>"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", "python"}
SKIP_EXT = (".sh",)


PRIVACY = """הבנתי (Hevanti) - פרטיות / Privacy

התמלול וקריאת השקופיות רצים במחשב שלך. ההרצאות נשמרות בתיקייה "הקורסים שלי" במחשב שלך.
הבנתי שולחת מידע החוצה רק במקרים האלה:
- ה-AI שלך (Claude, ChatGPT, Gemini) קורא מההרצאות רק כשמבקשים ממנו, ומה שהוא קורא עובר לחברה שלו כמו כל שיחה איתו.
- "סנכרון לענן" כבוי עד שמפעילים אותו. כשהוא פועל, התמלולים מועתקים לתיקיית Google Drive / OneDrive שלך.
- בדיקת עדכונים: בכל הפעלה הבנתי שואלת את GitHub (api.github.com) אם יצאה גרסה חדשה. לא נשלח שום מידע עליך.
  אפשר לכבות: בתיבה בהתקנה, או אחר כך בהגדרות, בלשונית "פרטיות".
- בפעם הראשונה היא מורידה את מודל התמלול (Hugging Face) ואת קריאת השקופיות (GitHub, אם מסכימים).
- "תשובה כאן" שולחת ל-Google (Gemini, עם המפתח שלך) רק כשאתה שואל. פרטים בהמשך.

בקצרה (גרסה 2.14)
- מה נשמר: תמלול ההרצאות, צילומי מסך של מה שבחרת לצלם, והטקסט שנקרא מהם.
- איפה: רק במחשב שלך. אין חשבון ואין שרת של הבנתי. אם "הקורסים שלי" נמצאת בתוך OneDrive או Google Drive
  (למשל Documents שמסונכרן), התוכנה של הענן מעתיקה אותה לחשבון שלך שם, כולל צילומי המסך.
- מה נשלח ל-AI: רק כשלוחצים על "שאלה ל-AI" או על משימה (סיכום, כרטיסיות, מבחן דמה), או כשמבקשים מ-AI מחובר.
- מה בשליטתך: לצלם חלון אחד או חלק מהמסך במקום כל המסך, להשהות את הצילום (כפתור, או Ctrl+Alt+P ב-Windows),
  לטשטש אזורים קבועים (מוזאיקה), ולמחוק צילומים לצמיתות (לא לסל המחזור; עותק ב-OneDrive יכול להישאר בסל
  המחזור של OneDrive עד 30 יום).
- ברירת המחדל מצלמת את כל המסך הראשי. כדאי לבחור חלון אחד או חלק מהמסך.
- "תשובה כאן" (עם מפתח Gemini שלך): בכל לחיצה נשלחים ל-Google השאלה, התמלול של הדקות האחרונות (או של ההרצאה,
  במשימה כמו סיכום) והשקופית שעל המסך. השאלות והתשובות נשמרות בתיקיית ההרצאה במחשב שלך.
  "Answer here" (your own Gemini key): each click sends the question, the recent transcript and the current slide to Google.
- "קריאת נוסחאות וכתב יד" (פועלת כברירת מחדל כשמוסיפים מפתח Gemini; אפשר לכבות בהגדרות): כשהיא פועלת, כל תמונת שקופית שנשמרת נשלחת ל-Google.
  בתוכנית החינמית Google עשויה להשתמש בהן לשיפור המוצרים שלה. המפתח נשמר מוצפן (Windows DPAPI).
  "Formula reading" (on by default once you save your own Gemini key; can be turned off in Settings): slide pictures that are not clearly plain printed text (formulas, handwriting, pictures) are sent to Google (plain printed text is read on your computer).

אחריות: הבנתי ניתנת כמו שהיא, בלי אחריות מכל סוג. השימוש בה הוא באחריות המשתמש בלבד. לפני שמשתמשים, כל משתמש צריך
לבדוק מה הנהלים והכללים במוסד שלו ואצל המרצה. מפתחי הכלי אינם אחראים לשימוש בה.
Responsibility: Hevanti is provided "as is", without warranty of any kind. Use is entirely the user's responsibility.
Each user must check the rules of their own institution and lecturer before using it. The author and contributors are not liable.

Short version (2.14): what is kept - transcripts, screenshots of what you chose to capture, and the text read from them,
all on your computer. No account, no server of ours. If the "הקורסים שלי" folder sits inside OneDrive / Google Drive,
that service copies it to your account there. Text (and a picture, if you attach it) goes to an AI company only when
you press an "ask AI" / study-task button or ask a connected AI. You can capture one window or part of the screen
instead of the whole screen, pause capturing (button, or Ctrl+Alt+P on Windows), permanently mosaic parts of the
screen, and delete screenshots for good. The default still captures the whole main screen.

Transcription and slide reading run on your computer; lectures stay in the "הקורסים שלי" folder.
Hevanti sends information to other networked systems only in the cases listed in the full policy: your questions to
Google Gemini (with your own key, only when you ask), the one-time model download from Hugging Face and, if you agree,
Tesseract from GitHub. It also asks GitHub whether a newer release exists when it starts; nothing about you is sent,
and you can turn that off in the installer or later in Settings, Privacy. Your AI app reads lectures only when
you ask it; "sync to the cloud" is off until you turn it on.
Full policy: https://github.com/pechter-roei41/hevanti/blob/main/CODE_SIGNING.md
"""


def make_icon(path):
    """The logo (a green bubble with a short tail and a thick yellow tick) as a Windows .ico, drawn here - no image file in the repo.
    Every size is drawn on its own (8x, then smoothed down) and fills its square, so the taskbar and Start icons stay crisp."""
    from PIL import Image, ImageDraw
    green, yellow = (31, 122, 85, 255), (247, 212, 76, 255)

    def draw(S):
        k = 8
        N = S * k
        im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        u = N * 0.98 / 108   # the mark is 108 x 106 units: fill the square
        ox, oy = N * 0.01 - 6 * u, N * 0.01 + (N * 0.98 - 106 * u) / 2 - 8 * u

        def P(x, y):
            return (ox + x * u, oy + y * u)
        d.rounded_rectangle([P(6, 8), P(114, 94)], radius=24 * u, fill=green)
        d.polygon([P(68, 93), P(92, 93), P(100, 114)], fill=green)
        pts = [P(33, 52), P(52, 71), P(87, 33)]
        d.line(pts, fill=yellow, width=int(17 * u), joint="curve")
        for x, y in pts:
            d.ellipse((x - 8.5 * u, y - 8.5 * u, x + 8.5 * u, y + 8.5 * u), fill=yellow)
        return im.resize((S, S), Image.LANCZOS)
    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    frames = [draw(n) for n in sizes]
    frames[-1].save(path, format="ICO", sizes=[(n, n) for n in sizes], append_images=frames[:-1])


def main():
    embed, get_pip, out = sys.argv[1:4]
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for item in ("README.txt", "LICENSE"):
        shutil.copy2(os.path.join(ROOT, item), os.path.join(out, item))
    for d, dirs, files in os.walk(os.path.join(ROOT, "System")):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        rel = os.path.relpath(d, ROOT)
        os.makedirs(os.path.join(out, rel), exist_ok=True)
        for f in files:
            if not f.endswith(SKIP_EXT) and f != "error_log.txt":
                shutil.copy2(os.path.join(d, f), os.path.join(out, rel, f))
    py = os.path.join(out, "python")
    with zipfile.ZipFile(embed) as z:
        z.extractall(py)
    for f in os.listdir(py):
        if f.endswith("._pth"):   # let it use installed packages (off in the embeddable Python)
            p = os.path.join(py, f)
            with open(p, encoding="ascii") as h:
                body = h.read()
            with open(p, "w", encoding="ascii") as h:
                h.write(body.replace("#import site", "import site"))
    shutil.copy2(get_pip, os.path.join(py, "get-pip.py"))
    make_icon(os.path.join(out, "hevanti.ico"))
    with open(os.path.join(out, "PRIVACY.txt"), "w", encoding="utf-8-sig") as f:   # shown by the installer
        f.write(PRIVACY)
    print("ready:", out)


if __name__ == "__main__":
    main()
