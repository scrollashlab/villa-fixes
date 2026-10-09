import re, sys, urllib.request, html
def ls(prefix):
    u = f"https://huggingface.co/buckets/scrollprize/datasets/tree/{prefix}"
    t = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "zaudit"}), timeout=60).read().decode()
    names = re.findall(r'href="/buckets/scrollprize/datasets/(?:tree|resolve|blob)/([^"?#]+)"', t)
    return sorted(set(html.unescape(n) for n in names if n.startswith(prefix + "/") and n.count("/") == prefix.count("/") + 1))
if __name__ == "__main__":
    for n in ls(sys.argv[1]): print(n)
