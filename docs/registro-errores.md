# Registro de errores

| Fecha | Error | Causa | Prevención |
|---|---|---|---|
| 21/11/2026 | Fallo en CI por binario de WhiteboxTools inexistente (`RasterioIOError: breached.tif`) | La caché restauraba `whitebox/WBT/` pero no `whitebox/whitebox_tools` (el paquete copia el ejecutable fuera de WBT/). Con la carpeta presente no volvía a descargar, e `is_whitebox_available()` devolvía `True` porque solo miraba métodos del envoltorio. | `is_whitebox_available()` comprueba que el ejecutable exista físicamente y sea ejecutable; la caché en CI guarda `WBT/`, `whitebox_tools`, `img/` y `plugins/` (PR #6). |
| 21/11/2026 | Citas con revista y páginas incorrectas en spec 006 (tabla de mermas de rinde) | Datos tomados de memoria o de fuentes secundarias sin verificación directa en la publicación original. | DOI obligatorio + enlace verificable que abra el documento + frase textual corta por cada fila; toda fila sin documento original accesible se elimina directamente. |
