#!/usr/bin/env python3
"""Reproduce the ancient Eurasian Y-DNA demo from three pinned public tables.

Run scripts/fetch_data_assets.py --ancient-y-sources first. All source tables
remain ignored; generation uses the standard library and performs no network IO.
"""
import colorsys
import copy
import csv
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'samples/public/source-snapshots/ancient-y'
OUT=ROOT/'samples'
STEM='ancient-y-eurasian-subclades'
PAA='https://github.com/poseidon-framework/aadr-archive/tree/7406a4162bbde48dbae41dc8e68381a30ce0116e/AADR_v66_p1_1240K'
AADR_DOI='https://doi.org/10.7910/DVN/FFIDCW'
SOURCES=json.loads((ROOT/'assets/data-assets.json').read_text())['ancient-y-sources']
for name,entry in SOURCES.items():
    data=(SRC/name).read_bytes()
    if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise ValueError('Pinned source mismatch: '+name)
rows=list(csv.DictReader((SRC/'aadr-v66-p1.janno').open(),delimiter='\t'))
FILTER=dict(start=None,end=None,hidden_entities=[],hidden_categories=[],hidden_sources=[],
            search='',predicates=[],selected_only=False,bounds=None,located_only=False)
CAMERA=dict(yaw=-.55,pitch=.65,zoom=1.,pan=[0.,0.],time_scale=1.)


def epoch_year(year):
    """Proleptic Gregorian astronomical year -> seconds since 1970-01-01."""
    y = math.floor(year)
    a = y - 1  # January lies in the preceding March-based year.
    era = a // 400
    yoe = a - era * 400
    doy = (153 * 10 + 2) // 5
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    days = era * 146097 + doe - 719468
    next_days = 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
    return (days + (year-y)*next_days) * 86400

def bp_epoch(bp):
    return epoch_year(1950-float(bp))

def calendar_age(text):
    """Use the calendar BC/AD column; never mistake a raw 14C ± age for calendar BP."""
    s=text.strip().replace('\t','').replace(',','').replace('–','-').replace('—','-').replace('−','-')
    if not s or s.upper()=='N/A' or s.lstrip().startswith(('<','>')):return None
    # Rare cross-era brackets are handled explicitly.
    cross=re.match(r'~?\s*(\d+)\s*BC\s*-\s*(\d+)\s*AD',s,re.I)
    if cross:
        a,b=1-float(cross[1]),float(cross[2]);return min(a,b),max(a,b),'calendar range across BCE/CE'
    m=re.match(r'^[~≈]?\s*(\d+(?:\.\d+)?(?:\s*[/\-]\s*\d+(?:\.\d+)?)*)(?:\s*(cal\s*)?(BC|AD|BCE|CE))?',s,re.I)
    if not m:return None
    nums=[float(x) for x in re.findall(r'\d+(?:\.\d+)?',m[1])]
    era=(m[3] or 'BC').upper()
    values=nums if era in ('AD','CE') else [1-x for x in nums]
    method=('calendar range' if len(values)>1 else 'approximate calendar date')+('; era from BC column heading' if not m[3] else '')
    return min(values),max(values),method

def major_haplogroup(raw):
    s=raw.strip()
    if re.search(r'\?|~',s) or re.match(r'^(BT|CT|CF|IJ|HI|NO)',s):return 'Other / unresolved'
    for g in ['R1a','R1b','I1','I2','G2','J1','J2']:
        if s.startswith(g):return g
    if s and s[0] in 'CDEFGHIJLNOPQRT':return s[0]
    return 'Other / unresolved'


def source_workbook():
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(SRC/'aydb-v5.xlsx') as z:
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        table=[]
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row',ns):
            values={}
            for cell in row:
                value=cell.find('m:v',ns)
                if value is not None:
                    values[re.sub(r'\d','',cell.attrib['r'])]=strings[int(value.text)] if cell.attrib.get('t')=='s' else value.text
            table.append(values)
    return [{table[0][k]:v for k,v in row.items()} for row in table[1:]]


