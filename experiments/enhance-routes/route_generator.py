import argparse, random, xml.etree.ElementTree as ET
from collections import defaultdict
from heapq import heappush, heappop

def load_net(path):
    root = ET.parse(path).getroot()
    nodes = {j.get("id") for j in root.findall("junction") if j.get("id")}
    edges, out = {}, defaultdict(list)
    for e in root.findall("edge"):
        eid, a, b = e.get("id"), e.get("from"), e.get("to")
        if not eid or eid.startswith(":") or not a or not b: continue
        lanes = e.findall("lane")
        if not lanes: continue
        L = float(lanes[0].get("length", "1"))
        V = float(lanes[0].get("speed", "13.9"))
        edges[eid] = (a,b,L,V)
        out[a].append(eid)
    return nodes, edges, out

def dijkstra(start, goal, edges, out, banned=()):
    banned=set(banned); pq=[(0.0,start)]; dist={start:0.0}; prev={}
    while pq:
        d,u=heappop(pq)
        if d!=dist.get(u): continue
        if u==goal: break
        for eid in out.get(u,()):
            if eid in banned: continue
            a,b,L,V=edges[eid]; nd=d+L/max(V,.1)
            if nd<dist.get(b,1e100):
                dist[b]=nd; prev[b]=eid; heappush(pq,(nd,b))
    if goal not in dist: return None
    r=[]; cur=goal
    while cur!=start:
        e=prev[cur]; r.append(e); cur=edges[e][0]
    return r[::-1]

def length(route,edges): return sum(edges[e][2] for e in route)
def valid(route,edges):
    return bool(route) and all(edges[a][1]==edges[b][0] for a,b in zip(route,route[1:]))

def alternatives(start,goal,base,edges,out,rng,k,detour):
    ans=[]; seen={tuple(base)}
    if len(base)<3: return ans
    base_len=length(base,edges)
    for _ in range(k*10):
        ban=set()
        idx=list(range(1,len(base)-1)); rng.shuffle(idx)
        for i in idx[:max(1,min(3,len(base)//8))]: ban.add(base[i])
        r=dijkstra(start,goal,edges,out,ban)
        if not r or tuple(r) in seen or not valid(r,edges): continue
        if length(r,edges)>base_len*detour: continue
        overlap=len(set(r)&set(base))/max(1,len(set(base)))
        if overlap>.90: continue
        seen.add(tuple(r)); ans.append(r)
        if len(ans)>=k: break
    return ans

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("-n","--net-file",required=True); ap.add_argument("-o","--output",required=True)
    ap.add_argument("-v","--vehicles",type=int,default=1000); ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--end",type=float,default=3600); ap.add_argument("--min-distance",type=float,default=300)
    ap.add_argument("--alternatives",type=int,default=3); ap.add_argument("--max-detour",type=float,default=1.60)
    ap.add_argument("--alt-prob",type=float,default=.75); args=ap.parse_args()
    rng=random.Random(args.seed); nodes,edges,out=load_net(args.net_file)
    starts=[n for n in nodes if out.get(n)]
    vehicles=[]
    weights=[("motorcycle",65),("car",25),("taxi",4),("bus",3),("truck",3)]
    types=[t for t,w in weights for _ in range(w)]
    backups=0
    for i in range(args.vehicles):
        for _ in range(5000):
            s,g=rng.choice(starts),rng.choice(list(nodes))
            if s==g: continue
            base=dijkstra(s,g,edges,out)
            if base and length(base,edges)>=args.min_distance: break
        else: raise RuntimeError("Không tìm đủ OD pair; giảm --min-distance hoặc --vehicles.")
        alts=alternatives(s,g,base,edges,out,rng,args.alternatives,args.max_detour)
        chosen=rng.choice(alts) if alts and rng.random()<args.alt_prob else base
        backups+=len(alts)
        vehicles.append((rng.uniform(0,max(0,args.end-1)),str(i),rng.choice(types),chosen))
    root=ET.Element("routes")
    for vid,shape,speed in [("car","passenger","13.9"),("motorcycle","motorcycle","15"),("taxi","passenger","13.9"),("bus","bus","12"),("truck","truck","11")]:
        ET.SubElement(root,"vType",{"id":vid,"vClass":"passenger" if vid in ("car","taxi") else vid,"guiShape":shape,"maxSpeed":speed,"accel":"2.6","decel":"4.5","sigma":".5","length":"4.5" if vid not in ("bus","truck") else "10"})
    for dep,vid,typ,r in sorted(vehicles):
        v=ET.SubElement(root,"vehicle",{"id":vid,"type":typ,"depart":f"{dep:.1f}","departLane":"best","departSpeed":"max"})
        ET.SubElement(v,"route",{"edges":" ".join(r)})
    tree=ET.ElementTree(root); ET.indent(tree,space="  "); tree.write(args.output,encoding="utf-8",xml_declaration=True)
    print(f"Nodes={len(nodes)} Edges={len(edges)} Vehicles={len(vehicles)} BackupRoutesFound={backups}")
    print("DONE:",args.output)

if __name__=="__main__": main()
