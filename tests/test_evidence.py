"""Evidence selection keeps the event frame, valid JPEGs, ordering and bounds."""
import base64
import os
import subprocess
import sys

import cv2
import numpy as np
import pytest

from test_api import upload, wait_job


@pytest.fixture
def long_video(tmp_path):
    path = tmp_path / 'four-seconds.mov'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (32, 24))
    assert writer.isOpened()
    for index in range(40): writer.write(np.full((24,32,3), index*5, np.uint8))
    writer.release()
    return path


def decode_all(frames):
    assert 1 <= len(frames) <= 3
    times = [frame['timestamp_sec'] for frame in frames]
    assert times == sorted(set(times))
    for frame in frames:
        assert set(frame) == {'timestamp_sec', 'image_base64'}
        raw=base64.b64decode(frame['image_base64'],validate=True)
        assert raw.startswith(b'\xff\xd8')
        assert cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR) is not None
    return times


@pytest.mark.parametrize('count', [1,2,3])
def test_event_frame_is_always_in_selected_evidence(service,long_video,monkeypatch,count):
    module,client,_=service
    monkeypatch.setattr(module,'EVIDENCE_FRAMES',count)
    monkeypatch.setattr(module,'analyze_video',lambda path:[{'type':'test','timecode_sec':2.,'description':'synthetic'}])
    job=wait_job(client,upload(client,long_video).json()['job_id'])
    frames=job['violations'][0]['evidence_frames']
    times=decode_all(frames)
    assert len(frames)==count and 2. in times
    assert times == {1:[2.],2:[1.,2.],3:[1.,2.,3.]}[count]
    ui=client.get('/ui/api/jobs/'+job['job_id']).json()
    assert ui['violations'][0]['evidence_frames']==frames


@pytest.mark.parametrize('timecode,expected', [(0.,[0.,1.]),(.1,[0.,.1,1.1]),(3.9,[2.9,3.9])])
def test_video_edges_are_clamped_and_deduplicated(service,long_video,timecode,expected):
    module,_,_=service
    assert decode_all(module.evidence_frames(long_video,timecode)) == pytest.approx(expected)


def test_short_video_deduplicates_neighbor_frames(service,video):
    module,_,_=service
    assert decode_all(module.evidence_frames(video,0.))==pytest.approx([0.,.9])
    assert decode_all(module.evidence_frames(video,.9))==pytest.approx([0.,.9])


@pytest.mark.parametrize('value', ['0','4','bad'])
def test_invalid_evidence_env_fails_clearly(value):
    result=subprocess.run([sys.executable,'-X','utf8','-c','import main'],env={**os.environ,'EVIDENCE_FRAMES':value},capture_output=True,timeout=15)
    assert result.returncode != 0
    assert b'EVIDENCE_FRAMES' in result.stderr


def test_default_and_one_frame_environment():
    for value,expected in [(None,3),('1',1)]:
        env={**os.environ}
        env.pop('EVIDENCE_FRAMES',None)
        if value: env['EVIDENCE_FRAMES']=value
        result=subprocess.run([sys.executable,'-c','import main;print(main.EVIDENCE_FRAMES)'],env=env,capture_output=True,timeout=15)
        assert result.returncode==0 and int(result.stdout)==expected
