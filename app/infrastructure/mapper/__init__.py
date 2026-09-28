import importlib
import pkgutil
from pathlib import Path

from app.infrastructure.mapper.global_mapper import GlobalMapper

_package_name = __name__
_package_path = [str(Path(__file__).parent)]

for _module_info in pkgutil.walk_packages(
    path=_package_path, prefix=_package_name + "."
):
    if not _module_info.name.endswith(".global_mapper"):
        importlib.import_module(_module_info.name)

__all__ = ["GlobalMapper"]


# Cómo funciona:

# pkgutil.walk_packages recorre recursivamente todos los módulos dentro del
# paquete app.infrastructure.mapper
# Excluye mapper.py (que ya se importó directamente) para evitar reimportarlo
# Cada módulo encontrado se importa con importlib.import_module, lo que ejecuta
# el código a nivel de módulo, incluido el mapper.register(...)
# Ahora cuando agregues un nuevo archivo de mapper en cualquier subcarpeta
# (como response_to_domain/nuevo.py), simplemente pones el mapper.register(...)
# al final y se descubre automáticamente, sin tocar el __init__.py.
