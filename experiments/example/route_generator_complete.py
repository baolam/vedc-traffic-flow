from pathlib import Path
import argparse, random, xml.etree.ElementTree as ET
from collections import defaultdict
from heapq import heappush, heappop

VCLS={"car":"passenger","taxi":"passenger","motorcycle":"motorcycle","bus":"bus","truck":"truck"}
WEIGHTS={"motorcycle":65,"car":25,"taxi":4,"bus":3,"truck":3}

def toks(x): return set((x or "").replace(","," ").split())
def allowed(a,v):
    al,di=toks(a.get("allow")),toks(a.get("disallow"))
    return (not al or v in al) and v not in di

def load(fn,vclass):
    root=ET.parse(fn).getroot(); E={}; T=defaultdict(list); usable=set()
    for e in root.findall("edge"):
        eid,fr,to=e.get("id"),e.get("from"),e.get("to")
        if not eid or eid.startswith(":") or not fr or not to: continue
        ls=[l for l in e.findall("lane") if allowed(l,vclass)]
        if not ls: continue
        b=min(ls,key=lambda l:float(l.get("length","1"))/max(float(l.get("speed","13.9")),0.1))
        E[eid]={"from":fr,"to":to,"length":float(b.get("length","1")),"speed":float(b.get("speed","13.9")),"lanes":{l.get("index") for l in ls}}
        usable.add(eid)
    for c in root.findall("connection"):
        a,b=c.get("from"),c.get("to")
        if a not in usable or b not in usable or not allowed(c,vclass): continue
        fl=c.get("fromLane")
        if fl is not None and fl not in E[a]["lanes"]: continue
        T[a].append(b)
    if not T:
        for a,ea in E.items(): T[a]=[b for b,eb in E.items() if ea["to"]==eb["from"]]
    for a in list(T): T[a]=list(dict.fromkeys(x for x in T[a] if x in E))
    return E,T

def sp(s,g,E,T,banned=()):
    banned=set(banned); q=[(0,s)]; d={s:0}; p={}
    while q:
        c,u=heappop(q)
        if c!=d.get(u): continue
        if u==g: break
        for v in T.get(u,()):
            if v in banned: continue
            w=E[v]["length"]/max(E[v]["speed"],.1); nc=c+w
            if nc<d.get(v,float("inf")): d[v]=nc;p[v]=u;heappush(q,(nc,v))
    if g not in d:return None
    r=[];u=g
    while u!=s:r.append(u);u=p[u]
    r.append(s);return r[::-1]

def valid(r,E,T): return bool(r) and all(b in T.get(a,()) for a,b in zip(r,r[1:]))
def rlen(r,E): return sum(E[x]["length"] for x in r)

def backups(s,g,base,E,T,rng,n,maxdetour):
    out=[];seen={tuple(base)};L=rlen(base,E)
    if len(base)<3:return out
    for _ in range(max(20,n*20)):
        ids=list(range(1,len(base)-1));rng.shuffle(ids)
        ban={base[i] for i in ids[:max(1,min(3,len(ids)))]}
        r=sp(s,g,E,T,ban)
        if not r or tuple(r) in seen or not valid(r,E,T):continue
        if rlen(r,E)>L*maxdetour:continue
        if len(set(r)&set(base))/max(1,len(set(base)))>.90:continue
        seen.add(tuple(r));out.append(r)
        if len(out)>=n:break
    return out

def corridors(E,T,minedges,maxedges,limit):
    inc=defaultdict(list)
    for a,bs in T.items():
        for b in bs:inc[b].append(a)
    starts=[e for e in E if len(inc[e])!=1 or len(T.get(e,()))!=1] or list(E)
    cand=[]
    for s in starts:
        r=[s];used={s};u=s
        while len(r)<maxedges:
            ns=[x for x in T.get(u,()) if x not in used]
            if not ns:break
            ns.sort(key=lambda x:(len(T.get(x,())), -E[x]["length"]))
            u=ns[0];r.append(u);used.add(u)
            if len(r)>=minedges and len(T.get(u,()))>2:break
        if len(r)>=minedges:
            L=rlen(r,E); penalty=sum(max(0,len(T.get(x,()))-1) for x in r)
            cand.append((L-40*penalty,L,r))
    cand.sort(reverse=True,key=lambda x:(x[0],x[1]));sel=[]
    for x in cand:
        rs=set(x[2])
        if any(len(rs&set(y[2]))/max(1,min(len(rs),len(y[2])))>.80 for y in sel):continue
        sel.append(x)
        if len(sel)>=limit:break
    return sel

def typ(rng):
    p=[]
    for k,w in WEIGHTS.items():p += [k]*w
    return rng.choice(p)

def normal(E,T,rng,a):
    U=list(E)
    for _ in range(a.max_od_attempts):
        s,g=rng.choice(U),rng.choice(U)
        if s==g:continue
        base=sp(s,g,E,T)
        if not base or rlen(base,E)<a.min_distance:continue
        bs=backups(s,g,base,E,T,rng,a.alternatives,a.max_detour)
        return {"route":rng.choice(bs) if bs and rng.random()<a.alt_prob else base,"departPos":None,"arrivalPos":None,"kind":"normal","backups":len(bs)}
    return None