def make_baseline():
    events=[]
    source_rows=source_workbook()
    assert len(source_rows)==1797
    for n,r in enumerate(source_rows,2):
        age=calendar_age(r.get('Age (BC)',''))
        if age is None:continue
        lo,hi,method=age
        lat,lon=float(r['Latitude']),float(r['Longitude'])
        assert -90<=lat<=90 and -180<=lon<=180
        group=major_haplogroup(r.get('Haplogroup',''))
        attrs={**r,'country':r.get('Country',''),'site':r.get('Location',''),
               'specimen':r.get('Published ID',''),'y_haplogroup_reported':r.get('Haplogroup',''),
               'y_display_group':group,'calendar_year_min_astronomical':lo,'calendar_year_max_astronomical':hi,
               'age_mean_bp':1950-(lo+hi)/2,'date_basis':method+'; midpoint is a display anchor only',
               'source_url':'https://github.com/eelhaik/aYDB',
               'coordinate_basis':'Coordinates supplied by aYChr-DB; some were assigned by database authors from site descriptions.',
               'interpretation':'Ancient sampled paternal lineage, not population frequency, ethnicity, language, individual travel or a directly observed migration route.'}
        events.append(dict(entity=group,time=epoch_year((lo+hi)/2),end=None,lat=lat,lon=lon,value=None,
             attrs={k:str(v) for k,v in attrs.items()},category=r.get('Revised Period','Unknown period'),
             label=f"{r.get('Published ID')} · {r.get('Location')} · {r.get('Haplogroup')}",
             related_to='',tags=[],note='Ancient DNA sample. Dates are estimates, not exact lifetimes or continuous occupations.',
             source='Freeman et al. 2020 / aYChr-DB v5',source_row=n))
    events.sort(key=lambda e:(e['time'],e['entity'],e['source_row']))
    for i,e in enumerate(events,1):e['id']=i
    assert len(events)==1708
    return dict(format='chronoscope.workspace',version=6,time_resolution='fractional_second',
                dataset=dict(name='Ancient Y-DNA · Eurasian subclades',events=events),
                selected=[],camera=CAMERA,groups=[],imports=[],
                field_roles={'value':'ignore','entity':'category','time':'timestamp'})


def norm(s):
    s=re.sub(r'(?:\.(?:AG|DG|SG|HO|WGC|REF))+$','',s.strip(),flags=re.I)
    return re.sub(r'[^a-z0-9]','',s.casefold())

def aliases(r):
    result=set()
    for k in ['Poseidon_ID','AADR_Genetic_ID','AADR_Individual_ID','AADR_Skeletal_Code']:
        for value in r.get(k,'').split(';'):
            if value.strip() not in ('','..','n/a'):result.add(norm(value))
    return result

index=defaultdict(set)
for i,r in enumerate(rows):
    for a in aliases(r):index[a].add(i)

# The old source sometimes uses genetic IDs retired in v66. Bridge only exact
# v62 identifiers to a unique v66 individual; no Y call is taken from v62.
v62=list(csv.DictReader((SRC/'aadr-v62.anno').open(),delimiter='\t'))
gkey=next(k for k in v62[0] if k.startswith('Genetic ID'))
bridges=0
for r in v62:
    old={norm(r.get(k,'')) for k in [gkey,'Master ID','Skeletal code'] if r.get(k,'') not in ('','..')}
    targets=set().union(*(index.get(a,set()) for a in old))
    individuals={rows[i]['AADR_Individual_ID'] for i in targets}
    if len(individuals)==1:
        for a in old:index[a].update(targets)
        bridges+=1

def distance_km(lat,lon,r):
    try:a,b=float(r['AADR_Lat']),float(r['AADR_Long'])
    except (ValueError,KeyError):return math.inf
    p1,p2=map(math.radians,(lat,a));dp=p2-p1;dl=math.radians(b-lon)
    q=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 12742*math.asin(min(1,math.sqrt(q)))

