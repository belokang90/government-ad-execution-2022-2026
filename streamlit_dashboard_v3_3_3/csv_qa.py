"""정부광고 원본 CSV 기반 질의-집계 엔진.
외부 AI는 질의를 제한된 구조로만 변환하며 집계는 반드시 pandas로 계산한다.
"""
import json
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

COLUMNS = {'기관명', '매체명', '매체구분', '기관분류', '광고명'}
MEDIA = ('인터넷', '방송', '인쇄', '옥외', '해외')


def unsupported_reason(question):
    """CSV에 존재하지 않는 사유·판단·예산 편성 등에 대한 질문을 집계 질문으로 오인하지 않는다.

    이 검사는 유료 AI 해석 모드에서도 먼저 실행한다. 별도 자료가 없다면
    무리해서 수치를 계산하거나 AI에게 추정 답변을 생성하도록 하지 않는다.
    """
    q = re.sub(r'\s+', '', str(question)).lower()
    # 원본 CSV에는 기관·매체·광고명·금액·날짜가 있지만 선정 이유/심사 자료는 없음.
    reason_markers = (
        '선정이유', '선정사유', '선정배경', '선정근거', '선정기준', '선정과정',
        '선택이유', '선택사유', '선택기준', '매체심사', '심사기준',
        '집행이유', '집행사유', '집행배경', '집행목적', '집행취지',
        '왜선정', '왜선택', '왜집행', '왜늘', '왜줄', '왜증가', '왜감소',
        '광고매체를선정', '광고매체선정', '매체를선정', '광고매체를선택',
        '선정한구체적인', '선정했는지', '선정하였는지',
        '정치적이유', '구체적인이유', '정책적이유', '정책적배경',
        '예산편성이유', '예산편성근거', '예산편성금액', '편성예산',
    )
    if any(token in q for token in reason_markers):
        return ('이 질문은 원본 CSV만으로 확인할 수 없습니다. '
                '정부광고 집행내역에는 기관명·매체명·광고명·금액·날짜 등이 있지만 '
                '광고 매체를 선정한 이유나 심사 기준은 없습니다. '
                '확인하려면 해당 기관의 매체 선정 자료나 정보공개 회신 등이 필요합니다.')
    # 이유를 묻는 다양한 자연어 표현. 원인 추론과 실제 집계는 구분한다.
    if ('이유' in q or '사유' in q or '배경' in q or '취지' in q or '왜' in q) and (
        any(word in q for word in ('광고','매체','기관','집행','금액','변화','증가','감소','예산'))
    ):
        return ('이 질문은 광고비의 원인이나 이유를 묻고 있습니다. '
                '원본 CSV에는 실제 집행내역만 있으므로 원인이나 선정 사유는 확인할 수 없습니다. '
                '관련 기관의 공식 설명 등 추가 자료가 필요합니다.')
    if ('예산' in q and any(token in q for token in ('편성','책정','배정','확보'))) or '예산총액' in q:
        return ('원본 CSV에는 광고 집행내역이 기록되어 있습니다. '
                '예산 편성액을 확인할 수 있는 자료가 아니므로 이 질문에는 답할 수 없습니다.')
    return None


def _normalize(value):
    return re.sub(r'[^0-9a-z가-힣]', '', unicodedata.normalize('NFKC', str(value)).casefold())


def _year_list(question):
    return [int(y) for y in dict.fromkeys(re.findall(r'20(?:22|23|24|25|26)(?=\s*년|\b)', question))]


def _best_name(question, values):
    # 정확히 명시된 원본 이름만 매칭한다. 서로 다른 법인명을 자동 통합하지 않는다.
    nq = _normalize(question)
    matches = [str(x) for x in values if len(_normalize(x)) >= 3 and _normalize(x) in nq]
    return max(matches, key=lambda x: len(_normalize(x))) if matches else None



def _subject_in_question(question):
    """질문에서 검색 대상으로 보이는 말만 보수적으로 추출한다."""
    q = re.sub(r'20(?:22|23|24|25|26)\s*년', ' ', question)
    q = re.sub(r'\b(?:와|과|및|대비)\b', ' ', q)
    # 예: '2025년 경기도 광고비', '2025년 조선일보 광고금액'
    m = re.search(r'([가-힣A-Za-z0-9().·\s]+?)\s*(?:의\s*)?(?:정부\s*)?광고\s*(?:비|료|금액|건수|집행|규모)',q)
    if not m:
        return None
    phrase=m.group(1).strip(' ,?')
    phrase=re.sub(r'^(?:과|와|대비|전체|총|정부)\s*','',phrase).strip()
    phrase=re.sub(r'\s*(?:기관|언론사|매체)의?$', '', phrase).strip()
    if _normalize(phrase) in ('','전체','정부','정부광고','국내','모든','각','연도별','월별','매체별','기관별','매체유형별','기관유형별','언론사별','유형별','매체유형'):
        return None
    # 범위 이외의 일반 질의 문구는 이름이 아니다.
    if re.search(r'^(?:어느|어떤|얼마나|가장|몇|광고를|광고비를)',phrase):
        return None
    return phrase


