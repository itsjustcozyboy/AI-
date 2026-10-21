import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt, font_manager
import numpy as np
from .common import ROOT
from .scenario_model import compare


def render(output,tables,comparison,ranks,freq,scenarios):
    font=ROOT/'assets/NanumGothic-Regular.ttf'
    font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':font_manager.FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'font.size':10})
    folder=output/'figures';folder.mkdir(exist_ok=True)
    footer='2026년 9월 | 서울특별시 OA-12913 | 월·노선·정류장·시간대 카드 집계 (차량 이벤트 아님)'
    def save(fig,name,kind):
        fig.text(.02,.02,footer+'\n'+kind,fontsize=8)
        fig.tight_layout(rect=(0,.11,1,.97));fig.savefig(folder/f'{name}.png',dpi=160);plt.close(fig)
    h=tables['hourly_demand'];fig,ax=plt.subplots(figsize=(10,5))
    ax.plot(h.hour,h.boardings/10000,label='승차');ax.plot(h.hour,h.alightings/10000,label='하차')
    ax.set(xlabel='시간대 (시)',ylabel='월 카드 이용 (만 건)',title='관측 시간대별 승하차 수요');ax.legend()
    save(fig,'01_hourly','관측 수요: 실측 지연이나 정책 효과를 뜻하지 않음')
    ref=ranks[(ranks.experiment=='reference')&(ranks.policy=='scenario_4')].head(10).iloc[::-1]
    fig,ax=plt.subplots(figsize=(11,6));ax.barh(ref.stop_name+' ['+ref.stop_id+']',ref.conditional_daily_saved_seconds/60)
    ax.set(xlabel='조건부 차량 시간 절감 (분/달력일)',title='하차 고려 선택적 정책: 현장 확인 전 후보')
    save(fig,'02_candidates','가정: Base · 뒷문 비율 0.35 · 하차/승차 ≤ 0.5 · 피크 상위 10%')
    fig,axs=plt.subplots(1,3,figsize=(12,5));b,r=np.meshgrid(np.linspace(0,30,101),np.linspace(0,1,101));p={**scenarios['common'],**scenarios['conditions']['Base']}
    for ax,a in zip(axs,[0,10,20]):
        saved=compare(b,a,r,p)[2];im=ax.pcolormesh(b,r,saved,vmin=-60,vmax=60,cmap='RdBu',shading='auto')
        ax.contour(b,r,saved,levels=[0],colors='black',linewidths=.8);ax.set(title=f'가정 하차 {a}명',xlabel='가정 승차 (명/이벤트)',ylabel='뒷문 승차 비율')
    fig.colorbar(im,ax=axs.tolist(),label='절감 초/이벤트 (음수: 지연)',location='top',fraction=.06)
    fig.text(.02,.02,footer+'\n전부 가정한 이벤트 부하와 Base 처리시간 · 검정선: 변화 0 · 관측 이벤트 아님',fontsize=8)
    fig.subplots_adjust(left=.07,right=.97,bottom=.24,top=.69,wspace=.3);fig.savefig(folder/'03_surface.png',dpi=160);plt.close(fig)
    c=comparison[comparison.experiment=='reference'];labels=['현행','제한 뒷문','전 문 확대','피크 선택','하차 고려']
    fig,axs=plt.subplots(1,2,figsize=(11,5));axs[0].bar(labels,c.conditional_daily_saved_seconds/3600);axs[0].axhline(0,color='black',lw=.7)
    axs[0].set(ylabel='조건부 차량 시간 절감 (시간/달력일)',title='전체 분석 모집단 합계')
    axs[1].bar(labels,c.worsened_cells);axs[1].set(ylabel='악화 집계 셀 수',title='차량·승객 피해 비율이 아님')
    for ax in axs:ax.tick_params(axis='x',rotation=25)
    save(fig,'04_policies','가정: reference (Base) · 같은 전체 모집단 · 음수 절감 보존')
    f=freq[freq.policy=='scenario_4'].set_index('stop_id').loc[ref.stop_id]
    fig,ax=plt.subplots(figsize=(11,6));y=np.arange(len(f));ax.hlines(y,f.min_rank,f.max_rank);ax.scatter(f.min_rank,y,label='최고 순위');ax.scatter(f.max_rank,y,label='최저 순위')
    ax.set_yticks(y,ref.stop_name+' ['+ref.stop_id+']');ax.set(xlabel=f'{int(f.experiment_count.iloc[0])}개 탐색 설정 내 순위 (작을수록 앞)',title='기준 상위 10곳의 가정별 순위 범위');ax.legend()
    save(fig,'05_stability','가정 조합 빈도는 확률이 아님 · 운행횟수 상쇄 확인 2회 제외 · 독립 기간 검증 없음')