def valid_call(s):
    return bool(re.fullmatch(r'[A-T](?:\d+[a-z]?)*(?:[?~])?',s))

def call_for(r):
    manual=r['AADR_Y_Haplogroup_Manual'].strip()
    auto=r['AADR_Y_Haplogroup_ISOGG'].strip()
    if manual not in ('','..'):
        if valid_call(manual):return manual,'AADR curated manual call'
        return None,'Manual call requires individual review'
    return (auto,'AADR automatic ISOGG v15.73 call') if valid_call(auto) else (None,'No usable AADR Y call')

def consistent_root(old,new):
    old=old.strip()
    for superclade,desc in [('HIJK','HIJKLNOPQRT'),('IJK','IJKLNOPQRT'),('BT','BCDEFGHIJKLNOPQRT'),('CT','CDEFGHIJKLNOPQRT'),('CF','CFGHIJKLNOPQRT'),('IJ','IJ'),('NO','NO'),('P','PQR')]:
        if old.startswith(superclade):return new[0] in desc
    return old[:1]==new[:1]

PREFIXES=['E1b1a','E1b1b','E1a','E1b','E2','I2a','I2b','I2c','I1','I2',
          'G2a','G2b','G1','G2','J2a','J2b','J1','J2','R1a','R1b','R2',
          'N1a','N1b','N1c','N2','N1','N3','O1a','O1b','O2a','O2b','O1','O2','O3',
          'Q1a','Q1b','Q1c','Q2','Q1','C1a','C1b','C2a','C2b','C2','C1','C3','C6',
          'D1a','D1b','D2','D1','H1','H2','H3','T1','T2','L1','L2']

def display_group(s,source):
    s=s.strip();base=re.split(r'[(*?~\s]',s,maxsplit=1)[0]
    branch=next((p for p in PREFIXES if base.startswith(p)),None)
    if branch is None:return 'Unresolved · '+(base or 'unknown')
    # Old C3/C6, N3 and O3 labels must not masquerade as current tree branches.
    if source=='Original reported call' and branch in ('C3','C6','N3','O3'):
        branch+=' (legacy)'
    if '?' in s or '~' in s:branch+=' (tentative)'
    return branch

def score(r):
    try:return float(r['AADR_SNPs_1240k'])
    except ValueError:return 0

