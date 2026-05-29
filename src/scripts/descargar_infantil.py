"""
Descarga muestras públicas de habla infantil en español (Nexdata, sin login)
para la prueba de domain gap. Habla ESPONTÁNEA (no las 32 palabras de Bosch).
"""
from __future__ import annotations
import os, sys, glob
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from huggingface_hub import snapshot_download

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESTINO = os.path.join(RAIZ, "data", "raw", "nexdata_child")

REPOS = [
    "Nexdata/Latin_American_Spanish_Children_Spontaneous_Speech_Data",
    "Nexdata/145_Hours_Spanish_Child_Spontaneous_Speech_Data",
]


def main():
    for repo in REPOS:
        sub = os.path.join(DESTINO, repo.split("/")[-1])
        try:
            snapshot_download(repo_id=repo, repo_type="dataset", local_dir=sub)
            print(f"OK: {repo}")
        except Exception as e:
            print(f"[WARN] {repo}: {e}")
    wavs = glob.glob(os.path.join(DESTINO, "**", "*.wav"), recursive=True)
    txts = glob.glob(os.path.join(DESTINO, "**", "*.txt"), recursive=True)
    print(f"\nWAV: {len(wavs)} | TXT: {len(txts)}")
    for w in wavs[:5]:
        t = os.path.splitext(w)[0] + ".txt"
        trans = open(t, encoding="utf-8").read().strip() if os.path.exists(t) else "(sin txt)"
        print(f"  {os.path.basename(w)}: {trans[:70]}")


if __name__ == "__main__":
    main()