def resolve_name_request(question, plan, catalogs):
    """모호한 기관/매체명을 선택 요청으로 바꾸고 미인식 이름을 차단."""
    if plan is None:
        return None, None
    filters=plan.setdefault('filters',{})
    term=_subject_in_question(question)
    if not term:
        return plan,None
    normalized=_normalize(term)
    if normalized in {_normalize(v) for v in MEDIA}:
        filters['매체구분']=next(v for v in MEDIA if _normalize(v)==normalized)
        return plan,None
    # 검색할 이름이 이미 전체 이름으로 잡힌 경우에도 본문에 나온 이름을 우선한다.
    if normalized in {'인터넷','방송','인쇄','옥외','해외'}:
        return plan,None
    candidates=[]
    for col in ('기관명','매체명'):
        matches=sorted({str(n) for n in catalogs.get(col,[]) if normalized in _normalize(n)},key=lambda x:(len(x),x))
        if matches: candidates.append((col,matches))
    if not candidates:
        return None, f'질문에 적은 「{term}」을 원본 기관명이나 매체명에서 찾지 못했습니다. 정확한 이름을 확인해 주세요. 전체 광고비로 대신 계산하지 않습니다.'
    # 기관/매체 동시 검색이 가능하다면 명시적 문맥을 우선한다.
    col=next((c for c,v in candidates if c=='기관명'),candidates[0][0])
    if re.search(r'언론사|신문|방송사|매체명',question) and any(c=='매체명' for c,v in candidates): col='매체명'
    matches=next(v for c,v in candidates if c==col)
    exact=[m for m in matches if _normalize(m)==normalized]
    if exact and len(matches)==1:
        filters[col]=exact[0]
        plan.setdefault('match_mode',{})[col]='exact'
        return plan,None
    # '경기도'처럼 일부만 일치하면 이용자가 직접 범위를 정한다.
    filters.pop(col,None)
    plan['pending_name']={'column':col,'term':term,'matches':matches}
    return plan,None

def parse_basic(question, catalogs):
    """무료·오프라인 기본 질문 해석. 불명확하면 추측하지 않고 오류를 반환."""
    q = question.strip()
    reason_error = unsupported_reason(q)
    if reason_error:
        return None, reason_error
    years = _year_list(q)
    comparing = bool(re.search(r'비교|대비|차이|증감|늘었|줄었|변했|변화|달라|증가|감소', q))
    top = bool(re.search(r'가장\s*많|최다|1위|상위|순위|톱\s*\d+|top\s*\d+', q, re.I))
    n_match = re.search(r'(?:상위|톱|top)\s*(\d+)\s*(?:개|곳|명|위)?', q, re.I)
    n = min(30, max(1, int(n_match.group(1)))) if n_match else (5 if '상위' in q else 1)
    metric = '건수' if re.search(r'건수|몇\s*건|광고\s*수|집행\s*횟수', q) else '금액'
    # 집단 순위는 매체명/기관명/매체유형 중 하나
    group = '매체명' if re.search(r'언론사|매체명|신문사|어느\s*매체|광고를\s*받은|광고비를\s*받은',q) else ('기관명' if re.search(r'기관별|어느\s*기관|정부기관\s*순위|기관\s*순위',q) else '매체구분' if re.search(r'매체\s*유형|매체별|인터넷.*방송|방송.*인터넷', q) else None)
    filters = {}
    # 기관·매체 이름은 resolve_name_request에서 확인하고 모호하면 선택을 받는다.
    media = [m for m in MEDIA if re.search(rf'(?<![가-힣]){m}(?:\s*광고|\s*매체|\s*분야|\s*유형|\s*광고비|\s*집행|\s*에|\s*의|\s*는|\s*가|\s*와|\s*과|\s*을|\s*에서|\b)', q)]
    if len(media) == 1 and '매체명' not in filters:
        filters['매체구분'] = media[0]
    if len(years) > 2 and comparing:
        return None, '비교할 연도는 두 개까지만 지정해 주세요.'
    if not years:
        return None, '질문에 2022~2026년 중 분석 연도를 명시해 주세요.'
    month_match = re.search(r'(?<!\d)(1[0-2]|[1-9])\s*월', q)
    if month_match:
        filters['월'] = int(month_match.group(1))
    if top:
        if group is None:
            return None, '어떤 대상을 순위로 볼지 지정해 주세요. 예: 2025년 광고를 가장 많이 받은 언론사는?'
        return resolve_name_request(q, {'kind':'rank','years':years,'filters':filters,'metric':metric,'group':group,'top_n':n}, catalogs)
    if comparing:
        if len(years) != 2:
            return None, '비교 질문에는 기준 연도와 비교 연도를 모두 명시해 주세요.'
        return resolve_name_request(q, {'kind':'compare','years':years,'filters':filters,'metric':metric}, catalogs)
    if group and re.search(r'별|분포|내역|현황|비중', q):
        return resolve_name_request(q, {'kind':'group','years':years,'filters':filters,'metric':metric,'group':group,'top_n':30}, catalogs)
    # '집행기관' 같은 단어만으로 집행 총액을 요청한 것으로 간주하지 않는다.
    if re.search(r'얼마|총액|합계|몇\s*건|건수|규모|집행액|집행규모|광고비|광고료|금액', q):
        return resolve_name_request(q, {'kind':'total','years':years,'filters':filters,'metric':metric}, catalogs)
    return None, '현재 지원하는 질문 유형이 아닙니다. 연도와 금액·건수·비교·순위 등을 포함해 질문해 주세요.'


