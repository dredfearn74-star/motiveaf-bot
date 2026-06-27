#!/usr/bin/env python3
"""
MotiveAF daily poster — runs on GitHub Actions (free cloud runner).
Posts the meme whose date == today to Facebook + Instagram.

Repo must contain:
  - MotiveAF_queue.csv   (date, post_time_local, brand, seq, image_file_id, image_filename, caption_ref, platforms, status)
  - captions.json        ({"1": "full caption", ...})
  - images/<image_filename>   (the 33 square jpgs)

Secrets (GitHub repo > Settings > Secrets and variables > Actions):
  - FB_PAGE_TOKEN  : a long-lived (non-expiring) PAGE access token for MotiveAF
  - FB_PAGE_ID     : 1179462511909328
  - IG_USER_ID     : 17841414971833045
  - IMG_BASE_URL   : public raw base for the images folder, e.g.
                     https://raw.githubusercontent.com/<user>/<repo>/main/images/

Optional:
  - RUN_DATE  : YYYY-MM-DD to force a specific day (manual run / catch-up)
  - DRY_RUN   : "1" to log what WOULD post without posting
"""
import os, csv, json, sys, time, datetime, urllib.parse, urllib.request

GRAPH = "https://graph.facebook.com/v21.0"

PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
PAGE_ID    = os.environ["FB_PAGE_ID"]
IG_USER_ID = os.environ["IG_USER_ID"]
IMG_BASE   = os.environ["IMG_BASE_URL"].rstrip("/") + "/"
DRY_RUN    = os.environ.get("DRY_RUN") == "1"

# "today" in US Central (handoff says ~8 AM local). GitHub runs in UTC.
def central_today():
    if os.environ.get("RUN_DATE"):
        return os.environ["RUN_DATE"].strip()
    # Central is UTC-5 (CDT, summer). Good enough for a date stamp.
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=5)).date().isoformat()

def http_post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def post_facebook(image_url, caption):
    r = http_post(f"{GRAPH}/{PAGE_ID}/photos",
                  {"url": image_url, "caption": caption, "access_token": PAGE_TOKEN})
    return r  # {"id":..., "post_id":...}

def post_instagram(image_url, caption):
    create = http_post(f"{GRAPH}/{IG_USER_ID}/media",
                       {"image_url": image_url, "caption": caption, "access_token": PAGE_TOKEN})
    cid = create["id"]
    # give Meta a moment to fetch/process the image
    time.sleep(5)
    pub = http_post(f"{GRAPH}/{IG_USER_ID}/media_publish",
                    {"creation_id": cid, "access_token": PAGE_TOKEN})
    return pub  # {"id":...}

def main():
    today = central_today()
    captions = json.load(open("captions.json", encoding="utf-8"))
    rows = list(csv.DictReader(open("MotiveAF_queue.csv", encoding="utf-8")))

    due = [r for r in rows if r["date"] == today and r["status"].strip().upper() == "QUEUED"]
    if not due:
        print(f"[{today}] nothing due. Exiting cleanly.")
        return

    for r in due:
        seq = r["seq"].strip()
        caption = captions[seq]
        image_url = IMG_BASE + urllib.parse.quote(r["image_filename"])
        print(f"[{today}] posting seq {seq}: {r['image_filename']}")
        if DRY_RUN:
            print("  DRY_RUN — would post to FB + IG with image:", image_url)
            continue
        fb = post_facebook(image_url, caption)
        print("  FB ok:", fb.get("post_id") or fb.get("id"))
        ig = post_instagram(image_url, caption)
        print("  IG ok:", ig.get("id"))
        print(f"  DONE seq {seq}. (Mark this row POSTED in MotiveAF_queue.csv.)")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.read().decode(), file=sys.stderr)
        sys.exit(1)
