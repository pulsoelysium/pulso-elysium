# Pulso Elysium

Analítica independiente de Elysium (L2 de Kinetiq sobre Hyperliquid, chain 99901).
Etapa 1: salud de la red y flujo de capital.

## Cómo actualizar los datos

Requiere Python 3.9 o superior, sin instalar nada más.

    python3 indexer.py          # lee la red y actualiza data.json (unos 5 minutos la primera vez, segundos después)
    python3 build_datasets.py   # genera las tablas del tablero en la carpeta out/

Cada ejecución agrega una foto nueva (saldo del bridge, gas, estado del rollup) y completa los días que falten.
Conviene ejecutarlo al menos una vez por día: el saldo de HYPE en el bridge solo se puede leer al momento,
así que su historial depende de estas fotos.

## Radar de lanzamientos

    python3 radar.py                       # actualiza docs/data/radar.json
    python3 radar.py --desde 2026-11-15    # solo la primera vez, sin estado previo: carga historial desde esa fecha

Sigue cada token nuevo de los pools de Uniswap v4 durante 8 días y calcula, por día de lanzamiento,
cuántos nunca se operaron, cuántos se apagaron en menos de 2 horas y cuántos seguían activos a las 24 horas.
Su estado (radar_estado.json.gz) no se guarda en main: la tarea horaria lo deja en la rama radar-estado,
que se reemplaza en cada corrida para no acumular historial. Si esa rama se pierde, el radar arranca de cero
y las cohortes diarias se reconstruyen solas a partir del día siguiente.

Los nombres de las plataformas (Montra, Eleos, Ascend) se identificaron en el explorador de Elysium;
están en el diccionario LABELS de radar.py.

## Alojamiento (GitHub, gratis)

El repositorio se actualiza y se publica solo:

- `.github/workflows/actualizar.yml` ejecuta el indexador cada hora y guarda los datos nuevos.
- La carpeta `docs/` es el sitio público (GitHub Pages).

Pasos una sola vez:

1. Crear un repositorio público en GitHub (por ejemplo `pulso-elysium`) y subir todo el contenido de esta carpeta.
2. En el repositorio: Settings > Pages > Source "Deploy from a branch", rama `main`, carpeta `/docs`.
3. En la pestaña Actions, habilitar los workflows y ejecutar "Actualizar datos" una vez a mano para probar.

Opcional: si el RPC público empieza a limitar, crear el secreto `ELYSIUM_RPC` (Settings > Secrets and variables > Actions)
con la dirección de un proveedor como Alchemy o Chainstack.

## Archivos

- indexer.py: lee el RPC de Elysium, el RPC de HyperEVM y la API de DefiLlama.
- build_datasets.py: arma las tablas en docs/data/ (diario, resumen, reparto, rollup y la serie horaria del bridge).
- build_pages.py: genera docs/index.html (inglés) y docs/es/index.html (español) desde una sola plantilla.
  Los textos de las dos versiones están en el diccionario S; después de cambiarlos, ejecutarlo de nuevo.
- data.json: base con las series diarias y las fotos horarias.
- docs/: sitio público (index.html, es/index.html, style.css, app.js, data/).

## Límites conocidos

- El RPC público limita lotes grandes y corta búsquedas de eventos en 10.000 resultados.
  Para la etapa 2 (radar de lanzamientos) hará falta una clave de proveedor.
- El calendario de desbloqueos de KNTQ está cargado a mano desde fuentes de terceros.
- Falta ubicar la dirección de recompras de KNTQ.
- GitHub puede demorar o saltear alguna ejecución horaria; es normal.
