"""Read-only hash of the owner's real Daggerfall Unity registry key, to prove test launches left it alone."""
import hashlib
import winreg

KEY = r"Software\Daggerfall Workshop\Daggerfall Unity"

with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ) as key:
    count = winreg.QueryInfoKey(key)[1]
    values = sorted((winreg.EnumValue(key, i) for i in range(count)), key=lambda v: v[0])
print(count, "values", hashlib.sha256(repr(values).encode()).hexdigest())