project=make_baseline()
audit=[]
before=Counter(e['entity'] for e in project['dataset']['events'])
for e in project['dataset']['events']:
    a=e['attrs'];old=a['y_haplogroup_reported'];sample=a['specimen']
    candidates=sorted(index.get(norm(sample),set())) if re.search('[A-Za-z]',sample) else []
    accepted=[];reasons=Counter()
    bp_lo=1950-float(a['calendar_year_max_astronomical'])
    bp_hi=1950-float(a['calendar_year_min_astronomical'])
    for i in candidates:
        r=rows[i];call,basis=call_for(r)
        if r['AADR_Assessment'].lower()!='pass':reasons['QC not Pass']+=1;continue
        if r['Genetic_Sex']!='M':reasons['Not genetically male']+=1;continue
        if not call:reasons[basis]+=1;continue
        if distance_km(e['lat'],e['lon'],r)>50:reasons['Coordinates differ by >50 km']+=1;continue
        try:
            bp=float(r['AADR_Date_Mean_BP'])
            sd=float(r['AADR_Date_SD']) if r['AADR_Date_SD']!='..' else 0
        except ValueError:reasons['No usable AADR age']+=1;continue
        tolerance=max(500,2*sd)
        if not bp_lo-tolerance<=bp<=bp_hi+tolerance:reasons['Calendar ages do not overlap within tolerance']+=1;continue
        if not consistent_root(old,call):reasons['Conflicting major clade']+=1;continue
        accepted.append((i,call,basis))
    status='No accepted AADR match';chosen=None
    if accepted:
        persons={rows[i]['AADR_Individual_ID'] for i,_,_ in accepted}
        calls={re.sub('[?~]','',c) for _,c,_ in accepted}
        nested=all(x.startswith(y) or y.startswith(x) for x in calls for y in calls)
        if len(persons)!=1:status='Ambiguous specimen identity; retained original'
        elif not nested:status='Conflicting AADR representation calls; retained original'
        else:
            chosen=max(accepted,key=lambda x:score(rows[x[0]]));status='AADR match accepted'
    selected=old;basis='Original reported call'
    if chosen:
        i,selected,basis=chosen;r=rows[i]
        a.update(y_aadr_genetic_id=r['AADR_Genetic_ID'],y_aadr_individual_id=r['AADR_Individual_ID'],
                 y_aadr_persistent_genetic_id=r['AADR_Persistent_Genetic_ID'],
                 y_aadr_isogg=r['AADR_Y_Haplogroup_ISOGG'],y_aadr_terminal_mutation=r['AADR_Y_Haplogroup_Terminal_Mutation'],
                 y_aadr_manual=r['AADR_Y_Haplogroup_Manual'],y_aadr_qc=r['AADR_Assessment'],
                 y_aadr_snps_1240k=r['AADR_SNPs_1240k'],y_aadr_publication_doi=r['AADR_Publication_DOI'],
                 y_assignment_source_url=PAA,y_assignment_dataset='AADR v66.p1, Poseidon metadata package 1.0.0',
                 y_match_distance_km=f'{distance_km(e["lat"],e["lon"],r):.3f}')
    group=display_group(selected,basis)
    a.update(y_display_group_previous=e['entity'],y_assignment_selected=selected,y_assignment_basis=basis,
             y_assignment_tree='AADR v66.p1 / ISOGG v15.73' if chosen else 'Original study nomenclature',
             y_assignment_match_status=status,y_display_group=group,
             y_full_label=selected+((' · '+a['y_aadr_terminal_mutation']) if chosen and a['y_aadr_terminal_mutation'] not in ('','..') else ''),
             y_match_policy='Normalized exact identifier (with unique v62 alias bridge where needed), male, AADR Pass, <=50 km, overlapping ages with >=500-year tolerance, one individual, nested calls across representations; otherwise retain original.')
    e['entity']=group
    e['label']=f'{sample} · {a["site"]} · {a["y_full_label"]}'
    audit.append(dict(id=e['id'],specimen=sample,original_call=old,previous_group=a['y_display_group_previous'],
                      selected_call=selected,display_group=group,assignment_basis=basis,status=status,
                      accepted_candidates=len(accepted),rejected_candidate_reasons=dict(reasons),
                      aadr_genetic_id=a.get('y_aadr_genetic_id'),terminal_mutation=a.get('y_aadr_terminal_mutation')))

after=Counter(e['entity'] for e in project['dataset']['events'])
base_colors={'R1b':'#ffad5a','R1a':'#ee6f91','I2a':'#6eb9f7','I2b':'#aac8fa','I1':'#9b9cff',
             'G2a':'#55d3b1','G2b':'#359b82','J2a':'#d5b6ee','J2b':'#b68bdf','J1':'#c38af1',
             'O1a':'#f2d480','O1b':'#ce9e75','O2a':'#f1a16a','O2b':'#d87652',
             'N1a':'#e3a6c9','N1b':'#b484ba','N1c':'#c7a1eb','Q1a':'#c7b17e','Q1b':'#aa905e',
             'C1a':'#8fcbd0','C2b':'#44a5ae','E1b1b':'#ebce65','E1b1a':'#babd57'}
colors={}
palette={}
for i,g in enumerate(sorted({x.removesuffix(' (tentative)') for x in after})):
    if g in base_colors:palette[g]=base_colors[g]
    else:
        rgb=colorsys.hls_to_rgb((i*.61803398875)%1,.65,.58)
        palette[g]='#'+''.join(f'{round(x*255):02x}' for x in rgb)
