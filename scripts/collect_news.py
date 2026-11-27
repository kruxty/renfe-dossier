import json
news=[{"titulo":"Ejemplo Renfe","medio":"Europa Press","texto":"Contenido"}]
json.dump(news,open("data/news.json","w"),ensure_ascii=False)