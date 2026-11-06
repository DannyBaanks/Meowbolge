# meowbolge 🐈‍⬛

Generador de programas **Malbolge clasico** que imprimen texto arbitrario.
La verificacion siempre es contra un interprete real — nunca contra un modelo.

```
 /\_/\
( o.o )
 > ^ <
```
*(salida real de `examples/gatito.malbolge`, verificado en 3 backends)*

## La onda

Escribir Malbolge no es escribir instrucciones. El opcode sale de

    op = (mem[c] + c) % 94

asi que no lo decide la celda: lo decide la celda **y su posicion**.
En cada posicion el opcode requerido se fuerza resolviendo `mem[c] = (op - c) mod 94`.
Generar Malbolge es resolver una congruencia por paso.

El estado no se adivina a ciegas: cada candidato se acepta SOLO si el interprete
real emite exactamente lo que se pidio. Propuestas rapidas si, atajos no.

## Uso

```bash
# Síntesis instantánea con Autobolge 2.0 Conveyor O(N) en ~2 ms
python3 meowbolge.py "meow"

# Guardar en archivo
python3 meowbolge.py "meow" -o meow.malbolge

# Generar y verificar el gatito ASCII con consenso multi-oráculo
python3 examples/make_gatito.py

# Selección de motor explícito (--engine auto|conveyor|bfs)
python3 meowbolge.py "texto" --engine conveyor
python3 meowbolge.py "texto" --engine bfs
```

Variables de entorno (opcionales, ahora cuenta con VM canónica embebida autónoma):

| Variable | Default |
|---|---|
| `MEOWBOLGE_INTERPRETER` | VM clásica embebida en meowbolge.py (o ruta externa) |
| `MEOWBOLGE_ENGINE_C` | opcional: binario C/Zig para verificación extra |
| `MEOWBOLGE_ORACLE_DIR` | opcional: directorio de malbolge-oracle |

## Motores de Síntesis (Edición 2026)

1. **Autobolge 2.0 Conveyor Engine ($O(N)$)**:
   - Salto cuántico de alta memoria ($c=0 \to 3315, d=121$) sobre brecha estéril de 3.194 celdas.
   - Cero búsqueda combinatoria: sintetiza cualquier texto o arte ASCII en **2–5 ms** de forma 100% determinista.
2. **Camino rápido guiado por estado (BFS v2)**:
   - BFS nivel por nivel sobre `(a, d)` con dedup y haz acotado para programas ultra-densos.
3. **Fuerza bruta (v1)**:
   - Búsqueda exhaustiva combinatoria como fallback.

## El gatito

`examples/gatito.malbolge` (750 celdas, 652 pasos, HALT limpio) se genero como una
cadena: meowbolge-v2 resolvio los caracteres amigables; los dificiles (`/`) cayeron
fuera del rango estable del proponedor en CPython y el fallback uso
[Malbolge-Translator](https://github.com/DannyBaanks/Malbolge-Translator)
(semilla 42, 0.95 s, 35,756 evaluaciones). Triple verificacion sin discrepancias:
interprete canonico + oraculo independiente + motor C.
Evidencia completa con hashes: `evidence/gatito_evidence.json`.

Leccion honesta: la frontera entre "gui rapida" y "busqueda pesada" es territorio
Zig — el arsenal tiene `frontier_scan`, que evalua mil millones de programas
en horas; meowbolge-python se queda en las centenas de miles.

## Estado

- ✅ generador v2 con camino rapido + verificacion real obligatoria
- ✅ gatito ASCII verificado en 3 backends
- ⚠️ caracteres "dificiles" pueden requerir el fallback externo o mas potencia
- ❌ sin licencia aun; codigo de laboratorio
