import requests, json, re
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

URL="https://contratacion.aena.es/contratacion/principal?portal=licitaciones"
HEAD={"User-Agent":"Mozilla/5.0 SALNES-ROT-Licitaciones/1.0"}
def clean(x): return re.sub(r"\s+"," ",x or "").strip()
def main():
    r=requests.get(URL,headers=HEAD,timeout=40); r.raise_for_status()
    s=BeautifulSoup(r.text,"html.parser"); items=[]
    tables=s.find_all("table")
    target=None
    for t in tables:
        txt=clean(t.get_text(" ",strip=True)).lower()
        if "ccmayor" in txt and "fecha límite" in txt and "título" in txt:
            target=t; break
    if not target: raise RuntimeError("No se encontró la tabla de licitaciones de AENA")
    for tr in target.find_all("tr"):
        cells=tr.find_all(["td","th"])
        if len(cells)<8 or tr.find("th"): continue
        vals=[clean(c.get_text(" ",strip=True)) for c in cells]
        links=tr.find_all("a",href=True)
        info=""
        for a in links:
            if "infoexp" in a["href"]: info=urljoin(URL,a["href"]); break
        # Columnas oficiales: publicación, expediente, título, destino, bruto, neto, valor estimado, límite, info
        if len(vals)>=8 and re.search(r"\d+/\d{4}",vals[1]):
            items.append({"published":vals[0],"id":vals[1],"title":vals[2],"place":vals[3],
                          "gross":vals[4],"amount":vals[5],"estimated":vals[6],"deadline":vals[7],
                          "url":info or URL,"source":"AENA"})
    out={"updated":datetime.now().astimezone().strftime("%d/%m/%Y %H:%M"),"source":URL,"items":items}
    with open("data.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print("AENA:",len(items),"licitaciones")
if __name__=="__main__": main()
