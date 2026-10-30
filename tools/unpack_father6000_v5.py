#!/usr/bin/env python3
"""Unpack SHA-locked, fully source-anchored *draft* readings to physical board directories.
This script never promotes reviews to approved and never touches WenguaApp V8 mathematics.
"""
import base64, gzip, hashlib, json, pathlib, re, sys

GROUP_ROOT=pathlib.Path('staging/father6000_v5')
PATTERN=re.compile(r'^疾病/病情程度/盘面/(阳遁|阴遁)/(0[1-9])局/(.{2})/父亲/case-(\d{6})-jieqi-a\.v5\.json$')
SCORE={'极大吉':5,'大吉':4,'中吉':3,'小吉':2,'极小吉':1,'微恙':0,'极小凶':-1,'小凶':-2,'中凶':-3,'大凶':-4,'极大凶':-5}
SECTIONS={'macro','illness','patient','doctor','medicine','hour','chief','gender','verdict','timing'}

def sha(value:bytes):return hashlib.sha256(value).hexdigest()

def check_path_record(name:str,obj:dict,idx:int):
    m=PATTERN.fullmatch(name)
    if not m:raise ValueError('invalid board path: '+name)
    direction,ju,hour,serial=m.groups()
    if int(serial)!=idx:raise ValueError('wrong serial: '+name)
    board=obj['physical_chart']; source=obj['source_context']; lock=obj['fact_lock']; ed=obj['editorial']
    expected=('yang' if direction=='阳遁' else 'yin')+'-'+ju+'-'+hour
    if board['key']!=expected or board['direction']!=('yang' if direction=='阳遁' else 'yin') or board['ju']!=int(ju):raise ValueError('physical mismatch: '+name)
    if board['hour_ganzhi']!=hour or source['hour']!=hour or source['scenario_id']!=idx:raise ValueError('hour mismatch: '+name)
    if obj['schema_version']!='wengua_reading_v1' or ed['version']!=5:raise ValueError('wrong version: '+name)
    if source['relationship']!='father' or source['solar_term_branch']!='a' or source['natal_mode']!='none' or source['year']!='甲子':raise ValueError('unexpected relationship or term: '+name)
    if lock['patient_symbol']!='甲' or lock['patient_source_ganzhi']!='甲子' or lock['carrier_stem']!='戊':raise ValueError('wrong six-jia father source: '+name)
    if not all(len(lock[f])==64 for f in ('original_text_sha256','original_evidence_sha256','physical_board_sha256')):raise ValueError('bad SHA: '+name)
    if SCORE[lock['grade']]!=lock['score'] or not ed['front_screen']['title'].startswith(lock['grade']+'：'):raise ValueError('grade drift: '+name)
    if set(ed['professional_sections'])!=SECTIONS:raise ValueError('chapters missing: '+name)
    if ed['status']!='draft' or ed['human_approved'] or ed.get('reviewer'):raise ValueError('unexpected approval: '+name)
    if len(ed['front_screen']['text'])<140:raise ValueError('short main text: '+name)
    return True

def unpack(root:pathlib.Path):
    manifest=json.loads((root/GROUP_ROOT/'READY.json').read_text('utf-8'))
    if manifest['case_count']!=6000 or manifest['approved']!=0 or len(manifest['chunks'])!=60:raise ValueError('manifest mismatch')
    prepared=[];nums=set()
    for part in manifest['chunks']:
        source=root/GROUP_ROOT/part['file']
        encoded=source.read_bytes()
        if sha(encoded)!=part['encoded_sha256']:raise ValueError('encoded SHA mismatch: '+str(source))
        zipped=base64.b64decode(b''.join(encoded.splitlines()),validate=True)
        if sha(zipped)!=part['compressed_sha256']:raise ValueError('gzip SHA mismatch: '+str(source))
        raw=gzip.decompress(zipped)
        if sha(raw)!=part['uncompressed_sha256']:raise ValueError('payload SHA mismatch: '+str(source))
        lines=[x for x in raw.splitlines() if x]
        if len(lines)!=100 or part['cases']!=100:raise ValueError('wrong chunk count: '+str(source))
        for i,line in enumerate(lines):
            entry=json.loads(line)
            idx=part['case_start']+i
            if idx in nums or idx>part['case_end']:raise ValueError('duplicate/wrong case: '+str(idx))
            nums.add(idx)
            name=entry['path']
            obj=entry['record']
            check_path_record(name,obj,idx)
            dest=root/pathlib.PurePosixPath(name)
            if dest.exists():raise FileExistsError('refuse overwrite: '+name)
            prepared.append((dest,json.dumps(obj,ensure_ascii=False,indent=2)+'\n'))
    if nums!=set(range(1,6001)):raise ValueError('case index gaps')
    for dest,content in prepared:
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(content,encoding='utf-8')
    print(json.dumps({'written':len(prepared),'physical_cases':len({p.parent.parent.as_posix() for p,_ in prepared}),'approved':0,'release':'DRAFTS_ONLY','manifest':sha((root/GROUP_ROOT/'READY.json').read_bytes())},ensure_ascii=False))

if __name__=='__main__':unpack(pathlib.Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve())