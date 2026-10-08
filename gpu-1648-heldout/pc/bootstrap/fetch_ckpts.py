"""Download the two public ink_9um checkpoints from Hugging Face and verify their sha256 (HF LFS oids)."""
import hashlib, os, sys, urllib.request
EXPECTED = {
    "hybrid_3d2d-seed42/step-075000.pth": "e635558ae6a1a807a7e5ec1e83adfd45bc3c0ac53883ea43f1d4e085d62a9cab",
    "hybrid_3d2d-seed43/step-075000.pth": "2aeaa85a35ef28d7bc7bf3e848c4a6a91385e9132710927fdba41133c4ecb28f",
}
dest = sys.argv[1]; os.makedirs(dest, exist_ok=True)
for rel, sha in EXPECTED.items():
    out = os.path.join(dest, rel.replace("/", "-"))
    if not (os.path.exists(out) and hashlib.sha256(open(out, "rb").read()).hexdigest() == sha):
        url = "https://huggingface.co/scrollprize/ink_9um/resolve/main/" + rel
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gpu-1648-heldout"}), timeout=300) as r:
            data = r.read()
        open(out + ".part", "wb").write(data); os.replace(out + ".part", out)
    got = hashlib.sha256(open(out, "rb").read()).hexdigest()
    print(rel, got, "OK" if got == sha else "MISMATCH"); assert got == sha
