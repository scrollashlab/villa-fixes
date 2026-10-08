"""Cache titles/bodies of all ScrollPrize/villa issues and PRs (unauthenticated GitHub REST API) for prior-art search."""
import json, sys, time, urllib.request
out = sys.argv[1]; allx = []
# the listing endpoint caps at 10 pages; walk from both ends and merge by number
for direction, page in [(d, p) for d in ("asc", "desc") for p in range(1, 11)]:
    url = f"https://api.github.com/repos/ScrollPrize/villa/issues?state=all&per_page=100&page={page}&sort=created&direction={direction}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "catalog-qa-audit"})
    with urllib.request.urlopen(req, timeout=60) as r:
        rem = r.headers.get("X-RateLimit-Remaining"); batch = json.load(r)
    allx += [{"number": i["number"], "title": i["title"], "user": i["user"]["login"], "state": i["state"], "is_pr": "pull_request" in i,
              "created_at": i["created_at"], "comments": i["comments"], "body": i.get("body") or "", "html_url": i["html_url"]} for i in batch]
    print(page, len(batch), "remaining", rem, flush=True)
json.dump(sorted({i["number"]: i for i in allx}.values(), key=lambda i: i["number"]), open(out, "w"))
print("total unique", len({i["number"] for i in allx}), "max", max(i["number"] for i in allx))
