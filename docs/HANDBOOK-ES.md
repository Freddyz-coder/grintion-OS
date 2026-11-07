# Manual de Usuario de Grintion-OS (Guía Rápida)

Bienvenido al manual oficial en español de **Grintion-OS**, una distribución Linux independiente, segura y de alto rendimiento sin systemd.

## 1. Filosofía Central

- **Supervisión Ligera**: Grintion-OS utiliza `runit` para la supervisión de procesos y arranque determinista.
- **Transacciones Atómicas**: El gestor de paquetes `garb` mantiene generaciones de paquetes con capacidad de reversión instantánea.
- **Seguridad en Profundidad**: Perfiles de seguridad (`workstation`, `server`, `kiosk`, `air-gapped`), perfiles AppArmor integrados y aislamiento mediante `grintion-sandbox`.

## 2. Instalación Rápida

Instalación desatendida básica:
```bash
grintion-install --disk /dev/nvme0n1 --user grintion --desktop xfce --security-profile workstation
```

Instalación con cifrado completo LUKS2:
```bash
grintion-install --disk /dev/nvme0n1 --encrypt --user grintion
```

Asistente interactivo:
```bash
grintion-install --tui
```

## 3. Comandos Esenciales

| Tarea | Comando |
| :--- | :--- |
| **Instalar software** | `garb install <paquete>` |
| **Reversión de versión** | `garb rollback-generation <ID>` |
| **Estado de servicios** | `sv status /var/service/*` |
| **Configuración unificada**| `grintion-config` |
| **Escaneo de redes Wi-Fi**| `grintion-network scan` |
| **Reporte de seguridad** | `grintion-security-report` |
| **Aislamiento de apps** | `grintion-sandbox --no-net <comando>` |
| **Reparación del sistema**| `grintion-doctor --fix` |
| **Ayuda y códigos de error**| `grintion-help <CODIGO>` |

