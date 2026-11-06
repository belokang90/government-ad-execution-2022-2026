"""정부광고 데이터 분석 + 사실표 기반 RAG 검증 대시보드.
실행: python -m streamlit run app.py
"""
from pathlib import Path
import re
import os
import unicodedata
import pandas as pd
import streamlit as st
import plotly.express as px
from csv_qa import parse_basic, interpret_with_api, execute_plan, validate_plan, resolve_name_request, unsupported_reason
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="정부광고 데이터 저널리즘",page_icon="📊",layout="wide",initial_sidebar_state="expanded")
st.markdown("""<style>
.block-container {padding-top:1.2rem; max-width:1680px; padding-bottom:2rem}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#121b31,#17213b)}
[data-testid="stMetric"] {background:linear-gradient(135deg,#182640,#172035);border:1px solid #34466a;border-radius:15px;padding:15px}
[data-testid="stMetricLabel"] {font-size:.9rem}
[data-testid="stMetricValue"] {font-size:1.65rem}
.stTabs [data-baseweb="tab"] {font-size:.94rem}
div[data-testid="stExpander"] {border:1px solid #34466a;border-radius:12px}
[data-testid="stDataFrame"] {border-radius:10px}
.hero {padding:20px 22px;border:1px solid #324563;border-radius:16px;background:linear-gradient(105deg,#1d3050,#151c33);margin-bottom:18px}
.hero h1 {font-size:2rem;margin:.1rem 0 .35rem;color:#f5f8ff}
.hero p {color:#bac8df;font-size:.94rem;margin:0}
.section-title {font-size:1.16rem;font-weight:700;margin:14px 0}
.notice {padding:11px 14px;border-radius:10px;background:#162e48;border:1px solid #275277;color:#d2e9ff}
.small-muted{color:#aabbd2;font-size:.82rem}
</style>""", unsafe_allow_html=True)

MEDIA = pd.DataFrame([
    (2023,'인터넷',101563,355707854975),(2023,'방송',15109,350198208053),
    (2023,'인쇄',82175,271158495832),(2023,'옥외',28827,253710205604),(2023,'해외',980,35599737552),
    (2025,'인터넷',120966,408478609054),(2025,'방송',14967,333573067329),
    (2025,'인쇄',79687,273208900952),(2025,'옥외',29243,262376990396),(2025,'해외',980,31865013296),
],columns=['연도','매체구분','광고건수','광고총액'])
TOTAL = MEDIA.groupby('연도',as_index=False).agg(광고건수=('광고건수','sum'),광고총액=('광고총액','sum'))
BASE_CONTEXT = "광고시작일이 각 연도 1월 1일~12월 31일인 행만 포함. 총계(VAT포함)를 전액 집계. CSV 행 수를 광고 건수로 표시."
FACTS = [
 {'id':'F-1','category':'전체','question':'정부광고 전체 집행금액은 얼마나 증가했나','content':'2023년 전체 정부광고 광고금액은 1,266,374,502,016원, 2025년은 1,309,502,581,027원이며 43,128,079,011원(3.41%) 증가했다.','source':BASE_CONTEXT},
 {'id':'F-2','category':'인터넷','question':'인터넷 광고 집행금액은 얼마나 증가했나','content':'인터넷 매체 광고금액은 2023년 355,707,854,975원, 2025년 408,478,609,054원으로 14.84% 증가했다. 전체 정부광고 집행금액 중 비중은 28.09%에서 31.19%로 늘었다.','source':BASE_CONTEXT},
 {'id':'F-3','category':'방송','question':'방송 광고 집행금액은 얼마나 감소했나','content':'방송 매체 광고금액은 2023년 350,198,208,053원, 2025년 333,573,067,329원으로 4.75% 감소했다. 전체 비중은 27.65%에서 25.47%로 줄었다.','source':BASE_CONTEXT},
]

@st.cache_data(show_spinner=False, max_entries=12)
def load_csv(data: bytes, name: str):
    import io
    df = None
    for enc in ('utf-8-sig', 'cp949', 'euc-kr'):
        try:
            df = pd.read_csv(io.BytesIO(data), encoding=enc, low_memory=False)
            break
        except UnicodeError:
            continue
    if df is None:
        raise ValueError('파일 인코딩을 해독하지 못했습니다. CSV를 UTF-8 또는 CP949로 저장하세요.')
    required = {'광고시작일','총계(VAT포함)','매체구분'}
    missing=required-set(df.columns)
    if missing:
        raise ValueError('필수 열 누락: ' + ', '.join(sorted(missing)))
    raw_date=df['광고시작일'].astype('string').str.strip().str.replace(r'\.0$', '', regex=True)
    dates=pd.to_datetime(raw_date,format='%Y%m%d',errors='coerce')
    money_str=df['총계(VAT포함)'].astype('string').str.replace(',','',regex=False).str.strip()
    amount=pd.to_numeric(money_str,errors='coerce')
    df['광고시작일_변환']=dates
    df['집계금액']=amount
    return df


def source_year(name: str):
    # unicode NFD filenames supported: year is always first four digits
    m=re.match(r'^(202[2-6])',Path(name).name)
    return int(m.group(1)) if m else None


def prepare_one(data: bytes, filename: str, year: int):
    original=load_csv(data, filename)
    date_invalid=int(original['광고시작일_변환'].isna().sum())
    amount_invalid=int(original['집계금액'].isna().sum())
    valid=original[original['광고시작일_변환'].dt.year.eq(year)].copy()
    valid['연도']=year
    info={'연도':year,'파일':filename,'원본행수':len(original),'집계행수':len(valid),
          '날짜변환오류':date_invalid,'금액변환오류_원본':amount_invalid,
          '집계금액결측':int(valid['집계금액'].isna().sum()),
          '연도외행수':len(original)-len(valid)}
    return valid,info

def fmt(n): return f'{int(n):,}'
def money(n): return f'{n/1e8:,.1f}억 원'
def plot_layout(fig):
    fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',legend_title_text='',margin=dict(l=5,r=5,t=30,b=5))
    return fig