def interpret_with_api(question, api_key, catalogs):
    """LLM에는 질의 해석만 위임. 데이터는 전송하지 않음. 구조화된 명령만 허용."""
    reason_error = unsupported_reason(question)
    if reason_error:
        raise ValueError(reason_error)
    from openai import OpenAI
    client = OpenAI(api_key=api_key, timeout=25)
    # 모델에 원본 행을 보내지 않는다. 긴 기관·매체 목록도 보내지 않는다.
    instruction = (
        '한국어 정부광고 데이터 질의를 분석 명령 JSON으로만 변환한다. '
        '설명이나 답을 생성하지 않는다. 허용 kind: total, compare, rank, group. '
        '허용 years: 2022~2026의 연도 배열. compare는 2개 연도 필수. '
        'metric은 금액 또는 건수. group은 기관명, 매체명, 매체구분 중 하나 또는 null. '
        'filters는 기관명, 매체명, 매체구분, 기관분류, 광고명, 월만 허용. '
        '질문에 없는 기관이나 매체를 만들어 내면 안 된다. '
        '알 수 없는 질문은 kind=unsupported로 답한다. '
        'JSON 키: kind, years, metric, group, filters, top_n. '
        '상위 몇 개가 명시되지 않으면 top_n=1. CSV 값 자체는 이 단계에서 알 수 없다.'
    )
    response = client.chat.completions.create(
        model='gpt-4.1-mini', temperature=0,
        messages=[{'role':'system','content':instruction},{'role':'user','content':question}],
        response_format={'type':'json_object'},
    )
    plan = json.loads(response.choices[0].message.content)
    return validate_plan(plan, catalogs)


def validate_plan(plan, catalogs):
    if not isinstance(plan, dict):
        raise ValueError('질의 해석 형식이 올바르지 않습니다.')
    kind = plan.get('kind')
    if kind not in {'total','compare','rank','group'}:
        raise ValueError('현재 지원하지 않는 유형의 질문입니다.')
    years = plan.get('years')
    if not isinstance(years,list) or not years or len(years)>5 or any(type(y) is not int or y not in range(2022,2027) for y in years):
        raise ValueError('연도는 2022~2026년 중에서 지정해야 합니다.')
    if kind=='compare' and len(years)!=2:
        raise ValueError('두 연도를 지정한 비교 질문이어야 합니다.')
    if plan.get('metric') not in ('금액','건수'):
        raise ValueError('금액 또는 건수를 지정해야 합니다.')
    group = plan.get('group')
    if kind in ('rank','group') and group not in ('매체명','기관명','매체구분'):
        raise ValueError('순위/집계 대상을 확인할 수 없습니다.')
    filters=plan.get('filters') or {}
    if not isinstance(filters,dict) or any(k not in COLUMNS|{'월'} for k in filters):
        raise ValueError('지원하지 않는 검색 조건이 들어 있습니다.')
    for key,value in filters.items():
        if key=='월':
            if type(value) is not int or value<1 or value>12:
                raise ValueError('월은 1~12 사이여야 합니다.')
        elif not isinstance(value,str) or len(value)>120 or not value.strip():
            raise ValueError('검색 조건이 올바르지 않습니다.')
        elif key=='매체구분' and value not in MEDIA:
            raise ValueError('매체 유형을 확인할 수 없습니다.')
    n=plan.get('top_n',1)
    if type(n) is not int: n=1
    return {'kind':kind,'years':list(dict.fromkeys(years)),'metric':plan['metric'],
            'group':group,'filters':filters,'top_n':min(30,max(1,n)),
            'match_mode':{c:m for c,m in plan.get('match_mode',{}).items() if c in ('기관명','매체명') and m=='exact'}}


