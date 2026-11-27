import json,pathlib
items=json.load(open("data/classified.json"))
sources=open("data/sources.txt").read().splitlines()
body=''.join([f"<div><h3>{i['titulo']}</h3><p>{i['medio']}</p><p>{i['color']}</p></div>" for i in items])
html=f"""<html><head><meta charset='utf-8'><title>Dossier Presidencia</title></head><body><h1>RENFE - DOSSIER EJECUTIVO</h1><p>🔴 🟡 🟢 Clasificación semáforo</p>{body}<h2>Disclaimer</h2><p>Informe generado automáticamente mediante Inteligencia Artificial.</p><h2>Medios monitorizados</h2><ul>{''.join(f'<li>{s}</li>' for s in sources)}</ul></body></html>"""
pathlib.Path('output/dossier.html').write_text(html,encoding='utf-8')