@st.cache_resource(show_spinner=False)
def build_retriever():
    # 실제 문서 검색: 사실ID별 본문을 검색 가능한 형태로 색인한다.
    texts=[f["question"]+' '+f["category"]+' '+f["content"] for f in FACTS]
    v=TfidfVectorizer(analyzer='char',ngram_range=(2,4))
    return v,v.fit_transform(texts)

def find_evidence(question):
    v,m=build_retriever()
    sims=cosine_similarity(v.transform([question]),m)[0]
    return sorted([(FACTS[i],float(sims[i])) for i in range(len(FACTS))],key=lambda z:z[1],reverse=True)

def relevant_fact(question):
    # 원자료에 없는 질문을 다른 사실과 억지로 연결하지 않도록 주제를 좁힌다.
    q=re.sub(r'\s+','',question)
    excluded=['언론사','매체명','기관명','신문사','정책','법률','계약','2024','2026','순위','가장많이받','1위','상위','광고주']
    if any(x in q for x in excluded): return None
    if ('인터넷' in q or '온라인' in q): return FACTS[1]
    if ('방송' in q or 'TV' in q): return FACTS[2]
    if any(x in q for x in ['전체','총액','총금액','총규모','전체광고','정부광고','집행금액']):
        if ('증가' in q or '차이' in q or '비교' in q or '변화' in q or '얼마' in q): return FACTS[0]
    return None

def answer_question(question,use_api=False,api_key=''):
    ranked=find_evidence(question)
    fact=relevant_fact(question)
    if fact is None: return '제공된 자료로는 확인할 수 없습니다.', ranked, []
    if not use_api:
        return f'{fact["content"]} [{fact["id"]}]',ranked,[fact['id']]
    # 검색된 근거만 LLM에 제공. API 기능은 선택사항이며 키는 파일에 저장하지 않는다.
    try:
        from openai import OpenAI
        client=OpenAI(api_key=api_key)
        evidence=f'[{fact["id"]}] {fact["content"]} (집계 기준: {fact["source"]})'
        resp=client.responses.create(model='gpt-4.1-mini',instructions=(
            '너는 정부광고 사실표 검증 챗봇이다. 제공된 근거에 있는 내용만 2문장 이내 한국어로 답하고 '
            '답변 끝에 [F-1]처럼 사실ID를 표시한다. 자료 밖 내용은 "제공된 자료로는 확인할 수 없습니다."만 출력한다.'),
            input=f'근거:\n{evidence}\n질문: {question}')
        ans=resp.output_text.strip()
        ids=set(re.findall(r'\[(F-\d+)\]',ans))
        if ids-{fact['id']} or (not ids and '확인할 수 없습니다' not in ans):
            return '근거ID 검증에 실패해 AI 답변을 표시하지 않습니다.',ranked,[]
        return ans,ranked,sorted(ids)
    except Exception as e:
        return f'API 호출 실패: {type(e).__name__} — API 키 및 네트워크 설정을 확인하세요.',ranked,[]



# ZIP 독립 실행은 앱 폴더의 data/를 우선 사용한다.
# GitHub 통합 저장소에서는 상위 data/의 2022~2026년 원본 CSV를 재사용한다.
APP_DIR = Path(__file__).resolve().parent
OWN_DATA_DIR = APP_DIR / 'data'
SHARED_DATA_DIR = APP_DIR.parent / 'data'
if any(OWN_DATA_DIR.glob('*.csv')):
    DATA_DIR = OWN_DATA_DIR
elif any(SHARED_DATA_DIR.glob('202[2-6]*.csv')):
    DATA_DIR = SHARED_DATA_DIR
else:
    DATA_DIR = OWN_DATA_DIR
    DATA_DIR.mkdir(exist_ok=True)

@st.cache_data(show_spinner=False,max_entries=10)
def read_local(path: str, mtime_ns: int, size: int):
    return Path(path).read_bytes()

sources = {}
errors = []
ambiguous = set()
for f in sorted(DATA_DIR.glob('*.csv')):
    yr = source_year(f.name)
    if yr is None:
        errors.append(f'{f.name}: 파일명 앞부분에서 2022~2026 연도를 찾지 못했습니다.')
    elif yr in ambiguous:
        pass
    elif yr in sources:
        ambiguous.add(yr)
        sources.pop(yr, None)
        errors.append(f'{yr}년도 CSV 파일이 중복되어 자동 집계에서 제외했습니다. 한 개만 남겨 주세요.')
    else:
        try:
            stat = f.stat()
            sources[yr] = (read_local(str(f), stat.st_mtime_ns, stat.st_size), f.name, '로컬 폴더')
        except OSError as exc:
            errors.append(f'{f.name}: 파일 읽기 오류 ({type(exc).__name__})')

st.sidebar.title('📊 정부광고 데이터 허브')
st.sidebar.caption('광고시작일 기준 · VAT 포함')
PAGES = ['🏠 홈','📊 무엇이 달라졌나','📈 매체 흐름','🏛 기관 비교','📰 언론사 찾기',
         '📅 월별 변화','🤖 CSV 근거 질의응답']
page = st.sidebar.radio('분석 메뉴',PAGES,label_visibility='collapsed')
st.sidebar.divider()
with st.sidebar.expander('CSV 연결 상태 및 임시 업로드',expanded=False):
    st.caption('별도 업로드 없이 프로젝트 data 폴더의 CSV를 읽습니다. 업로드 시 같은 연도는 임시 파일로 대체됩니다.')
    uploads = st.file_uploader('연도별 CSV 업로드',type='csv',accept_multiple_files=True)
    st.caption('업로드 파일은 원본 CSV를 덮어쓰지 않습니다.')
for file in uploads or []:
    yr = source_year(file.name)
    if yr is None:
        errors.append(f'{file.name}: 파일명 앞부분에 2022~2026년을 넣어 주세요.')
    else:
        sources[yr] = (file.getvalue(),file.name,'임시 업로드')

