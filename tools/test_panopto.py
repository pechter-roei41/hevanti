"""A recording sent from Panopto (the bookmark in "הרצאה מוקלטת"): the page offers it with its name, the name becomes
the lecture's name, an HLS stream goes to yt-dlp, and a Panopto link that needs a sign-in explains the bookmark.
Any OS:  python3 tools/test_panopto.py"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["BZM_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(HERE, "System", "Program"))
import live_transcribe as L  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + str(detail)))
    if not ok:
        fails.append(name)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error title={name}::" + str(detail)[:300].replace("\n", " | "))


app = L.APP
MP4 = "https://s-cloudfront.cdn.ap.panopto.com/sessions/abc/def-mp4.mp4?Policy=x&Signature=y"
HLS = "https://s-cloudfront.cdn.ap.panopto.com/sessions/abc/master.m3u8?InvocationID=1"

# the page offers what the bookmark sent, with the recording's name (made safe for a folder name)
app.command({"action": "offer", "source": MP4, "name": "הרצאה 5: מומנט התמד"})
p = app.state()["pending"]
check("offer keeps the name", p and p["name"] == p["title"] == "הרצאה 5 מומנט התמד", p)
app.command({"action": "offer", "source": MP4})
check("offer without a name: named from the link", app.state()["pending"]["title"] == "")
app.command({"action": "dismiss_pending"})

# where each link goes: a stream in pieces (HLS) and Panopto pages -> yt-dlp; a file -> downloaded directly
to_site, to_http = [], []
L.site_download = lambda url: to_site.append(url) or None


class Resp:
    headers = {"Content-Type": "video/mp4"}

    def close(self):
        pass


L._http = lambda url, **k: to_http.append(url) or Resp()
L.save_download = lambda resp, url: os.path.join(tempfile.mkdtemp(), "def-mp4.mp4")
L.fetch_link(HLS)
check("an HLS stream goes to yt-dlp", to_site == [HLS], to_site)
L.fetch_link("https://tau.cloud.panopto.eu/Panopto/Pages/Viewer.aspx?id=123")
check("a Panopto page goes to yt-dlp", len(to_site) == 2)
L.LINK_TITLES[MP4] = "הרצאה 5 מומנט התמד"
m = L.fetch_link(MP4)
check("the file is downloaded directly", to_http == [MP4], to_http)
check("the lecture is named after the recording", m is not None and m.title == "הרצאה 5 מומנט התמד", m and m.title)

# a Panopto link that needs a sign-in: the message explains the bookmark
said = []
L.problem = said.append
L.run_ytdlp = lambda args, password=None, on_line=None: (False, ["ERROR: This video is only available for registered users. Use --cookies"])
L._ytdlp_info("https://tau.cloud.panopto.eu/Panopto/Pages/Viewer.aspx?id=123")
check("Panopto sign-in: points to the bookmark", said and said[-1] == L.PANOPTO_MSG, said)
L._ytdlp_info("https://vimeo.com/123")
check("other sites: the usual sign-in message", said[-1] == L.LINK_MESSAGES["login"], said[-1])

print("\nall passed" if not fails else f"\n{len(fails)} failed: {fails}")
sys.exit(1 if fails else 0)
