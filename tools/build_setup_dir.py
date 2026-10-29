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
הבנתי לא שולחת שום דבר בעצמה:
- ה-AI שלך (Claude, ChatGPT, Gemini) קורא מההרצאות רק כשמבקשים ממנו, ומה שהוא קורא עובר לחברה שלו כמו כל שיחה איתו.
- "סנכרון לענן" כבוי עד שמפעילים אותו. כשהוא פועל, התמלולים מועתקים לתיקיית Google Drive / OneDrive שלך.
- הבנתי בודקת ב-GitHub אם יצאה גרסה חדשה, ומורידה בפעם הראשונה את מודל התמלול (Hugging Face) ואת קריאת השקופיות (GitHub, אם מסכימים).
  אפשר לכבות את בדיקת העדכונים: "בדיקת עדכונים" בחיבור AI.

בקצרה (גרסה 2.2)
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
- "קריאת נוסחאות וכתב יד" (כבוי עד שמפעילים, עם מפתח Gemini שלך): כשהוא פועל, תמונות השקופיות נשלחות ל-Google.
  בתוכנית החינמית Google עשויה להשתמש בהן לשיפור המוצרים שלה. המפתח נשמר מוצפן (Windows DPAPI).
  "Formula reading" (off until you turn it on, with your own Gemini key): slide pictures are sent to Google.

אחריות: הבנתי ניתנת כמו שהיא, בלי אחריות מכל סוג. השימוש בה הוא באחריות המשתמש בלבד. לפני שמשתמשים, כל משתמש צריך
לבדוק מה הנהלים והכללים במוסד שלו ואצל המרצה. רועי פכטר ומפתחי הכלי אינם אחראים לשימוש בה.
Responsibility: Hevanti is provided "as is", without warranty of any kind. Use is entirely the user's responsibility.
Each user must check the rules of their own institution and lecturer before using it. The author and contributors are not liable.

Short version (2.2): what is kept - transcripts, screenshots of what you chose to capture, and the text read from them,
all on your computer. No account, no server of ours. If the "הקורסים שלי" folder sits inside OneDrive / Google Drive,
that service copies it to your account there. Text (and a picture, if you attach it) goes to an AI company only when
you press an "ask AI" / study-task button or ask a connected AI. You can capture one window or part of the screen
instead of the whole screen, pause capturing (button, or Ctrl+Alt+P on Windows), permanently mosaic parts of the
screen, and delete screenshots for good. The default still captures the whole main screen.

Transcription and slide reading run on your computer; lectures stay in the "הקורסים שלי" folder.
This program will not transfer any information to other networked systems unless specifically requested by the user
or the person installing or operating it. It checks GitHub for a newer release (can be turned off), downloads the
transcription model from Hugging Face and, if you agree, Tesseract from GitHub. Your AI app reads lectures only when
you ask it; "sync to the cloud" is off until you turn it on.
Full policy: https://github.com/pechter-roei41/hevanti/blob/main/CODE_SIGNING.md
"""


def make_icon(path):
    """The logo (a green speech bubble with a yellow tick) as a Windows .ico, drawn here - no image file in the repo."""
    from PIL import Image, ImageDraw
    big = 512
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    green, yellow = (31, 122, 85, 255), (247, 212, 76, 255)
    d.rounded_rectangle((26, 60, 486, 384), radius=60, fill=green)
    d.polygon([(330, 370), (420, 370), (432, 470)], fill=green)   # the bubble's tail
    d.line([(150, 222), (218, 290), (362, 146)], fill=yellow, width=52, joint="curve")
    for x, y in ((150, 222), (218, 290), (362, 146)):
        d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=yellow)
    im.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


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
