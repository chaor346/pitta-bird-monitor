"""Train/evaluate the fairy_pitta_binary_v1 dataset. Python >=3.9."""
import argparse, csv, hashlib, json, random
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from sklearn.metrics import (average_precision_score, roc_auc_score,
    precision_recall_curve, confusion_matrix, precision_score, recall_score, f1_score)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_data(root):
    root = Path(root).resolve()
    if (root/'BUILD_INCOMPLETE.txt').exists():
        raise ValueError('数据生成未完成，不能训练。')
    cfg = json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    if cfg.get('schema') != 'fairy_pitta_binary_v1' or cfg['labels'] != {'non_target':0,'target':1}:
        raise ValueError('需要第五步的 fairy_pitta_binary_v1 数据。')
    norm = cfg['normalization']
    if norm['source'] != 'train_retained_features_only' or not np.isfinite([norm['mean'],norm['std']]).all() or norm['std'] <= 0:
        raise ValueError('训练集标准化统计不合法。')
    with (root/'manifest.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    groups, recordings, paths = defaultdict(set), defaultdict(set), set()
    for r in rows:
        r['label'] = int(r['label'])
        if r['split'] not in ('train','val','test') or r['label'] not in (0,1):
            raise ValueError('非法标签或split')
        if r['class_name'] != ('target' if r['label'] else 'non_target'):
            raise ValueError('类别名称与标签不一致')
        p = (root/r['feature_path']).resolve()
        if root not in p.parents or p in paths or not p.is_file():
            raise ValueError(f'特征路径缺失、重复或越界: {p}')
        paths.add(p)
        groups[r['group_id']].add(r['split'])
        recordings[r['record_id']].add(r['split'])
    if any(len(v)>1 for v in list(groups.values())+list(recordings.values())):
        raise ValueError('来源组或录音跨集合，请修复划分。')
    for s in ('train','val','test'):
        if {r['label'] for r in rows if r['split']==s} != {0,1}:
            raise ValueError(f'{s} 缺少某个类别')
    return cfg, rows


class Features(Dataset):
    def __init__(self, root, rows, cfg, augment=False):
        self.rows, self.root, self.augment = rows, Path(root), augment
        self.mean, self.std = cfg['normalization']['mean'], cfg['normalization']['std']
        fc = cfg['feature_config']
        n = round(fc['sr']*fc['clip_sec'])
        frames = 1 + ((n if fc['center'] else n-fc['n_fft'])//fc['hop_length'])
        self.shape = (fc['n_mels'], frames)
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]
        x = np.load(self.root/r['feature_path'], allow_pickle=False)
        if x.shape != self.shape or not np.isfinite(x).all():
            raise ValueError(f'特征形状/数值异常: {r["feature_path"]}, {x.shape}')
        x = torch.from_numpy(((x.astype(np.float32)-self.mean)/self.std).copy()).unsqueeze(0)
        if self.augment:
            # Conservative masking, applied only to training features.
            for axis, limit in ((1,4),(2,10)):
                width = random.randint(0,min(limit,x.shape[axis]-1))
                start = random.randint(0,x.shape[axis]-width)
                if axis==1: x[:,start:start+width,:] = 0
                else: x[:,:,start:start+width] = 0
        return x, torch.tensor(float(r['label']),dtype=torch.float32)


class BirdCNN(nn.Module):
    def __init__(self):
        super().__init__()
        layers=[]
        for a,b in ((1,16),(16,32),(32,64)):
            layers += [nn.Conv2d(a,b,3,padding=1,bias=False),nn.BatchNorm2d(b),nn.ReLU(),nn.MaxPool2d(2)]
        self.features=nn.Sequential(*layers)
        self.head=nn.Sequential(nn.AdaptiveAvgPool2d((4,1)),nn.Flatten(),nn.Dropout(.3),nn.Linear(256,1))
    def forward(self,x): return self.head(self.features(x)).squeeze(1)


def sample_weights(rows):
    # Equal class mass; equal recording mass within each class.
    counts=Counter((r['label'],r['record_id']) for r in rows)
    nrecs=Counter(label for label,rec in counts)
    return torch.tensor([1/(nrecs[r['label']]*counts[r['label'],r['record_id']]) for r in rows],dtype=torch.double)


@torch.no_grad()
def predict(model, loader, device):
    model.eval(); ys=[]; ps=[]; loss_sum=0
    for x,y in loader:
        x,y=x.to(device),y.to(device)
        logits=model(x)
        loss_sum += nn.functional.binary_cross_entropy_with_logits(logits,y,reduction='sum').item()
        ys.extend(y.cpu().numpy().tolist()); ps.extend(torch.sigmoid(logits).cpu().numpy().tolist())
    return np.array(ys,dtype=int),np.array(ps),loss_sum/len(ys)


def metrics(y,p,t):
    pred=(p>=t).astype(int)
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return dict(threshold=float(t),precision=float(precision_score(y,pred,zero_division=0)),
        recall=float(recall_score(y,pred,zero_division=0)),f1=float(f1_score(y,pred,zero_division=0)),
        average_precision=float(average_precision_score(y,p)),roc_auc=float(roc_auc_score(y,p)),
        accuracy=float((pred==y).mean()),tn=int(tn),fp=int(fp),fn=int(fn),tp=int(tp),
        note='窗口指标；不是完整录音的事件指标。AP为average precision，不是梯形积分PR-AUC。')


def select_threshold(y,p):
    pr,re,th=precision_recall_curve(y,p)
    f=2*pr[:-1]*re[:-1]/np.maximum(pr[:-1]+re[:-1],1e-12)
    # Among equal best F1 thresholds, prefer the highest.
    return float(th[np.flatnonzero(np.isclose(f,f.max(),rtol=0,atol=1e-12))[-1]])


def export_eval(out, split, rows, y,p,t,loss):
    report={'selected_threshold':metrics(y,p,t),'threshold_0_5':metrics(y,p,.5),'loss':loss}
    save_json(out/f'{split}_metrics.json',report)
    with (out/f'{split}_predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['audio_path','record_id','start_sec','end_sec','label','probability','prediction']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r,prob in zip(rows,p):
            z={k:r[k] for k in fields[:5]};z.update(probability=float(prob),prediction=int(prob>=t));w.writerow(z)
    cm=confusion_matrix(y,p>=t,labels=[0,1])
    fig,ax=plt.subplots(figsize=(4,4));ax.imshow(cm,cmap='Blues')
    for i in range(2):
        for j in range(2):ax.text(j,i,str(cm[i,j]),ha='center',va='center',color='red')
    ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['non_target','target'],yticklabels=['non_target','target'],xlabel='Predicted',ylabel='True',title=f'{split}: threshold={t:.4f}')
    fig.tight_layout();fig.savefig(out/f'{split}_confusion.png',dpi=150);plt.close(fig)
    print(split,json.dumps(report['selected_threshold'],ensure_ascii=False))


def is_improved(ap, val_loss, best_ap, best_val_loss):
    """AP is primary; loss breaks AP ties. Ignore numerical noise."""
    if not np.isfinite([ap, val_loss]).all():
        raise ValueError('验证指标出现 NaN/Inf，停止训练。')
    ap_tol = 1e-8
    loss_min_delta = 1e-6
    return (ap > best_ap + ap_tol or
            (abs(ap - best_ap) <= ap_tol and
             val_loss < best_val_loss - loss_min_delta))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',default='processed/binary_v1');ap.add_argument('--out',default='runs/binary_v1')
    ap.add_argument('--epochs',type=int,default=40);ap.add_argument('--patience',type=int,default=8)
    ap.add_argument('--batch-size',type=int,default=32);ap.add_argument('--epoch-samples',type=int,default=2048)
    ap.add_argument('--lr',type=float,default=0.001);ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--device',choices=['auto','cpu','cuda'],default='auto')
    ap.add_argument('--threads',type=int,default=4);ap.add_argument('--no-augment',action='store_true')
    ap.add_argument('--evaluate-test',action='store_true',help='只在选好模型与阈值后评估测试集')
    a=ap.parse_args()
    if min(a.epochs,a.patience,a.batch_size,a.epoch_samples,a.threads)<=0 or a.lr<=0:ap.error('数值参数必须大于0')
    random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed);torch.set_num_threads(a.threads)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(a.seed)
    torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    device='cuda' if a.device=='auto' and torch.cuda.is_available() else ('cpu' if a.device=='auto' else a.device)
    cfg,rows=read_data(a.data)
    rr={s:[r for r in rows if r['split']==s] for s in ('train','val','test')}
    out=Path(a.out)
    if out.exists() and any(out.iterdir()):raise ValueError('输出目录非空，请更换 --out，避免覆盖旧实验。')
    out.mkdir(parents=True,exist_ok=True);(out/'TRAINING_INCOMPLETE.txt').write_text('Do not use as a completed experiment.')
    datasets={s:Features(a.data,rr[s],cfg,augment=s=='train' and not a.no_augment) for s in ('train','val')}
    weights=sample_weights(rr['train'])
    sampler=WeightedRandomSampler(weights,a.epoch_samples,replacement=True,generator=torch.Generator().manual_seed(a.seed))
    train_loader=DataLoader(datasets['train'],batch_size=a.batch_size,sampler=sampler,num_workers=0)
    val_loader=DataLoader(datasets['val'],batch_size=a.batch_size,num_workers=0)
    model=BirdCNN().to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=1e-4)
    loss_fn=nn.BCEWithLogitsLoss() # No additional class weight: sampler already balances classes.
    run_cfg={'arguments':vars(a),'device':device,'dataset_config':cfg,'model':'BirdCNN_v1','parameters':sum(p.numel() for p in model.parameters()),'sampler':'equal_class_then_equal_recording','selection':'max validation AP; tied AP -> min validation loss','ap_tolerance':1e-8,'loss_min_delta':1e-6,'script_version':'binary_v1_checkpoint_fix','threshold_selection':'max validation window F1','torch_version':str(torch.__version__),'manifest_sha256':hashlib.sha256((Path(a.data)/'manifest.csv').read_bytes()).hexdigest()}
    save_json(out/'train_config.json',run_cfg)
    print('Device:',device,'Parameters:',run_cfg['parameters'],'Counts:',{s:dict(Counter(r['label'] for r in rr[s])) for s in rr},flush=True)
    best=-1.;best_val_loss=float("inf");best_epoch=0;bad=0;history=[];checkpoint=out/'best_model.pt'
    for epoch in range(1,a.epochs+1):
        model.train();total=0.;n=0
        for x,y in train_loader:
            x,y=x.to(device),y.to(device);optimizer.zero_grad(set_to_none=True)
            loss=loss_fn(model(x),y)
            if not torch.isfinite(loss):raise ValueError('训练损失非有限数值')
            loss.backward();optimizer.step();total+=loss.item()*len(y);n+=len(y)
        y,p,vl=predict(model,val_loader,device);score=float(average_precision_score(y,p));mm=metrics(y,p,.5)
        row=dict(epoch=epoch,train_loss=total/n,val_loss=vl,val_ap=score,val_f1_05=mm['f1'],val_recall_05=mm['recall'],val_precision_05=mm['precision']);history.append(row)
        with (out/'history.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerows(history)
        print(f"Epoch {epoch:03d} train_loss={total/n:.4f} val_loss={vl:.4f} val_AP={score:.4f} F1@0.5={mm['f1']:.4f}",flush=True)
        if is_improved(score, vl, best, best_val_loss):
            best=score;best_val_loss=vl;best_epoch=epoch;bad=0
            torch.save({'state_dict':model.state_dict(),'model_name':'BirdCNN_v1',
                        'dataset_config':cfg,'epoch':epoch,'val_ap':score,
                        'val_loss':vl,'selection':run_cfg['selection']},checkpoint)
            print(f'  Saved best: epoch={epoch}, AP={score:.8f}, val_loss={vl:.8f}; patience reset',flush=True)
        else:
            bad+=1
            print(f'  No improvement: {bad}/{a.patience}; best_epoch={best_epoch}',flush=True)
        if bad>=a.patience:
            print(f'Early stopping. Best epoch={best_epoch}')
            break
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(ck['state_dict']);model.to(device)
    y,p,vl=predict(model,val_loader,device);t=select_threshold(y,p)
    ck['threshold']=t;torch.save(ck,checkpoint)
    save_json(out/'threshold.json',{'threshold':t,'source':'validation_only','criterion':'max window F1','best_epoch':ck['epoch']})
    export_eval(out,'val',rr['val'],y,p,t,vl)
    if a.evaluate_test:
        test_loader=DataLoader(Features(a.data,rr['test'],cfg),batch_size=a.batch_size,num_workers=0)
        y,p,tl=predict(model,test_loader,device);export_eval(out,'test',rr['test'],y,p,t,tl)
    fig,axs=plt.subplots(1,2,figsize=(10,4));e=[h['epoch'] for h in history]
    axs[0].plot(e,[h['train_loss'] for h in history],label='train (balanced)');axs[0].plot(e,[h['val_loss'] for h in history],label='val (original)');axs[0].legend();axs[0].set_title('Loss: different sampling distributions')
    axs[1].plot(e,[h['val_ap'] for h in history],label='validation AP');axs[1].plot(e,[h['val_f1_05'] for h in history],label='validation F1 @0.5');axs[1].legend()
    for ax in axs:ax.set_xlabel('Epoch')
    fig.tight_layout();fig.savefig(out/'training_curve.png',dpi=150);plt.close(fig)
    (out/'TRAINING_INCOMPLETE.txt').unlink()
    print(f'完成。最佳epoch={ck["epoch"]}, threshold={t:.6f}, output={out}',flush=True)

if __name__=='__main__':
    main()
