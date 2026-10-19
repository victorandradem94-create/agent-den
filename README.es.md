# agent-den 🐻

**Cómo opero un equipo de 4 agentes de IA en producción con presupuesto cero — y lo que aprendí.**

[English](README.md)

Cuatro agentes de Slack (Python, Slack Bolt, Socket Mode, Grok vía la API de
xAI) corren 24/7 en una VM ARM64 Always Free de Oracle Cloud, como servicios
`systemd --user`. Sin Docker, sin Kubernetes, sin monitoreo de pago.

No es "una herramienta que todos necesitan". Es la documentación de un caso
real y dos piezas pequeñas de código: un **generador seguro de unidades
systemd** y un **Guardian de rotación de tokens que falla cerrado**. Nació como
*Osito Cloud Migrator*; `agentden` es el nombre genérico.

## El recorrido

Terminal en macOS → LaunchAgents de **launchd** (`KeepAlive`) más un
supervisor de tokens, *Slack Token Guardian* (`StartInterval`) → Ubuntu en la
nube con **servicios systemd de usuario**, `loginctl enable-linger` y un timer
`OnCalendar`. Detalles en el [caso de estudio](docs/case-study.md).

| macOS (launchd) | Ubuntu (systemd) |
| --- | --- |
| `KeepAlive` in a LaunchAgent plist | `Restart=on-failure` |
| `StartInterval` (Guardian) | `.timer` con `OnCalendar=*:0/5` |
| `~/Library/LaunchAgents/` | `~/.config/systemd/user/` |
| `launchctl` | `systemctl --user` |
| corre mientras la sesión del usuario está abierta | `loginctl enable-linger` |

Quedó un residuo: un comentario/bucle "wait for launchd" sobrevivió a la
migración; la v0.2 lo elimina.

## Estado / qué está verificado

| Afirmación | Estado |
| --- | --- |
| Los 4 agentes responden en Slack desde la VM | ✅ observado 2026-10-19 |
| Los servicios sobreviven al cerrar SSH (linger) | ✅ observado |
| El timer de Guardian corre cada 5 min (`OnCalendar`) | ✅ observado |
| Guardian con operaciones reales responde `WAIT` si no toca renovar | ✅ observado (Guardian original) |
| Primera rotación OAuth **real** en producción | ⏳ **aún no observada** |
| Recuperación completa tras **reiniciar la VM** | ⏳ **aún no probada** |
| Guardian v0.2 (este repo) en producción | ⏳ no desplegado; probado con fakes |
| Plugin de Slack contra la API real | ⏳ solo pruebas con fakes |

## Prueba rápida (sin red ni servidores)

```bash
python3 -m unittest discover -s tests -t . -v
PYTHONPATH=src python3 -m agentden validate sample-config.json
PYTHONPATH=src python3 -m agentden generate sample-config.json --output ./generated
```

El generador solo escribe en `--output`; no ejecuta SSH ni `systemctl` y
rechaza generar un Guardian con operaciones reales.

## Guardian en un párrafo

Algunos tokens de Slack rotan y el refresh token puede ser de un solo uso.
Por eso Guardian guarda `uncertain` **antes** de pedir un token nuevo; si algo
queda dudoso, se queda en `uncertain` y sale con código 4: nunca reintenta
solo. Con un recibo válido reinicia el agente **una vez** y vuelve a `ok`
solo cuando el proceso *nuevo* escribe un heartbeat conectado. Por defecto es
simulación (dry run).

## Documentación

La documentación detallada está en inglés en [docs/](docs/): arquitectura,
caso de estudio, lecciones, seguridad, migración, rollback y costos.

## Límites honestos

Una sola VM es un punto único de falla. "Always Free" es una oferta de Oracle,
no una promesa mía. El uso de xAI cuesta dinero. Un heartbeat prueba una
conexión viva, no una respuesta correcta.

## Autor

Víctor Andrade ([@Victorandrade94](https://github.com/Victorandrade94)), México. Licencia MIT.