for g in sorted(after):
    if g.startswith('Unresolved'):colors[g]='#7b8798'
    else:colors[g]=palette[g.removesuffix(' (tentative)')]


def scene(mode,bounds,camera=None):
    return dict(renderer='cesium',mode=mode,bounds=bounds,cesium_camera=camera,
                expanded=False,inspector_tab='views',render_budget=100000,time_height=1.8,
                entity_colors=colors,table_attributes=True,table_open=False,
                playback_fade=False,playback_fade_amount=0,
                display=dict(mode='points',show_points=True,show_tracks=False,show_trails=False,
                             show_centroids=False,spatial_culling=False,point_scale=1.5,bloom=False))


def saved(name,sc,filter=None):
    return dict(name=name,scene=copy.deepcopy(sc),mode='SpaceTime' if sc['mode']=='space-time' else 'Map',
                filter=copy.deepcopy(filter or FILTER),selected=[],camera=CAMERA)


def period(young,old,bounds=None):
    f={**copy.deepcopy(FILTER),'start':bp_epoch(old),'end':bp_epoch(young)}
    if bounds:f['bounds']=dict(zip(['west','south','east','north'],bounds))
    return f


REGIONS=[{'name': 'Europe', 'bounds': [-12, 34, 35, 63], 'camera': {'position': [1280174.1441226448, 2075593.4318970004, 3947432.8445916595], 'direction': [4.41299633963434e-16, 0.7071067811865474, -0.7071067811865478], 'up': [-2.972810364169849e-17, 0.7071067811865474, 0.7071067811865478]}}, {'name': 'Caucasus and West Asia', 'bounds': [25, 25, 65, 46], 'camera': {'position': [5009377.085697309, 911282.7640590607, 3693073.018782853], 'direction': [-8.860657084233997e-17, 0.7071067811865482, -0.7071067811865469], 'up': [3.824211667627923e-16, 0.7071067811865482, 0.7071067811865469]}}, {'name': 'Eurasian steppe and Siberia', 'bounds': [30, 40, 115, 72], 'camera': {'position': [8070663.082512339, 1637697.4067107714, 5548604.837593196], 'direction': [1.4690729796022616e-16, 0.7071067811865495, -0.7071067811865457], 'up': [2.254119208944145e-16, 0.7071067811865495, 0.7071067811865457]}}, {'name': 'East Asia', 'bounds': [90, 5, 145, 55], 'camera': {'position': [13080040.168209646, -1044477.3195583753, 5385937.460555495], 'direction': [2.6466423236151115e-16, 0.7071067811865461, -0.7071067811865491], 'up': [1.0765498649313336e-16, 0.7071067811865461, 0.7071067811865491]}}]
lat,lon=map(math.radians,(45,55));radius=6378137+13500000
camera=dict(position=[radius*math.cos(lat)*math.cos(lon),radius*math.cos(lat)*math.sin(lon),radius*math.sin(lat)],
            direction=[-math.cos(lat)*math.cos(lon),-math.cos(lat)*math.sin(lon),-math.sin(lat)],
            up=[-math.sin(lat)*math.cos(lon),-math.sin(lat)*math.sin(lon),math.cos(lat)])
globe=scene('globe',[-15,5,170,75],camera)
globe.update(globe_time=True,globe_altitude=False,globe_time_scale=20)
views=[saved('Eurasia · paternal lineages · 12–2 ka BP',globe,period(2000,12000))]
for r in [REGIONS[i] for i in [0,2,3,1]]:
    views.append(saved(r['name']+' · Time · 12–2 ka BP',scene('space-time',r['bounds'],r['camera']),period(2000,12000,r['bounds'])))
world=scene('map',[-15,5,170,75])
europe=scene('map',[-13,29,60,66])
views.extend([saved('Eurasia · all dated records',world),
              saved('Before farming · 12–8 ka BP',europe,period(8000,12000,[-13,29,60,66])),
              saved('Early-farmer period · 8–5.5 ka BP',europe,period(5500,8000,[-13,29,60,66])),
              saved('Steppe-expansion period · 5.5–3.5 ka BP',europe,period(3500,5500,[-13,29,60,66]))])