loaded, infos = [], []
for yr, (raw, filename, source) in sorted(sources.items()):
    try:
        prepared, info = prepare_one(raw,filename,yr)
        info['연결방식'] = source
        loaded.append(prepared)
        infos.append(info)
    except Exception as exc:
        errors.append(f'{yr}년 {filename}: {type(exc).__name__}: {exc}')
if errors:
    with st.sidebar.expander(f'⚠️ 데이터 경고 {len(errors)}건',expanded=True):
        for msg in errors: st.warning(msg)
if infos:
    st.sidebar.success('연결: '+', '.join(str(v['연도']) for v in infos)+'년')
else:
    st.sidebar.info('CSV가 연결되지 않았습니다. 2023·2025년 확인된 기본 집계만 표시됩니다.')
st.sidebar.caption('실제 광고비 지급일이 아닌 광고시작일을 기준으로 집계합니다.')
st.sidebar.info('2026년 자료: 2026년 9월 30일 기준 공개 파일. 파일 안에는 10~12월 광고시작일도 일부 포함됩니다.')

if loaded:
    ALL = pd.concat(loaded,ignore_index=True)
    # For every year, retain only rows starting in that file's year (prepare_one handles this).
    ALL['매체구분'] = ALL['매체구분'].astype('string').str.strip()
    if '기관명' in ALL.columns: ALL['기관명'] = ALL['기관명'].astype('string').str.strip()
    if '매체명' in ALL.columns: ALL['매체명'] = ALL['매체명'].astype('string').str.strip()
    YEAR_LIST = sorted(ALL['연도'].unique().tolist())
else:
    ALL = None
    YEAR_LIST = [2023,2025]

# 원본의 파일 제공 기준일과 미래 광고시작일 기록을 구분한다.
if ALL is not None and 2026 in YEAR_LIST:
    future_starts = int(((ALL['연도']==2026) & (ALL['광고시작일_변환'] > pd.Timestamp('2026-09-30'))).sum())
    st.caption(f'자료 안내 · **2026년 파일은 2026.09.30 기준 공개본**이며 그 안에 10~12월 광고시작일 기록이 {future_starts:,}건 포함돼 있습니다. 2026년 금액은 연간 확정 집계가 아닙니다.')

NUM = '집계금액'
METRIC_NAMES={'금액':'광고총액','건수':'광고건수'}
def fmt_amount(n):
    return f'{float(n)/1e8:,.1f}억 원'
def fmt_count(n):
    return f'{int(n):,}건'
def display_column(mode):
    return '표시값'
def axis_title(mode):
    return '광고금액(억 원)' if mode=='금액' else '광고 건수(건)'
def to_display_value(series, mode):
    return series / 1e8 if mode=='금액' else series
def fmt_text_value(v, mode):
    return f'{v:,.1f}억' if mode=='금액' else f'{int(v):,}건'
def year_color_map(years):
    palette=['#3B82F6','#CBD5E1','#8B5CF6','#22C55E','#F59E0B']
    return {str(y):palette[i % len(palette)] for i,y in enumerate(sorted(years))}
def fmt_delta(n, mode='금액'):
    s = '+' if n>0 else ''
    return s+(fmt_amount(n) if mode=='금액' else fmt_count(n))
def rel_change(a,b):
    return (b-a)/a*100 if a else None
def trend(a,b):
    return '증가' if b>a else ('감소' if b<a else '동일')
def header(title,sub):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>',unsafe_allow_html=True)
def summary(df,by=None):
    if by:
        return df.groupby(by,dropna=False).agg(광고총액=(NUM,'sum'),광고건수=(NUM,'size')).reset_index()
    return {'금액':df[NUM].sum(),'건수':len(df)}
def get_year_agg(df):
    return df.groupby('연도',as_index=False).agg(광고총액=(NUM,'sum'),광고건수=(NUM,'size')).sort_values('연도')
def normalize_search(text):
    """Unicode NFC and whitespace/punctuation-insensitive substring search."""
    t = unicodedata.normalize('NFKC', str(text)).casefold()
    return ''.join(ch for ch in t if ch.isalnum())

@st.cache_data(show_spinner=False, max_entries=6)
def media_name_index(names):
    return [(name, normalize_search(name)) for name in names]

def match_media_names(df, term):
    """Match original 매체명 variants; never merge distinct outlets automatically."""
    if not term.strip() or '매체명' not in df.columns:
        return df
    needle = normalize_search(term)
    if not needle:
        return df.iloc[0:0]
    values = tuple(sorted(df['매체명'].dropna().astype(str).unique()))
    hits = [name for name, key in media_name_index(values) if needle in key]
    return df[df['매체명'].isin(hits)]

def filtered(df,media=None,orgcat=None,inst=None,outlet=None,months=None):
    z=df
    if media and media!='전체': z=z[z['매체구분']==media]
    if orgcat and orgcat!='전체' and '기관분류' in z: z=z[z['기관분류'].astype(str)==orgcat]
    if inst and '기관명' in z: z=z[z['기관명'].str.contains(inst,case=False,regex=False,na=False)]
    if outlet and '매체명' in z: z=match_media_names(z,outlet)
    if months:
        z=z[z['광고시작일_변환'].dt.month.isin(months)]
    return z

def selectable_values(col):
    if ALL is None or col not in ALL: return ['전체']
    vals=sorted({str(x) for x in ALL[col].dropna().unique() if str(x).strip()})
    return ['전체']+vals

