"""meowbolge -- generador de programas Malbolge que imprimen texto arbitrario.

Escribir Malbolge no es escribir instrucciones. El opcode sale de

    op = (mem[c] + c) % 94

asi que no lo decide la celda: lo deciden la celda Y su posicion. Como el
fuente lo escribimos nosotros, en cada posicion se fuerza el opcode que haga
falta resolviendo `mem[c] = (op - c) mod 94`. Generar Malbolge es resolver una
congruencia por paso.

LO QUE HACE QUE ESTO FUNCIONE
-----------------------------
No simular la maquina... o mejor dicho: proponer con un simulador, DECIDIR con
la maquina. El generador construye el programa paso a paso y cada candidato se
ACEPTA SOLO si el interprete real emite exactamente lo pedido. El estado no se
estima a ciegas y ninguna propuesta se confia sin verificacion.

Historia de la v2: la busqueda exhaustiva pura (v1) explota combinatoriamente
en caracteres que piden prefijos profundos. La via rapida anade un proponente
que simula EXACTAMENTE las reglas del interprete canonico (op=(contenido+pos)
%94, escrituras ROT/CRAZY sobre mem[d], cifrado post-ejecucion de la propia
celda, avance incondicional de d) y propone rutas cortas por DFS con podado;
el interprete real sigue siendo la unica puerta de aceptacion. Cuatro errores
clasicos que la simulacion espejo evita:

  1. no mover `d`: con el puntero quieto solo se alcanzan dos valores de `a`.
     Que hay que moverlo salio de medir el quine de Lutter, que hace movd
     6,631,123 veces en 69,547,437 pasos: 7.4x mas que rotaciones.
  2. suponer la memoria vacia: Malbolge rellena lo que el fuente no cubre con
     crazy(mem[i-1], mem[i-2]) encadenado.
  3. aplicar rot y crazy sobre `a`: operan sobre mem[d] y ESCRIBEN ahi; `a`
     solo recibe una copia. Por eso cada paso crea operandos nuevos.
  4. ignorar el cifrado post-ejecucion: el flujo pasa una vez por cada celda,
     pero `d` puede releerlas como dato y entonces ve el valor cifrado.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

BAJO, ALTO = 33, 126
MOD = 94

OP_OUT, OP_ROT, OP_MOVD, OP_CRAZY, OP_NOP, OP_HALT = 5, 39, 40, 62, 68, 81

#: Operaciones que el generador puede encadenar para mover el acumulador.
CANDIDATAS = (OP_ROT, OP_CRAZY, OP_MOVD)

#: Ruta del interprete canonico; sobreescrible con MEOWBOLGE_INTERPRETER.
_INTERPRETE = Path(
    os.environ.get(
        "MEOWBOLGE_INTERPRETER",
        r"C:\Development\ISyCo\workspace\assembly\malbolge"
        r"\malbolge_interpreter.py",
    )
)

#: Limites del proponente rapido.
_PROF_MAX = 20
_NODO_MAX = 2_000_000
_RUTAS_MAX = 500


def _cargar_interprete():
    spec = importlib.util.spec_from_file_location("malbolge_ref", _INTERPRETE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ref = _cargar_interprete()


def fuente_para(op: int, pos: int):
    """Caracter que en la posicion `pos` se ejecuta como `op`, o None."""
    ch = BAJO + ((op - pos - BAJO) % MOD)
    return chr(ch) if BAJO <= ch <= ALTO else None


def ejecutar(fuente: str):
    """Corre el fuente con el interprete real. Devuelve (salida, estados)."""
    estados = []

    def hook(steps, a, c, d, op, cell):
        estados.append((a, c, d))

    salida, pasos, status = _ref.run(fuente, max_steps=200000, on_step=hook)
    return salida, estados, status


def _estado_tras(fuente: str):
    """Acumulador con el que arrancaria la siguiente celda del fuente."""
    salida, estados, _ = ejecutar(fuente)
    return salida, (estados[-1] if estados else (0, 0, 0))


def _cola_halt(pos: int) -> str:
    c = fuente_para(OP_HALT, pos)
    if c is None:
        raise ValueError(f"la posicion {pos} no admite halt")
    return c


def _combinaciones(largo: int):
    """Todas las rutas de `largo` operaciones candidatas, en orden estable."""
    if largo == 0:
        yield ()
        return
    from itertools import product
    for combo in product(CANDIDATAS, repeat=largo):
        yield combo


# ---------------------------------------------------------------------------
# Via rapida: traza guiada toroidal. Un BFS por niveles sobre el estado
# (a, d) -- ambos avanzan ciclicamente como en la maquina -- con dedup y haz
# acotado. Devuelve la ruta MAS CORTA que existe dentro del alcance. Solo
# propone: la unica puerta de aceptacion sigue siendo el interprete real.
# ---------------------------------------------------------------------------

_OP_ORDEN = (OP_OUT, OP_ROT, OP_CRAZY, OP_MOVD)

_HAZ_MAX = 60_000


def _proponer_ruta(prefijo: str, objetivo: int, restrict_past: bool = True):
    """Rutas de ops cuyo OUT emitiria `objetivo`, segun simulacion espejo,
    ordenadas por longitud (BFS toroidal con dedup y haz acotado).

    Devuelve LISTA de rutas candidatas (posiblemente muchas): las que leen
    zonas inestables fallaran la verificacion real y la siguiente entra.
    Con restrict_past=True (Tier A) MOVD solo toca celdas pasadas (exacto);
    con False (Tier B) se permiten saltos lejanos salvo la ventana fuente
    cercana."""
    ref = _ref
    enc = getattr(ref, "_ENC", None)
    mems = ref.MEM_SIZE
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
            mem[pos] = enc[mem[pos]]
        d = (d + 1) % mems

    desde = len(prefijo)
    presupuesto = [_NODO_MAX]
    metas = []

    def expandir(pos, a, d, ruta):
        """Aplica un op en pos con undo; devuelve (a2, d2, byte|None) o None."""
        ch = None
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
                    # un OUT intermedio emitiria un byte basura: prohibido
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
                if destino >= pos and (restrict_past or
                                       destino <= pos + _PROF_MAX + 4):
                    mem[pos] = undo.pop(0)[1]
                    continue
                d2 = destino
            if enc is not None and 33 <= mem[pos] <= 126:
                undo.append((pos, mem[pos]))
                mem[pos] = enc[mem[pos]]
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


def generar(texto: str, ancho: int = 40, verbose: bool = False,
            rapido: bool = True) -> str:
    """Programa Malbolge que imprime `texto`, verificado contra el interprete.

    Por caracter: intento directo (OUT si `a` ya vale), luego ruta propuesta
    por el simulador espejo, luego busqueda exhaustiva como respaldo. Todo
    candidato pasa por ejecucion real antes de aceptarse.
    """
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
                for ruta in _proponer_ruta(fuente, byte_obj,
                                           restrict_past=restrict):
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
            print(f"  [{i + 1}/{len(texto)}] {ch!r} -> {len(fuente)} celdas "
                  f"({metodo})", file=sys.stderr)

    return fuente + _cola_halt(len(fuente))


if __name__ == "__main__":
    texto = sys.argv[1] if len(sys.argv) > 1 else "meow"
    prog = generar(texto, verbose=True)
    salida, _, status = ejecutar(prog)
    print(f"texto    : {texto!r}", file=sys.stderr)
    print(f"programa : {len(prog)} celdas", file=sys.stderr)
    print(f"ejecucion: {salida!r} ({status})", file=sys.stderr)
    if salida != texto:
        sys.exit(f"NO COINCIDE: {salida!r} != {texto!r}")
    sys.stdout.write(prog)
