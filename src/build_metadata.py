"""
Genera metadata.csv a partir de los nombres de archivo de Base_datos_palabras/.

Convencion observada:  palabra_usuario_sexo_pais.mp3
 - Hay inconsistencias: orden invertido (palabra_usuario_pais_sexo),
   mayusculas, typos en el nombre de fichero, y carpeta 'niño' con encoding NFD.
 - Usamos el NOMBRE DE LA CARPETA como 'palabra' fiable (corrige typos como 'espdad').

Salida: metadata.csv con columnas:
   ruta, palabra, hablante, sexo, pais, origen, revisar
"""
import csv
import os
import sys
import unicodedata

# Asegura que la consola de Windows pueda imprimir acentos / caracteres unicode.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Base_datos_palabras")

SEX_TOKENS = {"h": "hombre", "m": "mujer"}

# Mapa pais -> origen. Claves en minuscula.
ESPANA = {"esp"}
LATAM = {"arg", "mex", "col", "chile", "ven", "peru", "cuba", "para",
         "gua", "cr", "bol", "uru", "ecu", "pan", "rd", "hon", "nic", "salv", "py"}
NO_NATIVO = {"eeuu", "fra", "ita", "ale", "ger", "uk", "usa", "bra", "por"}

# Paises cuya etiqueta de origen es dudosa (heritage speakers, etc.)
DUDOSOS = {"eeuu", "usa"}


def normaliza(texto: str) -> str:
    """NFC para arreglar 'niño' descompuesto, y minusculas."""
    return unicodedata.normalize("NFC", texto).strip().lower()


def pais_a_origen(pais: str):
    if pais in ESPANA:
        return "España"
    if pais in LATAM:
        return "Latam"
    if pais in NO_NATIVO:
        return "No nativo"
    return "DESCONOCIDO"


def parse_tokens(tokens):
    """Dado [usuario, t1, t2, ...] devuelve (hablante, sexo, pais).
    Detecta el token de sexo (h/m) en cualquier posicion."""
    hablante = tokens[0] if tokens else ""
    resto = tokens[1:]
    sexo_raw, pais_raw = "", ""
    sin_sexo = []
    for t in resto:
        tl = t.lower()
        if tl in SEX_TOKENS and not sexo_raw:
            sexo_raw = tl
        else:
            sin_sexo.append(tl)
    pais_raw = "_".join(sin_sexo) if sin_sexo else ""
    return hablante, sexo_raw, pais_raw


def main():
    filas = []
    for carpeta in sorted(os.listdir(BASE)):
        ruta_carpeta = os.path.join(BASE, carpeta)
        if not os.path.isdir(ruta_carpeta):
            continue
        palabra = normaliza(carpeta)
        for fn in sorted(os.listdir(ruta_carpeta)):
            if not fn.lower().endswith(".mp3"):
                continue
            base = normaliza(os.path.splitext(fn)[0])
            tokens = base.split("_")
            # tokens[0] suele repetir la palabra; lo descartamos y usamos la carpeta
            hablante, sexo_raw, pais_raw = parse_tokens(tokens[1:] if len(tokens) > 1 else tokens)
            sexo = SEX_TOKENS.get(sexo_raw, "DESCONOCIDO")
            origen = pais_a_origen(pais_raw)
            revisar = []
            if sexo == "DESCONOCIDO":
                revisar.append("sin_sexo")
            if origen == "DESCONOCIDO":
                revisar.append(f"pais_desconocido:{pais_raw}")
            if pais_raw in DUDOSOS:
                revisar.append("origen_dudoso")
            ruta_rel = os.path.join("Base_datos_palabras", carpeta, fn)
            filas.append({
                "ruta": ruta_rel,
                "palabra": palabra,
                "hablante": hablante,
                "sexo": sexo,
                "pais": pais_raw,
                "origen": origen,
                "revisar": ";".join(revisar),
            })

    salida = os.path.join(os.path.dirname(BASE), "metadata.csv")
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ruta", "palabra", "hablante", "sexo", "pais", "origen", "revisar"])
        w.writeheader()
        w.writerows(filas)

    # ---- Resumen por consola ----
    print(f"Total audios: {len(filas)}")
    print(f"CSV escrito en: {salida}\n")

    def conteo(campo):
        d = {}
        for r in filas:
            d[r[campo]] = d.get(r[campo], 0) + 1
        return dict(sorted(d.items(), key=lambda x: -x[1]))

    print("Por SEXO:   ", conteo("sexo"))
    print("Por ORIGEN: ", conteo("origen"))
    print("Hablantes unicos:", len({r["hablante"] for r in filas}))
    revisar = [r for r in filas if r["revisar"]]
    print(f"\nFilas a revisar ({len(revisar)}):")
    for r in revisar:
        print(f"  {r['ruta']}  ->  {r['revisar']}")


if __name__ == "__main__":
    main()