def media_chart(compare, measure='금액'):
    if compare.empty:
        return
    val = METRIC_NAMES[measure]
    df = compare.copy()
    df['연도'] = df['연도'].astype(str)
    df['표시값'] = to_display_value(df[val], measure)
    years = df['연도'].unique().tolist()
    fig = px.bar(
        df, x='매체구분', y='표시값', color='연도', barmode='group', text='표시값',
        category_orders={'매체구분':['인터넷','방송','인쇄','옥외','해외']},
        color_discrete_map=year_color_map([int(y) for y in years]),
        labels={'매체구분':'매체 유형','표시값':axis_title(measure), '연도':'연도'}
    )
    fig.update_xaxes(type='category')
    fig.update_yaxes(rangemode='tozero')
    fig.update_traces(
        texttemplate='%{text:,.1f}억' if measure=='금액' else '%{text:,.0f}건',
        textposition='outside', cliponaxis=False,
        customdata=df[[val]].to_numpy(),
        hovertemplate='<b>%{x}</b><br>연도=%{fullData.name}<br>' +
                      ('광고금액=%{customdata[0]:,.0f}원' if measure=='금액' else '광고 건수=%{customdata[0]:,.0f}건') + '<extra></extra>'
    )
    st.plotly_chart(plot_layout(fig), use_container_width=True)

def selected_two_years(prefix='cmp'):
    default_a=2023 if 2023 in YEAR_LIST else YEAR_LIST[0]
    default_b=2025 if 2025 in YEAR_LIST else YEAR_LIST[-1]
    a_idx=YEAR_LIST.index(default_a);b_idx=YEAR_LIST.index(default_b)
    x1,x2=st.columns(2)
    a=x1.selectbox('기준 연도',YEAR_LIST,index=a_idx,key=prefix+'_a')
    b=x2.selectbox('비교 연도',YEAR_LIST,index=b_idx,key=prefix+'_b')
    return a,b

def data_warnings(years):
    if 2026 in years:
        st.info('2026년은 **2026년 9월 30일 기준 공개 파일**입니다. 다만 원본에 광고시작일이 10~12월인 내역도 일부 포함됩니다. 따라서 2026년 집계는 확정 연간 통계가 아니며 다른 연도와 같은 범위라고 해석하지 마세요.')
    if infos:
        damaged=[i for i in infos if i['연도'] in years and (i['집계금액결측'] or i['날짜변환오류'])]
        if damaged:st.warning('선택 연도에 날짜/금액 변환 오류가 있습니다. 「CSV 검증」을 확인하세요.')

def data_required():
    if ALL is not None:return True
    st.warning('이 분석은 CSV 파일이 필요합니다. 프로그램의 data 폴더에 2022~2026년도 CSV를 복사해 주세요. 기존 2023·2025년 검증 수치는 홈에서 확인할 수 있습니다.')
    return False

def readable_number_table(df):
    """표시할 때만 천 단위 쉼표를 넣는다. 원본/계산/CSV 자료형은 유지."""
    column_names = {
        '광고총액', '광고건수', '광고금액', '집계금액', '증감',
        '원본행수', '집계행수', '날짜변환오류', '금액변환오류_원본',
        '집계금액결측', '연도외행수',
    }
    for column in df.columns:
        if str(column).endswith('년') and str(column)[:4].isdigit():
            column_names.add(column)
    formats = {
        col: (lambda v: f'{v:,.0f}' if pd.notna(v) else '—')
        for col in df.columns if col in column_names and pd.api.types.is_numeric_dtype(df[col])
    }
    return df.style.format(formats) if formats else df

def show_source_table(z):
    cols=[v for v in ['연도','기관분류','기관명','매체구분','매체명','광고명','광고시작일','광고종료일','집계금액'] if v in z.columns]
    with st.expander('선택한 조건의 광고 집행내역 확인',expanded=False):
        st.caption(f'조건에 맞는 행: {len(z):,}건 · 화면에는 선두 200건만 표시')
        st.dataframe(readable_number_table(z[cols].head(200)),use_container_width=True,hide_index=True)
        if len(z)>0:
            export=z[cols].copy()
            st.download_button('현재 조건의 집행내역 CSV 다운로드',export.to_csv(index=False).encode('utf-8-sig'),
                               file_name='정부광고_선택조건_집행내역.csv',mime='text/csv')

if page=='🏠 홈':
    header('정부광고 데이터 분석 대시보드','2022~2026년 · 광고시작일 기준 · VAT 포함 · 2026년 자료: 2026.09.30 기준 파일')
    if ALL is None:
        st.info('원본 CSV가 아직 연결되지 않았습니다. 아래에는 기존에 검증한 2023년·2025년 숫자만 표시합니다.')
        k1,k2,k3=st.columns(3)
        k1.metric('2023년 집행금액',fmt_amount(1266374502016))
        k2.metric('2025년 집행금액',fmt_amount(1309502581027))
        k3.metric('2023 → 2025년 변화','+3.41%')
        media_chart(MEDIA.assign(광고총액=MEDIA['광고총액']), '금액')
    else:
        totals=get_year_agg(ALL)
        k1,k2,k3=st.columns(3)
        k1.metric('연결 연도 전체 광고금액',fmt_amount(totals['광고총액'].sum()))
        k2.metric('연결 연도 전체 광고 건수',fmt_count(totals['광고건수'].sum()))
        k3.metric('연도 연결 현황',f'{len(totals)}개 연도')
        data_warnings(YEAR_LIST)
        left,right=st.columns([1.35,1])
        with left:
            st.subheader('연도별 광고금액')
            view = totals.copy()
            view['연도'] = view['연도'].astype(str)
            view['표시값'] = view['광고총액'] / 1e8
            fig=px.bar(view,x='연도',y='표시값',text='표시값',color_discrete_sequence=['#6aaaff'], labels={'표시값':'광고금액(억 원)','연도':'연도'})
            fig.update_traces(texttemplate='%{text:,.1f}억',textposition='outside',cliponaxis=False, customdata=view[['광고총액']].to_numpy(), hovertemplate='<b>%{x}</b><br>광고금액=%{customdata[0]:,.0f}원<extra></extra>')
            fig.update_xaxes(type='category');fig.update_yaxes(rangemode='tozero')
            st.plotly_chart(plot_layout(fig),use_container_width=True)
        with right:
            st.subheader('매체별 광고 비중')
            y=st.selectbox('분석 연도',YEAR_LIST,index=len(YEAR_LIST)-1,key='home_y')
            m=summary(ALL[ALL['연도']==y],['매체구분'])
            if m['광고총액'].sum():
                st.plotly_chart(plot_layout(px.pie(m,names='매체구분',values='광고총액',hole=.55)),use_container_width=True)
        st.subheader('매체별 광고금액')
        year=st.selectbox('매체별 금액을 볼 연도',YEAR_LIST,index=len(YEAR_LIST)-1,key='home_media_year')
        m=summary(ALL[ALL['연도']==year],['매체구분']).sort_values('광고총액',ascending=False)
        cards=st.columns(max(1,min(len(m),5)))
        for i,(_,r) in enumerate(m.head(5).iterrows()):
            cards[i].metric(str(r['매체구분']),fmt_amount(r['광고총액']))
        st.caption('표시하는 매체별 금액은 선택한 단일 연도의 집계값입니다. 여러 연도를 단순 합산한 수치가 아닙니다.')
    st.markdown('---')
    st.markdown('**이용 안내** · 「무엇이 달라졌나」에서 두 연도를 자유롭게 비교하고 기관·매체명 조건을 적용할 수 있습니다. 기존 F-1~F-3은 과제용 확정 사실표로 별도 보존합니다.')

