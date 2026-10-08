import csv, json, subprocess, sys
import numpy as np
from xframe import geom
from xframe.tifxyz import read_tifxyz
from conftest import A, B, C


def run(*args, root):
    return subprocess.run([sys.executable, "-m", "xframe", *args, "--bucket-root", str(root)],
                          capture_output=True, text=True)


def test_verify_classes_and_exit_code(fake_bucket):
    r = run("verify", "S1", fake_bucket["seg"], "--json", root=fake_bucket["root"])
    assert r.returncode == 1, r.stderr          # one deliberately shifted mesh -> non-zero
    rows = {x["target_volume"] + ":" + x["kind"]: x for x in json.loads(r.stdout)}
    assert rows[f"{B}:derived"]["class"] == "CONSISTENT" and rows[f"{B}:derived"]["shape_match"]
    assert rows[f"{A}:copy"]["class"] == "CONSISTENT" and rows[f"{A}:copy"]["max_vox"] == 0.0
    bad = rows[f"{C}:derived"]
    assert bad["class"] == "DRIFT" and abs(bad["median_vox"] - 3 * 3 ** 0.5) < 0.02   # 3 vox on each axis = 5.196


def test_explain_warns_downscale(fake_bucket):
    r = run("explain", "S1", fake_bucket["seg"], root=fake_bucket["root"])
    assert r.returncode == 0, r.stderr
    assert "1/4 grid" in r.stdout
    # downscale 4 x matrix ~0.4 = net ~1.6x UP; downscale 4 x matrix 2.0 = ~8x UP
    assert "UP-sampled ~1.60x" in r.stdout and "UP-sampled ~8.00x" in r.stdout and "byte copy" in r.stdout


def test_convert_csv_roundtrip(fake_bucket, tmp_path):
    src = tmp_path / "pts.csv"
    src.write_text("id,x,y,z\na,100,200,300\nb,1.5,2.5,3.5\n")
    r = run("convert", "--sample", "S1", "--from", A, "--to", B, str(src), str(tmp_path / "b.csv"), root=fake_bucket["root"])
    assert r.returncode == 0, r.stderr
    rows = list(csv.DictReader(open(tmp_path / "b.csv")))
    back = tmp_path / "back_in.csv"
    back.write_text("id,x,y,z\n" + "".join(f"{x['id']},{x['x_out']},{x['y_out']},{x['z_out']}\n" for x in rows))
    r = run("convert", "--sample", "S1", "--from", B, "--to", A, str(back), str(tmp_path / "a.csv"), root=fake_bucket["root"])
    assert r.returncode == 0, r.stderr
    out = list(csv.DictReader(open(tmp_path / "a.csv")))
    np.testing.assert_allclose([[float(o[k]) for k in ("x_out", "y_out", "z_out")] for o in out], [[100, 200, 300], [1.5, 2.5, 3.5]], atol=1e-8)
    assert abs(float(rows[0]["x_out_um"]) - float(rows[0]["x_out"]) * 9.0) < 1e-6
    assert json.load(open(tmp_path / "b.csv.provenance.json"))["how"] == "catalog"


def test_convert_tifxyz_from_normalized(fake_bucket, tmp_path):
    key = fake_bucket["base"] + "/intermediate/tifxyz_normalized"
    r = run("convert", "--sample", "S1", "--from-normalized-of", fake_bucket["seg"], "--to", B, key, str(tmp_path / "out"), root=fake_bucket["root"])
    assert r.returncode == 0, r.stderr
    Q, meta = read_tifxyz(None, str(tmp_path / "out"))
    np.testing.assert_array_equal(Q, fake_bucket["Qb"])
    assert meta["scale"] == [0.05, 0.05] and meta["voxel_size_um"] == 9.0 and meta["xframe"]["prescale"] == 4.0
