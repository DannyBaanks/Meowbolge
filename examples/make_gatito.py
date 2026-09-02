"""Genera el gatito ASCII como un programa Malbolge real y lo verifica.

Salidas:
  examples/gatito.malbolge     -- el programa
  examples/gatito_salida.txt   -- lo que la maquina emite
  evidence/gatito_evidence.json-- hashes + verificacion multi-backend

Uso:
  py examples/make_gatito.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from meowbolge import ejecutar, generar

GATITO = " /\\_/\\\n( o.o )\n > ^ <"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def verificar_engine_c(prog_path: Path, max_steps: int):
    exe = os.environ.get("MEOWBOLGE_ENGINE_C")
    if not exe or not Path(exe).exists():
        return {"backend": "engine_c", "status": "SKIPPED",
                "note": "define MEOWBOLGE_ENGINE_C para incluir este backend"}
    proc = subprocess.run([exe, str(prog_path), str(max_steps)],
                          input=b"", capture_output=True, timeout=60)
    out = proc.stdout
    stripped = out[:-2] if out.endswith(b"\r\n") else out
    return {"backend": "engine_c", "output_hex": stripped.hex(),
            "note": "wrapper CRLF del host removido si estaba presente"}


def verificar_oracle(src: str):
    arsenal = os.environ.get("MEOWBOLGE_ORACLE_DIR")
    if not arsenal or not Path(arsenal).exists():
        return {"backend": "oracle_py", "status": "SKIPPED",
                "note": "define MEOWBOLGE_ORACLE_DIR para incluir este backend"}
    sys.path.insert(0, arsenal)
    from oracle import Oracle
    om = Oracle()
    om.load_ascii(src)
    om.provide_input("")
    r = om.run(max_steps=200000)
    out = getattr(r, "output", "") or ""
    return {"backend": "oracle_py", "steps": getattr(r, "steps", -1),
            "halt_reason": str(getattr(r, "halt_reason", "")),
            "output_hex": out.encode("latin-1").hex()}


def main() -> int:
    print(f"objetivo ({len(GATITO)} chars):\n{GATITO}\n", file=sys.stderr)
    prog = generar(GATITO, verbose=True)

    salida_pyref, pasos, status = ejecutar(prog)
    assert salida_pyref == GATITO and status == "HALTED", \
        f"pyref divergente: {salida_pyref!r} {status}"

    ejemplos = RAIZ / "examples"
    evidencia = RAIZ / "evidence"
    ejemplos.mkdir(exist_ok=True)
    evidencia.mkdir(exist_ok=True)
    prog_path = ejemplos / "gatito.malbolge"
    prog_path.write_text(prog, encoding="ascii", newline="")
    (ejemplos / "gatito_salida.txt").write_text(salida_pyref,
                                                encoding="ascii", newline="")

    checks = [
        {"backend": "pyref_canonico", "steps": pasos, "status": status,
         "output_hex": salida_pyref.encode("ascii").hex()},
        verificar_engine_c(prog_path, 200000),
        verificar_oracle(prog),
    ]
    hexes = {c.get("output_hex") for c in checks if c.get("output_hex")}
    objetivo_hex = GATITO.encode("ascii").hex()
    consenso = hexes == {objetivo_hex}

    ev = {
        "schema_version": 1,
        "experiment": "meowbolge gatito",
        "target_ascii": GATITO,
        "target_sha256": sha(GATITO.encode("ascii")),
        "program_cells": len(prog),
        "program_sha256": sha(prog.encode("ascii")),
        "pyref_steps": pasos,
        "backends": checks,
        "consenso_multi_backend": consenso,
    }
    (evidencia / "gatito_evidence.json").write_text(
        json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"programa : {len(prog)} celdas -> {prog_path}", file=sys.stderr)
    print(f"consenso : {consenso} ({[c['backend'] for c in checks]})",
          file=sys.stderr)
    print(GATITO)
    return 0 if consenso else 1


if __name__ == "__main__":
    sys.exit(main())
