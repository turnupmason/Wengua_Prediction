#!/usr/bin/env python3
"""Read true BigFish 1080.zip + fact-locked editorials, verify ordered physical facts.
Does NOT verify 200-table, calendar, V8 scores or medical correctness.
Example:
  python3 tools/verify_imported_bigfish_sources.py --charts 1080.zip --facts all_6000_source_fact_locked.jsonl
"""
from __future__ import annotations
import argparse, collections, hashlib, json, pathlib, re, zipfile
GUA={'坎':1,'坤':2,'震':3,'巽':4,'乾':6,'兑':7,'艮':8,'离':9}
PALACE=re.compile(r'落([坎坤震巽乾兑艮离])[一二三四六七八九]宫')
PAIRS=re.compile(r'([乙丙丁戊己庚辛壬癸])加([乙丙丁戊己庚辛壬癸])「')
DETAIL=re.compile(r'九星(.+?)，八门(.+?)，八神(.+?)；天盘干(.+?)，地盘干(.+?)；天地格',re.S)
KEYS=('illness','doctor','medicine','patient','hour','chief','gender')
STEMS='甲乙丙丁戊己庚辛壬癸'
def digest(b):return hashlib.sha256(b).hexdigest()
def read_charts(path):
    atlas={}
    with zipfile.ZipFile(path) as z:
        for item in z.infolist():
            if not item.filename.endswith('.json') or item.filename.startswith('__MACOSX/'):continue
            b=z.read(item);chart=json.loads(b);pid=chart['physical_id']
            if pid in atlas:raise ValueError('duplicate original chart: '+pid)
            atlas[pid]=(chart,digest(b))
            if len(chart['palaces'])!=9:raise ValueError('missing centre/outer palace: '+pid)
            c=chart['palaces']['5']
            if c['heaven_stars'] or c['door'] or c['deity']:raise ValueError('phantom centre star: '+pid)
    if len(atlas)!=1080:raise ValueError('expected exactly 1080 original charts, got '+str(len(atlas)))
    return atlas
def ordered_pairs(palace,chart):
    s=[x['carried_stem'] for x in palace['heaven_stars']]
    e=palace['earth_stem']
    if palace['palace']==2:
        centre=chart['palaces']['5']['earth_stem']
        return [(s[0],e),(s[1],centre)] if len(s)>1 else ([(s[0],e),(s[0],centre)] if s else [])
    return [(x,e) for x in s]
def compare(record, atlas):
    pid=record['physical_id'];issues=[]
    if pid not in atlas:return ['missing_chart']
    chart,physical_sha=atlas[pid]
    if physical_sha!=record['physical_board_sha256']:issues.append('chart_sha_mismatch')
    context=record['source_context']
    if chart['hour_ganzhi']!=context['hour']:issues.append('hour_mismatch')
    if context['relationship']=='father' and context['year']=='甲子':
        if context['main_symbol']!='甲' or context['carrier_stem']!='戊':issues.append('father_source')
        carrier=[int(k) for k,p in chart['palaces'].items() if any(x['carried_stem']=='戊' for x in p['heaven_stars'])]
        if carrier!=[context['patient_palace']]:issues.append('father_palace_mismatch')
    for role in KEYS:
        src=record['original_sections'].get(role,'')
        m=PALACE.search(src)
        if not m:continue
        p=chart['palaces'][str(GUA[m.group(1)])]
        d=DETAIL.search(src)
        if not d:issues.append(role+':no_sky_door_deity');continue
        star,door,god,sky,earth=d.groups()
        if not p['heaven_stars'] or not star.startswith(p['heaven_stars'][0]['star']):issues.append(role+':star')
        if not door.startswith(p['door']):issues.append(role+':door')
        if not god.startswith(p['deity']):issues.append(role+':deity')
        if re.findall('['+STEMS+']',sky)!=[x['carried_stem'] for x in p['heaven_stars']]:issues.append(role+':heaven')
        expected_earth=[p['earth_stem']]+([chart['palaces']['5']['earth_stem']] if p['palace']==2 else [])
        if re.findall('['+STEMS+']',earth)!=expected_earth:issues.append(role+':earth')
        if PAIRS.findall(src)!=ordered_pairs(p,chart):issues.append(role+':81_ordered_pairs')
    return issues
def main(charts,facts):
    atlas=read_charts(charts);status=collections.Counter();examples=[]
    with open(facts,encoding='utf-8') as f:
        for line in f:
            if not line.strip():continue
            r=json.loads(line);issues=compare(r,atlas)
            status['total']+=1
            status['flagged' if issues else 'matched']+=1
            if issues and len(examples)<30:examples.append((r['record_id'],issues))
    result={'charts':len(atlas),'records':status['total'],'matched':status['matched'],
            'flagged':status['flagged'],'examples':examples,
            'scope':'PHYSICAL_BOARD_FIELDS_ONLY_NOT_RECOMPUTED_V8_OR_200'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if status['flagged'] else 0
if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--charts',required=True);a.add_argument('--facts',required=True)
    x=a.parse_args()
    raise SystemExit(main(x.charts,x.facts))