def random_end(E,T,rng,a):
    U=list(E)
    for _ in range(a.max_od_attempts):
        s,g=rng.choice(U),rng.choice(U)
        if s==g:continue
        r=sp(s,g,E,T)
        if not r:continue
        return {"route":r,"departPos":rng.uniform(0,E[r[0]]["length"]*.75),"arrivalPos":rng.uniform(E[r[-1]]["length"]*.2,E[r[-1]]["length"]*.9),"kind":"random-end","backups":0}
    return None

def irregular(E,T,rng,a):
    U=list(E)
    for _ in range(a.max_od_attempts):
        r=[rng.choice(U)]
        while len(r)<a.irregular_max_edges:
            ns=[x for x in T.get(r[-1],()) if x!=r[-1]]
            if not ns:break
            r.append(rng.choice(ns))
            if len(r)>=a.irregular_min_edges and rng.random()<.22:break
        if len(r)>=a.irregular_min_edges and valid(r,E,T):
            return {"route":r,"departPos":rng.uniform(0,E[r[0]]["length"]*.7),"arrivalPos":rng.uniform(E[r[-1]]["length"]*.2,E[r[-1]]["length"]*.9),"kind":"irregular","backups":0}
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("-n","--net-file",required=True);ap.add_argument("-o","--output",required=True)
    ap.add_argument("-v","--vehicles",type=int,default=3000);ap.add_argument("--end",type=float,default=3600);ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--fixed-percent",type=float,default=15);ap.add_argument("--random-end-percent",type=float,default=15);ap.add_argument("--irregular-percent",type=float,default=10)
    ap.add_argument("--fixed-corridors",type=int,default=2);ap.add_argument("--fixed-min-edges",type=int,default=6);ap.add_argument("--fixed-max-edges",type=int,default=30)
    ap.add_argument("--min-distance",type=float,default=300);ap.add_argument("--alternatives",type=int,default=3);ap.add_argument("--max-detour",type=float,default=1.6);ap.add_argument("--alt-prob",type=float,default=.75)
    ap.add_argument("--irregular-min-edges",type=int,default=4);ap.add_argument("--irregular-max-edges",type=int,default=20);ap.add_argument("--max-od-attempts",type=int,default=5000)
    a=ap.parse_args()
    if a.fixed_percent+a.random_end_percent+a.irregular_percent>100: raise ValueError("special percentages > 100")
    rng=random.Random(a.seed); graphs={}; reps={}
    for vt,vc in VCLS.items():
        E,T=load(a.net_file,vc);graphs[vt]=(E,T);reps[vt]=corridors(E,T,a.fixed_min_edges,a.fixed_max_edges,max(4,a.fixed_corridors*3))
        print(f"[{vt}] edges={len(E)} corridors={len(reps[vt])}")
    repfile=str(Path(a.output).with_name("fixed_corridors.txt"))
    with open(repfile,"w",encoding="utf-8") as f:
        for vt,cs in reps.items():
            f.write(f"\n[{vt}]\n")
            for i,(_,L,r) in enumerate(cs):f.write(f"corridor {i}: {L:.1f} m | {' '.join(r)}\n")
    fc=round(a.vehicles*a.fixed_percent/100);rc=round(a.vehicles*a.random_end_percent/100);ic=round(a.vehicles*a.irregular_percent/100);nc=a.vehicles-fc-rc-ic
    vehicles=[];bt=0
    def add(item,vt):
        if item:
            item["type"]=vt;item["depart"]=rng.uniform(0,max(0,a.end-1));vehicles.append(item)
    for i in range(fc):
        vt=typ(rng);E,T=graphs[vt];cs=reps[vt]
        if cs:
            r=cs[i%min(a.fixed_corridors,len(cs))][2]
            if valid(r,E,T):add({"route":r[:],"departPos":None,"arrivalPos":None,"kind":"fixed","backups":0},vt)
    for _ in range(nc):
        vt=typ(rng);E,T=graphs[vt];x=normal(E,T,rng,a)
        if x:bt+=x["backups"];add(x,vt)
    for _ in range(rc):
        vt=typ(rng);E,T=graphs[vt];add(random_end(E,T,rng,a),vt)
    for _ in range(ic):
        vt=typ(rng);E,T=graphs[vt];add(irregular(E,T,rng,a),vt)
    root=ET.Element("routes")
    for i,x in enumerate(sorted(vehicles,key=lambda z:z["depart"])):
        at={"id":str(i),"type":x["type"],"depart":f'{x["depart"]:.1f}',"departLane":"best","departSpeed":"max"}
        if x["departPos"] is not None:at["departPos"]=f'{x["departPos"]:.2f}'
        if x["arrivalPos"] is not None:at["arrivalPos"]=f'{x["arrivalPos"]:.2f}'
        v=ET.SubElement(root,"vehicle",at);ET.SubElement(v,"route",{"edges":" ".join(x["route"])})
    tree=ET.ElementTree(root);ET.indent(tree,space="  ");tree.write(a.output,encoding="utf-8",xml_declaration=True)
    print(f"Generated={len(vehicles)} fixed={fc} normal={nc} random-end={rc} irregular={ic} backups={bt}")
    print("Routes:",a.output);print("Corridors:",repfile)

if __name__=="__main__": main()