for e in project['dataset']['events']:
    a=e['attrs']
    a['y_is_legacy']='yes' if '(legacy)' in e['entity'] else 'no'
matched={**copy.deepcopy(FILTER),'predicates':[dict(field='y_assignment_tree',op='Equals',value='AADR v66.p1 / ISOGG v15.73')]}
views.append(saved('Eurasia · matched AADR nomenclature only',world,matched))
resolved={**copy.deepcopy(FILTER),'hidden_entities':[g for g in after if g.startswith('Unresolved')]}
views.append(saved('Eurasia · resolved branches only',world,resolved))
project.update(mode='Map',scene=copy.deepcopy(views[0]['scene']),filter=copy.deepcopy(views[0]['filter']),views=views)
project['provenance']=[
 dict(title='aYChr-DB v5 · ancient Eurasian Y haplogroups',creator='Freeman, Brimacombe & Elhaik (2020)',
      source_url='https://doi.org/10.1093/nargab/lqaa081',license='CC BY 4.0',license_url='https://creativecommons.org/licenses/by/4.0/',
      changes='1,708 of 1,797 records retained: 74 missing calendar ages and 15 open-ended dates excluded. Original specimen, site, coordinates, reported haplogroup, calendar dates and study references retained. Calendar BC/AD range midpoints are display anchors, not precise lifetimes; raw radiocarbon BP values are not substituted for calendar ages. BP is relative to 1950. No inferred routes, coordinate jitter or synthetic samples. Legacy and tentative calls remain explicit. Counts reflect sampling, not population frequencies; the basemap uses modern geography.'),
 dict(title='Allen Ancient DNA Resource · v66.p1 · 1240K metadata',creator='Swapan Mallick & David Reich; Poseidon metadata packaging',
      source_url=AADR_DOI,license='CC0 1.0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',
      changes='1,031 conservative metadata matches to the same source specimens, with Pass/male, identity, geographic and dating checks. Preserve original aYChr-DB labels alongside manual, automatic ISOGG v15.73, terminal-SNP and source-study fields. No sequence-based reanalysis. Broad or conflicting calls are not assigned an invented descendant. Poseidon package 1.0.0, pinned source: '+PAA),
 dict(title='The Allen Ancient DNA Resource (AADR) a curated compendium of ancient human genomes',creator='Mallick et al. (2024), Scientific Data 11:182',
      source_url='https://doi.org/10.1038/s41597-024-03031-7',license='CC BY 4.0',license_url='https://creativecommons.org/licenses/by/4.0/',
      changes='Methodological citation accompanying the AADR v66.p1 dataset citation. Underlying study identifiers and references remain attached to each sample.')]

target=OUT/(STEM+'.chronoscope')
with zipfile.ZipFile(target,'w') as z:
    entry=zipfile.ZipInfo('manifest.json',(2026,11,24,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(entry,json.dumps(project,ensure_ascii=False,separators=(',',':'),allow_nan=False))
report=dict(records=len(audit),display_groups=len(after),matched_aadr_records=sum(x['status']=='AADR match accepted' for x in audit),
            unresolved_records=sum(n for g,n in after.items() if g.startswith('Unresolved')),
            source_records=1797,excluded_missing_calendar_age=74,excluded_open_ended_calendar_age=15,
            project_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),project_bytes=target.stat().st_size,
            source_tables=SOURCES,views=[dict(index=i,name=v['name']) for i,v in enumerate(views)])
assert report['records']==1708 and report['matched_aadr_records']==1031 and report['display_groups']==78
(ROOT/'samples/public/ancient-y-provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(ROOT/'samples/public'/f'{STEM}.attribution.json').write_text(json.dumps(project['provenance'],ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['records','display_groups','matched_aadr_records','unresolved_records','project_bytes']},indent=2))