elif page=='📊 무엇이 달라졌나':
    header('무엇이 달라졌나','비교할 두 연도와 매체·기관·언론사 조건을 선택하면 수치와 그래프가 함께 갱신됩니다.')
    if data_required():
        c1,c2,c3,c4,c5=st.columns([1,1,1.05,1.15,1.15])
        default_a=YEAR_LIST.index(2023) if 2023 in YEAR_LIST else 0
        default_b=YEAR_LIST.index(2025) if 2025 in YEAR_LIST else len(YEAR_LIST)-1
        ya=c1.selectbox('기준 연도',YEAR_LIST,index=default_a)
        yb=c2.selectbox('비교 연도',YEAR_LIST,index=default_b)
        med=c3.selectbox('매체 유형',selectable_values('매체구분'))
        cat=c4.selectbox('기관분류',selectable_values('기관분류'))
        mode=c5.selectbox('비교 지표',['금액','건수'])
        t1,t2=st.columns(2)
        inst=t1.text_input('기관명 (포함 검색)',placeholder='미입력 시 전체 기관')
        outlet=t2.text_input('매체명·언론사명 (포함 검색)',placeholder='미입력 시 전체 매체')
        if ya==yb:
            st.warning('서로 다른 두 연도를 선택해 주세요.')
        else:
            data_warnings([ya,yb])
            z=filtered(ALL[ALL['연도'].isin([ya,yb])],med,cat,inst,outlet)
            va=summary(z[z['연도']==ya]);vb=summary(z[z['연도']==yb]); key='금액' if mode=='금액' else '건수'
            base,tar=va[key],vb[key]
            diff=tar-base;rate=rel_change(base,tar)
            k1,k2,k3,k4=st.columns(4)
            formatter=fmt_amount if mode=='금액' else fmt_count
            k1.metric(f'{ya}년 {mode}',formatter(base))
            k2.metric(f'{yb}년 {mode}',formatter(tar))
            k3.metric('증감',fmt_delta(diff,mode))
            k4.metric('증감률',f'{rate:+.2f}%' if rate is not None else '계산 불가')
            if not len(z):
                st.warning('선택 조건에 해당하는 데이터가 없습니다.')
            else:
                if base==0: st.info('기준 연도 집계값이 0이므로 증감률을 계산하지 않습니다.')
                l,r=st.columns([.8,1.2])
                with l:
                    st.subheader('전체 비교')
                    totals=get_year_agg(z)
                    target_col=METRIC_NAMES[mode]
                    totals_view = totals.copy()
                    totals_view['연도'] = totals_view['연도'].astype(str)
                    totals_view['표시값'] = to_display_value(totals_view[target_col], mode)
                    fig=px.bar(
                        totals_view, x='연도', y='표시값', color='연도', text='표시값',
                        color_discrete_map=year_color_map([int(v) for v in totals_view['연도']]),
                        labels={'표시값':axis_title(mode), '연도':'연도'}
                    )
                    fig.update_xaxes(type='category')
                    fig.update_yaxes(rangemode='tozero')
                    fig.update_traces(
                        texttemplate='%{text:,.1f}억' if mode=='금액' else '%{text:,.0f}건',
                        textposition='outside', cliponaxis=False,
                        customdata=totals_view[[target_col]].to_numpy(),
                        hovertemplate='<b>%{x}</b><br>' +
                                      ('광고금액=%{customdata[0]:,.0f}원' if mode=='금액' else '광고 건수=%{customdata[0]:,.0f}건') + '<extra></extra>'
                    )
                    st.plotly_chart(plot_layout(fig),use_container_width=True)
                with r:
                    st.subheader('매체 유형별 비교')
                    by_media=summary(z,['연도','매체구분'])
                    media_chart(by_media,mode)
                st.subheader('매체별 상세 비교')
                by_media=summary(z,['연도','매체구분'])
                values=by_media.pivot(index='매체구분',columns='연도',values=METRIC_NAMES[mode]).fillna(0)
                for y in [ya,yb]:
                    if y not in values:values[y]=0
                detailed=values[[ya,yb]].copy()
                detailed.columns=[f'{ya}년',f'{yb}년']
                detailed['증감']=detailed[f'{yb}년']-detailed[f'{ya}년']
                detailed['증감률(%)']=detailed.apply(lambda r:rel_change(r[f'{ya}년'],r[f'{yb}년']),axis=1)
                st.dataframe(readable_number_table(detailed),hide_index=False,use_container_width=True)
                st.markdown('#### 선택 조건에서 확인되는 변화')
                msg=(f'{ya}년 대비 {yb}년 {mode}은 {formatter(abs(diff))} '
                     f'{trend(base,tar)}했습니다.' if diff else f'{ya}년과 {yb}년의 {mode}은 동일합니다.')
                st.info(msg+' 원인이나 정책적 의미는 이 집계만으로 단정하지 않습니다.')
                show_source_table(z)

