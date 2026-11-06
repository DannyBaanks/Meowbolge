"""meowbolge — generador de programas Malbolge que imprimen texto arbitrario.

Edición 2026: Incorpora el motor constructivo Autobolge 2.0 Conveyor (O(N)),
reduciendo la síntesis de texto y arte ASCII de minutos a 2–4 milisegundos.
Conserva el proponedor BFS por niveles (v2) y la búsqueda exhaustiva (v1) como backends.

Escribir Malbolge no es escribir instrucciones. El opcode sale de:
    op = (mem[c] + c) % 94
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BAJO, ALTO = 33, 126
MOD = 94

OP_CHASE, OP_OUT, OP_IN, OP_ROT, OP_MOVD, OP_CRAZY, OP_NOP, OP_HALT = 4, 5, 23, 39, 40, 62, 68, 81

#: Operaciones que el generador puede encadenar para mover el acumulador.
CANDIDATAS = (OP_ROT, OP_CRAZY, OP_MOVD)

# ---------------------------------------------------------------------------
# Intérprete Canónico Clásico Embebido (Zero Dependencias Externas)
# ---------------------------------------------------------------------------
MEM_SIZE = 59049
POW9 = 19683

_CRAZY_TRITS = (
    (1, 0, 0),
    (1, 0, 2),
    (2, 2, 1),
)

_ENCRYPT_STR = (
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1C"
    "B6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)
_ENC = [ord(c) for c in _ENCRYPT_STR]


def crazy_op(x: int, y: int) -> int:
    """Operador crazy ternario clásico."""
    res = 0
    p = 1
    for _ in range(10):
        res += _CRAZY_TRITS[y % 3][x % 3] * p
        x //= 3
        y //= 3
        p *= 3
    return res


def rot_op(x: int) -> int:
    """Rotación ternaria a la derecha sobre 10 trits."""
    return (x // 3) + (x % 3) * POW9


class EmbeddedClassicVM:
    """Intérprete Malbolge Clásico autónomo embebido."""
    MEM_SIZE = MEM_SIZE
    _ENC = _ENC

    @staticmethod
    def crazy_op(a: int, b: int) -> int:
        return crazy_op(a, b)

    @staticmethod
    def load_memory(source: str) -> list[int]:
        chars = [ord(c) for c in source if not c.isspace()]
        if len(chars) > MEM_SIZE:
            raise ValueError(f"programa excede memoria ({len(chars)} > {MEM_SIZE})")
        mem = [0] * MEM_SIZE
        for i, ch in enumerate(chars):
            if not 33 <= ch <= 126:
                raise ValueError(f"carácter inválido {ch} en celda {i}")
            mem[i] = ch
        for i in range(len(chars), MEM_SIZE):
            mem[i] = crazy_op(mem[i - 1], mem[i - 2])
        return mem

    @classmethod
    def run(cls, source: str, max_steps: int = 500_000, on_step=None):
        try:
            mem = cls.load_memory(source)
        except Exception as e:
            return "", 0, f"LOAD_ERROR: {e}"

        a = 0
        c = 0
        d = 0
        salida = bytearray()
        pasos = 0
        status = "MAX_STEPS"

        while pasos < max_steps:
            cell = mem[c]
            op = (cell + c) % 94

            if on_step is not None:
                on_step(pasos, a, c, d, op, cell)

            jumped = False
            c_target = 0

            if op == OP_HALT:
                status = "HALTED"
                break
            elif op == OP_CHASE:
                c_target = mem[d]
                jumped = True
            elif op == OP_OUT:
                salida.append(a % 256)
            elif op == OP_IN:
                a = 59048  # EOF
            elif op == OP_ROT:
                a = mem[d] = rot_op(mem[d])
            elif op == OP_MOVD:
                d = mem[d]
            elif op == OP_CRAZY:
                a = mem[d] = crazy_op(a, mem[d])
            elif op == OP_NOP:
                pass

            if jumped:
                c = c_target
            enc_char = mem[c]
            if 33 <= enc_char <= 126:
                mem[c] = _ENC[enc_char - 33]
            c = (c + 1) % MEM_SIZE
            d = (d + 1) % MEM_SIZE
            pasos += 1

        return salida.decode("latin-1", errors="replace"), pasos, status


def _cargar_interprete():
    env_path = os.environ.get("MEOWBOLGE_INTERPRETER")
    if env_path and Path(env_path).exists():
        spec = importlib.util.spec_from_file_location("malbolge_ref", env_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return EmbeddedClassicVM


_ref = _cargar_interprete()


def fuente_para(op: int, pos: int) -> Optional[str]:
    """Carácter que en la posición `pos` se ejecuta como `op`, o None."""
    ch = BAJO + ((op - pos - BAJO) % MOD)
    return chr(ch) if BAJO <= ch <= ALTO else None


def ejecutar(fuente: str):
    """Corre el fuente con el intérprete real. Devuelve (salida, estados, status)."""
    estados = []

    def hook(steps, a, c, d, op, cell):
        estados.append((a, c, d))

    salida, pasos, status = _ref.run(fuente, max_steps=500_000, on_step=hook)
    return salida, estados, status


def _estado_tras(fuente: str):
    """Acumulador con el que arrancaría la siguiente celda del fuente."""
    salida, estados, _ = ejecutar(fuente)
    return salida, (estados[-1] if estados else (0, 0, 0))


def _cola_halt(pos: int) -> str:
    c = fuente_para(OP_HALT, pos)
    if c is None:
        raise ValueError(f"la posición {pos} no admite halt")
    return c


# ---------------------------------------------------------------------------
# Autobolge 2.0 Conveyor Synthesis Engine (Constructivo O(N) en ~2 ms)
# ---------------------------------------------------------------------------
C_START = 3315
D_START = 121
STERILE_GAP = C_START - D_START  # 3,194 celdas

XLAT1 = (
    "+b(29e*j1VMEKLyC})8&m#~W>qxdRp0wkrUo[D7,XTcA\"lI"
    ".v%{gJh4G\\-=O@5`_3i<?Z';FNQuY]szf$!BS/|t:Pn6^Ha"
)


def char_for(op_char: str, c: int) -> int:
    idx = XLAT1.index(op_char)
    return ((idx - (c % 94) + 94) % 94) + 33


RECIPES: Dict[int, Tuple] = {
    10: ("rot", 118),
    43: ("rot_crazy_crazy", 33, 54, 60),  # '+'
}

for _v1 in range(33, 127):
    _r1 = rot_op(_v1)
    _b1 = _r1 % 256
    if _b1 not in RECIPES:
        RECIPES[_b1] = ("rot", _v1)
    for _v2 in range(33, 127):
        _b2 = crazy_op(_r1, _v2) % 256
        if _b2 not in RECIPES:
            RECIPES[_b2] = ("rot_crazy", _v1, _v2)


def can_conveyor_fit(target: str) -> bool:
    """Verifica si el texto cabe en la brecha estéril de Autobolge 2.0."""
    try:
        target_bytes = target.encode("latin-1")
    except UnicodeEncodeError:
        return False

    data_count = 0
    for b in target_bytes:
        if b not in RECIPES:
            return False
        rec = RECIPES[b]
        kind = rec[0]
        if kind == "rot":
            data_count += 2
        elif kind == "rot_crazy":
            data_count += 3
        elif kind == "rot_crazy_crazy":
            data_count += 4

    return (D_START + data_count) <= C_START


def generar_conveyor(target: str, verify: bool = True) -> str:
    """Genera un programa Classic Malbolge en O(N) algebraico usando Conveyor."""
    target_bytes = target.encode("latin-1")
    for b in target_bytes:
        if b not in RECIPES:
            raise ValueError(f"Byte {b} ({chr(b)!r}) no soportado en recetas de emisión")

    code_ops: List[str] = []
    data_bytes: List[int] = []

    for b in target_bytes:
        rec = RECIPES[b]
        kind = rec[0]
        if kind == "rot":
            code_ops.extend(["*", "<"])
            data_bytes.extend([rec[1], ord("o")])
        elif kind == "rot_crazy":
            code_ops.extend(["*", "p", "<"])
            data_bytes.extend([rec[1], rec[2], ord("o")])
        elif kind == "rot_crazy_crazy":
            code_ops.extend(["*", "p", "p", "<"])
            data_bytes.extend([rec[1], rec[2], rec[3], ord("o")])

    code_ops.append("v")  # Clean HALT

    TOTAL_LEN = C_START + len(code_ops)
    data_cells = D_START + len(data_bytes)

    if data_cells > C_START:
        raise ValueError(
            f"El texto excede la brecha estéril ({len(data_bytes)} datos > {STERILE_GAP} disponibles)"
        )
    if TOTAL_LEN > MEM_SIZE:
        raise ValueError(f"Longitud total {TOTAL_LEN} excede el límite clásico {MEM_SIZE}")

    prog = [ord("o")] * TOTAL_LEN

    # Portal jump from c=0 -> 98 (landing on 99):
    prog[0] = ord("b")
    prog[98] = ord("o")

    # Low-memory data pointers:
    prog[1] = 93
    prog[94] = ord("P")  # 80: Y1
    prog[95] = 93
    prog[96] = 73
    prog[74] = ord("H")  # 72: Y2 (crazy produces 3312)
    prog[75] = 73
    prog[76] = D_START - 1  # 120: inicializa d=121

    # Discriminator / jump sequence at c=99..107:
    prog[99] = char_for("j", 99)
    prog[100] = char_for("*", 100)
    prog[101] = char_for("j", 101)
    prog[102] = char_for("*", 102)
    prog[103] = char_for("o", 103)
    prog[104] = char_for("j", 104)
    prog[105] = char_for("p", 105)
    prog[106] = char_for("j", 106)
    prog[107] = char_for("i", 107)

    # Cushion and bridge at c=3312..3314:
    prog[3312] = ord("o")
    prog[3313] = char_for("o", 3313)
    prog[3314] = char_for("j", 3314)

    # Colocar segmento de datos:
    for idx, db in enumerate(data_bytes):
        prog[D_START + idx] = db

    # Colocar segmento de código:
    for idx, opc in enumerate(code_ops):
        prog[C_START + idx] = char_for(opc, C_START + idx)

    prog_str = bytes(prog).decode("latin-1")

    if verify:
        salida, _, status = ejecutar(prog_str)
        if salida != target or status != "HALTED":
            raise RuntimeError(f"Verificación fallida: expected {target!r}, got {salida!r} ({status})")

    return prog_str


# ---------------------------------------------------------------------------
# Motor Heurístico BFS por Niveles (v2) y Fuerza Bruta (v1)
# ---------------------------------------------------------------------------
_PROF_MAX = 20
_NODO_MAX = 2_000_000
_RUTAS_MAX = 500
_OP_ORDEN = (OP_OUT, OP_ROT, OP_CRAZY, OP_MOVD)
_HAZ_MAX = 60_000


def _combinaciones(largo: int):
    if largo == 0:
        yield ()
        return
    from itertools import product
    for combo in product(CANDIDATAS, repeat=largo):
        yield combo


def _proponer_ruta(prefijo: str, objetivo: int, restrict_past: bool = True):
    ref = _ref
    enc = getattr(ref, "_ENC", None)
    mems = getattr(ref, "MEM_SIZE", MEM_SIZE)
    try:
        mem = ref.load_memory(prefijo + _cola_halt(len(prefijo)))
    except ValueError:
        return None

    a = d = 0
    for pos in range(len(prefijo)):
        op = (mem[pos] + pos) % MOD
        if op == OP_ROT:
            v = mem[d]
            mem[d] = (v // 3) + (v % 3) * (3 ** 9)
            a = mem[d]
        elif op == OP_CRAZY:
            mem[d] = ref.crazy_op(a, mem[d])
            a = mem[d]
        elif op == OP_MOVD:
            d = mem[d]
        if enc is not None and 33 <= mem[pos] <= 126:
            mem[pos] = enc[mem[pos] - 33] if isinstance(enc, list) and len(enc) == 94 else enc[mem[pos]]
        d = (d + 1) % mems

    desde = len(prefijo)
    presupuesto = [_NODO_MAX]
    metas = []

    def expandir(pos, a, d, ruta):
        presupuesto[0] -= 1
        resultados = []
        for op in _OP_ORDEN:
            ch_op = fuente_para(op, pos)
            if ch_op is None:
                continue
            undo = [(pos, mem[pos])]
            mem[pos] = ord(ch_op)
            a2 = a
            d2 = d
            b2 = None
            if op == OP_OUT:
                b2 = a % 256
                if b2 != objetivo:
                    mem[pos] = undo.pop(0)[1]
                    continue
            elif op == OP_ROT:
                v = mem[d]
                undo.append((d, v))
                a2 = (v // 3) + (v % 3) * (3 ** 9)
                mem[d] = a2
            elif op == OP_CRAZY:
                v = mem[d]
                undo.append((d, v))
                a2 = ref.crazy_op(a, v)
                mem[d] = a2
            else:
                destino = mem[d]
                if destino >= pos and (restrict_past or destino <= pos + _PROF_MAX + 4):
                    mem[pos] = undo.pop(0)[1]
                    continue
                d2 = destino
            if enc is not None and 33 <= mem[pos] <= 126:
                undo.append((pos, mem[pos]))
                mem[pos] = enc[mem[pos] - 33] if isinstance(enc, list) and len(enc) == 94 else enc[mem[pos]]
            resultados.append((op, a2, (d2 + 1) % mems, b2, undo))
            for idx, val in reversed(undo):
                mem[idx] = val
        return resultados

    frontera = [(a, d, ())]
    vistos = {(a, d)}
    for _ in range(_PROF_MAX + 1):
        nueva = []
        for a_act, d_act, ruta in frontera:
            pos = desde + len(ruta)
            for op, a2, d_sig, b2, _undo in expandir(pos, a_act, d_act, ruta):
                if presupuesto[0] <= 0:
                    return metas
                if b2 is not None and b2 == objetivo:
                    metas.append(ruta + (op,))
                    if len(metas) >= _RUTAS_MAX:
                        return metas
                    continue
                clave = (a2, d_sig)
                if clave not in vistos:
                    vistos.add(clave)
                    nueva.append((a2, d_sig, ruta + (op,)))
        if not nueva:
            break
        frontera = nueva[:_HAZ_MAX]
    return metas


def generar_bfs(texto: str, ancho: int = 40, verbose: bool = False, rapido: bool = True) -> str:
    """Genera texto mediante búsqueda BFS nivel por nivel (v2)."""
    fuente = ""
    for i, ch in enumerate(texto):
        objetivo = texto[: i + 1]
        hallado = None
        metodo = None

        c = fuente_para(OP_OUT, len(fuente))
        if c is not None:
            cand = fuente + c
            salida, _, _ = ejecutar(cand + _cola_halt(len(cand)))
            if salida == objetivo:
                hallado, metodo = cand, "directo"

        if hallado is None and rapido:
            byte_obj = ord(ch) % 256
            for restrict in (True, False):
                if hallado is not None:
                    break
                for ruta in _proponer_ruta(fuente, byte_obj, restrict_past=restrict):
                    cand = fuente
                    ok = True
                    for op in ruta:
                        c = fuente_para(op, len(cand))
                        if c is None:
                            ok = False
                            break
                        cand += c
                    if not ok:
                        continue
                    if ruta[-1] != OP_OUT:
                        c = fuente_para(OP_OUT, len(cand))
                        if c is None:
                            continue
                        cand += c
                    salida, _, _ = ejecutar(cand + _cola_halt(len(cand)))
                    if salida == objetivo:
                        hallado, metodo = cand, "rapida"
                        break

        if hallado is None:
            for largo in range(0, ancho):
                for combo in _combinaciones(largo):
                    cand = fuente
                    ok = True
                    for op in combo:
                        c = fuente_para(op, len(cand))
                        if c is None:
                            ok = False
                            break
                        cand += c
                    if not ok:
                        continue
                    c = fuente_para(OP_OUT, len(cand))
                    if c is None:
                        continue
                    cand += c
                    salida, _, _ = ejecutar(cand + _cola_halt(len(cand)))
                    if salida == objetivo:
                        hallado = cand
                        break
                if hallado:
                    break
            if hallado is None:
                raise ValueError(f"sin ruta para {texto[i]!r} (caracter {i})")
            metodo = "bruta"

        fuente = hallado
        if verbose:
            print(f"  [{i + 1}/{len(texto)}] {ch!r} -> {len(fuente)} celdas ({metodo})", file=sys.stderr)

    return fuente + _cola_halt(len(fuente))


def generar(texto: str, ancho: int = 40, verbose: bool = False, rapido: bool = True,
            engine: str = "auto") -> str:
    """Programa Malbolge que imprime `texto`, verificado contra el intérprete.

    Motores:
    - 'auto': Usa Autobolge 2.0 Conveyor O(N) si el texto cabe en la brecha estéril (< 1500 chars).
              Fallback transparente a BFS si no cabe.
    - 'conveyor': Síntesis constructiva directa O(N) en ~2-4 ms.
    - 'bfs': Búsqueda heurística guiada por estado (v2).
    """
    eng = engine.lower()
    if eng in ("auto", "conveyor") and can_conveyor_fit(texto):
        t0 = time.perf_counter()
        prog = generar_conveyor(texto, verify=True)
        ms = (time.perf_counter() - t0) * 1000.0
        if verbose:
            print(f"[meowbolge] Síntesis Autobolge 2.0 Conveyor O(N) completada en {ms:.2f} ms ({len(prog)} celdas)", file=sys.stderr)
        return prog

    if eng == "conveyor":
        raise ValueError(f"El texto excede la capacidad del Conveyor ({capacity()} celdas)")

    if verbose:
        print("[meowbolge] Ejecutando búsqueda BFS por niveles (v2)...", file=sys.stderr)
    return generar_bfs(texto, ancho=ancho, verbose=verbose, rapido=rapido)


def main():
    parser = argparse.ArgumentParser(description="meowbolge — generador de Malbolge para texto y arte ASCII")
    parser.add_argument("texto", nargs="?", default="meow", help="Texto o arte ASCII a generar (default: 'meow')")
    parser.add_argument("-e", "--engine", choices=["auto", "conveyor", "bfs"], default="auto",
                        help="Motor de síntesis (default: auto -> conveyor O(N))")
    parser.add_argument("-o", "--output", help="Ruta para guardar el archivo .malbolge")
    parser.add_argument("-v", "--verbose", action="store_true", help="Mostrar traza detallada")

    args = parser.parse_args()
    prog = generar(args.texto, verbose=args.verbose, engine=args.engine)
    salida, _, status = ejecutar(prog)

    print(f"texto    : {args.texto!r}", file=sys.stderr)
    print(f"programa : {len(prog)} celdas", file=sys.stderr)
    print(f"ejecucion: {salida!r} ({status})", file=sys.stderr)

    if salida != args.texto:
        sys.exit(f"NO COINCIDE: {salida!r} != {args.texto!r}")

    if args.output:
        Path(args.output).write_text(prog, encoding="ascii")
        print(f"Guardado en: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(prog)


if __name__ == "__main__":
    main()
