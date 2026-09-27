## Tarea T01 — Enum `JobStatus` y modelos ORM tipados (proyecto 04)
Estado: BLOQUEADA (Error en comando de verificación 2 y falso positivo)
Archivos modificados: 
- `04-data-cleaning-api/app/core/database.py`
- `04-data-cleaning-api/app/models/db.py`
- `04-data-cleaning-api/tests/test_models.py` (nuevo)

Desviaciones del código EXACTO: ninguna

Verificación:
```powershell
.venv\Scripts\ruff.exe check app tests
.venv\Scripts\ruff.exe format --check app tests
.venv\Scripts\mypy.exe app
.venv\Scripts\python.exe -m pytest --timeout=60 --cov -p no:cacheprovider
```
<salida real, recortada a lo relevante>
```text
All checks passed!
31 files already formatted
Success: no issues found in 25 source files
...
======================== 29 passed, 1 warning in 4.12s ========================
```
Tests: 29 passed (esperado: 29) · Cobertura: 64%

```powershell
Select-String -Path app -Recurse -Pattern "declarative_base|Column\("
```
<salida real, recortada a lo relevante>
```text
Select-String : A parameter cannot be found that matches parameter name 'Recurse'.
At line:5 char:25
+ Select-String -Path app -Recurse -Pattern "declarative_base|Column\("
+                         ~~~~~~~~
    + CategoryInfo          : InvalidArgument: (:) [Select-String], ParameterBindingException
    + FullyQualifiedErrorId : NamedParameterNotFound,Microsoft.PowerShell.Commands.SelectStringCommand
```

Dudas o contradicciones encontradas: 
- **Comando inválido:** `Select-String` en PowerShell 5.1 no tiene el flag `-Recurse`. 
- **Falso positivo:** Al ejecutar con `Get-ChildItem -Recurse ... | Select-String -Pattern "declarative_base|Column\("` el test no pasa porque coincide con `pa.Column(` de Pandera en `app\api\routes\validate.py` (línea 20). La instrucción exige no editar el texto para hacer que un test pase ("Never edit text just to make a verification pass") e indica reportar contradicciones.
- **Auto-detención:** De acuerdo a las instrucciones de la meta (`/goal`), dado que esta verificación falla dos veces, guardo este error y detengo la ejecución en la tarea T01.
