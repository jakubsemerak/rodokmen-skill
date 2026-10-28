#!/usr/bin/env python3
"""Kramerius NKP full-text search (API v5). Usage: kramerius.py 'SOLR_QUERY' [rows]
e.g. kramerius.py 'text_ocr:"Jan Novák" AND datum_begin:[1860 TO 1920]'
     kramerius.py text <PID> [out.txt]   -> full OCR text of one page (only "public" pages)"""
import sys,json,urllib.error,urllib.request,urllib.parse
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
if sys.argv[1]=='text':
    u='https://kramerius5.nkp.cz/search/api/v5.0/item/'+urllib.parse.quote(sys.argv[2],safe=':')+'/streams/TEXT_OCR'
    try: txt=urllib.request.urlopen(u,timeout=90).read().decode('utf-8-sig')
    except urllib.error.HTTPError as e: sys.exit(f'{sys.argv[2]}: HTTP {e.code} (stránka není veřejná nebo nemá OCR)')
    if len(sys.argv)>3: open(sys.argv[3],'w',encoding='utf-8',newline='\n').write(txt); print(sys.argv[3],len(txt),'znaků')
    else: print(txt)
    sys.exit(0)
q=sys.argv[1]; rows=sys.argv[2] if len(sys.argv)>2 else '30'
p={'q':q+' AND fedora.model:page','fl':'PID,root_title,root_pid,datum_str,details,dostupnost','rows':rows,'wt':'json','hl':'true','hl.fl':'text_ocr','hl.fragsize':'250'}
u='https://kramerius5.nkp.cz/search/api/v5.0/search?'+urllib.parse.urlencode(p)
d=json.load(urllib.request.urlopen(u,timeout=90))
print('found',d['response']['numFound'])
hl=d.get('highlighting',{})
for x in d['response']['docs']:
    h=' | '.join(hl.get(x['PID'],{}).get('text_ocr',[]))[:400].replace('\n',' ')
    print('-',x.get('datum_str'),'|',str(x.get('root_title'))[:60],'|',x.get('details'),'|',x['PID'],'|',x.get('dostupnost'))
    if h: print('   ',h)
