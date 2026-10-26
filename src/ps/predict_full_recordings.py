"""Continuous offline prediction on complete validation or test recordings. Python >=3.9."""
import argparse, csv, hashlib, json
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import torch
from torch import nn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

class BirdCNN(nn.Module):
    def __init__(self):
        super().__init__(); layers=[]
        for a,b in ((1,16),(16,32),(32,64)):
            layers += [nn.Conv2d(a,b,3,padding=1,bias=False),nn.BatchNorm2d(b),nn.ReLU(),nn.MaxPool2d(2)]
        self.features=nn.Sequential(*layers)
        self.head=nn.Sequential(nn.AdaptiveAvgPool2d((4,1)),nn.Flatten(),nn.Dropout(.3),nn.Linear(256,1))
    def forward(self,x):return self.head(self.features(x)).squeeze(1)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def dump(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def write_csv(path,rows,fields):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def overlap(a,b,intervals):
    return sum(max(0.,min(b,e)-max(a,s)) for s,e in intervals)

def feature(y,c):
    mel=librosa.feature.melspectrogram(y=y,sr=c['sr'],n_fft=c['n_fft'],hop_length=c['hop_length'],
        n_mels=c['n_mels'],center=c['center'],pad_mode=c['pad_mode'],window=c['window'],
        power=c['power'],fmin=c['fmin'],fmax=c['fmax'],htk=c['htk'],norm=c['norm'])
    if c['db_ref']!='max':raise ValueError('不支持此db_ref')
    return librosa.power_to_db(mel,ref=np.max,top_db=c['power_top_db']).astype(np.float32)

def merge_events(rows,threshold,min_hits):
    # Only consecutive positive windows belong to one run. Any negative resets it.
    events=[];run=[]
    def finish():
        if len(run)>=min_hits:
            events.append(dict(audio_path=run[0]['audio_path'],record_id=run[0]['record_id'],
                start_sec=run[0]['start_sec'],end_sec=run[-1]['end_sec'],
                trigger_sec=run[min_hits-1]['end_sec'],positive_windows=len(run),
                peak_score=max(r['score'] for r in run),
                touches_uncertain=any(r['uncertain_overlap_sec']>0 for r in run)))
    for r in rows:
        if r['score']>=threshold:run.append(r)
        else:finish();run=[]
    finish();return events

@torch.inference_mode()
def infer(model,y,c,norm,hop,batch_size,device):
    size=round(c['sr']*c['clip_sec']);step=round(hop*c['sr'])
    if len(y)<size:raise ValueError('录音短于模型窗口，本版本不补零，请单独处理。')
    starts=list(range(0,len(y)-size+1,step))
    if starts[-1]!=len(y)-size:starts.append(len(y)-size)
    scores=[]
    for j in range(0,len(starts),batch_size):
        xx=np.stack([feature(y[s:s+size],c) for s in starts[j:j+batch_size]])
        xx=(xx-norm['mean'])/norm['std']
        if not np.isfinite(xx).all():raise ValueError('特征出现非有限数值')
        x=torch.from_numpy(xx[:,None].astype(np.float32)).to(device)
        scores.extend(torch.sigmoid(model(x)).cpu().tolist())
    if not np.isfinite(scores).all():raise ValueError('模型分数异常')
    return starts,scores,size

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',required=True)
    ap.add_argument('--data',default='processed/binary_v1')
    ap.add_argument('--root',default='.')
    ap.add_argument('--out',required=True)
    ap.add_argument('--split',choices=['val','test'],required=True,help='明确选择完整验证集或完整测试集')
    ap.add_argument('--threshold',type=float,default=None,help='不指定时用模型内保存的阈值')
    ap.add_argument('--min-hits',type=int,default=1,help='连续超阈值窗口数，初次检查用1')
    ap.add_argument('--batch-size',type=int,default=32)
    ap.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    ap.add_argument('--threads',type=int,default=4)
    a=ap.parse_args()
    if a.split=='test' and a.threshold is None:
        ap.error('测试必须明确传入在验证阶段选定的 --threshold；本轮使用 --threshold 0.5 --min-hits 1。')
    if min(a.min_hits,a.batch_size,a.threads)<1:ap.error('计数参数必须大于0')
    torch.set_num_threads(a.threads)
    device='cuda' if a.device=='auto' and torch.cuda.is_available() else ('cpu' if a.device=='auto' else a.device)
    ck=torch.load(a.model,map_location='cpu',weights_only=True)
    if ck.get('model_name')!='BirdCNN_v1':raise ValueError('模型结构不是本轮BirdCNN_v1')
    c=ck['dataset_config'];data=Path(a.data);root=Path(a.root).resolve()
    disk_cfg=json.loads((data/'config.json').read_text(encoding='utf-8-sig'))
    if c!=disk_cfg:raise ValueError('模型中的数据配置与--data/config.json不一致，请选对应的数据版本。')
    if (data/'BUILD_INCOMPLETE.txt').exists():raise ValueError('数据集未生成完成')
    if c['labels']!={'non_target':0,'target':1}:raise ValueError('标签映射不一致')
    records=json.loads((data/'recordings.json').read_text(encoding='utf-8-sig'))
    records=[r for r in records if r['split']==a.split]
    if not records:raise ValueError(f'recordings.json没有 {a.split} 录音')
    t=float(ck['threshold'] if a.threshold is None else a.threshold)
    if not 0<t<1:raise ValueError('阈值必须在0和1之间')
    norm=c['normalization']
    if not np.isfinite([norm['mean'],norm['std']]).all() or norm['std']<=0:raise ValueError('标准化参数异常')
    hop=float(c['window_hop_sec'])
    if hop<=0 or round(hop*c['feature_config']['sr'])<1:raise ValueError('窗口间隔异常')
    out=Path(a.out)
    if out.exists() and any(out.iterdir()):raise ValueError('输出目录非空，请换--out，避免覆盖旧结果。')
    out.mkdir(parents=True,exist_ok=True);(out/'INCOMPLETE.txt').write_text('Prediction not completed')
    model=BirdCNN().to(device);model.load_state_dict(ck['state_dict'],strict=True);model.eval()
    print(f'Split={a.split}, recordings={len(records)}, epoch={ck["epoch"]}, threshold={t:.9f}, min_hits={a.min_hits}, hop={hop}',flush=True)
    dump(out/'reference_annotations.json',[{k:r[k] for k in ('audio_path','record_id','split','duration_sec','target','uncertain')} for r in records])
    allrows=[];allevents=[];summary=[]
    for i,r in enumerate(records,1):
        path=(root/r['audio_path']).resolve()
        if root not in path.parents:raise ValueError('录音路径越界')
        if digest(path)!=r['sha256']:raise ValueError('原始录音已变化: '+str(path))
        y,sr=sf.read(str(path),dtype='float32',always_2d=True)
        channel=int(c['channel'])-1
        if not 0<=channel<y.shape[1] or not len(y) or not np.isfinite(y).all():raise ValueError('录音或声道异常: '+str(path))
        y=np.ascontiguousarray(y[:,channel]);fc=c['feature_config']
        if sr!=fc['sr']:y=librosa.resample(y,orig_sr=sr,target_sr=fc['sr'],res_type='soxr_hq')
        y=np.ascontiguousarray(y,dtype=np.float32)
        if abs(len(y)/fc['sr']-r['duration_sec'])>0.05:raise ValueError('解码长度与第五步不一致')
        starts,scores,size=infer(model,y,fc,norm,hop,a.batch_size,device)
        rows=[]
        for s,p in zip(starts,scores):
            begin=s/fc['sr'];end=(s+size)/fc['sr']
            rows.append(dict(audio_path=r['audio_path'],record_id=r['record_id'],start_sec=begin,end_sec=end,
                score=p,prediction=int(p>=t),target_overlap_sec=overlap(begin,end,r['target']),
                uncertain_overlap_sec=overlap(begin,end,r['uncertain'])))
        events=merge_events(rows,t,a.min_hits);allrows.extend(rows);allevents.extend(events)
        summary.append(dict(audio_path=r['audio_path'],duration_sec=len(y)/fc['sr'],windows=len(rows),
            positive_windows=sum(x['prediction'] for x in rows),candidate_events=len(events),
            annotated_intervals=len(r['target']),max_score=max(scores)))
        fig,ax=plt.subplots(figsize=(12,3.5))
        ax.plot([x['end_sec'] for x in rows],scores,lw=1,label='score (at window end)')
        ax.axhline(t,color='red',ls='--',label=f'threshold={t:.6f}')
        for j,(b,e) in enumerate(r['target']):ax.axvspan(b,e,color='green',alpha=.22,label='target annotation' if j==0 else None)
        for j,(b,e) in enumerate(r['uncertain']):ax.axvspan(b,e,color='gray',alpha=.3,label='uncertain' if j==0 else None)
        ax.set(xlim=(0,len(y)/fc['sr']),ylim=(-.02,1.05),xlabel='Audio time (s); score uses the preceding 2 s',ylabel='Target score',title=Path(r['audio_path']).name)
        ax.legend(loc='best');fig.tight_layout();fig.savefig(out/(r['record_id']+'_scores.png'),dpi=150);plt.close(fig)
        print(f'[{i}/{len(records)}] {r["audio_path"]}: windows={len(rows)}, positives={sum(x["prediction"] for x in rows)}, events={len(events)}',flush=True)
    write_csv(out/'window_predictions.csv',allrows,['audio_path','record_id','start_sec','end_sec','score','prediction','target_overlap_sec','uncertain_overlap_sec'])
    write_csv(out/'candidate_events.csv',allevents,['audio_path','record_id','start_sec','end_sec','trigger_sec','positive_windows','peak_score','touches_uncertain'])
    write_csv(out/'recording_summary.csv',summary,['audio_path','duration_sec','windows','positive_windows','candidate_events','annotated_intervals','max_score'])
    dump(out/'run_config.json',dict(arguments=vars(a),threshold=t,threshold_source='checkpoint' if a.threshold is None else ('fixed_before_test' if a.split=='test' else 'explicit_validation_experiment'),
        model_sha256=digest(a.model),model_epoch=ck['epoch'],dataset_id=c['dataset_id'],recordings_sha256=digest(data/'recordings.json'),
        hop_sec=hop,device=device,versions={'torch':str(torch.__version__),'librosa':librosa.__version__,'soundfile':sf.__version__},
        split=a.split,clip_sec=c['feature_config']['clip_sec'],min_hits=a.min_hits,threshold_optimized_on_this_run=False,
        note='No threshold fitting or training. All windows retained, including boundaries/silence/uncertain. Event bounds are window unions, not precise bird-call boundaries. trigger_sec is earliest audio availability, excludes computation delay. No event accuracy computed.'))
    (out/'INCOMPLETE.txt').unlink();print('完成:',out)

if __name__=='__main__':main()