def execute_plan(data, plan):
    years = plan['years']
    z = data.loc[data['연도'].isin(years)].copy()
    applied=[]
    for col, wanted in plan['filters'].items():
        if col=='월':
            z=z.loc[z['광고시작일_변환'].dt.month.eq(wanted)]
            applied.append(f'광고시작일 {wanted}월')
            continue
        if col not in z.columns:
            return None, f'원본 데이터에 {col} 열이 없습니다.'
        if col=='매체구분':
            z=z.loc[z[col].astype('string').str.strip().eq(wanted)]
        else:
            if plan.get('match_mode',{}).get(col)=='exact':
                z=z.loc[z[col].astype('string').str.strip().eq(wanted)]
            else:
                z=z.loc[z[col].astype('string').str.contains(wanted,regex=False,case=False,na=False)]
        if plan.get('selected_names',{}).get(col):
            selected=plan['selected_names'][col]
            z=z.loc[z[col].astype('string').isin(selected)]
        applied.append(f'{col}={wanted} (정확히 일치)' if plan.get('match_mode',{}).get(col)=='exact' else (f'{col}에 "{wanted}" 포함' if col!='매체구분' else f'매체구분={wanted}'))
    v='집계금액' if plan['metric']=='금액' else None
    valid=z['집계금액'].notna() if v else pd.Series(True,index=z.index)
    z=z.loc[valid]
    if z.empty:
        return {'answer':'해당 조건에 일치하는 집행내역이 없습니다.','data':pd.DataFrame(), 'source':z,'applied':applied,'years':years},None
    unit='원' if v else '건'
    formatter=lambda x:f'{int(x):,}{unit}'
    agg=lambda d: d['집계금액'].sum() if v else len(d)
    kind=plan['kind']
    result=None
    if kind=='total':
        if len(years)>1:
            values=[(y,agg(z[z['연도']==y])) for y in years]
            result=pd.DataFrame(values,columns=['연도',f'광고{plan["metric"]}'])
            body=' / '.join(f'{y}년 {formatter(value)}' for y,value in values)
            ans=f'연도별 광고 {plan["metric"]}: {body}. 선택 연도 합계 {formatter(agg(z))}.'
        else:
            ans=f'{years[0]}년 조건에 해당하는 {"광고금액은" if v else "광고 건수는"} {formatter(agg(z))}입니다.'
    elif kind=='compare':
        a,b=years
        av=agg(z[z['연도']==a]);bv=agg(z[z['연도']==b]);diff=bv-av
        result=pd.DataFrame({'연도':[a,b],f'광고{plan["metric"]}':[av,bv]})
        pct=(diff/av*100) if av else None
        delta='증가' if diff>0 else '감소' if diff<0 else '변화 없음'
        ans=f'{a}년 {formatter(av)}에서 {b}년 {formatter(bv)}으로 {formatter(abs(diff))} {delta}'
        if pct is not None: ans+=f'했습니다. 증감률은 {pct:+.2f}%입니다.'
        else: ans+='했습니다. 기준 연도가 0이므로 증감률은 계산하지 않습니다.'
    else:
        group=plan['group']
        if group not in z.columns: return None,f'{group} 열이 없습니다.'
        result=z.groupby(group,dropna=False).agg(광고금액=('집계금액','sum'),광고건수=('집계금액','size')).reset_index()
        col='광고금액' if v else '광고건수'
        result=result.sort_values(col,ascending=False).head(plan['top_n'] if kind=='rank' else 30)
        ans=f'선택 조건의 {group}별 {plan["metric"]} 상위 결과입니다. '
        if group=='매체명':
            ans+='※ 매체명에는 온라인 플랫폼·광고 상품 등이 섞여 있을 수 있으므로 이 순위가 언론사 순위와 같다는 뜻은 아닙니다. '
        ans+=' / '.join(f'{str(row[group])}: {formatter(row[col])}' for _,row in result.head(10).iterrows())
    return {'answer':ans, 'data':result,'source':z,'applied':applied,'years':years},None