elif page=='📈 매체 흐름':
    header('매체 흐름','인터넷·방송·인쇄·옥외·해외 매체별 변화와 구성비를 확인합니다.')
    if data_required():
        chosen=st.multiselect('분석 연도',YEAR_LIST,default=YEAR_LIST)
        mode=st.radio('지표',['금액','건수'],horizontal=True,key='media_mode')
        if chosen:
            z=ALL[ALL['연도'].isin(chosen)]
            data_warnings(chosen)
            data=summary(z,['연도','매체구분'])
            st.subheader('매체 유형별 연도 비교')
            st.caption('각 매체 유형 안에서 선택한 연도를 나란히 표시합니다. 누적 합계가 아닙니다.')
            media_chart(data,mode)
            st.subheader('연도별 매체 구성비')
            y=st.selectbox('기준 연도',chosen,key='media_pct')
            part=data[data['연도']==y]
            st.plotly_chart(plot_layout(px.pie(part,names='매체구분',values=METRIC_NAMES[mode],hole=.5)),use_container_width=True)
            st.subheader('매체별 집계표')
            st.dataframe(readable_number_table(data.sort_values(['연도','매체구분'])), use_container_width=True, hide_index=True)
        else:st.warning('연도를 선택해 주세요.')

elif page=='🏛 기관 비교':
    header('기관 비교','집행기관과 기관분류별 정부광고를 비교합니다.')
    if data_required():
        yr=st.multiselect('연도',YEAR_LIST,default=YEAR_LIST)
        cat=st.selectbox('기관분류',selectable_values('기관분류'),key='agency_cat')
        term=st.text_input('기관명 검색',placeholder='예: 문화체육관광부',key='agency_term')
        z=filtered(ALL[ALL['연도'].isin(yr)],orgcat=cat,inst=term)
        if '기관명' in z:
            group=summary(z,['기관명']).sort_values('광고총액',ascending=False)
            st.metric('선택 조건 전체 집행금액',fmt_amount(z[NUM].sum()))
            st.subheader('기관별 광고금액 상위 20개')
            top=group.head(20)
            st.plotly_chart(plot_layout(px.bar(top,x='광고총액',y='기관명',orientation='h',
                  labels={'광고총액':'광고금액(원)','기관명':'기관'}).update_layout(yaxis={'categoryorder':'total ascending'})),use_container_width=True)
            st.dataframe(readable_number_table(group),use_container_width=True,hide_index=True)
            show_source_table(z)
        else:st.warning('기관명 열이 원본에 없습니다.')

elif page=='📰 언론사 찾기':
    header('언론사·매체 찾기','CSV의 매체명 열에서 검색합니다. 띄어쓰기·괄호·일부 기호 차이는 무시하되 다른 매체를 임의로 합치지 않습니다.')
    if data_required():
        term=st.text_input('매체명 검색',placeholder='예: 한겨레 / 한겨레신문 / 한국일보',key='outlet_term')
        yr=st.multiselect('분석 연도',YEAR_LIST,default=YEAR_LIST,key='outlet_year')
        if not yr:
            st.warning('분석할 연도를 하나 이상 선택해 주세요.')
        elif not term.strip():
            st.info('매체명 일부를 입력하면 해당 문자열이 포함된 원본 기록만 검색합니다.')
        else:
            scope=ALL[ALL['연도'].isin(yr)]
            if '매체명' not in scope.columns:
                st.error('CSV에 매체명 열이 없습니다.')
            else:
                z=match_media_names(scope,term)
                if z.empty:
                    st.warning('선택한 연도에서 일치하는 매체명을 확인하지 못했습니다. 원본에 다른 명칭이 사용됐을 수도 있습니다.')
                    st.caption('검색 결과 없음은 해당 언론사에 정부광고가 없었다는 확정적인 의미가 아닙니다.')
                    # Fuzzy suggestions are labels, not automatic conflation.
                    import difflib
                    names=scope['매체명'].dropna().astype(str).unique().tolist()
                    candidates=difflib.get_close_matches(term,names,n=12,cutoff=0.3)
                    if candidates:
                        st.write('원본 매체명에서 비슷한 표기 (직접 확인용)')
                        st.write(' · '.join(candidates))
                else:
                    st.metric('검색 결과 광고금액 합계',fmt_amount(z[NUM].sum()))
                    st.metric('검색된 집행내역 행 수',fmt_count(len(z)))
                    actual=sorted(z['매체명'].dropna().astype(str).unique())
                    st.caption(f'원본에서 실제로 일치한 매체명 {len(actual)}종: '+', '.join(actual[:20]) + (' 외' if len(actual)>20 else ''))
                    totals=get_year_agg(z)
                    view=totals.copy()
                    view['연도']=view['연도'].astype(str)
                    view['표시값']=view['광고총액']/1e8
                    fig=px.bar(view,x='연도',y='표시값',text='표시값',labels={'표시값':'광고금액(억 원)'},
                               color_discrete_sequence=['#60A5FA'])
                    fig.update_traces(texttemplate='%{text:,.1f}억',textposition='outside',cliponaxis=False)
                    fig.update_xaxes(type='category');fig.update_yaxes(rangemode='tozero')
                    st.plotly_chart(plot_layout(fig),use_container_width=True)
                    group=summary(z,['연도','매체명']).sort_values(['연도','광고총액'],ascending=[True,False])
                    st.dataframe(readable_number_table(group),use_container_width=True,hide_index=True)
                    st.caption('매체명 표기가 다른 경우에도 검색은 할 수 있지만 실제 동일 법인·언론사인지는 원자료로 확인해야 합니다.')
                    show_source_table(z)

