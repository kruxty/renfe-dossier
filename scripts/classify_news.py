import json
data=json.load(open("data/news.json"))
for n in data:n.update({"color":"verde","prioridad":50,"resumen":"Resumen IA pendiente integración Gemini"})
json.dump(data,open("data/classified.json","w"),ensure_ascii=False,indent=2)