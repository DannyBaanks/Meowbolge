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

```powershell
py meowbolge.py "meow"            # imprime el programa en stdout
py examples/make_gatito.py        # regenera/verifica textos multi-linea
```

Variables de entorno:

| Variable | Default |
|---|---|
| `MEOWBOLGE_INTERPRETER` | interprete canonico del repo (ruta absoluta) |
| `MEOWBOLGE_ENGINE_C` | opcional: malbolge.exe para verificacion extra |
| `MEOWBOLGE_ORACLE_DIR` | opcional: directorio de malbolge-oracle |

## Como funciona (v2)

Para cada caracter, en orden:

1. **Directo** — si `a` ya tiene el valor, un solo OUT.
2. **Camino rapido (busqueda guiada por estado)** — BFS nivel por nivel sobre el estado
   `(a, d)` con dedup y un beam acotado, simulando las reglas de la maquina EXACTAMENTE
   (cifrado post-ejecucion, avance incondicional de `d`, escrituras ROT/CRAZY
   sobre `mem[d]`). Regresa MUCHAS rutas candidatas ordenadas por longitud; la
   verificacion real decide cual sobrevive.
   - Nivel A: solo MOVD hacia celdas pasadas conocidas (simulacion exacta).
   - Nivel B: se permiten saltos lejanos excepto la ventana cercana del fuente
     (aproximado; el verificador descarta divergencias).
3. **Fuerza bruta** — enumeracion exhaustiva como fallback (el v1 original).

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