elif page=='📅 월별 변화':
    header('월별 변화','광고시작일을 기준으로 월별 집행금액과 건수를 비교합니다. 2026년은 2026.09.30 기준 공개 파일입니다.')
    if data_required():
        yrs=st.multiselect('연도',YEAR_LIST,default=YEAR_LIST,key='monthly_year')
        med=st.selectbox('매체 유형',selectable_values('매체구분'),key='monthly_med')
        metric=st.radio('지표',['금액','건수'],horizontal=True,key='monthly_metric')
        if not yrs:
            st.warning('연도를 하나 이상 선택해 주세요.')
        else:
            z=filtered(ALL[ALL['연도'].isin(yrs)],media=med)
            if z.empty:
                st.warning('선택 조건에 해당하는 집행내역이 없습니다.')
            else:
                col=METRIC_NAMES[metric]
                monthly=summary(z.assign(월=z['광고시작일_변환'].dt.month),['연도','월'])
                # Real data's last observed advertising start month for each file-year.
                # Past it, data coverage is unknown rather than monetary zero.
                coverage=ALL.groupby('연도')['광고시작일_변환'].max().dt.month.to_dict()
                rows=[]
                for year in sorted(yrs):
                    last=int(coverage.get(year,0))
                    for month in range(1,13):
                        rows.append({'연도':year,'월':month,
                                     '자료상태':'미수록/미확인' if month>last else '집계 범위 내'})
                full=pd.DataFrame(rows).merge(monthly,on=['연도','월'],how='left')
                for field in ['광고총액','광고건수']:
                    inside=full['자료상태'].eq('집계 범위 내')
                    full.loc[inside,field]=full.loc[inside,field].fillna(0)
                    # Outside coverage intentionally remains NaN; never convert to zero.
                full['연도명']=full['연도'].astype(str)
                full['표시값']=to_display_value(full[col],metric)
                fig=px.line(full,x='월',y='표시값',color='연도명',markers=True,
                            color_discrete_map=year_color_map(yrs),
                            labels={'월':'월','표시값':axis_title(metric),'연도명':'연도'})
                fig.update_xaxes(dtick=1,range=[0.7,12.3],tickvals=list(range(1,13)),ticktext=[f'{m}월' for m in range(1,13)])
                fig.update_traces(connectgaps=False,
                                  hovertemplate='월=%{x}월<br>'+ ('광고금액=%{y:,.1f}억 원' if metric=='금액' else '광고 건수=%{y:,.0f}건')+'<extra>%{fullData.name}년</extra>')
                st.plotly_chart(plot_layout(fig),use_container_width=True)
                if 2026 in yrs:
                    last=coverage.get(2026,0)
                    st.info(f'2026년 파일의 제공 기준일은 2026.09.30이지만 광고시작일은 {last}월까지 일부 기재되어 있습니다. 10~12월 값은 9월 30일 기준 파일에 수록된 미래 시작 광고 기록일 수 있으며 연말 확정 집계로 해석하면 안 됩니다.')
                st.caption('자료상태는 원본에 기록된 광고시작일의 최댓값을 이용한 표시이며, 공식 제공 기준일(2026.09.30)과 다릅니다. 미기록·미공개 기간의 총액을 0원이라고 단정하지 않습니다.')
                table=full[['연도','월','자료상태','광고총액','광고건수']].copy()
                st.subheader('월별 집계표')
                st.dataframe(readable_number_table(table),use_container_width=True,hide_index=True)
                data_warnings(yrs)

