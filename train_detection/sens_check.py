import cv2
from collections import defaultdict
from ultralytics import YOLO
from tracking import Detection, TrainTracker, dedupe
from count_formation import read, NAMES
m=YOLO('runs/formation/weights/best.pt')
clips={'minehead 18:07':'captures/20260830T180712_minehead_station_dense.mp4',
       'minehead 18:10':'captures/20260830T181037_minehead_station_dense.mp4',
       'blue anchor 10:14':'captures/20260831T101456_blue_anchor_2_dense.mp4',
       'seaward 18:06':'captures/20260830T180618_minehead_seaward_crossing_dense.mp4'}
STEPS=(3,15,40,80,150)
print(f"{'clip':<20} " + ' '.join(f'{"≥"+str(n):>8}' for n in STEPS))
for name,c in clips.items():
    frames=read(c)
    trackers={k:TrainTracker() for k in NAMES}
    for i,f in enumerate(frames):
        r=m.predict(f,conf=0.45,verbose=False)[0]
        per=defaultdict(list)
        for b,cl,s in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy(), r.boxes.conf.cpu().numpy()):
            x1,y1,x2,y2=[int(v) for v in b]
            per[int(cl)].append(Detection(box=(x1,y1,x2,y2),conf=float(s),centre=((x1+x2)//2,(y1+y2)//2)))
        for k,t in trackers.items(): t.update(float(i), dedupe(per.get(k,[])))
    row=[]
    for n in STEPS:
        counts={NAMES[k]: sum(1 for t in tr.tracks.values() if len(t.path)>=n)
                for k,tr in trackers.items()}
        row.append(f"{counts['loco']}L {counts['wagon']}W")
    print(f'{name:<20} ' + ' '.join(f'{v:>8}' for v in row))
