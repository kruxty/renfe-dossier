from datetime import datetime
from pathlib import Path
html=f"<html><body><h1>Dossier Presidencia</h1><p>Generado {datetime.now()}</p><p>Informe generado automáticamente mediante IA.</p></body></html>"
Path('reports/latest.html').write_text(html,encoding='utf-8')
print('OK')