else:
    header('CSV 근거 질의응답',
           '2022~2026년 정부광고 원본 CSV의 실제 행을 검색하고 계산합니다. 답변에는 조건, 집계 건수, 근거 데이터가 함께 표시됩니다.')
    if data_required():
        st.info('2026년은 **2026.09.30 기준 공개 CSV**입니다. 파일에는 광고시작일이 10~12월인 기록도 일부 포함돼 있으므로 확정 연간 집계로 해석하지 마세요.')
        with st.expander('질문 방법 안내', expanded=False):
            st.write('**기본 모드 (무료)**: 연도별 광고비와 건수, 두 연도의 차이, 기관·매체별 순위를 계산합니다. 예를 들어 “2025년 경기도 광고비”라고 물어볼 수 있습니다.')
            st.write('**AI 해석 모드 (유료 API 선택 시)**: 질문이 길거나 복잡할 때 AI가 검색 조건을 정하도록 돕습니다. 실제 금액과 건수는 AI가 추측하지 않고 원본 CSV로 계산합니다.')
            st.write('**이름 검색**: “경기도”처럼 여러 기관이 검색되면 어떤 기관을 볼지 먼저 선택합니다. “경기도청”만 볼 수도 있고, 이름에 “경기도”가 들어간 기관을 합쳐 볼 수도 있습니다.')
            st.write('이름을 찾지 못하면 전체 광고비를 대신 알려주지 않습니다. 검색 범위를 확인한 다음 계산합니다.')
            st.write('**답할 수 없는 질문**: 광고 매체를 선정한 이유나 예산 편성 사유 등 CSV에 없는 정보는 추측하지 않고 확인할 수 없다고 안내합니다.')
            st.caption('참고: 기관 이름에 “경기도”가 포함되는 것과 경기도에 위치한 모든 기관을 찾는 것은 서로 다릅니다.')
            ai_enabled = st.checkbox('AI 질문 해석 사용 (OpenAI API 키가 필요하고 사용료가 발생할 수 있음)', value=False, key='qa_ai_enabled')
            qa_api_key = st.text_input('OpenAI API 키 (이 세션에서만 사용)', type='password', key='qa_api_key') if ai_enabled else ''
        example_questions = [
            '2025년 정부광고 총액은 얼마인가요?',
            '2023년과 2025년 인터넷 광고금액은 얼마나 달라졌나요?',
            '2025년 광고를 가장 많이 받은 언론사는 어디인가요?',
            '2024년 방송 광고 건수는 몇 건인가요?',
            '2025년 매체 유형별 광고금액 현황은?',
        ]
        example = st.selectbox('질문 예시', ['직접 입력']+example_questions, key='csv_qa_example')
        question=st.text_input('원본 CSV에 질문하기', value='' if example=='직접 입력' else example,
                               placeholder='예: 2025년 광고를 가장 많이 받은 언론사는?', key='csv_qa_question')
        if st.button('CSV에서 조회·계산',type='primary',disabled=not question.strip(),key='csv_qa_submit'):
            st.session_state.pop('csv_qa_pending',None)
            st.session_state.pop('csv_qa_result',None)
            try:
                catalog={col:ALL[col].dropna().unique().tolist() for col in ('기관명','매체명') if col in ALL.columns}
                reason_error = unsupported_reason(question)
                if reason_error:
                    # AI 모드에서도 CSV에 없는 사유 질문은 API 호출 없이 안내한다.
                    plan=None; err=reason_error
                elif ai_enabled:
                    if not qa_api_key:
                        plan=None;err='AI 해석 모드를 사용하려면 API 키를 입력해 주세요.'
                    else:
                        plan=interpret_with_api(question,qa_api_key,catalog)
                        plan,err=resolve_name_request(question,plan,catalog)
                else:
                    plan,err=parse_basic(question,catalog)
                if err:
                    st.session_state['csv_qa_result']={'error':err,'question':question}
                elif plan.get('pending_name'):
                    st.session_state['csv_qa_pending']={'question':question,'plan':plan}
                else:
                    plan=validate_plan(plan,catalog)
                    result,err=execute_plan(ALL,plan)
                    st.session_state['csv_qa_result']={'error':err,'question':question,'plan':plan,'result':result}
            except Exception as exc:
                st.session_state['csv_qa_result']={'error':f'질문을 처리하지 못했습니다 ({type(exc).__name__}): {exc}', 'question':question}
        pending=st.session_state.get('csv_qa_pending')
        if pending:
            info=pending['plan']['pending_name']
            col, term, names=info['column'],info['term'],info['matches']
            st.warning(f'“{term}”과 연결되는 {col}이(가) {len(names):,}개 있습니다. 어떤 범위를 계산할까요?')
            selection=st.radio('검색 범위 선택',
                ['기관/매체 이름에 들어간 항목 전체 합산','목록에서 하나만 선택','목록에서 여러 개 직접 선택'],
                index=1,key='qa_selection_type')
            chosen=[]
            if selection=='목록에서 하나만 선택':
                chosen=[st.selectbox('정확한 이름 선택',names,key='qa_exact_name')]
            elif selection=='목록에서 여러 개 직접 선택':
                chosen=st.multiselect('합산할 이름 선택',names,key='qa_multi_names')
            with st.expander(f'검색된 실제 {col} 이름 {len(names):,}개 확인',expanded=False):
                st.dataframe(pd.DataFrame({col:names}),hide_index=True,use_container_width=True)
            st.caption('이름에 해당 글자가 들어간다고 해서 같은 기관이나 법인인 것은 아닙니다.')
            if st.button('선택한 범위로 계산',key='qa_confirm_name',disabled=selection=='목록에서 여러 개 직접 선택' and not chosen):
                plan=pending['plan'].copy()
                plan.pop('pending_name',None)
                plan['filters']=dict(plan['filters'])
                plan['match_mode']=dict(plan.get('match_mode',{}))
                if selection=='기관/매체 이름에 들어간 항목 전체 합산':
                    plan['filters'][col]=term
                elif len(chosen)==1:
                    plan['filters'][col]=chosen[0]
                    plan['match_mode'][col]='exact'
                else:
                    plan['filters'][col]=term
                    plan['selected_names']={col:chosen}
                try:
                    plan=validate_plan(plan,{}) if 'selected_names' not in plan else plan
                    result,err=execute_plan(ALL,plan)
                    st.session_state['csv_qa_result']={'error':err,'question':pending['question'],'plan':plan,'result':result}
                    st.session_state.pop('csv_qa_pending',None)
                    st.rerun()
                except Exception as exc:
                    st.error(f'선택 범위를 계산하지 못했습니다: {exc}')
        saved=st.session_state.get('csv_qa_result')
        if saved:
            st.markdown('### 조회 결과')
            st.caption('질문: '+saved['question'])
            if saved.get('error'):
                st.warning(saved['error'])
            else:
                plan=saved['plan'];result=saved['result']
                with st.expander('해석한 검색·집계 조건',expanded=True):
                    st.json({'질의 유형':plan['kind'], '분석 연도':plan['years'],
                             '기준 지표':plan['metric'],'집계 대상':plan.get('group'),
                             '추가 조건':plan['filters']}, expanded=False)
                st.success(result['answer'])
                st.caption(f'근거: data 폴더의 2022~2026 정부광고 집행내역 CSV · 광고시작일이 선택 연도에 해당하는 기록 · 총계(VAT포함) · 해당 조건 원본 {len(result["source"]):,}행')
                if 2026 in plan['years']:
                    data_warnings([2026])
                if result['data'] is not None and len(result['data']):
                    st.subheader('계산 결과표')
                    st.dataframe(readable_number_table(result['data']),hide_index=True,use_container_width=True)
                with st.expander('근거가 된 원본 광고 집행내역 (최대 200건 미리보기)'):
                    src=result['source']
                    cols=[c for c in ['연도','기관분류','기관명','매체구분','매체명','광고명','광고시작일','집계금액'] if c in src.columns]
                    st.dataframe(readable_number_table(src[cols].head(200)),use_container_width=True,hide_index=True)
                    if len(src):
                        # 필요한 열만 전송. 표시 다운로드는 원본 파일 자체를 변경하지 않는다.
                        st.download_button('근거 행 CSV 내려받기',data=src[cols].to_csv(index=False).encode('utf-8-sig'),
                                           file_name='질의응답_근거집행내역.csv',mime='text/csv')
                st.caption('검색·분석 결과는 정부광고 CSV의 입력 값과 해당 집계 조건에 의존합니다. 특정 매체가 실제 동일 법인인지 또는 집행의 적정성은 별도 검증이 필요합니다.')
