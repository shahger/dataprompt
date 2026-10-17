"""Verify JPEG triplets on an explicitly isolated localhost demo stack only."""
import base64
import json
from pathlib import Path
import time

import cv2
import numpy as np
import requests

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8001'
FAKE_KEY='evidence-check-local-test-key'


def main():
    try:
        until=time.monotonic()+120
        while time.monotonic()<until:
            try:
                health=requests.get(BASE+'/health',timeout=3).json()
                if health.get('demo_mode') is True and health.get('model_loaded') is False: break
            except (requests.RequestException,ValueError): pass
            time.sleep(.5)
        else: raise RuntimeError('isolated demo not ready')
        path=ROOT/'.test-artifacts/evidence-five-seconds.mov'
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,48))
        if not writer.isOpened(): raise RuntimeError('video writer unavailable')
        try:
            for index in range(50): writer.write(np.full((48,64,3),index*4,np.uint8))
        finally: writer.release()
        report={}
        for prefix,headers in [('/api/v1',{'X-API-Key':FAKE_KEY}),('/ui/api',{})]:
            with path.open('rb') as stream:
                response=requests.post(BASE+prefix+'/analyze',headers=headers,files={'file':(path.name,stream,'video/quicktime')},timeout=20)
            if response.status_code!=200: raise RuntimeError('upload failed')
            job=response.json()['job_id']; until=time.monotonic()+30
            while time.monotonic()<until:
                response=requests.get(BASE+prefix+'/jobs/'+job,headers=headers,timeout=10)
                result=response.json()
                if result['status']!='processing': break
                time.sleep(.05)
            if set(result)!={'job_id','status','verdict','violations'} or result['status']!='done' or result['verdict']!='violation': raise RuntimeError('schema or job failure')
            violation=result['violations'][0]
            if violation['type']!='ДЕМО': raise RuntimeError('expected explicitly synthetic result')
            frames=violation['evidence_frames']
            if len(frames)!=3: raise RuntimeError('expected three unique frames')
            timestamps=[frame['timestamp_sec'] for frame in frames]
            if timestamps!=sorted(set(timestamps)): raise RuntimeError('ordering/dedup failure')
            for frame in frames:
                if set(frame)!={'timestamp_sec','image_base64'}: raise RuntimeError('frame schema failure')
                raw=base64.b64decode(frame['image_base64'],validate=True)
                image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
                if not raw.startswith(b'\xff\xd8') or image is None or image.shape!=(48,64,3): raise RuntimeError('invalid JPEG')
            report[prefix]={'frames':3,'timestamps':timestamps,'jpeg_decode':'PASS'}
        print(json.dumps(report))
        return 0
    except Exception:
        print('FAIL: isolated evidence check; payload and exception details suppressed')
        return 1


if __name__=='__main__': raise SystemExit(main())
